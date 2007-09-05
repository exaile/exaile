#!/usr/bin/env python
# Copyright (C) 2006 Adam Olsen <arolsen@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from gettext import gettext as _
import xl.common, urllib, os, re, gobject, xl.panels, gtk
from xl import xlmisc, media, common
from xl.panels import radio
from xl.gui import playlist as trackslist
import xl.plugins as plugins

PLUGIN_ID = 'Shoutcast Radio'
PLUGIN_NAME = _("Shoutcast Radio")
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.4.5'
PLUGIN_DESCRIPTION = _(r"""Allows you to browse the Shoutcast Streaming Radio
network""")
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None

PLS = re.compile("<a href=\"(/sbin/shoutcast-playlist\.pls\?rn=\d+&file="
    "filename\.pls)\">.*?<a.*?href=\"[^\"]*\">([^<]*)</a>.*?Now Playing:</font>"
    "([^<]*)</font>.*?size=\"2\" color=\"\#FFFFFF\">(\d+/\d+)</font>.*?"
    "size=\"2\" color=\"#FFFFFF\">(\d+)</font>")

NEXT = re.compile("startat=(\d+)\">\[ Next")

def parse_genre(genre, stations, url=None, func=None, s_term='sgenre'):
    """
        Parses a genre for all streams
    """
    if url == None:
        url = "http://www.shoutcast.com/directory/" \
            "index.phtml?%s=%s&numresult=500" % (s_term, 
            urllib.quote_plus(str(genre)))
    h = urllib.urlopen(url)
    data = h.read().replace("\n", " ")
    h.close()
    xlmisc.log('read url %s' % url)

    tup = re.findall(PLS, data)
    for station in tup:
        new = []
        check = True
        # make sure the track information is unicode worthy (I have found that
        # not all are)
        for a in station:
            try:
                new.append(unicode(a))
            except:
                check = False

        if not check: continue
        station = new
        s = dict()
        s['loc'] = "http://www.shoutcast.com%s" % station[0]
        s['album'] = station[1]
        s['album'] = station[1]
        s['title'] = station[2]
        s['bitrate'] = station[4]

        s['artist'] = s['loc']

        stations.append(s)
        if func:
            gobject.idle_add(func, s)

    if len(stations) >= 100:
        return
    m = NEXT.search(data)
    if m != None:
        # check the next page
        parse_genre(genre, stations,
            "http://www.shoutcast.com/directory/index.phtml" \
            "?startat=%s&%s=%s&numresult=500" % (m.group(1), s_term, genre), func)

class ShoutcastDriver(radio.RadioDriver):
    """
        Shoutcast Streaming Radio Driver
    """
    def __init__(self, panel):
        self.model = panel.model
        self.folder_icon = panel.folder
        self.note_icon = panel.track
        self.tree = panel.tree
        self.panel = panel
        self.add = []
        self.count = 0

    def load_cache(self, cache_file):
        return open(cache_file).readlines()

    def save_cache(self, cache_file, lines):
        h = open(cache_file, 'w')
        for line in lines:
            h.write("%s\n" % line)

        h.close()

    @xl.common.threaded
    def load_streams(self, node, load_node, use_cache=True):
        """
            Loads the shoutcast streams
        """
        cache_file = xl.path.get_cache(PLUGIN_ID + '_radio_plugin.cache')
        if use_cache and os.path.isfile(cache_file):
            lines = self.load_cache(cache_file)
        else:
            reg = re.compile(r'<OPTION VALUE="TopTen">-=\[Top 25 Streams\]=-(.*?)</SELECT>', re.DOTALL)

            data = urllib.urlopen('http://www.shoutcast.com').read()

            m = reg.search(data)
            lines = m.group(1).split('\n')
            self.save_cache(cache_file, lines)

        gobject.idle_add(self.show_streams, lines, node, load_node)

    def get_menu(self, item, menu):
        menu.append(_('Search'), self.on_search, 'gtk-find')
        return menu

    def show_streams(self, lines, node, load_node):
        """
            Actually displays the stream information
        """

        self.model.remove(load_node)
        self.last_node = None
        for line in lines:
            m = re.search(r'(\t+)<OPTION VALUE="(.*?)">', line)
            if m:
                tabcount = m.group(1)
                genre = m.group(2)
                if not tabcount == '\t\t': 
                    self.add_function(node, genre)
                else:
                    self.add_function(self.last_node, genre,
                        True)

        self.tree.expand_row(self.model.get_path(node), False)

    def load_genre(self, genre, rel=False):
        """
            Loads the genre specified
        """
        if rel or not APP.tracks.load(genre, PLUGIN_ID):
            self.fetch_genre(genre)

    def on_search(self, *e):
        dialog = common.MultiTextEntryDialog(self.panel.exaile.window,
            _("Search Stations"))
        dialog.add_field(_("Search:"))
        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_OK:
            values = dialog.get_values()
            self.genre = None
            tracks = trackslist.TracksListCtrl(self.panel.exaile)
            self.panel.exaile.playlists_nb.append_page(tracks,
                xlmisc.NotebookTab(self.panel.exaile, values[0],
                    tracks))
            self.panel.exaile.playlists_nb.set_current_page(
                self.panel.exaile.playlists_nb.get_n_pages() - 1)
            self.panel.exaile.tracks = tracks
            self.tracks = tracks
            self.do_search(values[0]) 

    @xl.common.threaded
    def do_search(self, value):
        stations = []
        parse_genre(value, stations, None, self.update, 's')
        gobject.idle_add(self.update, None)

        xlmisc.log("%d stations were found."  % len(stations))

    @xl.common.threaded
    def fetch_genre(self, genre):
        """
            Fetches the specified genre from shoutcast
        """
        self.genre = genre
        print "genre = ", str(genre)
        stations = []
        parse_genre(self.genre, stations, None, self.update)
        gobject.idle_add(self.update, None)

        xlmisc.log("%d stations were found." % len(stations))

    def update(self, track):
        """
            Updates the RadioTracksList with found tracks
        """
        if not track:
            if len(self.add):
                songs = self.tracks.songs
                for track in self.add:
                    if not track['loc'] in songs.paths:
                        tr = media.Track()
                        tr.set_info(**track)
                        tr.type = 'stream'
                        songs.append(tr)
                self.tracks.set_songs(songs)
            self.tracks.exaile.status.set_first(None)
            if self.genre:
                self.tracks.save(self.genre, PLUGIN_ID)
            self.tracks.playlist_songs = self.tracks.songs
        elif self.count <= 60:
            if not track['loc'] in self.tracks.songs.paths:
                tr = media.Track()
                tr.set_info(**track)

                tr.type = 'stream'
                self.tracks.append_song(tr)
        else:
            self.add.append(track)

        self.count += 1

    def add_function(self, node, genre, note_icon=False):
        icon = self.folder_icon
        item = urllib.unquote(genre)
        item = radio.RadioGenre(item, self)
        if note_icon: 
            icon = self.note_icon
        node = self.model.append(node, [icon, item])
        if not note_icon:
            self.last_node = node

        return False

    def __str__(self):
        return PLUGIN_NAME

def initialize():
    """
        Sets up the shoutcast driver
    """
    global PLUGIN

    PLUGIN = ShoutcastDriver(APP.pradio_panel)
    APP.pradio_panel.add_driver(PLUGIN, plugins.name(__file__))

    return True


def destroy():
    global PLUGIN

    if PLUGIN:
        APP.pradio_panel.remove_driver(PLUGIN)

    PLUGIN = None
