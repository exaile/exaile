# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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


#Lyrics manager.
#
from xl.manager import SimpleManager

class LyricsNotFoundException(Exception):
    pass

class LyricsManager(SimpleManager):
    """
        Lyrics Manager
    
        Manages talking to the lyrics plugins and updating the track
    """
        
    def find_lyrics(self, track, update_track = False):
        """
            Fetches lyrics for a track either from 
                1. a backend lyric plugin
                2. the actual tags in the track
            
            @param track: the track we want lyrics for, it
                must have artist/title tags 
            @param update_track: if true we try to write the lyrics
                to the tags in the track (only mp3 at the moment)
                
            @return: tuple of the following format (lyrics, source, url)
                where lyrics are the lyrics to the track
                source is where it came from (file, lyrics wiki, lyrics fly, etc.)
                url is a link to the lyrics (where applicable)
            
            @raise LyricsNotFoundException: when lyrics are not
                found
        """
        lyrics = None
        source = None
        url = None
        for method in self.get_methods():
            try:
                (lyrics, source, url) = method.find_lyrics(track)
            except LyricsNotFoundException:
                pass
            if lyrics:
                break

        # See if we want to update the track,
        # but only if we have lyrics
        if lyrics and update_track:
            track["lyrics"] = lyrics
            track.write_tags()
        
        if lyrics:
            return (lyrics, source, url)
        else:
            # no lyrcs were found, raise an exception
            raise LyricsNotFoundException()
    
    def add_defaults(self):
        """
            Adds default search methods
        """
        self.add_search_method(LocalLyricSearch())
        
class LyricSearchMethod(object):
    """
        Lyrics plugins will subclass this
    """
    
    def find_lyrics(self, track):
        """
            Called by LyricsManager when lyrics are requested
            
            @param track: the track that we want lyrics for
        """
        raise NotImplementedError
    
    def _set_manager(self, manager):
        """
            Sets the cover manager.  

            Called when this method is added to the cover manager via
            add_search_method()

            @param manager: the cover manager
        """
        self.manager = manager

class LocalLyricSearch(LyricSearchMethod):
    
    name="local"
    def find_lyrics(self, track):
        # TODO do people store lyrics in other files?
        return (track["lyrics"], "file", "")
