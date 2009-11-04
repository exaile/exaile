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

import urlparse
import urllib
import logging

import dbus
import gtk

import xl.cover
import xl.event

log = logging.getLogger(__name__)

MENU_ITEMS = {
        'play': {
            'stock': gtk.STOCK_MEDIA_PLAY,
            'title': 'Play'
            },

        'stop': {
            'stock': gtk.STOCK_MEDIA_STOP,
            'title': 'Stop'
            },

        'prev': {
            'stock': gtk.STOCK_MEDIA_PREVIOUS,
            'title': 'Previous'
            },

        'fwd': {
            'stock': gtk.STOCK_MEDIA_FORWARD,
            'title': 'Forward'
            },
        }

            


class ExaileAwn(object):

    def __init__(self):
        bus = dbus.SessionBus()
        obj = bus.get_object("com.google.code.Awn", "/com/google/code/Awn")
        self.awn = dbus.Interface(obj, "com.google.code.Awn")
        self.exaile = None
        self.menu_items = {}
        self.add_menu_items()
        self.enabled = True

    def xid(self):
        if self.exaile is None:
            return None
        return self.exaile.gui.main.window.get_window().xid

    def unset_cover(self):
        self.awn.UnsetTaskIconByXid(self.xid())

    def cleanup(self):
        self.unset_cover()

    def set_cover(self, *args, **kwargs):
        if self.exaile is None:
            return
        elif not hasattr(self.exaile, 'player'):
            log.debug("Player not loaded, ignoring set_cover call")
            return
        elif self.exaile.player.current is None:
            log.debug("Player stopped, removing AWN cover")
            self.unset_cover()
        else:
            try:
                cover_full_url = self.exaile.covers.get_cover(
                        self.exaile.player.current)
            except xl.cover.NoCoverFoundException:
                log.debug("No cover for current track, unsetting awn cover")
                self.unset_cover()
                return
            cover_full_url = urlparse.urlparse(cover_full_url)
            path = urllib.url2pathname(cover_full_url[2])
            log.debug("Setting AWN cover to %s" % repr(path))
            self.awn.SetTaskIconByXid(self.xid(), path)

    def add_menu_items(self, *args, **kwargs):
        if self.exaile is None or self.exaile.gui is None:
            return False
        title = self.exaile.gui.main.window.get_title()
        for key, val in MENU_ITEMS.iteritems():
            if key not in self.menu_items:
                id = self.awn.AddTaskMenuItemByName(
                        title,
                        val['stock'],
                        val['title'])
                self.menu_items[key] = id


EXAILE_AWN = None

TRACK_CHANGE_CALLBACKS = (
        'playback_current_changed',
        'playback_player_start',
        'playback_track_end',
        'player_loaded',
        )

def enable(exaile):
    global EXAILE_AWN
    if EXAILE_AWN is None:
        EXAILE_AWN = ExaileAwn()
    EXAILE_AWN.exaile = exaile
    for signal in TRACK_CHANGE_CALLBACKS:
        xl.event.add_callback(EXAILE_AWN.set_cover, signal)
    xl.event.add_callback(EXAILE_AWN.add_menu_items, 'gui_loaded')
    EXAILE_AWN.set_cover()

def disable(exaile):
    global EXAILE_AWN
    for signal in TRACK_CHANGE_CALLBACKS:
        xl.event.remove_callback(EXAILE_AWN.set_cover, signal)
    EXAILE_AWN.unset_cover()
    EXAILE_AWN.exaile = None
