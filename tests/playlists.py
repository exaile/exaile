from tests.base import BaseTestCase
from xl import playlist
import time, md5

class BasePlaylistTestCase(BaseTestCase):
    """
        stub
    """
    pass

class SmartPlaylistTestCase(BasePlaylistTestCase):
    def setUp(self):
        BasePlaylistTestCase.setUp(self)

        self.sp_loc = ".testtemp/sp_exaile%s.playlist" % \
            md5.new(str(time.time())).hexdigest()
        self.sp = playlist.SmartPlaylist(collection=self.collection)
        self.sp.add_param("artist", "=", "TestArtist")
        self.sp.add_param("album", "!=", "First")

    def testSearch(self, sp=None):
        if not sp: sp = self.sp

        p = sp.get_playlist()
        tracks = p.get_tracks()

        for i, track in enumerate(tracks):
            assert i+1 == track.get_track(), \
                "SmartPlaylist search failed"

    def testSaveLoad(self):
        self.sp.set_or_match(True)
        self.sp.save_to_location(self.sp_loc)

        # test playlist
        sp = playlist.SmartPlaylist(collection=self.collection)
        sp.load_from_location(self.sp_loc)
        
        assert sp.get_or_match() == True, "Loading saved smart playlist failed"
        sp.set_or_match(False)

        self.testSearch(sp)
        self.sp.set_or_match(False)

    def testReturnLimit(self):
        sp = playlist.SmartPlaylist(collection=self.collection)
        sp.set_return_limit(2)

        p = sp.get_playlist()

        assert len(p) == 2, "Return limit test failed"

    def testRandomSort(self):
        sp = playlist.SmartPlaylist(collection=self.collection)
        sp.set_random_sort(True)

        check = False
        p = sp.get_playlist()

        start = p.get_tracks()

        # if it's not different in 50 iterations, something *has* to be wrong
        for i in range(50):
            p = sp.get_playlist() 
            if start != p.get_tracks():
                check = True
                break

        assert check == True, "Random sort did not work in 50 iterations"
