# Copyright (C) 2011  Mathias Brodala <info@noctus.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from gi.repository import Gtk, Pango, GdkPixbuf

import logging
import os.path
from threading import Thread, Timer

import pylast

from xl import common, event, player, providers, settings
from xl.nls import gettext as _
from xlgui import icons
from xlgui.widgets.menu import MenuItem
from xlgui.widgets.playlist_columns import Column, ColumnMenuItem

from . import lastfmlove_preferences
from .cellrenderertoggleimage import CellRendererToggleImage

LASTFMLOVER = None
logger = logging.getLogger(__name__)

basedir = os.path.dirname(os.path.realpath(__file__))
icons.MANAGER.add_icon_name_from_directory('love', os.path.join(basedir, 'icons'))
icons.MANAGER.add_icon_name_from_directory(
    'send-receive', os.path.join(basedir, 'icons')
)


class LastFMPlugin:
    def enable(self, exaile):
        """
        Handles the deferred enable call
        """
        self.__lastfmlover = LastFMLover()

    def disable(self, exaile):
        """
        Disables the desktop cover plugin
        """
        self.__lastfmlover.destroy()
        self.__lastfmlover = None

    def get_preferences_pane(self):
        return lastfmlove_preferences


plugin_class = LastFMPlugin


class LoveColumn(Column):
    name = 'loved'
    display = _('Loved')
    menu_title = _('Last.fm Loved')
    size = 50
    renderer = CellRendererToggleImage
    datatype = bool
    dataproperty = 'active'
    last_fm_lover = None

    def __init__(self, *args):
        Column.__init__(self, *args)

        self.model = None

        pixbuf = icons.MANAGER.pixbuf_from_icon_name('love')
        pixbuf = self._set_icon_size(pixbuf)

        self.cellrenderer.props.pixbuf = pixbuf
        self.cellrenderer.connect('toggled', self.on_toggled)

    def data_func(self, column, cellrenderer, model, iter, user_data):
        """
        Displays the loved state
        """
        track = model.get_value(iter, 0)
        lastfm_track = pylast.Track(
            track.get_tag_display('artist'),
            track.get_tag_display('title'),
            self.last_fm_lover.network,
        )
        cellrenderer.props.active = lastfm_track in self.last_fm_lover.loved_tracks

        if self.last_fm_lover.network is None:
            cellrenderer.props.sensitive = False
            cellrenderer.props.render_prelit = False
        else:
            cellrenderer.props.sensitive = True
            cellrenderer.props.render_prelit = True

        self.model = model

    def on_toggled(self, cellrenderer, path):
        """
        Loves or unloves the selected track
        """
        if cellrenderer.props.sensitive and self.last_fm_lover.network is not None:
            track = self.model.get_value(self.model.get_iter(path), 0)
            self.last_fm_lover.toggle_loved(track)

    def _set_icon_size(self, pixbuf):
        if pixbuf is None:
            return pixbuf

        font = settings.get_option('gui/playlist_font', None)
        if font is not None:
            # get default font
            default = float(Gtk.Widget.get_default_style().font_desc.get_size())
            new_font = Pango.FontDescription(font).get_size()

            # scale pixbuf accordingly
            t = GdkPixbuf.InterpType.BILINEAR
            s = max(int(pixbuf.get_width() * (new_font / default)), 1)
            pixbuf = pixbuf.scale_simple(s, s, t)

        return pixbuf

    def on_option_set(self, typ, obj, data):
        """
        Refresh playlist love icon size on playlist font option set
        """
        if data == "gui/playlist_font":
            self.cellrenderer.props.pixbuf = self._set_icon_size(
                self.cellrenderer.props.pixbuf
            )


class LoveMenuItem(MenuItem):
    """
    A menu item representing the loved state of a
    track and allowing for loving and unloving it
    """

    def __init__(self, last_fm_lover, after, get_tracks_function=None):
        MenuItem.__init__(self, 'loved', None, after)
        LoveColumn.last_fm_lover = last_fm_lover
        self.__lastfmlover = last_fm_lover
        self.get_tracks_function = get_tracks_function

    def factory(self, menu, parent, context):
        """
        Sets up the menu item
        """
        item = Gtk.ImageMenuItem.new_with_mnemonic(_('_Love This Track'))
        item.set_image(Gtk.Image.new_from_icon_name('love', Gtk.IconSize.MENU))

        if self.get_tracks_function is not None:
            tracks = self.get_tracks_function()
            empty = len(tracks) == 0
        else:
            empty = context.get('selection-empty', True)
            if not empty:
                tracks = context.get('selected-tracks', [])

        if not empty and self.__lastfmlover.network is not None:
            # We only care about the first track
            track = tracks[0]
            lastfm_track = pylast.Track(
                track.get_tag_display('artist'),
                track.get_tag_display('title'),
                self.__lastfmlover.network,
            )

            if lastfm_track in self.__lastfmlover.loved_tracks:
                item.set_label(_('Unlove This Track'))

            item.connect('activate', self.on_activate, track)
        else:
            item.set_sensitive(False)

        return item

    def on_activate(self, menuitem, track):
        """
        Loves or unloves the selected track
        """
        self.__lastfmlover.toggle_loved(track)


