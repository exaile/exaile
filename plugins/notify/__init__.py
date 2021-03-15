# Copyright (C) 2009-2010
#     Adam Olsen <arolsen@gmail.com>
#     Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
#     Steve Dodier <sidnioulzg@gmail.com>
# Copyright (C) 2017 Christian Stadelmann
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

import html
import logging

import gi
from gi.repository import Gtk, GLib

from xl.player.adapters import PlaybackAdapter
from xl import covers, common
from xl import event as xl_event
from xl import player as xl_player
from xl import settings as xl_settings
from xl.nls import gettext as _
from xlgui import icons
from xlgui.guiutil import pixbuf_from_data

from . import notifyprefs


# For documentation on libnotify see also the "Desktop Notifications Specification":
# https://developer.gnome.org/notification-spec/
gi.require_version('Notify', '0.7')
from gi.repository import Notify


LOGGER = logging.getLogger(__name__)
DEFAULT_ICON_SIZE = (48, 48)

BODY_ARTIST_ALBUM = _('from {album} by {artist}')
BODY_ARTIST = _('by {artist}')
BODY_ALBUM = _('by {album}')


class NotifierSettings:
    @staticmethod
    def __inner_preference(klass):
        """Function will make a property for a given subclass of Preference"""

        def getter(self):
            return xl_settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            xl_settings.set_option(klass.name, val)

        # Migration:
        if hasattr(klass, 'pre_migration_name'):
            if xl_settings.get_option(klass.name, None) is None:
                old_value = xl_settings.get_option(
                    klass.pre_migration_name, klass.default or None
                )
                if old_value is not None:
                    xl_settings.set_option(klass.name, old_value)
                    xl_settings.MANAGER.remove_option(klass.name)

        return property(getter, setter)

    notify_pause = __inner_preference(notifyprefs.NotifyPause)
    resize_covers = __inner_preference(notifyprefs.ResizeCovers)
    show_covers = __inner_preference(notifyprefs.ShowCovers)
    show_when_focused = __inner_preference(notifyprefs.ShowWhenFocused)
    tray_hover = __inner_preference(notifyprefs.TrayHover)
    use_media_icons = __inner_preference(notifyprefs.UseMediaIcons)


class Notifier(PlaybackAdapter):

    settings = NotifierSettings()

    def __init__(self, exaile, caps):
        self.__exaile = exaile
        self.__old_icon = None
        self.__tray_connection = None

        notification = Notify.Notification.new("", None, None)

        if 'sound' in caps:
            notification.set_hint('suppress-sound', GLib.Variant.new_boolean(True))
        self.settings.can_show_markup = 'body-markup' in caps

        notification.set_urgency(Notify.Urgency.LOW)
        notification.set_timeout(Notify.EXPIRES_DEFAULT)

        # default action is invoked on clicking the notification
        notification.add_action(
            "default", "this should never be displayed", self.__on_default_action
        )

        self.notification = notification
        PlaybackAdapter.__init__(self, xl_player.PLAYER)

        xl_event.add_callback(self.on_option_set, 'plugin_notify_option_set')
        xl_event.add_callback(self.on_option_set, 'gui_option_set')
        # initial setup through options:
        self.on_option_set(None, xl_settings, notifyprefs.TrayHover.name)
        self.on_option_set(None, xl_settings, notifyprefs.ShowCovers.name)

    def __on_default_action(self, _notification, _action):
        self.__exaile.gui.main.window.present()

    def on_playback_player_end(self, _event, player, track):
        if self.settings.notify_pause:
            self.update_track_notify(player, track, 'media-playback-stop')

    def on_playback_track_start(self, _event, player, track):
        self.update_track_notify(player, track)

    def on_playback_toggle_pause(self, _event, player, track):
        if self.settings.notify_pause:
            if player.is_paused():
                self.update_track_notify(player, track, 'media-playback-pause')
            else:
                self.update_track_notify(player, track, 'media-playback-start')

    def on_playback_error(self, _event, _player, message):
        self.__maybe_show_notification("Playback error", message, 'dialog-error')

    def __on_query_tooltip(self, *_args):
        if self.settings.tray_hover:
            self.__maybe_show_notification(force_show=True)

    @common.idle_add()
    def __try_connect_tray(self):
        tray_icon = self.__exaile.gui.tray_icon
        if tray_icon:
            self.__tray_connection = tray_icon.connect(
                'query-tooltip', self.__on_query_tooltip
            )
        else:
            LOGGER.warning("Tried to connect to non-existing tray icon")

    def __set_tray_hover_state(self, state):
        # Interacting with the tray might break if our option handler is being
        # invoked when exaile.gui.tray_icon == None. This might happen because
        # it is not defined which 'option_set' handler is being invoked first.
        tray_icon = self.__exaile.gui.tray_icon
        if state and not self.__tray_connection:
            if tray_icon:
                self.__tray_connection = tray_icon.connect(
                    'query-tooltip', self.__on_query_tooltip
                )
            else:
                self.__try_connect_tray()
        elif not state and self.__tray_connection:
            if tray_icon:  # xlgui.main might already have destroyed the tray icon
                self.__exaile.gui.tray_icon.disconnect(self.__tray_connection)
            self.__tray_connection = None

    def on_option_set(self, _event, settings, option):
        if option == notifyprefs.TrayHover.name or option == 'gui/use_tray':
            has_tray = settings.get_option('gui/use_tray')
            shall_show_tray_hover = self.settings.tray_hover and has_tray
            self.__set_tray_hover_state(shall_show_tray_hover)
        elif option == notifyprefs.ShowCovers.name:
            # delete current cover if user doesn't want to see more covers
            if not self.settings.show_covers:
                if self.settings.resize_covers:
                    size = DEFAULT_ICON_SIZE[1]
                else:
                    size = Gtk.IconSize.DIALOG
                new_icon = icons.MANAGER.pixbuf_from_icon_name('exaile', size)
                self.notification.set_image_from_pixbuf(new_icon)

    def __maybe_show_notification(
        self, summary=None, body='', icon_name=None, force_show=False
    ):
        # If summary is none, don't update the Notification
        if summary is not None:
            try:
                self.notification.update(summary, body, icon_name)
            except GLib.Error:
                LOGGER.exception("Could not set new notification status.")
                return
        # decide whether to show the notification or not
        if (
            self.settings.show_when_focused
            or not self.__exaile.gui.main.window.is_active()
            or force_show
        ):
            try:
                self.notification.show()
            except GLib.Error:
                LOGGER.exception("Could not set new notification status.")
                self.__exaile.plugins.disable_plugin(__name__)

    def __get_body_str(self, track):
        artist_str = html.escape(
            track.get_tag_display('artist', artist_compilations=False)
        )
        album_str = html.escape(track.get_tag_display('album'))

        if self.settings.can_show_markup:
            if artist_str:
                artist_str = '<i>%s</i>' % artist_str
            if album_str:
                album_str = '<i>%s</i>' % album_str

        if artist_str and album_str:
            body = BODY_ARTIST_ALBUM.format(artist=artist_str, album=album_str)
        elif artist_str:
            body = BODY_ARTIST.format(artist=artist_str)
        elif album_str:
            body = BODY_ALBUM.format(album=album_str)
        else:
            body = ""
        return body

    def __get_icon(self, track, media_icon):
        # TODO: icons are too small, even with settings.resize_covers=False
        icon_name = None
        if media_icon and self.settings.use_media_icons:
            icon_name = media_icon
        elif self.settings.show_covers:
            cover_data = covers.MANAGER.get_cover(
                track, set_only=True, use_default=True
            )
            size = DEFAULT_ICON_SIZE if self.settings.resize_covers else None
            new_icon = pixbuf_from_data(cover_data, size)
            self.notification.set_image_from_pixbuf(new_icon)
        return icon_name

    def update_track_notify(self, _player, track, media_icon=None):
        # TODO: notification.add_action(): previous, play/pause, next ?
        title = html.escape(track.get_tag_display('title'))

        summary = title
        body = self.__get_body_str(track)
        icon_name = self.__get_icon(track, media_icon)

        # If icon_name is None, the previous icon will not be replaced
        self.__maybe_show_notification(summary, body, icon_name)

    def destroy(self):
        PlaybackAdapter.destroy(self)
        self.__set_tray_hover_state(False)
        notification = self.notification
        # must be called on separate thread, since it is a synchronous call and might block
        self.__close_notification(notification)
        self.notification.clear_actions()
        self.notification = None
        self.__exaile = None

    @staticmethod
    @common.threaded
    def __close_notification(notification):
        try:
            notification.close()
        except GLib.Error:
            LOGGER.exception("Failed to close notification")


