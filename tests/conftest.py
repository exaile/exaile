import collections
import os
import shutil
import tempfile

from gi.repository import Gio

import pytest

from xl.trax.track import Track

import logging

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(autouse=True)
def exaile_test_cleanup():
    """
    Teardown/setup of various Exaile globals
    """

    yield

    Track._Track__the_cuts = ['the', 'a']

    Track._Track__tracksdict.clear()


#
# Fixtures for test track data
#


TrackData = collections.namedtuple(
    'TrackData',
    ['ext', 'filename', 'uri', 'size', 'writeable', 'has_cover', 'has_tags'],
)


def _fname(ext):
    local_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            'data',
            'music',
            'delerium',
            'chimera',
            '05 - Truly',
        )
        + os.extsep
        + ext
    )

    return ext, local_path, Gio.File.new_for_path(local_path).get_uri()


_all_tracks = [
    # fmt: off
    TrackData(*_fname('aac'),  size=9404,  writeable=True, has_cover=True, has_tags=True),
    TrackData(*_fname('aiff'), size=21340, writeable=True, has_cover=True, has_tags=True),
    TrackData(*_fname('au'),   size=16425, writeable=False, has_cover=False, has_tags=False),
    TrackData(*_fname('flac'), size=20668, writeable=True, has_cover=True, has_tags=True),
    TrackData(*_fname('mp3'),  size=7495,  writeable=True, has_cover=True, has_tags=True),
    TrackData(*_fname('mp4'),  size=7763,  writeable=True, has_cover=True, has_tags=True),
    TrackData(*_fname('mpc'),  size=6650,  writeable=True, has_cover=False, has_tags=True),
    TrackData(*_fname('ogg'),  size=17303, writeable=True, has_cover=True, has_tags=True),
    TrackData(*_fname('spx'),  size=1000,  writeable=True, has_cover=False, has_tags=True),
    TrackData(*_fname('wav'),  size=46124, writeable=False, has_cover=False, has_tags=False),
    TrackData(*_fname('wma'),  size=4929,  writeable=True, has_cover=False, has_tags=True),
    TrackData(*_fname('wv'),   size=32293, writeable=True, has_cover=False, has_tags=True),
    # fmt: on
]


_writeable_tracks = [t for t in _all_tracks if t.writeable]


@pytest.fixture(params=_all_tracks)
def test_track(request):
    '''Provides TrackData objects for each test track'''
    return request.param


@pytest.fixture(params=_writeable_tracks)
def writeable_track(request):
    '''Provides TrackData objects for each test track that is writeable'''
    return request.param


@pytest.fixture()
def test_track_fp(test_track):
    with tempfile.NamedTemporaryFile(suffix='.' + test_track.ext) as tfp:
        with open(test_track.filename, 'rb') as fp:
            shutil.copyfileobj(fp, tfp)

        tfp.flush()

        yield tfp


@pytest.fixture()
def writeable_track_name(writeable_track):
    '''Fixture that returns names of temporary copies of writeable tracks'''
    with tempfile.NamedTemporaryFile(suffix='.' + writeable_track.ext) as tfp:
        with open(writeable_track.filename, 'rb') as fp:
            shutil.copyfileobj(fp, tfp)

        tfp.flush()

        yield tfp.name


@pytest.fixture
def test_tracks():
    """
    Returns an object that can be used to retrieve test track data
    """

    class _TestTracks:
        def get(self, ext):
            return [x for x in _all_tracks if x.filename.endswith(ext)][0]

    return _TestTracks()
