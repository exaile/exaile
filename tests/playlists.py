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

    def testSearch(self):
        self.sp.update()

        tracks = self.sp.get_tracks()
        tracks.reverse()

        for i, track in enumerate(tracks):
            assert i+1 == int(track['tracknumber']), \
                "SmartPlaylist search failed"

    def testSaveLoad(self):
        self.sp.save_to_location()

        # test playlist
        sp = playlist.SmartPlaylist(collection=self.collection,
            location=self.sp_loc)
        sp.load_from_location()

        self.testSearch()
