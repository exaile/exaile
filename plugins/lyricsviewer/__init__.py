# Copyright (C) 2009 Aren Olson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import gtk, gobject
from xl.nls import gettext as _
from xl import event, common
from xl.lyrics import LyricsNotFoundException

LYRICSPANEL = None

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global LYRICSPANEL
    LYRICSPANEL = LyricsPanel(exaile.lyrics)
    LYRICSPANEL.show_all()
    exaile.gui.add_panel(LYRICSPANEL, _('Lyrics'))

def disable(exaile):
    global LYRICSPANEL
    exaile.gui.remove_panel(LYRICSPANEL)
    LYRICSPANEL = None


class LyricsPanel(gtk.VBox):
    def __init__(self, lyrics):
        gtk.VBox.__init__(self)
        self.lyrics = lyrics

        self.scroller = gtk.ScrolledWindow()
        self.scroller.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.pack_start(self.scroller, True, True, 0)

        self.textview = gtk.TextView()
        self.textview.set_cursor_visible(False)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(gtk.WRAP_WORD)
        self.textview.set_justification(gtk.JUSTIFY_LEFT)
        self.textview.set_left_margin(4)
        self.scroller.add(self.textview)

        self.textbuffer = gtk.TextBuffer()
        self.textview.set_buffer(self.textbuffer)

        event.add_callback(self.playback_cb, 'playback_track_start')
        event.add_callback(self.playback_cb, 'playback_track_end')

    def playback_cb(self, eventtype, player, data):
        self.textbuffer.set_text("")
        if player.current:
            self.get_lyrics(player, player.current)

    @common.threaded
    def get_lyrics(self, player, track):
        try:
            lyr, source, url = self.lyrics.find_lyrics(track)
        except LyricsNotFoundException:
            return
        if player.current == track and lyr:
            gobject.idle_add(self.textbuffer.set_text, lyr)
