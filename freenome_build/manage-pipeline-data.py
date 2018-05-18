import os
import codecs
import tempfile
import urllib.parse
import hashlib
import subprocess
import logging
import shutil
from collections import namedtuple, OrderedDict

from google.cloud.storage.client import Client
from google.api_core.exceptions import NotFound

import portalocker

logger = logging.getLogger(__name__)

DEFAULT_GCP_PROJECT = 'freenome-computational'
DEFAULT_LOCAL_PREFIX = '/srv/reference_data/'
DEFAULT_REMOTE_PREFIX = 'gs://balrog/reference-data/'


class FileAlreadyExistsError(Exception):
    pass


class FileMismatchError(Exception):
    pass


class MissingFileError(Exception):
    pass


class KeyAlreadyExistsError(Exception):
    pass


def hex_to_base64(hex_str):
    return codecs.encode(codecs.decode(hex_str, 'hex'), 'base64').strip().decode('ascii')


def calc_md5sum_from_fname(fname):
    hex_str = subprocess.run(
        ["md5sum", fname],
        stdout=subprocess.PIPE
    ).stdout.split()[0].decode('ascii')
    return hex_to_base64(hex_str)


def calc_md5sum_from_fp(fp):
    fpos = fp.tell()
    m = hashlib.md5()
    fp.seek(0)
    m.update(fp.read().encode('utf8'))
    fp.seek(fpos)
    return hex_to_base64(m.hexdigest())


def _get_gcs_blob(remote_prefix, remote_relative_path):
    absolute_remote_path = remote_prefix + remote_relative_path
    res = urllib.parse.urlsplit(absolute_remote_path)
    rel_path = res.path[1:]
    blob = Client(DEFAULT_GCP_PROJECT).bucket(res.netloc).blob(rel_path)
    return blob


DataManifestRecord = namedtuple(
    'DataManifestRecord',
    ['name', 'local_path', 'remote_path', 'md5sum', 'size', 'notes']
)


