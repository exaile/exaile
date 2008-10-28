from tests.lyrics import LyricsBaseTestCase, LyricsNotFoundException

class LyricWikiTestCase(LyricsBaseTestCase):
    def setUp(self):
        LyricsBaseTestCase.setUp(self)
        self.lyricwiki_plugin = self.load_plugin("lyricwiki")

    def testFetchLyricsLyricWiki(self):
        """
            Test fetching lyrics from lyric wiki
        """
        # Enable the plugin
        self.lyricwiki_plugin.enable(self)
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track)
        assert(len(lyrics) > 0), "Lyrics search failed"
        assert(source == "Lyric Wiki"), "Lyrics search had wrong source"

    def testFetchLyricsFailLyricWiki(self):
        """
            Test fetching lyrics from lyric wiki that fails
        """
        # Enable the plugin
        self.lyricwiki_plugin.enable(self)
        self.failUnlessRaises(LyricsNotFoundException, self.lyrics.find_lyrics,self.fail_track)


