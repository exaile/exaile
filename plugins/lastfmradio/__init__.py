# Copyright (C) 2006 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

"""
    LastFM Proxy plugin.

    This plugin is a complete hack. 

    Props to Vidar Madsen for the lastfmproxy application, which this plugin
    uses directly
"""

from xl.nls import gettext as _
from xl import event, common, playlist, track, settings
from xl.radio import *
import os, os.path, logging
import lastfmmain
import config
import httpclient
logger = logging.getLogger(__name__)

def album_callback(*e):
    pass

@common.threaded
def run_proxy(config):
    count = 0
    while True:
        try:
            STATION.listenport = config.listenport
            PROXY.run(config.bind_address, config.listenport)
            return
        except Exception, e:
            if count >= 5:
                raise(e)

            if e.args[0] == 98:
                count += 1
                logger.warning("LastFM Proxy: Port %d in use, trying %d" %
                    (config.listenport, config.listenport + 1))
                config.listenport += 1
            else:
                raise(e)

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

STATION = None
PROXY = None
HTTP_CLIENT = None
BUTTONS = None
SHOW_COVER = None
def _enable(devicename, exaile, nothing):
    global STATION, PROXY, HTTP_CLIENT, BUTTONS, SHOW_COVER

    port = settings.get_option('plugin/lastfm/listenport', 1881)
    config.listenport = port

    config.username = settings.get_option('plugin/lastfm/user', '')
    config.password = settings.get_option('plugin/lastfm/password', '')

    if not STATION:
        STATION = LastFMRadioStation(config)
        exaile.radio.add_station(STATION)
        HTTP_CLIENT = httpclient.httpclient('__localhost', config.listenport)

    PROXY = lastfmmain.proxy(config.username, config.password)
    PROXY.np_image_func = album_callback
    basedir = os.path.dirname(os.path.realpath(__file__))
    PROXY.basedir = basedir
    run_proxy(config)

    event.add_callback(STATION.on_playback_start, 'playback_start',
        exaile.player)

    return True

def disable(exaile):
    global STATION, PROXY

    exaile.radio.remove_station(STATION)
    if PROXY:
        PROXY.np_image_func = None
        PROXY.quit = True

    PROXY = True
    if STATION:
        event.remove_callback(STATION.on_playback_start, 'playback_track_start',
            exaile.player)
    STATION = None

class LastFMRadioStation(RadioStation):
    """
        LastFM Radio
    """
    name = 'lastfm'
    def __init__(self, config):
        """
            Initializes the lastfm radio station
        """
        self.config = config

    def on_playback_start(self, type, player, track):
        station = track['lastfmstation']
        if station:
            self.command('/changestation/%s' % station)

    @common.threaded
    def command(self, command):
        logger.info("LastFM: running command %s" % command)
        HTTP_CLIENT.req(command)

    def _load_cache(self):
        pass

    def _save_cache(self):
        pass

    def get_lists(self, no_cache=False):
        """
            Returns the list of items for lastfm
        """
        stations = (
            (_('Personal'), 'lastfm://user/%s/personal' % self.config.username),
            (_('Recommended'), 'lastfm://user/%s/recommended/100' %
                self.config.username),
            (_('Neighbourhood'), 'lastfm://user/%s/neighbours' %
                self.config.username),
            (_('Loved Tracks'), 'lastfm://user/%s/loved' % self.config.username),
        )

        items = []
        for name, url in stations:
            item = RadioItem(name, station=self)
            item.get_playlist = lambda url=url, name=name: \
                self._get_playlist(url, name)
            items.append(item)

        return items

    def _get_playlist(self, url, name):
        self.listenport = config.listenport
        tr = track.Track()
        tr.set_loc('http://localhost:%d/lastfm.mp3' % self.listenport)
        tr['album'] = "LastFM: %s" % name
        tr['title'] = "LastFM: %s" % name
        tr['artist'] = _("LastFM Radio")
        tr['lastfmstation'] = url
        
        pl = playlist.Playlist(name=_("LastFM: %s") % name)
        pl.add_tracks([tr])

        return pl

    def get_menu(self, parent):
        return menu
