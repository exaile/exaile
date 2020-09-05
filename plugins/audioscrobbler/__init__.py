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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from gi.repository import GLib
from gi.repository import Gtk

from . import _scrobbler as scrobbler
from . import asprefs
from xl import common, event, xdg, player, settings, providers
from xl.nls import gettext as _
from xlgui.accelerators import Accelerator
from xlgui.widgets import menu
import logging
import time
import pickle
import os

logger = logging.getLogger(__name__)

SCROBBLER = None


def enable(exaile):
    """
    Enables the AudioScrobbler plugin
    """
    global SCROBBLER

    SCROBBLER = ExaileScrobbler(exaile)

    if exaile.loading:
        event.add_callback(__enb, 'gui_loaded')
    else:
        __enb(None, exaile, None)


def __enb(eventname, exaile, nothing):
    GLib.idle_add(_enable, exaile)


def _enable(exaile):
    #    SCROBBLER.exaile_menu = exaile.gui.builder.get_object('tools_menu')
    SCROBBLER.get_options('', '', 'plugin/ascrobbler/menu_check')


def disable(exaile):
    """
    Disables the AudioScrobbler plugin
    """
    global SCROBBLER

    if SCROBBLER:
        SCROBBLER.stop()
        SCROBBLER = None


def get_preferences_pane():
    return asprefs


