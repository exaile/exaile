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

from xl import common, event, playlist, xdg
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
        self.icecast_url = 'http://dir.xiph.org'
        self.genre_url = self.icecast_url + '/by_genre'
        self.search_url_prefix = self.icecast_url + '/search?search='
        self.cache_file = os.path.join(xdg.get_cache_dir(), 'icecast.cache')
        self.data = {}
        self._load_cache()
        self.subs = {}
        self.playlists = {}

        logger.debug(self.user_agent)

    def _load_cache(self):
        """
        Loads icecast data from cache
        """
        self.data = {}
        if os.path.isfile(self.cache_file):
            dom = minidom.parse(self.cache_file)
            for genre in dom.getElementsByTagName('genre'):
                self.data[genre.getAttribute('name')] = genre.getAttribute('location')

    def _save_cache(self):
        """
        Saves cache data
        """
        impl = minidom.getDOMImplementation()
        document = impl.createDocument(None, 'genrelist', None)
        genrelist = document.documentElement
        for k, v in self.data.items():
            genre = document.createElement('genre')
            genre.setAttribute('name', k)
            genre.setAttribute('location', v)
            genrelist.appendChild(genre)
        with open(self.cache_file, 'w') as h:
            document.writexml(h, indent='\n', encoding='utf-8')

    def get_lists(self, no_cache=False):
        """
        Returns the rlists for icecast
        """
        from xlgui.panel import radio

        if no_cache or not self.data:
            set_status(_('Contacting Icecast server...'))
            hostinfo = urllib.parse.urlparse(self.genre_url)
            c = http.client.HTTPConnection(hostinfo.netloc, timeout=20)
            try:
                c.request('GET', hostinfo.path, headers={'User-Agent': self.user_agent})
                response = c.getresponse()
            except (socket.timeout, socket.error):
                raise radio.RadioException(_('Error connecting to Icecast server.'))

            if response.status != 200:
                raise radio.RadioException(_('Error connecting to Icecast server.'))

            body = response.read()
            c.close()
            set_status('')

            data = {}
            dom = minidom.parseString(body)
            divs = dom.getElementsByTagName('div')
            for div in divs:
                if div.getAttribute('id') == 'content':
                    anchors = div.getElementsByTagName('a')
                    for anchor in anchors:
                        anchor.normalize()
                        for node in anchor.childNodes:
                            if node.nodeType == minidom.Node.TEXT_NODE:
                                data[node.nodeValue] = anchor.getAttribute('href')
                                break
                    break
            self.data = data
            self._save_cache()
        else:
            data = self.data
        rlists = []

        for item in data.keys():
            rlist = RadioList(item, station=self)
            rlist.get_items = lambda no_cache, name=item: self._get_subrlists(
                name=name, no_cache=no_cache
            )
            rlists.append(rlist)

        rlists.sort(key=operator.attrgetter('name'))
        self.rlists = rlists
        return rlists

    def _get_subrlists(self, name, no_cache=False):
        """
        Gets the subrlists for a rlist
        """
        if name in self.subs and not no_cache:
            return self.subs[name]

        url = self.icecast_url + self.data[name]

        rlists = self._get_stations(url)
        rlists.sort(key=operator.attrgetter('name'))

        self.subs[name] = rlists
        return rlists

    def _get_playlist(self, name, station_id):
        """
        Gets the playlist for the given name and id
        """
        if station_id in self.playlists:
            return self.playlists[station_id]
        url = self.icecast_url + '/listen/' + station_id + '/listen.xspf'
        set_status(_('Contacting Icecast server...'))

        self.playlists[station_id] = playlist.import_playlist(url)
        set_status('')
        return self.playlists[station_id]

    def search(self, keyword):
        """
        Searches the station for a specified keyword

        @param keyword: the keyword to search
        """
        url = self.search_url_prefix + urllib.parse.quote_plus(keyword)
        return self._get_stations(url)

    def _get_stations(self, url):
        from xlgui.panel import radio

        hostinfo = urllib.parse.urlparse(url)
        query = hostinfo.query
        items = []
        thisPage = -1
        nextPage = 0
        set_status(_('Contacting Icecast server...'))
        c = http.client.HTTPConnection(hostinfo.netloc, timeout=20)
        while thisPage < nextPage:
            thisPage += 1
            try:
                c.request(
                    'GET',
                    "%s?%s" % (hostinfo.path, query),
                    headers={'User-Agent': self.user_agent},
                )
                response = c.getresponse()
            except (socket.timeout, socket.error):
                raise radio.RadioException(_('Error connecting to Icecast server.'))

            if response.status != 200:
                raise radio.RadioException(_('Error connecting to Icecast server.'))

            body = response.read().decode('utf-8', 'replace')

            # XML parser can't handle the audio tag
            body = re.sub('<audio.*?>.*?</audio>', '', body, flags=(re.M | re.DOTALL))

            dom = minidom.parseString(body)
            divs = dom.getElementsByTagName('div')
            for div in divs:
                if div.getAttribute('id') == 'content':
                    servers = div.getElementsByTagName('tr')
                    for server in servers:
                        spans = server.getElementsByTagName('span')
                        for span in spans:
                            if span.getAttribute('class') == 'name':
                                span.normalize()
                                if span.firstChild.nodeType == minidom.Node.TEXT_NODE:
                                    sname = span.firstChild.nodeValue
                                else:
                                    sname = span.firstChild.firstChild.nodeValue
                                break
                        tds = server.getElementsByTagName('td')
                        for td in tds:
                            if td.getAttribute('class') == 'tune-in':
                                anchors = td.getElementsByTagName('a')
                                for anchor in anchors:
                                    href = anchor.getAttribute('href')
                                    matcher = re.match(
                                        '/listen/(\d+)/listen\.xspf\Z', href
                                    )
                                    if matcher:
                                        sid = matcher.group(1)
                                        break
                                paragraphs = td.getElementsByTagName('p')
                                for paragraph in paragraphs:
                                    if paragraph.hasAttribute('title'):
                                        quality = paragraph.getAttribute(
                                            'title'
                                        ).split()
                                        if quality[0] == 'Quality':
                                            sbitrate = self._calc_bitrate(quality[1])
                                        elif len(quality[0]) > 3:
                                            sbitrate = str(int(quality[0]) // 1024)
                                        else:
                                            sbitrate = quality[0]
                                        anchor = paragraph.getElementsByTagName(
                                            'a'
                                        ).item(0)
                                        anchor.normalize()
                                        for text in anchor.childNodes:
                                            if text.nodeType == minidom.Node.TEXT_NODE:
                                                sformat = text.nodeValue
                                                break
                                        break
                                break
                        items.append((sname, sid, sbitrate, sformat))

                    nextPage = -1
                    uls = div.getElementsByTagName('ul')
                    for ul in uls:
                        if ul.getAttribute('class') == 'pager':
                            anchors = ul.getElementsByTagName('a')
                            query = anchors.item(anchors.length - 1).getAttribute(
                                'href'
                            )
                            matcher = re.match('\?(.*?page=(\d+))\Z', query)
                            query = matcher.group(1)
                            nextPage = int(matcher.group(2))
                            break
                    break
            dom.unlink()
        c.close()
        set_status('')
        rlists = []

        for item in items:
            rlist = RadioItem(item[0], station=self)
            rlist.bitrate = item[2]
            rlist.format = item[3]
            rlist.get_playlist = lambda name=item[0], station_id=item[
                1
            ]: self._get_playlist(name, station_id)
            rlists.append(rlist)

        return rlists

    def _calc_bitrate(self, quality):
        q = float(quality.replace(',', '.'))
        if q < 5.0:
            bitrate = 64.0 + q * 16.0
        elif q < 9.0:
            bitrate = 160.0 + (q - 5.0) * 32.0
        else:
            bitrate = 320.0 + (q - 9.0) * 180.0
        return str(int(bitrate))

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
            lambda column, cell, model, iter: cell.set_property(
                'text', model.get_value(iter, 0).bitrate
            ),
        )
        self.list.append_column(col)
        text = Gtk.CellRendererText()
        text.set_property('xalign', 0.5)
        col = Gtk.TreeViewColumn(_('Format'), text)
        col.set_cell_data_func(
            text,
            lambda column, cell, model, iter: cell.set_property(
                'text', model.get_value(iter, 0).format
            ),
        )
        self.list.append_column(col)
