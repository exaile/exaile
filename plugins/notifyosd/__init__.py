# Copyright (C) 2009-2010
#	Adam Olsen <arolsen@gmail.com>
#	Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
#	Steve Dodier <sidnioulzg@gmail.com>
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

import cgi
import glib
import gtk.gdk
import logging
import pynotify

from xl import (
    common,
    covers,
    event,
    player,
    settings
)
from xl.nls import gettext as _
from xlgui import icons

import notifyosdprefs

logger = logging.getLogger(__name__)
pynotify.init('Exaile')

class ExaileNotifyOsd(object):

    def __inner_preference(klass):
        """Function will make a property for a given subclass of Preference"""
        def getter(self):
            return settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            settings.set_option(klass.name, val)

        return property(getter, setter)

    show_covers     = __inner_preference(notifyosdprefs.ShowCovers)
    notify_play     = __inner_preference(notifyosdprefs.NotifyPlay)
    notify_pause    = __inner_preference(notifyosdprefs.NotifyPause)
    use_media_icons = __inner_preference(notifyosdprefs.UseMediaIcons)
    tray_hover      = __inner_preference(notifyosdprefs.TrayHover)
    format_summary  = __inner_preference(notifyosdprefs.Summary)
    format_artist   = __inner_preference(notifyosdprefs.BodyArtist)
    format_album    = __inner_preference(notifyosdprefs.BodyAlbum)
    notify_change   = __inner_preference(notifyosdprefs.NotifyChange)

    def __init__(self):
        self.notify         = pynotify.Notification('Exaile')
        self.exaile         = None
        self.cover          = None
        self.pauseicon      = 'notification-audio-pause'
        self.resumeicon     = 'notification-audio-play'
        self.stopicon       = 'notification-audio-stop'
        # TRANSLATORS: title of a track if it is unknown
        self.unknown        = _('Unknown')
        self.summary        = None
        self.body           = None
        self.gui_callback   = False
        self.tray_connection= -1
        event.add_callback(self.on_tray_toggled, 'tray_icon_toggled')

    @common.threaded
    def update_track_notify(self, type, player, track, media_icon = None):
        if not track or (track != player.current):
            return
        title = track.get_tag_display('title')
        artist = cgi.escape(
            track.get_tag_display('artist', artist_compilations=False)
        )
        album = cgi.escape(track.get_tag_display('album'))
        # Find the icon we will use
        icon_allowed = False
        if media_icon and self.use_media_icons:
            self.cover = media_icon
            icon_allowed = True
        else:
            if self.cover == self.stopicon and self.summary == title and \
                    self.use_media_icons and self.notify_pause:
                # this is for when the song has been stopped previously
                self.cover = self.resumeicon
                icon_allowed = True
            elif self.show_covers:
                cover_data = covers.MANAGER.get_cover(track, use_default=True)
                self.cover = icons.MANAGER.pixbuf_from_data(cover_data)
                icon_allowed = True

        # Setup the summary and body for the notification
        self.summary = self.format_summary % {'title': title or self.unknown}

        if artist and album:
            self.body = self.format_artist % {'artist' : artist} + '\n' + \
                    self.format_album % {'album' : album}
        elif artist:
            self.body = self.format_artist % {'artist' : artist}
        elif album:
            self.body = self.format_album % {'album' : album}
        else:
            self.body = ""

        if icon_allowed and self.cover:
            try:
                cover_data = covers.MANAGER.get_cover(track, use_default=True)
                pixbuf = icons.MANAGER.pixbuf_from_data(cover_data)
            except glib.GError:
                pass
            else:
                self.notify.set_icon_from_pixbuf(pixbuf)
        self.notify.update(self.summary, self.body)

        if track == player.current:
            if settings.get_option("plugin/notifyosd/show_when_focused", \
                    True) or not self.exaile.gui.main.window.is_active():
                self.notify.show()

    def on_pause(self, type, player, track):
        if self.notify_pause:
            self.update_track_notify(type, player, track, self.pauseicon)

    def on_stop(self, type, player, track):
        if self.notify_pause:
            self.update_track_notify(type, player, track, self.stopicon)

    def on_resume(self, type, player, track):
        if self.notify_pause:
            self.update_track_notify(type, player, track, self.resumeicon)
        elif self.notify_play:
            self.update_track_notify(type, player, track)

    def on_play(self, type, player, track):
        if self.notify_play:
            self.update_track_notify(type, player, track)

    def on_quit(self, type, exaile, data=None):
        self.notify.close()

    def on_changed(self, type, track, tag):
        if self.notify_change:
            self.update_track_notify(type, player.PLAYER, track)

    def on_tooltip(self, *e):
        if self.tray_hover:
            track = player.PLAYER.current
            if track:
                if self.cover == self.stopicon or self.cover == self.pauseicon:
                    if self.use_media_icons:
                        self.update_track_notify(type, player.PLAYER, track, self.cover)
                        return
                self.update_track_notify(type, player.PLAYER, track)
            elif self.notify_pause and self.cover == self.stopicon: # if there is no track, then status is stopped
                if self.use_media_icons and self.cover:
                    try:
                        pixbuf = icons.MANAGER.pixbuf_from_data(self.cover)
                    except glib.GError:
                        pass
                    else:
                        self.notify.set_icon_from_pixbuf(pixbuf)
                self.notify.update(self.summary, self.body)
                self.notify.show()

    def exaile_ready(self, type = None, data1 = None, data2 = None):
        if self.exaile.gui.tray_icon:
            self.tray_connection = self.exaile.gui.tray_icon.connect('query-tooltip', self.on_tooltip)

    def on_tray_toggled(self, type, object, data):
        if data and self.tray_connection == -1:
            glib.timeout_add_seconds(1, self.exaile_ready)
        elif not data and self.tray_connection != -1:
            self.tray_connection = -1

