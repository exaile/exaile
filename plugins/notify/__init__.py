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
from xlgui.prefs import widgets
from xl import event, common
from xl.nls import gettext as _
from xl.settings import SettingsManager

logger = logging.getLogger(__name__)
settings = SettingsManager.settings

pynotify.init('exailenotify')

PREFERENCES = [getattr(notifyprefs, klass) for klass in dir(notifyprefs)
                if inspect.isclass(getattr(notifyprefs, klass))
                and issubclass(getattr(notifyprefs, klass), widgets.PrefsItem)]

logger.critical(PREFERENCES)

class ExaileNotification(object):

    def __init__(self):
        self.notification = pynotify.Notification("Exaile")
        self.exaile = None
        self.__initialize_settings()
        event.add_callback(self.get_options, 'option_set')

    def __get_resize(self):
        '''Returns if we should resize covers before outputting them'''
        return settings.get_option(notifyprefs.ResizeCovers.name,
                                notifyprefs.ResizeCovers.default or None)

    def __set_resize(self, val):
        settings.set_option(notifyprefs.ResizeCovers.name, val)

    resize = property(__get_resize, __set_resize)

    def __initialize_settings(self):
        '''Initialize the settings if they aren't already'''
        for p in PREFERENCES:
            if hasattr(p, 'default'):
                if settings.get_option(p.name) is None:
                    settings.set_option(p.name, p.default)
        logger.critical(self.resize)


    def on_play(self, type, player, track):
        title = " / ".join(track['title'] or _("Unknown"))
        artist = " / ".join(track['artist'] or "")
        album = " / ".join(track['album'] or "")
        summary = title
        if artist and album:
            body = _("by %(artist)s\nfrom <i>%(album)s</i>") % {
                'artist' : cgi.escape(artist), 
                'album' : cgi.escape(album)}
        elif artist:
            body = _("by %(artist)s") % {'artist' : cgi.escape(artist)}
        elif album:
            body = _("from %(album)s") % {'album' : cgi.escape(album)}
        else:
            body = ""
        self.notification.update(summary, body)
        item = track.get_album_tuple()
        image = None
        if all(item) and hasattr(self.exaile, 'covers'):
            image = self.exaile.covers.coverdb.get_cover(*item)
        if image is None:
            image = 'exaile'
        self.notification.set_property('icon-name', image)
        self.notification.show()

    def get_options(self, type, sm, option):
        """Callback for when a setting is set in exaile"""
        if option in (p.name for p in PREFERENCES):
            logger.critical("wtf? %s %s %s" % (type, sm, option))

EXAILE_NOTIFICATION = ExaileNotification()

def enable(exaile):
    EXAILE_NOTIFICATION.exaile = exaile
    event.add_callback(EXAILE_NOTIFICATION.on_play, 'playback_start')

def disable(exaile):
    event.remove_callback(EXAILE_NOTIFICATION.on_play, 'playback_start')

def get_prefs_pane():
    return notifyprefs