class DataManifest(OrderedDict):
    def _get_gcs_blob(self, remote_relative_path):
        return _get_gcs_blob(self.remote_prefix, remote_relative_path)

    def _save_to_disk(self):
        """Save the current data to disk."""
        with portalocker.Lock(self.fname, "r+") as fp:
            # first make sure that the manifest hasn't changed since we last read it
            on_disk_md5sum = calc_md5sum_from_fp(fp)
            if on_disk_md5sum != self._md5sum:
                raise RuntimeError(
                    f"'{self.fname}' was modified by another program (current md5sum "
                    f"'{on_disk_md5sum}' vs '{self._md5sum}')"
                )

            # truncate the file, and re-write it
            fp.seek(0)
            fp.truncate()
            fp.write("\t".join(self.header) + "\n")
            for record in self.values():
                fp.write("\t".join(record) + "\n")
            fp.flush()

            # update the md5sum
            self._md5sum = calc_md5sum_from_fp(fp)
            fp.close()

    def __init__(
            self,
            manifest_fname,
            remote_prefix=DEFAULT_REMOTE_PREFIX
    ):
        self.fname = manifest_fname
        self.remote_prefix = remote_prefix

        self.header = None

        # we lock the file to ensure that only one file is doing this at a time
        with portalocker.Lock(self.fname, 'r') as fp:
            # store the md5sum so that we can tell
            # if the file has been modified before writing it out
            self._md5sum = calc_md5sum_from_fp(fp)

            # read all of the file contents into memory
            for line_i, line in enumerate(fp):
                # read the header
                if line_i == 0:
                    self.header = line.strip("\n").split("\t")
                    continue
                # skip empty lines
                if line.strip() == '':
                    continue
                # parse and store this record to the ordered dict
                record = DataManifestRecord(*line.strip("\n").split("\t"))
                if record.name in self:
                    raise KeyAlreadyExistsError("'{record.name}' is duplicated in '{self.fname}'")
                self[record.name] = record

    def remove_file(self, name):
        """Remove a file from the manifest.

        This does *not* remove the file from the filesystem or from GCS.
        """
        del self[name]
        self._save_to_disk()

    def add_file(
            self,
            name,
            fname,
            local_relative_path,
            remote_relative_path,
            note=''
    ):
        """Add a file to the manifest.

        Add a file to the manifest and upload the file to GCS.
        """
        if name in self:
            raise KeyAlreadyExistsError("'{record.name}' is duplicated in '{self.fname}'")

        # make sure that we can open the file that we want to add for reading
        with open(fname) as _: # noqa
            pass

        # find the file's file size and calculate the checksum
        logger.info(f"Calculating md5sum for '{fname}'")
        local_md5sum = calc_md5sum_from_fname(fname)
        logger.debug(f"Calculated md5sum '{local_md5sum}' for '{fname}'.")
        local_fsize = os.path.getsize(fname)
        logger.debug(f"Calculated filesize '{local_fsize}' for '{fname}'.")

        # setup the remote file object
        blob = self._get_gcs_blob(remote_relative_path)
        try:
            blob.reload()
            # if it exists, make sure that it is the same as the local file
            if local_md5sum != blob.md5_hash:
                raise FileAlreadyExistsError(
                    f"File '{self.remote_prefix}{remote_relative_path}' already exists with md5sum"
                    f"'{blob.md5_hash}' vs '{local_md5sum}' for '{fname}')"
                )
            if local_fsize != blob.size:
                raise FileAlreadyExistsError(
                    f"File '{self.remote_prefix}{remote_relative_path}' already exists with file "
                    f"size '{blob.size}' vs '{local_fsize}' for '{fname}')"
                )
        # if we can't find the file, upload it
        except NotFound:
            logger.info(f"Uploading '{fname}' to '{self.remote_prefix}{remote_relative_path}'")
            blob.upload_from_filename(fname)
            assert blob.size == local_fsize, \
                "We just uploaded this file so the filesizes should match"
            assert blob.md5_hash == local_md5sum, \
                f"We just uploaded this file so the md5sums should match " \
                f"('{blob.md5_hash}' vs '{local_md5sum}')"
        assert blob.md5_hash is not None
        assert blob.size is not None

        self[name] = DataManifestRecord(
            name, local_relative_path, remote_relative_path, local_md5sum, str(local_fsize), note
        )
        self._save_to_disk()

    def _verify_record(self, record, local_abs_path, check_md5sums=True):
        """Verify that the file at 'local_abs_path' matches that in record.

        If check_md5sums is True then verify that the md5sums match (this is slow).
        """
        # check that the file exists
        if not os.path.exists(local_abs_path):
            raise MissingFileError("Can not find '{record.name}' at '{local_abs_path}'")

        # ensure the filesizes match
        local_fsize = os.path.getsize(local_abs_path)
        logger.debug(f"Calculated filesize '{local_fsize}' for '{local_abs_path}'.")
        if local_fsize != int(record.size):
            raise FileMismatchError(
                f"'{local_abs_path}' has size '{local_fsize}' vs '{record.size}' in the manifest")

        # ensure the md5sum matches
        if check_md5sums:
            logger.info(f"Calculating md5sum for '{local_abs_path}'.")
            local_md5sum = calc_md5sum_from_fname(local_abs_path)
            logger.debug(f"Calculated md5sum '{local_md5sum}' for '{local_abs_path}'.")
            if local_md5sum != record.md5sum:
                raise FileMismatchError(
                    f"'{local_abs_path}' has md5sum '{local_md5sum}' "
                    f"vs '{record.md5sum}' in the manifest"
                )

    def _sync_record(self, record, local_abs_path):
        # if local_path already exists, then make sure that it matches the remote file
        if os.path.exists(local_abs_path):
            self._verify_record(record, local_abs_path)
        # otherwise, copy it to the correct location
        else:
            # copy the file to local_path
            logger.info(f"Copying '{record.remote_path}' to '{local_abs_path}'.")
            blob = self._get_gcs_blob(record.remote_path)
            # make sure the directory exists
            dirname = os.path.dirname(local_abs_path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            blob.download_to_filename(local_abs_path)
            assert os.path.getsize(local_abs_path) == int(record.size), "{}, {}".format(
                os.path.getsize(local_abs_path), record.size
            )
            # skip this assert because it is slow (and filesize should catch anything weird)
            # assert calc_md5sum(local_path) == local_md5sum

    def sync(self, local_prefix):
        """Sync the remote files to a local path."""
        for record in self.values():
            local_abs_path = os.path.join(local_prefix, record.local_path)
            self._sync_record(record, local_abs_path)

    def verify(self, local_prefix, check_md5sums=False):
        """Ensure that the files at 'local_prefix' match the manifest.

        If 'slow' is True, then additionally ensure that the md5sum's match.
        """
        for record in self.values():
            local_abs_path = os.path.join(local_prefix, record.local_path)
            self._verify_record(record, local_abs_path, check_md5sums=check_md5sums)


def _add_base_to_path(rel_path):
    return os.path.normpath(os.path.join(os.path.abspath(os.path.dirname(__file__)), rel_path))


LOCAL_TEST_DATA_PREFIX = "PLACEHOLDER FOR FLAKE8 BUT NEEDS TO BE FIXED"

TEST_MANIFEST_FNAME = _add_base_to_path('../tests/data/pipeline-data/data-manifest.tsv')
TEST_DATA_FILE = _add_base_to_path('../tests/data/pipeline-data/eight_As.fa')

TEST_LOCAL_RELATIVE_PATH = 'eight_As.fa'
TEST_REMOTE_RELATIVE_PATH = 'eight_As.fa'
TEST_REMOTE_PATH = DEFAULT_REMOTE_PREFIX + TEST_REMOTE_RELATIVE_PATH

TEST_DATA_FILE_2 = os.path.normpath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '../tests/data/pipeline-data/hg38.chrom.interval.chrM.bed.gz')
)
TEST_2_LOCAL_RELATIVE_PATH = './hg38/hg38.chrom.interval.chrM.bed.gz'


