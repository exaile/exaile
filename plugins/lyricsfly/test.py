from tests.lyrics import LyricsBaseTestCase, LyricsNotFoundException

class LyricsFlyTestCase(LyricsBaseTestCase):
    def setUp(self):
        LyricsBaseTestCase.setUp(self)
        self.lyricsfly_plugin = self.load_plugin('lyricsfly')

    def testFetchLyricsLyricsFly(self):
        """
            Test fetching lyrics from lyric fly
        """
        # Enable the plugin
        self.lyricsfly_plugin.enable(self)
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track)
        assert(len(lyrics) > 0), "Lyrics search failed"
        assert(source == "Lyrics Fly"), "Lyrics search had wrong source, %s" % source

    def testFetchLyricsFailLyricsFly(self):
        """
            Test fetching lyrics from lyric wiki that fails
        """
        # Enable the plugin
        self.lyricsfly_plugin.enable(self)
        self.failUnlessRaises(LyricsNotFoundException, self.lyrics.find_lyrics,self.fail_track)

