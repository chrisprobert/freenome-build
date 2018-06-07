import os
import codecs
import hashlib
import subprocess
import logging
from collections import namedtuple, OrderedDict

from google.api_core.exceptions import NotFound

import portalocker

from freenome_build.util import get_gcs_blob

logger = logging.getLogger(__name__)

# TODOs
# (1) decide on the interface (eg do we need separate local/remote prefixes)
# (2) update so that only a single writer can be open at once
# (3) add 'get_local_path' method


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


DataManifestRecord = namedtuple(
    'DataManifestRecord',
    ['name', 'relative_local_path', 'relative_remote_path', 'md5sum', 'size', 'notes']
)


class _DataManifestBase(OrderedDict):
    """Track and manage data file dependencies

    This object has three main purposes:
    1) add and remove data files from a manifest
    2) sync manifest files from a remote repository
    3) verify that local files match those int he manifest

    Q1) Do we need a remote_base_path?
    Q2) Can the remote relative path be the same as the local relative path?
    """
    def _get_gcs_blob(self, remote_relative_path):
        return get_gcs_blob(self.remote_prefix, remote_relative_path)

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

    def __init__(self, manifest_fname, local_prefix, remote_prefix):
        self.fname = manifest_fname
        self.remote_prefix = remote_prefix
        self.local_prefix = local_prefix

        self.header = None

        # we lock the file to ensure that only one file is doing this at a time
        # XXX -- only allow one reader at a time
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


class DataManifestReader(_DataManifestBase):
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


class DataManifestWriter(_DataManifestBase):
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
