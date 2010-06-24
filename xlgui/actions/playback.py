# Copyright (C) 2008-2010 Adam Olsen
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


from xlgui.actions import _base
from xlgui.widgets import menu, playlist

from xl import player

from xlgui import main


class PlayPauseAction(_base.BaseAction):
    def __init__(self, name):
        _base.BaseAction.__init__(self, name)

    def create_menu_item(self, after):
        return play_pause_menuitem(self.name, after, self.on_menu_activate)

    def create_button(self):
        b = PlayPauseButton()
        b.connect('activate', self.on_button_activate)
        return b

    def activate(self):
        if player.PLAYER.get_state() in ('playing', 'paused'):
            player.PLAYER.toggle_pause()
        else:
            m = main.mainwindow()
            page = m.get_selected_page()
            if isinstance(page, playlist.PlaylistPage):
                playlist = page.playlist
                player.QUEUE.set_current_playlist(playlist)
                try:
                    idx = page.view.get_selected_paths()[0]
                except IndexError:
                    idx = 0
                playlist.current_position = idx
                player.QUEUE.play()
        _base.Action.activate(self)


playpause = PlayPauseAction('playback-playpause')

# TODO: move these into widgets once actions stabilize

def play_pause_menuitem(name, after, callback):
    def factory(menu, parent_obj, parent_context):
        if player.PLAYER.is_playing():
            icon = gtk.STOCK_MEDIA_PAUSE
            display = _("Pause")
        else:
            icon = gtk.STOCK_MEDIA_PLAY
            display = _("Play")
        item = gtk.ImageMenuItem(display)
        image = gtk.image_new_from_icon_name(icon,
                size=gtk.ICON_SIZE_MENU)
        item.set_image(image)
        item.connect('activate', callback, name, parent_obj, parent_context)
        return item
    return menu.Menuitem(name, factory, after=after)

class PlayPauseButton(gtk.Button):
    def __init__(self):
        gtk.Button.__init__(self)
        self.setup_image()
        for ev in ['player_end', 'track_start', 'toggle_pause', 'error']:
            event.add_callback('playback_%s'%ev, self.setup_image)

    def setup_image(self, *args):
        if player.PLAYER.is_playing():
            icon = gtk.STOCK_MEDIA_PAUSE
        else:
            icon = gtk.STOCK_MEDIA_PLAY
        image = gtk.image_new_from_icon_name(icon,
                size=gtk.ICON_SIZE_BUTTON)
        self.set_image(image)

next = _base.Action('playback-next', _('Next'), 'gtk-media-next')
def on_next_activate(action):
    player.QUEUE.next()
next.connect('activate', on_next_activate)

prev = _base.Action('playback-prev', _('Previous'), 'gtk-media-prev')
def on_prev_activate(action):
    player.QUEUE.prev()
prev.connect('activate', on_prev_activate)

stop = _base.Action('playback-stop', _('Stop'), 'gtk-media-stop')
def on_stop_activate(action):
    player.PLAYER.stop()
stop.connect('activate', on_stop_activate)


