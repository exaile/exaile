from base import BaseTestClass
from xl import playlist
import time, md5

class BasePlaylistTestClass(BaseTestClass):
    """
        stub
    """
    pass

class SmartPlaylistTestCase(BasePlaylistTestClass):
    def setUp(self):
        BasePlaylistTestClass.setUp(self)

        self.sp_loc = "/tmp/sp_exaile%s.playlist" % \
            md5.new(str(time.time())).hexdigest()
        self.sp = playlist.SmartPlaylist(collection=self.collection,
            location=self.sp_loc)
        self.sp.add_param("artist", "=", "TestArtist")
        self.sp.add_param("album", "!=", "First")

    def testSearch(self, sp=None):
        if not sp: sp = self.sp
        sp.update()

        tracks = sp.get_tracks()
        tracks.reverse()

        for i, track in enumerate(tracks):
            assert i+1 == int(track['tracknumber']), \
                "SmartPlaylist search failed"

    def testSaveLoad(self):
        self.sp.set_or_match(True)
        self.sp.save_to_location()

        # test playlist
        sp = playlist.SmartPlaylist(collection=self.collection,
            location=self.sp_loc)

        assert sp.get_or_match() == True, "Loading saved smart playlist failed"
        self.sp.set_or_match(False)
        sp.load_from_location()

        self.testSearch(sp)
