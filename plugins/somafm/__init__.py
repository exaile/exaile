# Copyright (C) 2012 Rocco Aliberti
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import logging
import operator

logger = logging.getLogger(__name__)
import os
from urllib.parse import urlparse
import http.client
import socket

import xml.etree.ElementTree as ETree
from xl import event, main, playlist, xdg
from xl.radio import RadioStation, RadioList, RadioItem
from xl.nls import gettext as _
from xlgui.panel import radio

STATION = None


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def _enable(o1, exaile, o2):
    global STATION

    STATION = SomaFMRadioStation()
    exaile.radio.add_station(STATION)


def disable(exaile):
    global STATION
    exaile.radio.remove_station(STATION)
    STATION = None


def set_status(message, timeout=0):
    radio.set_status(message, timeout)


class SomaFMRadioStation(RadioStation):

    name = "somafm"

    def __init__(self):
        """
        Initializes the somafm radio station
        """
        self.user_agent = main.exaile().get_user_agent_string('somafm')
        self.somafm_url = 'https://somafm.com/'
        self.channels_xml_url = self.somafm_url + 'channels.xml'
        self.cache_file = os.path.join(xdg.get_cache_dir(), 'somafm.cache')
        self.channelist = ''
        self.data = {}
        self._load_cache()
        self.subs = {}
        self.playlists = {}
        self.playlist_id = 0
        logger.debug(self.user_agent)

    def get_document(self, url):
        """
        Connects to the server and retrieves the document
        """
        set_status(_('Contacting SomaFM server...'))
        hostinfo = urlparse(url)

        try:
            c = http.client.HTTPConnection(hostinfo.netloc, timeout=20)
        except TypeError:
            c = http.client.HTTPConnection(hostinfo.netloc)

        try:
            c.request('GET', hostinfo.path, headers={'User-Agent': self.user_agent})
            response = c.getresponse()
        except (socket.timeout, socket.error):
            raise radio.RadioException(_('Error connecting to SomaFM server.'))

        if response.status != 200:
            raise radio.RadioException(_('Error connecting to SomaFM server.'))

        document = response.read()
        c.close()

        set_status('')
        return document

    def _load_cache(self):
        """
        Loads somafm data from cache
        """
        self.data = {}
        if os.path.isfile(self.cache_file):
            tree = ETree.parse(self.cache_file)
            for channel in tree.findall('channel'):
                self.data[channel.get("id")] = channel.get("name")

    def _save_cache(self):
        """
        Saves cache data
        """
        channellist = ETree.Element('channellist')
        for channel_id, channel_name in self.data.items():
            ETree.SubElement(channellist, 'channel', id=channel_id, name=channel_name)

        with open(self.cache_file, 'w') as h:
            h.write('<?xml version="1.0" encoding="UTF-8"?>')
            h.write(ETree.tostring(channellist, 'unicode'))

    def get_lists(self, no_cache=False):
        """
        Returns the rlists for somafm
        """
        if no_cache or not self.data:
            self.channellist = self.get_document(self.channels_xml_url)
            data = {}
            tree = ETree.fromstring(self.channellist)

            for channel in tree.findall('channel'):
                name = channel.find('title').text
                data[channel.get("id")] = name

            self.data = data
            self._save_cache()

        else:
            data = self.data

        rlists = []

        for id, name in data.items():
            rlist = RadioList(name, station=self)
            rlist.get_items = lambda no_cache, id=id: self._get_subrlists(
                id=id, no_cache=no_cache
            )
            rlists.append(rlist)

        rlists.sort(key=operator.attrgetter('name'))
        self.rlists = rlists

        return rlists

    def _get_subrlists(self, id, no_cache=False):
        """
        Gets the subrlists for a rlist
        """
        if no_cache or id not in self.subs:

            rlists = self._get_stations(id)
            rlists.sort(key=operator.attrgetter('name'))

            self.subs[id] = rlists

        return self.subs[id]

    def _get_playlist(self, url, playlist_id):
        """
        Gets the playlist for the given url and id
        """
        if playlist_id not in self.playlists:
            set_status(_('Contacting SomaFM server...'))
            try:
                self.playlists[playlist_id] = playlist.import_playlist(url)
            except Exception:
                set_status(_("Error importing playlist"))
                logger.exception("Error importing playlist")
            set_status('')

        return self.playlists[playlist_id]

    def _get_stations(self, id):
        if not self.channelist:
            self.channelist = self.get_document(self.channels_xml_url)

        tree = ETree.fromstring(self.channelist)
        channel = tree.find('.//channel[@id="%s"]' % id)
        plss = channel.findall('.//*[@format]')

        rlists = []
        for pls in plss:
            type = pls.tag.replace('pls', '')
            format = pls.attrib['format'].upper()
            url = pls.text
            display_name = format + " - " + type

            rlist = RadioItem(display_name, station=self)
            rlist.format = format
            rlist.get_playlist = (
                lambda url=url, playlist_id=self.playlist_id: self._get_playlist(
                    url, playlist_id
                )
            )

            self.playlist_id += 1
            rlists.append(rlist)
        return rlists

    def get_menu(self, parent):
        return parent.get_menu()
