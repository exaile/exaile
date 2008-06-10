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

        self.sp_loc = ".testtemp/sp_exaile%s.playlist" % \
            md5.new(str(time.time())).hexdigest()
        self.sp = playlist.SmartPlaylist(collection=self.collection,
            location=self.sp_loc)
        self.sp.add_param("artist", "=", "TestArtist")
        self.sp.add_param("album", "!=", "First")

    def testSearch(self, sp=None):
        if not sp: sp = self.sp

        p = sp.get_playlist()

        tracks = p.get_tracks()
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

            start = p.get_tracks()

        assert check == True, "Random sort did not work in 50 iterations"
