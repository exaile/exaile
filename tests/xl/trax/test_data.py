import os


TEST_TRACKS = [os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                 'data', 'music', 'delerium', 'chimera', '05 - Truly') + os.extsep + ext)
               for ext in ('aac', 'aiff', 'au', 'flac', 'mp3', 'mpc', 'ogg', 'spx',
                           'wav', 'wma', 'wv')]


def get_file_with_ext(ext):
    return [x for x in TEST_TRACKS if x.endswith(ext)][0]
TEST_TRACKS_SIZE = {
    get_file_with_ext('.mp3'): 4692,
}


def test_mp3_exists():
    assert get_file_with_ext('.mp3')


def test_all_tracks_exist():
    for track in TEST_TRACKS:
        assert os.path.exists(track), "%s does not exist" % track
