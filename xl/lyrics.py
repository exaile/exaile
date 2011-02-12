# Copyright (C) 2008-2010 Adam Olsen
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


#Lyrics manager.
#
from xl import providers, event, xdg
from xl import settings
from xl.nls import gettext as _
from datetime import datetime, timedelta
import threading
import shelve
import os

class LyricsNotFoundException(Exception):
    pass

class LyricsCache:
    '''
        Basically just a thread-safe shelf for convinience.  
        Supports container syntax.
    '''
    def __init__(self, location, default=None):
        '''
            @param location: specify the shelve file location
            
            @param default: can specify a default to return from getter when
                there is nothing in the shelve
        '''
        self.location = location
        self.db = shelve.open(location, flag='c', protocol=2, writeback=False)
        self.lock = threading.Lock()
        self.default = default

    def keys(self):
        '''
            Return the shelve keys
        '''
        return self.db.keys()
        
    def _get(self, key, default=None):
        with self.lock:
            try:
                return self.db[key]
            except:
                return default if default is not None else self.default
                
    def _set(self, key, value):
        with self.lock:
            self.db[key] = value
            # force save, wasn't auto-saving...
            self.db.sync()
                
    def __getitem__(self, key):
        return self._get(key)
        
    def __setitem__(self, key, value):
        self._set(key, value)
        
    def __contains__(self, key):
        return key in self.db

    def __delitem__(self, key):
        with self.lock:
            del self.db[key]

    def __iter__(self):
        return self.db.__iter__()
        
    def __len__(self):
        return len(self.db)

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
        self.cache = LyricsCache(os.path.join(xdg.get_cache_dir(),'lyrics.cache'))

    def get_method_names(self):
        """
            Returns a list of methods names in a readable format
        """
        methods=[]
        for k, method in self.methods.iteritems():
            methods.append(method.display_name)
        return methods

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
            raise AttributeError("order must be a list or tuple")
        self.preferred_order = order
        settings.set_option('lyrics/preferred_order', list(order))

    def on_provider_added(self, provider):
        """
            Adds the new provider to the methods dict and passes a
            reference of the manager instance to the provider.

            @param provider: the provider instance being added.
        """
        if not provider.name in self.methods:
            self.methods[provider.name] = provider
            provider._set_manager(self)
            event.log_event('lyrics_search_method_added', self, provider)

    def on_provider_removed(self, provider):
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

    def find_lyrics(self, track, refresh=False):
        """
            Fetches lyrics for a track either from
                1. a backend lyric plugin
                2. the actual tags in the track

            :param track: the track we want lyrics for, it
                must have artist/title tags
                
            :param refresh: if True, try to refresh cached data even if
                not expired

            :return: tuple of the following format (lyrics, source, url)
                where lyrics are the lyrics to the track
                source is where it came from (file, lyrics wiki,
                lyrics fly, etc.)
                url is a link to the lyrics (where applicable)

            :raise LyricsNotFoundException: when lyrics are not
                found
        """
        lyrics = None
        source = None
        url = None

        for method in self.get_methods():
            try:
                (lyrics, source, url) = self._find_cached_lyrics(method, track, refresh)
            except LyricsNotFoundException:
                pass
            if lyrics:
                break

        if not lyrics:
            # no lyrcs were found, raise an exception
            raise LyricsNotFoundException()

        lyrics = lyrics.strip()

        return (lyrics, source, url)

    def find_all_lyrics(self, track, refresh=False):
        """
            Like find_lyrics but fetches all sources and returns
            a list of lyrics.

            :param track: the track we want lyrics for, it
                must have artist/title tags

            :param refresh: if True, try to refresh cached data even if
                not expired

            :return: list of tuples in the same format as
                find_lyrics's return value

            :raise LyricsNotFoundException: when lyrics are not
                found from all sources.
        """
        lyrics_found=[]

        for method in self.get_methods():
            lyrics = None
            source = None
            url = None
            try:
                (lyrics, source, url) = self._find_cached_lyrics(method, track, refresh)
            except LyricsNotFoundException:
                pass
            if lyrics:
                lyrics = lyrics.strip()
                lyrics_found.append((method.display_name,lyrics, source, url))

        if not lyrics_found:
            # no lyrics were found, raise an exception
            raise LyricsNotFoundException()

        return lyrics_found
        
    def _find_cached_lyrics(self, method, track, refresh=False):
        """
            Checks the cache for lyrics.  If found and not expired, returns
            cached results, otherwise tries to fetch from method.
            
            :param method: the LyricSearchMethod to fetch lyrics from.
            
            :param track: the track we want lyrics for, it 
                must have artist/title tags
                
            :param refresh: if True, try to refresh cached data even if
                not expired
                
            :return: list of tuples in the same format as 
                find_lyric's return value
                
            :raise LyricsNotFoundException: when lyrics are not found 
                in cache or fetched from method
        """
        lyrics = None
        source = None
        url = None
        cache_time = settings.get_option('lyrics/cache_time', 720) # in hours
        key = str(track.get_loc_for_io()+method.display_name)

        try:
            # check cache for lyrics
            if key in self.cache:
                (lyrics, source, url, time) = self.cache[key]
                # return if they are not expired
                now = datetime.now()
                if (now-time < timedelta(hours=cache_time) and not refresh):
                    return (lyrics, source, url)

            (lyrics, source, url) = method.find_lyrics(track)
        except LyricsNotFoundException:
            pass
        else:
            if lyrics:
                # update cache
                time = datetime.now()
                self.cache[key] = (lyrics, source, url, time)
                
        if not lyrics:
            # no lyrcs were found, raise an exception
            raise LyricsNotFoundException()

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

    name="__local"
    display_name=_("Local")

    def find_lyrics(self, track):
        lyrics = track.get_tag_disk('lyrics')
        if not lyrics:
            raise LyricsNotFoundException()
        return (lyrics[0], self.name, "")

