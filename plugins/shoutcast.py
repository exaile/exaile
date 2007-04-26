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

PLUGIN_NAME = "Shoutcast Radio"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r"""Allows you to browse the Shoutcast Streaming Radio
network"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None
import xl.common, urllib, os, re, gobject, xl.panels
from xl import xlmisc
from xl import media

PLS = re.compile("<a href=\"(/sbin/shoutcast-playlist\.pls\?rn=\d+&file="
    "filename\.pls)\">.*?<a.*?href=\"[^\"]*\">([^<]*)</a>.*?Now Playing:</font>"
    "([^<]*)</font>.*?size=\"2\" color=\"\#FFFFFF\">(\d+/\d+)</font>.*?"
    "size=\"2\" color=\"#FFFFFF\">(\d+)</font>")

NEXT = re.compile("startat=(\d+)\">\[ Next")

def parse_genre(genre, stations, url=None, func=None):
    """
        Parses a genre for all streams
    """
    if url == None:
        url = "http://www.shoutcast.com/directory/" \
            "index.phtml?sgenre=%s&numresult=500" % urllib.quote_plus(str(genre))
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
            "?startat=%s&genre=%s&numresult=500" % (m.group(1), genre), func)


class ShoutcastDriver(xl.panels.PRadioDriver):
    """
        Shoutcast Streaming Radio Driver
    """
    def __init__(self, panel):
        self.model = panel.model
        self.folder_icon = panel.folder
        self.note_icon = panel.track
        self.tree = panel.tree
        self.add = []
        self.count = 0
        self

    @xl.common.threaded
    def load_streams(self, node, load_node):
        """
            Loads the shoutcast streams
        """
        reg = re.compile(r'<OPTION VALUE="TopTen">-=\[Top 25 Streams\]=-(.*?)</SELECT>', re.DOTALL)

        data = urllib.urlopen('http://www.shoutcast.com').read()

        m = reg.search(data)
        lines = m.group(1).split('\n')

        gobject.idle_add(self.show_streams, lines, node, load_node)

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

    @xl.common.threaded
    def load_genre(self, genre):
        """
            Loads the genre specified
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
            self.tracks.save(self.genre)
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
        item = xl.panels.PRadioGenre(item, self)
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
    APP.pradio_panel.add_driver(PLUGIN)

    return True


def destroy():
    global PLUGIN

    if PLUGIN:
        APP.pradio_panel.remove_driver(PLUGIN)

    PLUGIN = None
