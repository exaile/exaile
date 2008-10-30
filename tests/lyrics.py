import unittest, time, md5, shutil, sys
from xl.lyrics import LyricsManager
from xl.lyrics import LyricsNotFoundException
from tests.base import BaseTestCase
from xl.track import Track

import os, imp

class LyricsBaseTestCase(BaseTestCase):
    """
        Test loading lyrics from various plugins and saving
        embedded lyrics to supported formats
    """
    
    def setUp(self):
        BaseTestCase.setUp(self)
        self.plugindirs = 'plugins'
        self.lyrics = LyricsManager(self.settings)
        # Create a track object
        # (copying the file here so that it doesn't keep updating in bzr when
        # the lyrics manager finds the lyrics and changes the file)
        shutil.copyfile('tests/data/music/delerium/chimera/05 - Truly.mp3', 
            '.testtemp/truly.mp3')
        self.track = Track(".testtemp/truly.mp3")
        self.fail_track = Track("tests/data/music/testartist/first/1-black.ogg")
        # Setup plugins
        self.lyricsfly_plugin =  self.load_plugin("lyricsfly")
        self.lyricsfly_plugin.enable(self)
        # Remove all existing methods from lyrics manager
        for method in self.lyrics.get_providers():
            self.lyrics.remove_search_method(method)


class LyricsTestCase(LyricsBaseTestCase):
    def setUp(self):
        LyricsBaseTestCase.setUp(self)
        
    
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
        
    def testSaveLyricsMp3(self):
        """
            Test saving lyrics to an mp3 file (ID3 tags)
        """
        # Enable plugins to get the track data
        self.lyrics.add_defaults()
        self.lyricsfly_plugin = self.load_plugin('lyricsfly')
        self.lyricsfly_plugin.enable(self)
        # Update the track with new lyrics
        # Get the lyrics from online by forcing, and update the track
        (lyrics, source, url) = self.lyrics.find_lyrics(self.track, True)
        # Load the track to see if it saved
        track = Track("tests/data/music/delerium/chimera/05 - Truly.mp3")

        assert(track["lyrics"][0] == self.track["lyrics"][0]), "Lyrics not saved to track"
        
    def testSaveLyricsOgg(self):
        """
            Test saving lyrics to an ogg file 
        """
        # TODO find out how ogg/vorbis do their lyrics
        assert(True)