class NotifyPlugin:
    def __init__(self):
        self.__notifier = None
        self.__exaile = None

    def enable(self, exaile):
        self.__exaile = exaile
        self.__init_notify()

    @common.threaded
    def __init_notify(self):
        can_continue = True
        caps = None
        if not Notify.is_initted():
            can_continue = Notify.init('Exaile')
        if not can_continue:
            LOGGER.error("Notify.init() returned false.")

        if can_continue:
            # This is the first synchronous call to the Notify server.
            # This call might fail if no server is present or it is broken.
            # Test it on window manager sessions (e.g. Weston) without
            # libnotify support, not on a Desktop Environment (such as
            # GNOME, KDE) to reproduce.
            available, name, vendor, version, spec_version = Notify.get_server_info()
            if available:
                LOGGER.info(
                    "Connected with notify server %s (version %s) by %s",
                    name,
                    version,
                    vendor,
                )
                LOGGER.info("Supported spec version: %s", spec_version)
                # This is another synchronous, blocking call:
                caps = Notify.get_server_caps()
                # Example from Fedora 26 Linux with GNOME on Wayland:
                # ['actions', 'body', 'body-markup', 'icon-static', 'persistence', 'sound']
                LOGGER.debug("Notify server caps: %s", caps)
                if not caps or not isinstance(caps, list):
                    can_continue = False
            else:
                LOGGER.error(
                    "Failed to retrieve capabilities from notify server. "
                    "This may happen if the desktop environment does not support "
                    "the org.freedesktop.Notifications DBus interface."
                )
                can_continue = False
        self.__handle_init(can_continue, caps)

    # Must be run on main thread because we need to make sure that the plugin
    # is not being disabled while this function runs. Otherwise, race
    # conditions might trigger obscure bugs.
    @common.idle_add()
    def __handle_init(self, can_continue, caps):
        exaile = self.__exaile
        if exaile is None:  # Plugin has been disabled in the mean time
            return

        if can_continue:  # check again, might have changed
            if exaile.loading:
                xl_event.add_ui_callback(self.__init_notifier, 'gui_loaded', None, caps)
            else:
                self.__init_notifier(caps)
        else:
            LOGGER.warning("Disabling NotifyPlugin.")
            exaile.plugins.disable_plugin(__name__)
            if not exaile.loading:
                # TODO: send error to GUI
                pass

    def __init_notifier(self, caps):
        self.__notifier = Notifier(self.__exaile, caps)
        return GLib.SOURCE_REMOVE

    def disable(self, exaile):
        self.teardown(exaile)

        self.__exaile = None

    def teardown(self, exaile):
        if self.__notifier:
            self.__notifier.destroy()
            self.__notifier = None

    def get_preferences_pane(self):
        return notifyprefs


plugin_class = NotifyPlugin