class LastFMLover:
    """
    Allows for retrieval and setting
    of loved tracks via Last.fm
    """

    def __init__(self):
        """
        Sets up the connection to Last.fm
        as well as the graphical interface
        """
        self.network = None
        self.user = None
        self.loved_tracks = []
        self.timer = None
        self.column_menu_item = ColumnMenuItem(column=LoveColumn, after=['__rating'])
        self.menu_item = LoveMenuItem(self, after=['rating'])

        def get_tracks_function():
            """
            Drop in replacement for menu item context
            to retrieve the currently playing track
            """
            current_track = player.PLAYER.current

            if current_track is not None:
                return [current_track]

            return []

        self.tray_menu_item = LoveMenuItem(
            self, after=['rating'], get_tracks_function=get_tracks_function
        )

        self.setup_network()

        providers.register('playlist-columns', LoveColumn)
        providers.register('playlist-columns-menu', self.column_menu_item)
        providers.register('playlist-context-menu', self.menu_item)
        providers.register('tray-icon-context', self.tray_menu_item)

        event.add_ui_callback(self.on_option_set, 'plugin_lastfmlove_option_set')

    def destroy(self):
        """
        Cleanups
        """
        event.remove_callback(self.on_option_set, 'plugin_lastfmlove_option_set')

        providers.unregister('tray-icon-context', self.tray_menu_item)
        providers.unregister('playlist-context-menu', self.menu_item)
        providers.unregister('playlist-columns-menu', self.column_menu_item)
        providers.unregister('playlist-columns', LoveColumn)

        if self.timer is not None and self.timer.is_alive():
            self.timer.cancel()

    def setup_network(self):
        """
        Tries to set up the network, retrieve the user
        and the initial list of loved tracks
        """
        try:
            self.network = pylast.LastFMNetwork(
                api_key=settings.get_option('plugin/lastfmlove/api_key', 'K'),
                api_secret=settings.get_option('plugin/lastfmlove/api_secret', 'S'),
                username=settings.get_option('plugin/ascrobbler/user', ''),
                password_hash=settings.get_option('plugin/ascrobbler/password', ''),
            )
            self.user = self.network.get_user(self.network.username)
        except Exception as e:
            self.network = None
            self.user = None

            if self.timer is not None and self.timer.is_alive():
                self.timer.cancel()

            logger.warning('Error while connecting to Last.fm network: {0}'.format(e))
        else:
            thread = Thread(target=self.get_loved_tracks)
            thread.daemon = True
            thread.start()

            logger.info('Connection to Last.fm network successful')

    def restart_timer(self):
        """
        Restarts the timer which starts the retrieval of tracks
        """
        if self.timer is not None and self.timer.is_alive():
            self.timer.cancel()

        self.timer = Timer(
            settings.get_option('plugin/lastfmlove/refresh_interval', 3600),
            self.get_loved_tracks,
        )
        self.timer.daemon = True
        self.timer.start()

    def get_loved_tracks(self):
        """
        Updates the list of loved tracks
        """
        logger.debug('Retrieving list of loved tracks...')

        try:
            tracks = self.user.get_loved_tracks(limit=None)
            # Unwrap pylast.Track from pylast.LovedTrack
            self.loved_tracks = [l.track for l in tracks]
        except Exception as e:
            logger.warning('Failed to retrieve list of loved tracks: {0}'.format(e))

        self.restart_timer()

    def toggle_loved(self, track):
        """
        Toggles the loved state of a track

        :param track: the track to love/unlove
        :type track: `xl.trax.Track`
        """
        lastfm_track = pylast.Track(
            track.get_tag_display('artist'),
            track.get_tag_display('title'),
            self.network,
        )

        if lastfm_track in self.loved_tracks:
            self.unlove_track(lastfm_track)
        else:
            self.love_track(lastfm_track)

    @common.threaded
    def love_track(self, track):
        """
        Loves a track

        :param track: the track to love
        :type track: `pylast.Track`
        """
        try:
            track.love()
        except Exception as e:
            logger.warning('Error while loving track {0}: {1}'.format(track, e))
        else:
            self.loved_tracks.append(track)
            logger.info('Loved track {0}'.format(track))

    @common.threaded
    def unlove_track(self, track):
        """
        Unloves a track

        :param track: the track to unlove
        :type track: `pylast.Track`
        """
        try:
            track.unlove()
        except Exception as e:
            logger.warning('Error while unloving track {0}: {1}'.format(track, e))
        else:
            self.loved_tracks.remove(track)
            logger.info('Unloved track {0}'.format(track))

    def on_option_set(self, event, settings, option):
        """
        Takes action upon setting changes
        """
        if option in ('plugin/lastfmlove/api_key', 'plugin/lastfmlove/api_secret'):
            self.setup_network()
        elif option == 'plugin/lastfmlove/refresh_interval':
            self.restart_timer()
