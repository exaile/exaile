from gi.repository import GLib
from gi.repository import Gtk

import http.client
import logging
import operator
import os
import re
import socket
import urllib.parse
from xml.dom import minidom

from xl import common, event, playlist, xdg, trax
from xl.radio import RadioStation, RadioList, RadioItem
from xl.nls import gettext as _
from xlgui.widgets import dialogs


logger = logging.getLogger(__name__)
STATION = None


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "exaile_loaded")
    else:
        _enable(None, exaile, None)


def _enable(devicename, exaile, nothing):
    global STATION

    STATION = IcecastRadioStation(exaile)
    exaile.radio.add_station(STATION)


def disable(exaile):
    global STATION
    exaile.radio.remove_station(STATION)
    STATION = None


def set_status(message, timeout=0):
    from xlgui.panel import radio

    radio.set_status(message, timeout)


class IcecastRadioStation(RadioStation):
    """
    Icecast Radio

    Simple usage:

    >>> manager = RadioManager()
    >>> manager.add_station(IcecastRadioStation())
    >>> stations = manager.search('icecast', 'ravetrax')
    >>> tracks = stations[0].get_playlist().get_tracks()
    >>> len(tracks) > 0
    True
    >>>
    """

    name = 'icecast'

    def __init__(self, exaile):
        """
        Initializes the icecast radio station
        """
        self.exaile = exaile
        self.user_agent = exaile.get_user_agent_string('icecast')
        self.icecast_url = 'https://dir.xiph.org'

        self.xml_url = self.icecast_url + '/yp.xml'
        self.genres_url = self.icecast_url + '/genres'

        self.cache_file = os.path.join(xdg.get_cache_dir(), 'icecast.cache')
        self.data = {}
        self._load_cache()
        self.playlists = {}

        logger.debug(self.user_agent)

    def _load_cache(self):
        """
        Loads icecast data from cache
        """
        if os.path.isfile(self.cache_file):
            try:
                dom = minidom.parse(self.cache_file)
            except:
                return
            self.data = {}
            for genre in dom.getElementsByTagName('genre'):
                genre_urls = {}

                for station in genre.getElementsByTagName('station'):
                    entry = {}
                    entry['url'] = station.getAttribute('url')
                    entry['bitrate'] = station.getAttribute('bitrate')
                    entry['format'] = station.getAttribute('format')

                    genre_urls[station.getAttribute('name')] = entry
                self.data[genre.getAttribute('name')] = genre_urls

    def _save_cache(self):
        """
        Saves cache data
        """
        impl = minidom.getDOMImplementation()
        document = impl.createDocument(None, 'genrelist', None)
        genrelist = document.documentElement
        for genre_name, stations in self.data.items():
            genre = document.createElement('genre')
            genre.setAttribute('name', genre_name)
            for station_name, url in stations.items():
                station = document.createElement('station')
                station.setAttribute('name', station_name)
                station.setAttribute('url', url['url'])
                station.setAttribute('bitrate', url['bitrate'])
                station.setAttribute('format', url['format'])
                genre.appendChild(station)
            genrelist.appendChild(genre)
        with open(self.cache_file, 'w', encoding="utf-8") as h:
            document.writexml(h, indent='\n', encoding='utf-8')

    def get_lists(self, no_cache=False):
        """
        Returns the stations list for icecast
        """
        # Level 1
        from xlgui.panel import radio

        if no_cache or not self.data:
            set_status(_('Contacting Icecast server...'))
            genre_list = self._get_genres()
            hostinfo = urllib.parse.urlparse(self.xml_url)

            c = http.client.HTTPConnection(hostinfo.netloc, timeout=20)
            try:
                c.request('GET', hostinfo.path, headers={'User-Agent': self.user_agent})
                response = c.getresponse()
            except (socket.timeout, socket.error):
                raise radio.RadioException(_('Error connecting to Icecast server.'))

            if response.status != 200:
                raise radio.RadioException(_('Error connecting to Icecast server.'))

            set_status(_('Parsing stations XML...'))
            body = response.read()
            c.close()

            def get_text(node):
                for subnode in node.childNodes:
                    if subnode.nodeType == minidom.Node.TEXT_NODE:
                        return subnode.nodeValue

            data = {}
            dom = minidom.parseString(body)
            entries = dom.getElementsByTagName('entry')
            set_status(_('Retrieving stations...'))
            for entry in entries:
                url_node = entry.getElementsByTagName('listen_url')[0]
                name_node = entry.getElementsByTagName('server_name')[0]
                genre_node = entry.getElementsByTagName('genre')[0]
                bitrate_node = entry.getElementsByTagName('bitrate')[0]
                server_type_node = entry.getElementsByTagName('server_type')[0]

                name = get_text(name_node)
                url = get_text(url_node)
                genre = get_text(genre_node) or _('Unknown')
                bitrate = get_text(bitrate_node)
                format = get_text(server_type_node)

                station_genres = genre.split(' ')
                insert_genres = []
                for i in range(0, len(station_genres)):
                    if station_genres[i].lower() in genre_list:
                        insert_genres.append(station_genres[i])
                    if i < len(station_genres) - 1:
                        if (
                            (station_genres[i] + " " + station_genres[i + 1]).lower()
                        ) in genre_list:
                            insert_genres.append(
                                station_genres[i] + " " + station_genres[i + 1]
                            )

                entry = {}
                entry['url'] = url
                entry['bitrate'] = bitrate
                entry['format'] = format
                for genre in insert_genres:
                    if not genre in data:
                        data[genre] = {}
                    data[genre][name] = entry

            self.data = data
            self._save_cache()
        else:
            data = self.data
        rlists = []

        for item in data.keys():
            if item is None:
                continue
            rlist = RadioList(item, station=self)
            rlist.get_items = lambda no_cache, name=item: self._get_subrlists(
                name=name, no_cache=no_cache
            )
            rlists.append(rlist)

        rlists.sort(key=operator.attrgetter('name'))
        self.rlists = rlists
        set_status('')
        return rlists

    def _get_subrlists(self, name, no_cache=False):
        """
        Gets the stations to a genre
        """
        sublist = self.data[name]
        station_list = self._build_station_list(sublist)
        return station_list

    def _get_playlist(self, name, station_url):
        """
        Gets the playlist for the given name and id
        """
        if station_url in self.playlists:
            return self.playlists[station_url]
        set_status(_('Contacting Icecast server...'))

        track = trax.Track(station_url)
        pls = playlist.Playlist(name=name)
        pls.append(track)
        self.playlists[station_url] = pls

        set_status('')
        return pls

    def search(self, keyword):
        """
        Searches the station for a specified keyword

        @param keyword: the keyword to search
        """
        items = {}
        for genre, stations in self.data.items():
            for name, station in stations.items():
                if keyword.lower() in name.lower():
                    items[name] = station

        return self._build_station_list(items)

    def _build_station_list(self, list):
        station_list = []
        for station_name, url in list.items():
            stat = RadioItem(station_name, url['url'])
            stat.bitrate = url['bitrate']
            stat.format = url['format']
            stat.get_playlist = lambda name=station_name, station_url=url[
                'url'
            ]: self._get_playlist(name, station_url)

            station_list.append(stat)
        station_list.sort(key=operator.attrgetter('name'))
        return station_list

    def on_search(self):
        """
        Called when the user wants to search for a specific stream
        """
        dialog = dialogs.TextEntryDialog(
            _("Enter the search keywords"), _("Icecast Search")
        )

        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            keyword = dialog.get_value()

            self.do_search(keyword)

    @common.threaded
    def do_search(self, keyword):
        """
        Actually performs the search in a separate thread
        """
        lists = self.search(keyword)

        GLib.idle_add(self.search_done, keyword, lists)

    @common.idle_add()
    def search_done(self, keyword, lists):
        """
        Called when the search is finished
        """
        if not lists:
            dialogs.info(self.exaile.gui.main.window, _('No Stations Found'))
            return

        dialog = ResultsDialog(_("Icecast Search Results"))
        dialog.set_items(lists)
        dialog.connect('response', self._search_response)
        dialog.show_all()
        self._keyword = keyword

    def _search_response(self, dialog, result, *e):
        dialog.hide()
        if result == Gtk.ResponseType.OK:
            items = dialog.get_items()
            if not items:
                return

            self.do_get_playlist(self._keyword, items[0])

    @common.threaded
    def do_get_playlist(self, keyword, item):
        pl = item.get_playlist()
        if not pl:
            return

        GLib.idle_add(self.done_getting_playlist, pl)

    @common.idle_add()
    def done_getting_playlist(self, pl):
        self._parent.emit('playlist-selected', pl)

    def get_menu(self, parent):
        """
        Returns a menu that works for icecast radio
        """
        self._parent = parent
        menu = parent.get_menu()
        menu.add_simple(_("Search"), lambda *e: self.on_search(), Gtk.STOCK_FIND)
        return menu

    def _get_genres(self):
        from xlgui.panel import radio

        set_status(_('Contacting Icecast server...'))
        hostinfo = urllib.parse.urlparse(self.genres_url)

        c = http.client.HTTPConnection(hostinfo.netloc, timeout=20)
        try:
            c.request('GET', hostinfo.path, headers={'User-Agent': self.user_agent})
            response = c.getresponse()
        except (socket.timeout, socket.error):
            raise radio.RadioException(_('Error connecting to Icecast server.'))

        if response.status != 200:
            raise radio.RadioException(_('Error connecting to Icecast server.'))

        set_status(_('Parsing genre list...'))
        body = response.read()
        c.close()

        genres = {}
        next = False
        for line in body.splitlines():
            if next:
                genre = line.strip().decode('UTF-8')
                genres[genre.lower()] = genre
                next = False
            if b'list-group-item list-group-item-action' in line:
                next = True

        return genres


class ResultsDialog(dialogs.ListDialog):
    def __init__(self, title):
        dialogs.ListDialog.__init__(self, title)
        col = self.list.get_column(0)
        col.set_title(_('Name'))
        col.set_expand(True)
        col.set_resizable(True)
        self.list.set_headers_visible(True)
        text = Gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        col = Gtk.TreeViewColumn(_('Bitrate'), text)
        col.set_cell_data_func(
            text,
            lambda column, cell, model, iter, unused: cell.set_property(
                'text', model.get_value(iter, 0).bitrate
            ),
        )
        self.list.append_column(col)
        text = Gtk.CellRendererText()
        text.set_property('xalign', 0.5)
        col = Gtk.TreeViewColumn(_('Format'), text)
        col.set_cell_data_func(
            text,
            lambda column, cell, model, iter, unused: cell.set_property(
                'text', model.get_value(iter, 0).format
            ),
        )
        self.list.append_column(col)
