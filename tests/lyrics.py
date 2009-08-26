# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#
# The developers of the Exaile media player hereby grant permission 
# for non-GPL compatible GStreamer and Exaile plugins to be used and 
# distributed together with GStreamer and Exaile. This permission is 
# above and beyond the permissions granted by the GPL license by which 
# Exaile is covered. If you modify this code, you may extend this 
# exception to your version of the code, but you are not obligated to 
# do so. If you do not wish to do so, delete this exception statement 
# from your version.
from tests.base import BaseTestCase
import unittest, time, shutil, sys
from xl.lyrics import LyricsManager
from xl.lyrics import LyricsNotFoundException
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
        self.lyrics = LyricsManager()
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
