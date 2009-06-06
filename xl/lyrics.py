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


#Lyrics manager.
#
from xl import providers, event
from xl import settings

class LyricsNotFoundException(Exception):
    pass

class LyricsManager(providers.ProviderHandler):
    """
        Lyrics Manager
    
        Manages talking to the lyrics plugins and updating the track
    """
    
    def __init__(self):
        providers.ProviderHandler.__init__(self, "lyrics")
        self.methods = {}
        self.preferred_order = settings.get_option(
                'lyrics/preferred_order', [])
        self.add_defaults()
        
    def add_search_method(self, method):
        """
            Adds a search method to the provider list.
            
            @param method: the search method instance
        """
        providers.register(self.servicename, method)
        
    def remove_search_method(self, method):
        """
            Removes the given search method from the provider list.
            
            @param method: the search method instance
        """
        providers.unregister(self.servicename, method)
        
    def remove_search_method_by_name(self, name):
        """
            Removes a search method from the provider list.
            
            @param name: the search method name
        """
        try:
            providers.unregister(self.servicename, self.methods[name])
        except KeyError:
            return

    def set_preferred_order(self, order):
        """
            Sets the preferred search order

            @param order: a list containing the order you'd like to search
                first
        """
        if not type(order) in (list, tuple):
            raise AttributeError(_("order must be a list or tuple"))
        self.preferred_order = order
        settings.set_option('lyrics/preferred_order', list(order))

    def on_new_provider(self, provider):
        """
            Adds the new provider to the methods dict and passes a
            reference of the manager instance to the provider.
            
            @param provider: the provider instance being added.
        """
        if not provider.name in self.methods:
            self.methods[provider.name] = provider
            provider._set_manager(self)
            event.log_event('lyrics_search_method_added', self, provider) 

    def on_del_provider(self, provider):
        """
            Remove the provider from the methods dict, and the
            preferred_order dict if needed.
            
            @param provider: the provider instance being removed.
        """
        try:
            del self.methods[provider.name]
            event.log_event('lyrics_search_method_removed', self, provider) 
        except KeyError:
            pass
        try:
            self.preferred_order.remove(provider.name)
        except (ValueError, AttributeError):
            pass     

    def get_methods(self):
        """
            Returns a list of Methods, sorted by preference
        """
        methods = []
        
        for name in self.preferred_order:
            if name in self.methods:
                methods.append(self.methods[name])
        for k, method in self.methods.iteritems():
            if method not in methods:
                methods.append(method)
        return methods
    
    def add_defaults(self):
        """
            Adds default search methods
        """
        self.add_search_method(LocalLyricSearch())
        
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

        if not lyrics:
            # no lyrcs were found, raise an exception
            raise LyricsNotFoundException()

        lyrics = lyrics.strip()

        # See if we want to update the track,
        # but only if we have lyrics
        if update_track:
            track["lyrics"] = [lyrics]
            track.write_tags()
        
        return (lyrics, source, url)
    
        
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
            Sets the lyrics manager.  

            Called when this method is added to the lyrics manager.

            @param manager: the lyrics manager
        """
        self.manager = manager

class LocalLyricSearch(LyricSearchMethod):
    
    name="local"

    def find_lyrics(self, track):
        # TODO do people store lyrics in other files?
        if track['lyrics'] == None:
            raise LyricsNotFoundException()
        return (track["lyrics"][0], "file", "")
            
