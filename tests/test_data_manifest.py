import os
import tempfile
import shutil

from freenome_build.util import get_gcs_blob
from freenome_build.data_manifest import DataManifestReader, DataManifestWriter


DEFAULT_PROJECT = 'Freenome Computational'
DEFAULT_REMOTE_PREFIX = 'gs://balrog/reference-data/'


# TODOs
# (1) cleanup the test files (only use synthetic files)
# (2) migrate to Reader/Writer paradigm

def _add_base_to_path(rel_path):
    return os.path.normpath(os.path.join(os.path.abspath(os.path.dirname(__file__)), rel_path))


TEST_MANIFEST_FNAME = _add_base_to_path('../tests/data/pipeline-data/data-manifest.tsv')
TEST_FILE_PATHS_IN_MANIFEST = {
    'eight_as': _add_base_to_path('../tests/data/pipeline-data/eight_As.fa'),
    'eight_cs': _add_base_to_path('../tests/data/pipeline-data/eight_Cs.fa')
}
TEST_FILE_PATHS_NOT_IN_MANIFEST = {
    'twelve_cs': _add_base_to_path('../tests/data/pipeline-data/twelve_Cs.fa'),
}


def reset_test_manifest():
    shutil.copy(TEST_MANIFEST_FNAME+".orig", TEST_MANIFEST_FNAME)


def _add_file_to_manifest_upload_to_gcs_and_verify_local_matches_remote(manifest_fname):
    """Test that adding a file to the manifest works.

    This is called by the more specific test below.
    """
    remote_base_path = DEFAULT_REMOTE_PREFIX

    nf_key = 'twelve_cs'
    nf_path = TEST_FILE_PATHS_NOT_IN_MANIFEST[nf_key]
    nf_local_rel_path = nf_key
    nf_remote_rel_path = nf_key

    with tempfile.TemporaryDirectory() as local_base_path:
        remote_path = DEFAULT_REMOTE_PREFIX + nf_remote_rel_path
        try:
            print(f"Loading manifest: {manifest_fname}")
            manifest = DataManifestWriter(manifest_fname, remote_base_path, local_base_path)
            manifest.add_file(nf_key, nf_path, nf_local_rel_path, nf_remote_rel_path)

            # read the local data file into a string
            # we use this below to ensure that it exists
            print(f"Reading local file: {nf_path}")
            with open(nf_path, 'rb') as ifp:
                local_data = ifp.read()

            # check that the file exists in GCS and is the same as the local file
            print(f"Downloading remote file: {remote_path}")
            blob = get_gcs_blob(DEFAULT_PROJECT, DEFAULT_REMOTE_PREFIX, nf_remote_rel_path)
            gcs_data = blob.download_as_string()
            assert local_data == gcs_data, f"local data: {local_data}\ngcs data: {gcs_data}"
        finally:
            print(f"Reseting manifest: {manifest_fname}")
            reset_test_manifest()
            print(f"Deleting remote file ({remote_path})")
            blob = get_gcs_blob(DEFAULT_PROJECT, DEFAULT_REMOTE_PREFIX, nf_remote_rel_path)
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
    # by default _add_file_to_manifest_upload_to_gcs_and_verify_local_matches_remote adds a file
    # that doesn't already exist, so we don't need to do anything else
    _add_file_to_manifest_upload_to_gcs_and_verify_local_matches_remote()


def test_add_remote_present_file():
    """Test adding a file that does not exist in gcs."""
    # add the file and then ensure that adding to the manifest still works
    # _add_file_to_manifest_upload_to_gcs_and_verify_local_matches_remote adds a files that
    # already exists by default, so we first need to upload the file
    blob = get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH)
    blob.upload_from_filename(TEST_DATA_FILE)
    _add_file_to_manifest_upload_to_gcs_and_verify_local_matches_remote()


def test_add_remote_mismatch_file():
    """Test adding a file that exists in gcs but does not match the file being added."""
    # add a mismatched file and ensure that we get an error
    blob = get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH)
    blob.upload_from_string("NATHAN")
    try:
        _add_file_to_manifest_upload_to_gcs_and_verify_local_matches_remote()
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
        manifest_1 = DataManifestWriter(manifest_fname, remote_prefix=remote_prefix)
        print(f"Loading manifest 2: {manifest_fname}")
        manifest_2 = DataManifestWriter(manifest_fname, remote_prefix=remote_prefix)
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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_verify_success():
    """test that verify works when everything matches."""
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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_verify_size_fail():
    """test that verify failes when there is a size mismatch."""
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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()


def test_verify_md5_fail():
    """test that verify failes when the sizes match but the md5sum's dont."""
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
        get_gcs_blob(DEFAULT_REMOTE_PREFIX, TEST_REMOTE_RELATIVE_PATH).delete()

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