EXAILE_NOTIFYOSD = ExaileNotifyOsd()

def enable(exaile):
    EXAILE_NOTIFYOSD.exaile = exaile
    event.add_callback(EXAILE_NOTIFYOSD.on_play, 'playback_player_start', player.PLAYER)
    event.add_callback(EXAILE_NOTIFYOSD.on_pause, 'playback_player_pause', player.PLAYER)
    event.add_callback(EXAILE_NOTIFYOSD.on_stop, 'playback_player_end', player.PLAYER)
    event.add_callback(EXAILE_NOTIFYOSD.on_resume, 'playback_player_resume', player.PLAYER)
    event.add_callback(EXAILE_NOTIFYOSD.on_quit, 'quit_application')
    event.add_callback(EXAILE_NOTIFYOSD.on_changed, 'track_tags_changed')
    if hasattr(exaile, 'gui'):
        EXAILE_NOTIFYOSD.exaile_ready()
    else:
        event.add_callback(EXAILE_NOTIFYOSD.exaile_ready, 'gui_loaded')
        EXAILE_NOTIFYOSD.gui_callback = True

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFYOSD.on_play, 'playback_player_start', player.PLAYER)
    event.remove_callback(EXAILE_NOTIFYOSD.on_pause, 'playback_player_pause', player.PLAYER)
    event.remove_callback(EXAILE_NOTIFYOSD.on_stop, 'playback_player_end', player.PLAYER)
    event.remove_callback(EXAILE_NOTIFYOSD.on_resume, 'playback_player_resume', player.PLAYER)
    event.remove_callback(EXAILE_NOTIFYOSD.on_quit, 'quit_application')
    event.remove_callback(EXAILE_NOTIFYOSD.on_changed, 'track_tags_changed')
    if EXAILE_NOTIFYOSD.exaile.gui.tray_icon:
        EXAILE_NOTIFYOSD.exaile.gui.tray_icon.disconnect(EXAILE_NOTIFYOSD.tray_connection)
    if EXAILE_NOTIFYOSD.gui_callback:
        event.remove_callback(EXAILE_NOTIFYOSD.exaile_ready, 'gui_loaded')

def get_preferences_pane():
    return notifyosdprefs
