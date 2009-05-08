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
from xl import event, common
from xl.nls import gettext as _
from xl.settings import SettingsManager

logger = logging.getLogger(__name__)
settings = SettingsManager.settings
UNKNOWN_TEXT = _("Unknown")

pynotify.init('exailenotify')


class ExaileNotification(object):

    def __init__(self):
        self.notification = pynotify.Notification("Exaile")
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

    def on_play(self, type, player, track):
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
        summary = self.summary % {'title': title or UNKNOWN_TEXT,
                                  'artist': artist or UNKNOWN_TEXT,
                                  'album': album or UNKNOWN_TEXT,
                                  }
        body = body_format % {'title': cgi.escape(title or UNKNOWN_TEXT),
                              'artist': cgi.escape(artist or UNKNOWN_TEXT),
                              'album': cgi.escape(album or UNKNOWN_TEXT),
                              }
        self.notification.update(summary, body)
        self.notification.set_icon_from_pixbuf(
                notify_cover.get_image_for_track(track,
                                                 self.exaile,
                                                 self.resize,
                                                 ))
        self.notification.show()

EXAILE_NOTIFICATION = ExaileNotification()

def enable(exaile):
    EXAILE_NOTIFICATION.exaile = exaile
    event.add_callback(EXAILE_NOTIFICATION.on_play, 'playback_start')

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFICATION.on_play, 'playback_start')

def get_prefs_pane():
    return notifyprefs