class ExaileScrobbler:
    def __init__(self, exaile):
        """
        Connects events to the player object, loads settings and cache
        """
        scrobbler.set_user_agent(exaile.get_user_agent_string('audioscrobbler'))
        self.connected = False
        self.connecting = False
        self.use_menu = False
        self.exaile = exaile
        self.cachefile = os.path.join(xdg.get_data_dirs()[0], "audioscrobbler.cache")
        self.get_options('', '', 'plugin/ascrobbler/cache_size')
        self.get_options('', '', 'plugin/ascrobbler/user')
        self.load_cache()
        event.add_ui_callback(self.get_options, 'plugin_ascrobbler_option_set')
        event.add_callback(self._save_cache_cb, 'quit_application')

        # enable accelerator
        def toggle_submit(*x):
            logger.debug('Toggling AudioScrobbler submissions.')
            settings.set_option('plugin/ascrobbler/submit', not self.submit)

        self.accelerator = Accelerator(
            '<Primary>b', _('Toggle AudioScrobbler submit'), toggle_submit
        )
        providers.register('mainwindow-accelerators', self.accelerator)

    def get_options(self, type, sm, option):
        if option == 'plugin/ascrobbler/cache_size':
            self.set_cache_size(
                settings.get_option('plugin/ascrobbler/cache_size', 100), False
            )
            return

        if option in [
            'plugin/ascrobbler/user',
            'plugin/ascrobbler/password',
            'plugin/ascrobbler/submit',
            'plugin/ascrobbler/scrobble_remote',
        ]:
            username = settings.get_option('plugin/ascrobbler/user', '')
            password = settings.get_option('plugin/ascrobbler/password', '')
            server = settings.get_option(
                'plugin/ascrobbler/url', 'http://post.audioscrobbler.com/'
            )
            self.scrobble_remote = settings.get_option(
                'plugin/ascrobbler/scrobble_remote', False
            )
            self.submit = settings.get_option('plugin/ascrobbler/submit', True)

            if (not self.connecting and not self.connected) and self.submit:
                if username and password:
                    self.connecting = True
                    self.initialize(username, password, server)

        if option == 'plugin/ascrobbler/menu_check':
            self.use_menu = settings.get_option('plugin/ascrobbler/menu_check', False)
            if self.use_menu:
                self.setup_menu()
            else:
                self.remove_menu()

    def setup_menu(self):
        self.menu_agr = self.exaile.gui.main.accel_group

        providers.register(
            'menubar-tools-menu',
            menu.simple_separator('plugin-sep', ['track-properties']),
        )

        def factory(menu_, parent, context):
            item = Gtk.CheckMenuItem.new_with_label(_('Enable audioscrobbling'))
            item.set_active(self.submit)
            key, mods = Gtk.accelerator_parse('<Primary>B')
            item.add_accelerator(
                'activate', menu.FAKEACCELGROUP, key, mods, Gtk.AccelFlags.VISIBLE
            )
            item.connect('toggled', self._menu_entry_toggled)
            return item

        item = menu.MenuItem('scrobbler', factory, ['plugin-sep'])
        providers.register('menubar-tools-menu', item)

    def remove_menu(self):
        #        self.menu_entry.disconnect(self.menu_conn)

        for item in providers.get('menubar-tools-menu'):
            if item.name == 'scrobbler':
                providers.unregister('menubar-tools-menu', item)
                break

    def _menu_entry_toggled(self, widget):
        settings.set_option('plugin/ascrobbler/submit', widget.get_active())

    def stop(self):
        """
        Stops submitting
        """
        logger.info("Stopping AudioScrobbler submissions")
        if self.use_menu:
            self.remove_menu()
        if self.connected:
            event.remove_callback(self.on_play, 'playback_track_start', player.PLAYER)
            event.remove_callback(self.on_stop, 'playback_track_end', player.PLAYER)
            self.connected = False
            self.save_cache()
        providers.unregister('mainwindow-accelerators', self.accelerator)

    @common.threaded
    def initialize(self, username, password, server):
        try:
            logger.info("Attempting to connect to AudioScrobbler (%s)", server)
            scrobbler.login(username, password, hashpw=False, post_url=server)
        except Exception:

            try:
                scrobbler.login(username, password, hashpw=True, post_url=server)
            except Exception:
                self.connecting = False
                logger.exception("Error logging in")
                return

        logger.info("Connected to AudioScrobbler")

        event.add_callback(self.on_play, 'playback_track_start', player.PLAYER)
        event.add_callback(self.on_stop, 'playback_track_end', player.PLAYER)
        self.connected = True
        self.connecting = False

    @common.threaded
    def now_playing(self, player, track):
        # wait 5 seconds before now playing to allow for skipping
        time.sleep(5)
        if player.current != track:
            return

        logger.info(
            "Attempting to submit \"Now Playing\" information to AudioScrobbler..."
        )
        try:
            scrobbler.now_playing(
                track.get_tag_raw('artist', join=True),
                track.get_tag_raw('title', join=True),
                track.get_tag_raw('album', join=True),
                int(track.get_tag_raw('__length')),
                track.split_numerical(track.get_tag_raw('tracknumber'))[0] or 0,
            )
        except Exception as e:
            logger.warning("Error submitting \"Now Playing\": %s", e)

    def on_play(self, type, player, track):
        if self.submit:
            track.set_tags(
                __audioscrobbler_playtime=track.get_tag_raw('__playtime'),
                __audioscrobbler_starttime=time.time(),
            )

            if track.is_local() or self.scrobble_remote:
                self.now_playing(player, track)

    def on_stop(self, type, player, track):
        if (
            not track
            or (not track.is_local() and not self.scrobble_remote)
            or track.get_tag_raw('__playtime') is None
        ):
            return
        playtime = (track.get_tag_raw('__playtime') or 0) - (
            track.get_tag_raw('__audioscrobbler_playtime') or 0
        )
        if playtime > 240 or playtime > float(track.get_tag_raw('__length')) / 2.0:
            if self.submit and track.get_tag_raw('__length') > 30:
                self.submit_to_scrobbler(
                    track, track.get_tag_raw('__audioscrobbler_starttime'), playtime
                )

        track.set_tags(__audioscrobbler_starttime=None, __audioscrobbler_playtime=None)

    def set_cache_size(self, size, save=True):
        scrobbler.MAX_CACHE = size
        if save:
            settings.set_option("plugin/ascrobbler/cache_size", size)

    def _save_cache_cb(self, a, b, c):
        self.save_cache()

    def save_cache(self):
        cache = scrobbler.SUBMIT_CACHE
        f = open(self.cachefile, 'wb')
        pickle.dump(cache, f)
        f.close()

    def load_cache(self):
        try:
            f = open(self.cachefile, 'rb')
            cache = pickle.load(f)
            f.close()
            scrobbler.SUBMIT_CACHE = cache
        except Exception:
            pass

    @common.threaded
    def submit_to_scrobbler(self, track, time_started, time_played):
        if scrobbler.SESSION_ID and track and time_started and time_played:
            try:
                scrobbler.submit(
                    track.get_tag_raw('artist', join=True),
                    track.get_tag_raw('title', join=True),
                    int(time_started),
                    'P',
                    '',
                    int(track.get_tag_raw('__length')),
                    track.get_tag_raw('album', join=True),
                    track.split_numerical(track.get_tag_raw('tracknumber'))[0] or 0,
                    autoflush=True,
                )
            except Exception:
                logger.exception("AS: Failed to submit track")
