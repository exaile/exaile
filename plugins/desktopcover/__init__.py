# desktopcover - displays Exaile album covers on the desktop
# Copyright (C) 2006-2010  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import gobject
import gtk

from xl import (
    common,
    covers,
    event,
    main,
    settings
)
from xl.nls import gettext as _
from xlgui import (
    guiutil,
    icons
)

import prefs

DESKTOPCOVER = None

def enable(exaile):
    """
        Enables the mini mode plugin
    """
    global DESKTOPCOVER
    DESKTOPCOVER = DesktopCover()

def disable(exaile):
    """
        Disables the mini mode plugin
    """
    global DESKTOPCOVER
    del DESKTOPCOVER

def get_preferences_pane():
    return prefs

class DesktopCover(gtk.Window):
    gravity_map = {
        'topleft': gtk.gdk.GRAVITY_NORTH_WEST,
        'topright': gtk.gdk.GRAVITY_NORTH_EAST,
        'bottomleft': gtk.gdk.GRAVITY_SOUTH_WEST,
        'bottomright': gtk.gdk.GRAVITY_SOUTH_EAST
    }

    def __init__(self):
        gtk.Window.__init__(self)

        self.image = gtk.Image()
        self.add(self.image)
        self.image.show()

        self.set_accept_focus(False)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_role("desktopcover")
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_title("Exaile desktop cover")
        self._fade_in_id = None
        self._fade_out_id = None
        self._cross_fade_id = None
        self._cross_fade_step = 0

        event.add_callback(self.on_playback_player_start, 'playback_player_start')
        event.add_callback(self.on_playback_track_start, 'playback_track_start')
        event.add_callback(self.on_playback_player_end, 'playback_player_end')
        event.add_callback(self.on_option_set, 'option_set')

        try:
            exaile = main.exaile()
        except AttributeError:
            event.add_callback(self.on_exaile_loaded, 'exaile_loaded')
        else:
            self.on_exaile_loaded('exaile_loaded', exaile, None)

    def set_cover_from_track(self, track):
        """
            Updates the cover image and triggers cross-fading
        """
        cover_data = covers.MANAGER.get_cover(track)

        if cover_data is None:
            self.hide()
            return

        size = settings.get_option('plugin/desktopcover/size', 200)
        upscale = settings.get_option('plugin/desktopcover/override_size')
        pixbuf = icons.MANAGER.pixbuf_from_data(
            cover_data, size=(size, size), upscale=upscale)
        fading = settings.get_option('plugin/desktopcover/fading', False)

        if fading and self._cross_fade_id is None:
            duration = settings.get_option(
                'plugin/desktopcover/fading_duration', 50)
            self._cross_fade_id = gobject.timeout_add(
                int(duration), self.cross_fade, pixbuf, duration)
        else:
            self.image.set_from_pixbuf(pixbuf)

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        self.set_size_request(width, height)

    def update_position(self):
        """
            Updates the position based
            on gravity and offsets
        """
        gravity = settings.get_option('plugin/desktopcover/anchor', 'topleft')

        # Try to migrate old integer gravitys
        if gravity not in self.gravity_map:
            gravities = self.gravity_map.keys()
            
            try:
                gravity = self.gravity_map[gravities[gravity]]
            except IndexError:
                gravity = 'topleft'

        self.set_gravity(self.gravity_map[gravity])

        x = settings.get_option('plugin/desktopcover/x', 0)
        y = settings.get_option('plugin/desktopcover/y', 0)

        gravity = self.get_gravity()
        allocation = self.get_allocation()

        if gravity in (gtk.gdk.GRAVITY_NORTH_EAST,
                gtk.gdk.GRAVITY_SOUTH_EAST):
            workarea_width = guiutil.get_workarea_size()[0]
            x = workarea_width - allocation.width - x

        if gravity in (gtk.gdk.GRAVITY_SOUTH_EAST,
                gtk.gdk.GRAVITY_SOUTH_WEST):
            workarea_height = guiutil.get_workarea_size()[1]
            y = workarea_height - allocation.height - y

        self.move(int(x), int(y))

    def show(self):
        """
            Override to ensure WM hints and fade-in
        """
        self.set_keep_below(True)
        self.stick()

        fading = settings.get_option('plugin/desktopcover/fading', False)

        if fading and self._fade_in_id is None:
            self.set_opacity(0)

        gtk.Window.show(self)

        if fading and self._fade_in_id is None:
            duration = settings.get_option(
                'plugin/desktopcover/fading_duration', 50)
            self._fade_in_id = gobject.timeout_add(
                int(duration), self.fade_in)

    def hide(self):
        """
            Override for fade-out
        """
        fading = settings.get_option('plugin/desktopcover/fading', False)

        if fading and self._fade_out_id is None:
            duration = settings.get_option(
                'plugin/desktopcover/fading_duration', 50)
            self._fade_out_id = gobject.timeout_add(
                int(duration), self.fade_out)
        else:
            gtk.Window.hide(self)
            self.image.set_from_pixbuf(None)

    def fade_in(self):
        """
            Increases opacity until completely opaque
        """
        opacity = self.get_opacity()

        if opacity == 1:
            self._fade_in_id = None

            return False

        self.set_opacity(opacity + 0.1)

        return True

    def fade_out(self):
        """
            Decreases opacity until transparent
        """
        opacity = self.get_opacity()

        if opacity == 0:
            gtk.Window.hide(self)
            self.image.set_from_pixbuf(None)
            self._fade_out_id = None

            return False

        self.set_opacity(opacity - 0.1)

        return True

    def cross_fade(self, next_pixbuf, duration):
        """
            Fades between two cover images

            :param next_pixbuf: the cover image pixbuf to fade to
            :type next_pixbuf: :class:`gtk.gdk.Pixbuf`
            :param duration: the overall time for the fading
            :type duration: int
        """
        if self._cross_fade_step < duration:
            pixbuf = self.image.get_pixbuf()

            if pixbuf is None:
                self.image.set_from_pixbuf(next_pixbuf)

                return False

            alpha = (255.0 / duration) * self._cross_fade_step

            next_pixbuf.composite(
                dest=pixbuf,
                dest_x=0, dest_y=0,
                dest_width=pixbuf.get_width(),
                dest_height=pixbuf.get_height(),
                offset_x=0, offset_y=0,
                scale_x=1, scale_y=1,
                interp_type=gtk.gdk.INTERP_BILINEAR,
                overall_alpha=int(alpha)
            )

            self.image.queue_draw()
            self._cross_fade_step += 1

            return True

        self._cross_fade_id = None
        self._cross_fade_step = 0
        
        return False

    def on_playback_player_start(self, type, player, track):
        """
            Shows the window
        """
        print 'GOT HERE'
        self.set_cover_from_track(track)
        self.update_position()
        self.show()

    def on_playback_track_start(self, type, player, track):
        """
            Updates the cover image and shows the window
        """
        self.set_cover_from_track(track)
        self.update_position()

    def on_playback_player_end(self, type, player, track):
        """
            Hides the window at the end of playback
        """
        self.hide()

    def on_option_set(self, type, settings, option):
        """
            Updates the appearance
        """
        if option in ('plugin/desktopcover/anchor',
                'plugin/desktopcover/x',
                'plugin/desktopcover/y'):
            self.update_position()
        elif option in ('plugin/desktopcover/override_size',
                'plugin/desktopcover/size'):
            self.set_cover_from_track(self.player.current)

    def on_exaile_loaded(self, e, exaile, nothing):
        """
            Sets up references after controller is loaded
        """
        self.player = exaile.player

        if self.player.current is not None:
            self.set_cover_from_track(self.player.current)
            self.update_position()
            self.set_opacity(0)
            self.show()

        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

# vi: et sts=4 sw=4 tw=80
