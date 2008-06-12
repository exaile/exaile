import unittest, time, md5
from xl.lyrics import LyricsManager
from xl.lyrics import LyricsNotFoundException
from base import BaseTestClass
from xl.track import Track

import os, imp

class LyricsTestCase(BaseTestClass):
    """
        Test loading lyrics from various plugins and saving
        embedded lyrics to supported formats
    """
    
    def setUp(self):
        BaseTestClass.setUp(self)
        self.plugindirs = 'plugins'
        self.lyrics = LyricsManager()
        # Create a track object
        self.track = Track("tests/data/music/delerium/chimera/05 - Truly.mp3")
        self.fail_track = Track("tests/data/music/testartist/first/1-black.ogg")
        # Setup plugins
        self.lyricwiki_plugin = self.load_plugin("lyricwiki")
        self.lyricsfly_plugin =  self.load_plugin("lyricsfly")
        # Remove all existing methods from lyrics manager
        methods = self.lyrics.methods;
        self.lyrics.methods = {}
        
    def testFetchLyricsLyricWiki(self):
        """
            Test fetching lyrics from lyric wiki
        """
        # Enable the plugin
        self.lyricwiki_plugin.enable(self)
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track)
        assert(len(lyrics) > 0), "Lyrics search failed"
        assert(source == "Lyric Wiki"), "Lyrics search had wrong source"
        
    def testFetchLyricsLyricsFly(self):
        """
            Test fetching lyrics from lyric fly
        """
        # Enable the plugin
        self.lyricsfly_plugin.enable(self)
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track)
        assert(len(lyrics) > 0), "Lyrics search failed"
        assert(source == "Lyrics Fly"), "Lyrics search had wrong source, %s" % source
    
    def testFetchLyricsMp3(self):
        """
            Test fetching lyrics from the file itself
        """
        #Local searching is added by default
        self.lyrics.add_defaults()
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track)
        assert(len(lyrics) > 0), "Lyrics search failed"
        assert(source == "file"), "Lyrics came from wrong source"
        
    def testFetchLyricsFail(self):
        """
            Test the failing when not finding lyrics works
            correctly
        """
        #Local searching is added by default
        self.lyrics.add_defaults()
        self.failUnlessRaises(LyricsNotFoundException, self.lyrics.find_lyrics,self.fail_track)
        
    def testFetchLyricsFailLyricWiki(self):
        """
            Test fetching lyrics from lyric wiki that fails
        """
        # Enable the plugin
        self.lyricwiki_plugin.enable(self)
        self.failUnlessRaises(LyricsNotFoundException, self.lyrics.find_lyrics,self.fail_track)
        
    def testFetchLyricsFailLyricsFly(self):
        """
            Test fetching lyrics from lyric wiki that fails
        """
        # Enable the plugin
        self.lyricsfly_plugin.enable(self)
        self.failUnlessRaises(LyricsNotFoundException, self.lyrics.find_lyrics,self.fail_track)
        
    def testSaveLyricsMp3(self):
        """
            Test saving lyrics to an mp3 file (ID3 tags)
        """
        # Enable plugins to get the track data
        self.lyrics.add_defaults()
        self.lyricsfly_plugin.enable(self)
        self.lyricwiki_plugin.enable(self)
        # Update the track with new lyrics
        # Get the lyrics from online by forcing, and update the track
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track, True)
        # Load the track to see if it saved
        track = Track("tests/data/music/delerium/chimera/05 - Truly.mp3")
        assert(track["lyrics"] == self.track["lyrics"]), "Lyrics not saved to track"
        
    def testSaveLyricsOgg(self):
        """
            Test saving lyrics to an ogg file 
        """
        # TODO find out how ogg/vorbis do their lyrics
        assert(True)
        
    def load_plugin(self, pluginname):
        path = 'plugins/' + pluginname
        if path is None:
            return False
        plugin = imp.load_source(pluginname, os.path.join(path,'__init__.py'))
        return plugin
