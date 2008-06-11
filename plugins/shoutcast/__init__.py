import re, urllib
from xl.radio import *

def enable(exaile):
    exaile.radio.add_station(ShoutcastRadioStation())

def disable(exaile):
    exaile.radio.add_station("shoutcast")

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
        self.rlists = []
        self.subs = {}
        self.playlists = {}

    def load_lists(self):
        """
            Returns the rlists for shoutcast
        """
        data = urllib.urlopen(self.genre_url).read()
        items = re.findall(r'<genre name="([^"]*)"></genre>', data)
        rlists = []
        for item in items:
            rlist = RadioList(item)
            rlist.get_items = lambda name=item: \
                self._get_subrlists(name)
            rlists.append(rlist)
        
        self.rlists = []
        return rlists

    get_lists = load_lists

    def _get_subrlists(self, name):
        """
            Gets the subrlists for a rlist
        """
        if name in self.subs:
            return self.subs[name]

        url = self.cat_url % {'genre': name}
        data = urllib.urlopen(url).read()
        rlists = []
        items = re.findall(r'<station name="([^"]*)" .*? id="(\d+)"', data)
        
        for item in items:
            rlist = RadioItem(item[0])
            rlist.get_playlist = lambda name=item[0], station_id=item[1]: \
                self._get_playlist(name, station_id)
            rlists.append(rlist)

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
