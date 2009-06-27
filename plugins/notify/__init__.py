# Copyright (C) 2009 Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
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

import pynotify, cgi
import notifyprefs
import logging
import inspect
import notify_cover
from xlgui.prefs import widgets
from xl import event, common, settings
from xl.nls import gettext as _

logger = logging.getLogger(__name__)
UNKNOWN_TEXT = _("Unknown")

# This breaks stuff. if you want to enable it, set this to True and uncomment
# the commented section in the glade file
ATTACH_COVERS_OPTION_ALLOWED = False

pynotify.init('exailenotify')


class ExaileNotification(object):

    def __init__(self):
        self.notification_id = None
        self.exaile = None

    def __inner_preference(klass):
        """Function will make a property for a given subclass of PrefsItem"""
        def getter(self):
            return settings.get_option(klass.name, klass.default or None)

        def setter(self, val):
            settings.set_option(klass.name, val)

        return property(getter, setter)

    resize = __inner_preference(notifyprefs.ResizeCovers)
    body_artistalbum = __inner_preference(notifyprefs.BodyArtistAlbum)
    body_artist= __inner_preference(notifyprefs.BodyArtist)
    body_album = __inner_preference(notifyprefs.BodyAlbum)
    summary = __inner_preference(notifyprefs.Summary)
    attach_tray = __inner_preference(notifyprefs.AttachToTray)

    def on_play(self, type, player, track):
        '''Callback when we want to display a notification

        type and player arguments are ignored.

        '''
        title = " / ".join(track['title'] or "")
        artist = " / ".join(track['artist'] or "")
        album = " / ".join(track['album'] or "")
        if artist and album: 
            body_format = self.body_artistalbum
        elif artist:
            body_format = self.body_artist
        elif album:
            body_format = self.body_album
        else:
            body_format = ""
        # Get the replaced text. UNKNOWN_TEXT substituted here because we check
        # against the empty string above
        summary = self.summary % {'title': title or UNKNOWN_TEXT,
                                  'artist': artist or UNKNOWN_TEXT,
                                  'album': album or UNKNOWN_TEXT,
                                  }
        body = body_format % {'title': cgi.escape(title or UNKNOWN_TEXT),
                              'artist': cgi.escape(artist or UNKNOWN_TEXT),
                              'album': cgi.escape(album or UNKNOWN_TEXT),
                              }
        notif = pynotify.Notification(summary, body)
        notif.set_icon_from_pixbuf(notify_cover.get_image_for_track(track,
                                                 self.exaile,
                                                 self.resize,
                                                 ))
        # Attach to tray, if that's how we roll
        if ATTACH_COVERS_OPTION_ALLOWED:
            logger.debug("Attaching to tray")
            if self.attach_tray and hasattr(self.exaile, 'gui'):
                gui = self.exaile.gui
                if hasattr(gui, 'tray_icon') and gui.tray_icon:
                    notif.attach_to_status_icon(gui.tray_icon.icon)
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
    event.add_callback(EXAILE_NOTIFICATION.on_play, 'playback_track_start')

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFICATION.on_play, 'playback_track_start')

def get_prefs_pane():
    return notifyprefs