def reset_test_manifest():
    shutil.copy(TEST_MANIFEST_FNAME+".orig", TEST_MANIFEST_FNAME)


def add_file_to_manifest_and_verify():
    """Test that adding a file to the manifest works.

    This is called by the more specific test below.
    """
    # TODO - revert these to static global variables
    manifest_fname = TEST_MANIFEST_FNAME
    remote_prefix = DEFAULT_REMOTE_PREFIX
    test_data_fname = TEST_DATA_FILE
    local_relative_path = TEST_LOCAL_RELATIVE_PATH
    remote_relative_path = TEST_REMOTE_RELATIVE_PATH
    try:
        print(f"Loading manifest: {manifest_fname}")
        manifest = DataManifest(manifest_fname, remote_prefix=remote_prefix)
        manifest.add_file('eight_As', test_data_fname, local_relative_path, remote_relative_path)

        # read the local data file into a string
        # we use this below to ensure that it exists
        print(f"Reading local file: {test_data_fname}")
        with open(test_data_fname, 'rb') as ifp:
            local_data = ifp.read()

        # check that the file exists in GCS and is the same as the local file
        print(f"Downloading remote file: {DEFAULT_REMOTE_PREFIX}{TEST_REMOTE_RELATIVE_PATH}")
        blob = _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH)
        gcs_data = blob.download_as_string()
        assert local_data == gcs_data, f"local data: {local_data}\ngcs data: {gcs_data}"
    finally:
        print(f"Reseting manifest: {manifest_fname}")
        reset_test_manifest()
        print(f"Deleting remote file ({DEFAULT_REMOTE_PREFIX}{TEST_REMOTE_RELATIVE_PATH})")
        blob = _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH)
        blob.delete()


def test_add_duplicate_key():
    # test that we get an error if we try to add this file again with the same key
    try:
        manifest = DataManifest(TEST_MANIFEST_FNAME, DEFAULT_REMOTE_PREFIX)
        manifest.add_file(
            'eight_As', TEST_DATA_FILE, TEST_LOCAL_RELATIVE_PATH, TEST_REMOTE_RELATIVE_PATH)
        manifest.add_file(
            'eight_As', TEST_DATA_FILE, TEST_LOCAL_RELATIVE_PATH, TEST_REMOTE_RELATIVE_PATH)
    # this is what we expect. Any other exception will be propogated.
    except KeyAlreadyExistsError:
        pass

    # no expection is enexpected
    else:
        assert False, "Expected to see a 'KeyAlreadyExistsError'"
    finally:
        reset_test_manifest()


def test_add_remote_missing_file():
    """Test adding a file that is not in GCS."""
    # this is a vanilla add_file_to_manifest_and_verify call
    add_file_to_manifest_and_verify()


