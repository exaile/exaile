# Provides a signals-like system for sending and listening for 'events'
#
#
# Events are kind of like signals, except they may be listened for on a 
# global scale, rather than connected on a per-object basis like signals 
# are. This means that ANY object can emit ANY event, and these events may 
# be listened for by ANY object. Events may be emitted either syncronously 
# or asyncronously, the default is asyncronous.
#
# The events module also provides an idle_add() function similar to that of
# gobject's. However this should not be used for long-running tasks as they
# may block other events queued via idle_add().
#
# Events should be emitted AFTER the given event has taken place. Often the
# most appropriate spot is immediately before a return statement.

import urllib, re
from xl import playlist, track

class RadioManager(object):
    """
        Radio Station Manager

        Simple usage:

        >>> manager = RadioManager()
        >>> manager.add_station(RadioStation())
        >>> lists = manager.load_lists('test_station')
        >>> pl = lists[0].get_playlist()
        >>> print pl.get_tracks()[0]['title']
        Test Track
        >>>
    """
    def __init__(self):
        """ 
            Initializes the radio manager
        """
        self.stations = {}

    def add_station(self, station):
        """
            Adds a station to the manager

            @param station: The station to add
        """
        self.stations[station.name] = station

    def remove_station(self, station):
        """
            Removes a station from the manager
    
            @param station: The station to remvoe
        """
        if station.name in self.stations:
            del self.stations[station.name]

    def search(self, station, keyword):
        if station in self.stations:
            return self.stations[station].search(keyword)
        else:
            return None

    def load_lists(self, station):
        """
            Gets the rlists for the specified station

            @param station:  The name of the station
        """
        if station in self.stations:
            return self.stations[station].load_lists()
        else:
            return None


class RadioList(object):
    def __init__(self, name):
        """
            Initializes the rlist
        """
        self.name = name

    def set_name(self, name):
        self.name = name

    def get_name(self):
        return self.name

    def get_items(self):
        """
            Returns subrlists
        """
        return []

class RadioItem(object):
    """
        Radio Items
    """
    def __init__(self, name):
        """
            Initializes the radio item
        """
        self.name = name

    def get_playlist(self):
        tr = track.Track()
        tr['title'] = 'Test Track'
        pl = playlist.Playlist('Test Playlist')
        pl.add_tracks([tr])
        return pl
        
class RadioStation(object):
    name = 'test_station'
    def __init__(self):
        """
            Initialize the radio station
        """
        pass

    def load_lists(self):
        """
            Returns the rlists for this radio station
        """
        return [RadioItem('TestCategory')]

    def search(self, keyword):
        return None

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

    def load_items(self):
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
