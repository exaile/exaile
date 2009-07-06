import re, urllib, os
from xl.radio import *
from xl import common, playlist, xdg, event
from xlgui import guiutil, commondialogs
import gtk, gobject
from xl.nls import gettext as _

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)

STATION = None
def _enable(devicename, exaile, nothing):
    global STATION
    STATION = ShoutcastRadioStation()
    exaile.radio.add_station(STATION)

def disable(exaile):
    global STATION
    exaile.radio.remove_station(STATION)
    STATION = None

class ShoutcastRadioStation(RadioStation):
    """
        Shoutcast Radio

        Simple usage:

        >>> manager = RadioManager()
        >>> manager.add_station(ShoutcastRadioStation())
        >>> stations = manager.search('shoutcast', 'ravetrax')
        >>> tracks = stations[0].get_playlist().get_tracks()
        >>> len(tracks) > 0
        True
        >>>
    """
    name = 'shoutcast'
    def __init__(self):
        """
            Initializes the shoutcast radio station
        """
        self.genre_url = 'http://www.shoutcast.com/sbin/newxml.phtml'
        self.cat_url = 'http://www.shoutcast.com/sbin/newxml.phtml?genre=%(genre)s'
        self.playlist_url = 'http://www.shoutcast.com/sbin/tunein-station.pls?id=%(id)s'
        self.search_url = 'http://www.shoutcast.com/sbin/newxml.phtml?search=%(kw)s'
        self.cache_file = os.path.join(xdg.get_cache_dir(), 'shoutcast.cache')
        self.data = None 
        self._load_cache()
        self.subs = {}
        self.playlists = {}

    def _load_cache(self):
        """
            Loads shoutcast data from cache
        """
        if os.path.isfile(self.cache_file):
            self.data = open(self.cache_file).read()

    def _save_cache(self):
        """
            Saves cache data
        """
        h = open(self.cache_file, 'w')
        h.write(self.data)
        h.close()

    def get_lists(self, no_cache=False):
        """
            Returns the rlists for shoutcast
        """
        if no_cache or not self.data:
            data = urllib.urlopen(self.genre_url).read()
            self.data = data
            self._save_cache()
        else:
            data = self.data
        items = re.findall(r'<genre name="([^"]*)"></genre>', data)
        rlists = []
        for item in items:
            rlist = RadioList(item, station=self)
            rlist.get_items = lambda no_cache, name=item: \
                self._get_subrlists(name=name, no_cache=no_cache)
            rlists.append(rlist)
        
        sort_list = [(item.name, item) for item in rlists]
        sort_list.sort()
        rlists = [item[1] for item in sort_list]
        self.rlists = rlists
        return rlists

    def _get_subrlists(self, name, no_cache=False):
        """
            Gets the subrlists for a rlist
        """
        if name in self.subs:
            return self.subs[name]

        url = self.cat_url % {'genre': name}
        data = urllib.urlopen(url).read()
        rlists = []
        items = re.findall(r'<station name="([^"]*)" .*? id="(\d+)" br="(\d+)"', data)
        found_names = []
        
        for item in items:
            rlist = RadioItem(item[0], station=self)
            rlist.bitrate = item[2]
            if item[0] in found_names: continue
            found_names.append(item[0])
            rlist.get_playlist = lambda name=item[0], station_id=item[1]: \
                self._get_playlist(name, station_id)
            rlists.append(rlist)

        sort_list = [(item.name, item) for item in rlists]
        sort_list.sort()
        rlists = [item[1] for item in sort_list]

        self.subs[name] = rlists
        return rlists

    def _get_playlist(self, name, station_id):
        """
            Gets the playlist for the given name and id
        """
        if station_id in self.playlists:
            return self.playlists[station_id]
        url = self.playlist_url % {'id': station_id}
        handle = urllib.urlopen(url)

        self.playlists[station_id] = playlist.import_from_pls(name + ".pls",
            handle)
        return self.playlists[station_id]

    def search(self, keyword):
        """
            Searches the station for a specified keyword
            
            @param keyword: the keyword to search
        """
        url = self.search_url % {'kw': keyword}
        data = urllib.urlopen(url).read()
        rlists = []
        items = re.findall(r'<station name="([^"]*)" .*? id="(\d+)"', data)

        for item in items:
            rlist = RadioList(item[0])
            rlist.get_playlist = lambda name=item[0], station_id=item[1]: \
                self._get_playlist(name, station_id)
            rlists.append(rlist)

        return rlists

    def on_search(self):
        """
            Called when the user wants to search for a specific stream
        """
        dialog = commondialogs.TextEntryDialog(_("Enter the search keywords"), 
            _("Shoutcast Search"))

        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            keyword = dialog.get_value()
           
            self.do_search(keyword)

    @common.threaded
    def do_search(self, keyword):
        """
            Actually performs the search in a separate thread
        """
        lists = self.search(keyword)

        gobject.idle_add(self.search_done, keyword, lists)

    @guiutil.gtkrun
    def search_done(self, keyword, lists):
        """
            Called when the search is finished
        """
        dialog = commondialogs.ListDialog(_("Search Results"))
        dialog.set_items(lists)

        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            items = dialog.get_items()
            if not items: return

            self.do_get_playlist(keyword, items[0])

    @common.threaded
    def do_get_playlist(self, keyword, item):
        pl = item.get_playlist()
        pl.name = keyword

        gobject.idle_add(self.done_getting_playlist, pl)

    @guiutil.gtkrun
    def done_getting_playlist(self, pl):
        self._parent.emit('playlist-selected', pl)

    def get_menu(self, parent):
        """
            Returns a menu that works for shoutcast radio
        """
        self._parent = parent
        menu = parent.get_menu()
        menu.append(_("Search"), lambda *e: self.on_search(), 'gtk-find')
        return menu