def test_add_remote_present_file():
    """Test adding a file that does not exist in gcs."""
    # add the file and then ensure that adding to the manifest still works
    blob = _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH)
    blob.upload_from_filename(TEST_DATA_FILE)
    add_file_to_manifest_and_verify()


def test_add_remote_mismatch_file():
    """Test adding a file that exists in gcs but does not match the file being added."""
    # add a mismatched file and ensure that we get an error
    blob = _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH)
    blob.upload_from_string("NATHAN")
    try:
        add_file_to_manifest_and_verify()
    except FileAlreadyExistsError:
        # we should get a FileAlreadyExistsError
        pass
    else:
        assert False, "This should have failed due to a file mismatch."


def test_locking_works():
    """Make sure that we get an error if two people try to modify the same process."""
    manifest_fname = TEST_MANIFEST_FNAME
    test_data_fname = TEST_DATA_FILE
    remote_prefix = DEFAULT_REMOTE_PREFIX
    remote_relative_path = TEST_REMOTE_RELATIVE_PATH
    local_relative_path = TEST_LOCAL_RELATIVE_PATH
    try:
        print(f"Loading manifest 1: {manifest_fname}")
        manifest_1 = DataManifest(manifest_fname, remote_prefix=remote_prefix)
        print(f"Loading manifest 2: {manifest_fname}")
        manifest_2 = DataManifest(manifest_fname, remote_prefix=remote_prefix)
        # this should succeed
        print(f"Adding file to manifest 1.")
        manifest_1.add_file('eight_As', test_data_fname, local_relative_path, remote_relative_path)
        # this should fail
        print(f"Adding file to manifest 2.")
        manifest_2.add_file('eight_As', test_data_fname, local_relative_path, remote_relative_path)
    except RuntimeError as inst:
        print(f"Adding file to manifest 2 FAILED with {inst}.")
        pass
    finally:
        print(f"Reseting manifest: {manifest_fname}")
        reset_test_manifest()
        print(f"Deleting remote file ({remote_relative_path})")
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_adding_two_files_works():
    try:
        test_data_fname = TEST_DATA_FILE
        remote_relative_path = TEST_REMOTE_RELATIVE_PATH
        local_relative_path = TEST_LOCAL_RELATIVE_PATH
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(f"Adding file 1 to manifest.")
        manifest.add_file('eight_As', test_data_fname, local_relative_path, remote_relative_path)
        print(f"Adding file 2 to manifest.")
        manifest.add_file(
            'eight_As_v2', test_data_fname, local_relative_path+'.v2', remote_relative_path+'.v2')
    finally:
        reset_test_manifest()
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_removing_file_works():
    try:
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(f"Adding file to manifest.")
        manifest.add_file(
            'eight_As', TEST_DATA_FILE, TEST_LOCAL_RELATIVE_PATH, TEST_REMOTE_RELATIVE_PATH)
        # make sure that the file is in the manifest
        manifest_2 = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        assert 'eight_As' in manifest_2
        print(f"Removing file from manifest.")
        manifest_2.remove_file('eight_As')
        manifest_3 = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        assert 'eight_As' not in manifest_3
    finally:
        reset_test_manifest()
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_sync():
    try:
        local_test_data_prefix = tempfile.mkdtemp()
        print(f"Created temp directory '{local_test_data_prefix}'")
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(LOCAL_TEST_DATA_PREFIX)
        manifest.sync(LOCAL_TEST_DATA_PREFIX)
        print(f"Synced data to '{LOCAL_TEST_DATA_PREFIX}'")
    finally:
        reset_test_manifest()
        shutil.rmtree(local_test_data_prefix)
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_sync_add_sync():
    try:
        local_test_data_prefix = tempfile.mkdtemp()
        print(f"Created temp directory '{local_test_data_prefix}'")
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(f"Syncing data to '{LOCAL_TEST_DATA_PREFIX}'")
        manifest.sync(LOCAL_TEST_DATA_PREFIX)
        print(f"Adding file to manifest.")
        manifest.add_file(
            'eight_As', TEST_DATA_FILE, TEST_LOCAL_RELATIVE_PATH, TEST_REMOTE_RELATIVE_PATH)
        print(f"Re-Syncing data to '{LOCAL_TEST_DATA_PREFIX}'")
        manifest.sync(LOCAL_TEST_DATA_PREFIX)
    finally:
        reset_test_manifest()
        shutil.rmtree(local_test_data_prefix)
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_verify_success():
    try:
        local_test_data_prefix = tempfile.mkdtemp()
        print(f"Created temp directory '{local_test_data_prefix}'")
        os.mkdir(os.path.join(local_test_data_prefix, "./hg38"))
        shutil.copy(
            TEST_DATA_FILE_2,
            os.path.join(local_test_data_prefix, TEST_2_LOCAL_RELATIVE_PATH)
        )
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(local_test_data_prefix)
        manifest.sync(local_test_data_prefix)
        print(f"Synced data to '{local_test_data_prefix}'")
    finally:
        reset_test_manifest()
        print(local_test_data_prefix)
        # shutil.rmtree(local_test_data_prefix)
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_verify_size_fail():
    try:
        local_test_data_prefix = tempfile.mkdtemp()
        print(f"Created temp directory '{local_test_data_prefix}'")
        os.mkdir(os.path.join(local_test_data_prefix, "./hg38"))
        shutil.copy(
            # we are copying the wrong file to induce an error
            TEST_DATA_FILE,
            os.path.join(local_test_data_prefix, TEST_2_LOCAL_RELATIVE_PATH)
        )
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(local_test_data_prefix)
        manifest.sync(local_test_data_prefix)
        print(f"Synced data to '{local_test_data_prefix}'")
    finally:
        reset_test_manifest()
        print(local_test_data_prefix)
        # shutil.rmtree(local_test_data_prefix)
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_verify_md5_fail():
    try:
        local_test_data_prefix = tempfile.mkdtemp()
        print(f"Created temp directory '{local_test_data_prefix}'")
        os.mkdir(os.path.join(local_test_data_prefix, "./hg38"))
        shutil.copy(
            # we are copying the wrong file to induce an error
            TEST_DATA_FILE,
            os.path.join(local_test_data_prefix, TEST_2_LOCAL_RELATIVE_PATH)
        )
        print(f"Loading manifest: {TEST_MANIFEST_FNAME}")
        manifest = DataManifest(TEST_MANIFEST_FNAME, remote_prefix=DEFAULT_REMOTE_PREFIX)
        print(local_test_data_prefix)
        manifest.sync(local_test_data_prefix)
        print(f"Synced data to '{local_test_data_prefix}'")
    finally:
        reset_test_manifest()
        print(local_test_data_prefix)
        # shutil.rmtree(local_test_data_prefix)
        _get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()

