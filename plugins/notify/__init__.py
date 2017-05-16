# Copyright (C) 2009-2010 Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
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

import gi
import cgi
import inspect
import logging

from gi.repository import Gtk

gi.require_version('Notify', '0.7')
from gi.repository import Notify

from xl import covers, event, common, player, settings
from xl.nls import gettext as _
from xlgui import icons
from xlgui.preferences import widgets

import notifyprefs

logger = logging.getLogger(__name__)

# This breaks stuff. if you want to enable it, set this to True and uncomment
# the commented section in the UI designer file
ATTACH_COVERS_OPTION_ALLOWED = False

Notify.init('exailenotify')


class ExaileNotification(object):

    def __init__(self):
        self.notification_id = None
        self.exaile = None

    def __inner_preference(klass):
        """Function will make a property for a given subclass of Preference"""

        def getter(self):
            return settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            settings.set_option(klass.name, val)

        return property(getter, setter)

    resize = __inner_preference(notifyprefs.ResizeCovers)
    body_artistalbum = __inner_preference(notifyprefs.BodyArtistAlbum)
    body_artist = __inner_preference(notifyprefs.BodyArtist)
    body_album = __inner_preference(notifyprefs.BodyAlbum)
    summary = __inner_preference(notifyprefs.Summary)
    attach_tray = __inner_preference(notifyprefs.AttachToTray)

    @common.threaded
    def on_play(self, type, player, track):
        '''Callback when we want to display a notification

        type and player arguments are ignored.

        '''
        title = track.get_tag_display('title')
        artist = cgi.escape(
            track.get_tag_display('artist', artist_compilations=False)
        )
        album = cgi.escape(track.get_tag_display('album'))

        if artist and album:
            body_format = self.body_artistalbum
        elif artist:
            body_format = self.body_artist
        elif album:
            body_format = self.body_album
        else:
            body_format = ""

        summary = self.summary % {'title': title,
                                  'artist': artist,
                                  'album': album
                                  }
        body = body_format % {'title': title,
                              'artist': artist,
                              'album': album
                              }

        notif = Notify.Notification.new(summary, body)
        cover_data = covers.MANAGER.get_cover(track,
                                              set_only=True, use_default=True)
        size = (48, 48) if self.resize else None
        pixbuf = icons.MANAGER.pixbuf_from_data(cover_data, size)
        notif.set_icon_from_pixbuf(pixbuf)
        # Attach to tray, if that's how we roll
        if ATTACH_COVERS_OPTION_ALLOWED:
            logger.debug("Attaching to tray")
            if self.attach_tray and hasattr(self.exaile, 'gui'):
                gui = self.exaile.gui
                if hasattr(gui, 'tray_icon') and gui.tray_icon:
                    if isinstance(gui.tray_icon, type(Gtk.StatusIcon)):
                        notif.attach_to_status_icon(gui.tray_icon)
                    else:
                        notif.attach_to_widget(gui.tray_icon)
        # replace the last notification
        logger.debug("Setting id")
        if self.notification_id is not None:
            notif.props.id = self.notification_id
        logger.debug("Showing notification")
        notif.show()
        logger.debug("Storing id")
        self.notification_id = notif.props.id
        logger.debug("Notification done")

EXAILE_NOTIFICATION = ExaileNotification()


def enable(exaile):
    EXAILE_NOTIFICATION.exaile = exaile
    event.add_callback(EXAILE_NOTIFICATION.on_play, 'playback_track_start', player.PLAYER)


def disable(exaile):
    event.remove_callback(EXAILE_NOTIFICATION.on_play, 'playback_track_start', player.PLAYER)


def get_preferences_pane():
    return notifyprefs
