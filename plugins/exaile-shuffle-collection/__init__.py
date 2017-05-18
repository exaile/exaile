#!/usr/bin/python

# Copyright (C) 2012 Rainer Hihn ( rainer@hihn.org )
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

import logging
import xl
import xlgui
import xl.player.adapters

from xlgui import main

logger = logging.getLogger(__name__)
SHUFFLE = None

def enable(exaile):
    """Enables the Shuffle Collection plugin
    """
    global SHUFFLE
    SHUFFLE = Shuffle(exaile)
    if exaile.loading:
        xl.event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    '''
        Called when plugin is loaded.
    '''
    pass

def disable(exaile):
    '''
        Called when plugin is unloaded.  Remove Menu Item. Clean up.
    '''
    global SHUFFLE
    if SHUFFLE:
        SHUFFLE.stop()
        SHUFFLE = None

class Shuffle(xl.player.adapters.PlaybackAdapter):
    def __init__(self, exaile):
        self.exaile = exaile
        self.do_shuffle = False
        self.last_artists = []
        self.tracks = list()
        self.ban_repeat = 100 # ban an artist for x tracks
        self.build_menu()

    def build_menu(self):        
        menu = xlgui.widgets.menu.check_menu_item('shuffle', ['plugin-sep'], 'Shuffle',
            lambda *x: self.do_shuffle, lambda w, n, p, c: self.on_toggled(w))
        xl.providers.register('menubar-tools-menu', menu)
        xl.event.add_callback(self.on_playback_track_start, "playback_track_start", xl.player.PLAYER)

    def on_toggled(self, menuitem):
        '''
            Enables or disables the shuffle plugin.
        '''
        if menuitem.get_active():
            logger.debug('Shuffle activated.')
            self.do_shuffle = True
            self.play()
        else:
            logger.debug('Shuffle deactivated.')
            self.do_shuffle = False

    def remove_menu_item(self):
        '''
            Remove the Menu item.
        '''
        if self.menu_item:
            self.menu_item.hide()
            self.menu_item.destroy()
            self.menu_item = None

    def play(self):
        '''
            Calls find_track() and checks if it returns an artist
            that is redundant. Adds the track to the playlist and
            adds the artist to the last_artists.
            Also removes the first item from last_artists (if its full).
        '''
        if not self.do_shuffle:
            return
        fallback = 0
        while True:
            random_track = self.exaile.collection.get_random_track()
            if not self.is_redundant(random_track) or fallback == 50:
                break
            fallback += 1
        main.get_selected_playlist().playlist.append(random_track)
        if ( len(self.last_artists) >= self.ban_repeat ):
            self.last_artists.pop(0)
        self.last_artists.append(random_track.get_tag_display("artist"))

    def is_redundant(self, random_track):
        '''
            Return True if its redundant
            Checks if the Artist was already a shuffle-result
            the last x times. x can be set via self.ban_repeat (default: 20).
        '''
        if random_track == None:
            return False
        for artist in self.last_artists:
            if artist == random_track.get_tag_display("artist"):
                logger.debug("Banning %s for Redundancy", random_track.get_tag_display("artist"))
                return True
        return False

    def on_playback_track_start(self, event, player, track):
        '''
            Callback for when a track starts. The next track will be
            added when a track starts, not when a track fades out.
        '''
        if not self.do_shuffle:
            return
        self.play()

    def stop(self):
        self.remove_menu_item()

