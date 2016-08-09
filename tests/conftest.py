
import collections
import os
import shutil
import tempfile

from gi.repository import Gio

import pytest

from xl.trax.track import Track

import logging
logging.basicConfig(level=logging.DEBUG)


@pytest.yield_fixture(autouse=True)
def exaile_test_cleanup():
    '''
        Teardown/setup of various Exaile globals
    '''
    
    yield
    
    Track._Track__the_cuts = ['the', 'a']
    
    for key in Track._Track__tracksdict.keys():
        del Track._Track__tracksdict[key]

#
# Fixtures for test track data
#
    

TrackData = collections.namedtuple('TrackData',
                                   ['ext', 'filename', 'uri', 'size', 'writeable'])

def _fname(ext):
    local_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__),
        'data', 'music', 'delerium', 'chimera', '05 - Truly') + os.extsep + ext)
    
    return ext, local_path, Gio.File.new_for_path(local_path).get_uri()

_all_tracks = [
    TrackData(*_fname('aac'),  size=3639,  writeable=True),
    TrackData(*_fname('aiff'), size=16472, writeable=False),
    TrackData(*_fname('au'),   size=16425, writeable=False),
    TrackData(*_fname('flac'), size=17453, writeable=True),
    TrackData(*_fname('mp3'),  size=4692,  writeable=True),
    TrackData(*_fname('mpc'),  size=6650,  writeable=True),
    TrackData(*_fname('ogg'),  size=13002, writeable=True),
    TrackData(*_fname('spx'),  size=1000,  writeable=True),
    TrackData(*_fname('wav'),  size=46124, writeable=False),
    TrackData(*_fname('wma'),  size=3864,  writeable=True),
    TrackData(*_fname('wv'),   size=32293, writeable=True),
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


@pytest.yield_fixture(params=_all_tracks)
def test_track_fp(request):
    t = request.param
    with tempfile.NamedTemporaryFile(suffix='.' + t.ext) as tfp:
        with open(t.filename, 'rb') as fp:
            shutil.copyfileobj(fp, tfp)
            
        tfp.flush()
        
        yield tfp

@pytest.yield_fixture(params=_writeable_tracks)
def writeable_track_fp(request):
    '''Fixture that returns temporary copies of writeable tracks'''
    t = request.param
    with tempfile.NamedTemporaryFile(suffix='.' + t.ext) as tfp:
        with open(t.filename, 'rb') as fp:
            shutil.copyfileobj(fp, tfp)
        
        tfp.flush()
        
        yield tfp


@pytest.fixture
def test_tracks():
    '''
        Returns an object that can be used to retrieve test track data
    '''
    class _TestTracks:
        def get(self, ext):
            return [x for x in _all_tracks if x.filename.endswith(ext)][0]
        
    return _TestTracks()