# print("test_add_remote_missing_file")
# test_add_remote_missing_file()
# print("test_add_remote_present_file")
# test_add_remote_present_file()
# print("test_add_remote_mismatch_file")
# test_add_remote_mismatch_file()
# print("test_locking_works")
# test_locking_works()
# print("test_adding_two_files_works")
# test_adding_two_files_works()
# print("test_removing_file_works")
# test_removing_file_works()
# print("test_sync")
# test_sync()
# print("test_sync_add_sync")
# test_sync_add_sync()
# print("test_add_duplicate_key")
# test_add_duplicate_key()
# print("test_verify_success")
# test_verify_success()
# print("test_verify_fail")
# test_verify_fail()


def parse_args():
    # add data file
    # remove data file
    # replace data file
    pass


def main(fname):
    with open(fname) as ifp:
        for i, line in enumerate(ifp):
            if i == 0:
                print(line.strip("\n"))
                continue
            data = line.strip("\n").split("\t")
            # add space for the md5sum, filesize, and last update time
            data.insert(-1, None)
            data.insert(-1, None)
            data.insert(-1, None)

            data[-1] += "#old path: {}".format(data[1])
            # update to use the new path
            local_filename = data[2].replace("gs://balrog/", "/srv/")
            data[1] = local_filename
            # calculate the md5sum
            md5sum = subprocess.run(
                ["md5sum", data[1]],
                stdout=subprocess.PIPE
            ).stdout.split()[0].decode('UTF8')
            data[-4] = md5sum
            file_size = str(os.path.getsize(local_filename))
            data[-3] = file_size
            last_mtime = str(int(os.path.getmtime(local_filename)))
            data[-2] = last_mtime
            print("\t".join(data))
    return

# if __name__ == '__main__':
#     main(sys.argv[1])
