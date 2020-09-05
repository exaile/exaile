# Copyright (C) 2006-2010  Johannes Sasongko <sasongko@gmail.com>
# Copyright (C) 2010  Mathias Brodala <info@noctus.net>
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import cairo

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from xl import covers, event, player, settings

from xlgui.guiutil import get_workarea_dimensions, pixbuf_from_data

from . import desktopcover_preferences

DESKTOPCOVER = None


class DesktopCoverPlugin:
    def __init__(self):
        self.__desktop_cover = None

    def enable(self, _exaile):
        """
        Enables the plugin
        """
        self.__migrate_anchor_setting()

    def on_gui_loaded(self):
        self.__desktop_cover = DesktopCover()

    def disable(self, _exaile):
        """
        Disables the desktop cover plugin
        """
        self.__desktop_cover.destroy()
        self.__desktop_cover = None

    @staticmethod
    def __migrate_anchor_setting():
        """
        Migrates gravity setting from the old
        integer values to the new string values
        """
        gravity = settings.get_option('plugin/desktopcover/anchor', 'topleft')
        gravity_map = DesktopCover.gravity_map

        if gravity not in gravity_map:
            # Convert to list so we can index it with the old integer
            # setting value
            gravities = list(gravity_map.keys())

            try:
                gravity = gravities[gravity]
            except (IndexError, TypeError):
                gravity = 'topleft'

            settings.set_option('plugin/desktopcover/anchor', gravity)


def get_preferences_pane():
    return desktopcover_preferences


plugin_class = DesktopCoverPlugin


class DesktopCover(Gtk.Window):
    gravity_map = {
        'topleft': Gdk.Gravity.NORTH_WEST,
        'topright': Gdk.Gravity.NORTH_EAST,
        'bottomleft': Gdk.Gravity.SOUTH_WEST,
        'bottomright': Gdk.Gravity.SOUTH_EAST,
    }

    def __init__(self):
        Gtk.Window.__init__(self)

        self.image = Gtk.Image()
        self.add(self.image)
        self.image.show()

        self.set_accept_focus(False)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_below(True)
        self.set_resizable(False)
        self.set_role("desktopcover")
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_title("Exaile desktop cover")
        self.stick()

        self._fade_in_id = None
        self._fade_out_id = None
        self._cross_fade_id = None
        self._cross_fade_step = 0
        self._events = [
            'playback_track_start',
            'playback_player_end',
            'cover_set',
            'cover_removed',
        ]

        screen = self.get_screen()
        visual = screen.get_rgba_visual() or screen.get_rgb_visual()
        self.set_visual(visual)

        if player.PLAYER.current is not None:
            self.set_cover_from_track(player.PLAYER.current)
            GLib.idle_add(self.update_position)

        for e in self._events:
            if 'playback' in e:
                event.add_ui_callback(getattr(self, 'on_%s' % e), e, player.PLAYER)
            else:
                event.add_ui_callback(getattr(self, 'on_%s' % e), e)

        event.add_ui_callback(self.on_option_set, 'plugin_desktopcover_option_set')

        self.connect('draw', self.on_draw)
        self.connect('screen-changed', self.on_screen_changed)

    def destroy(self):
        """
        Cleanups
        """
        for e in self._events:
            if 'playback' in e:
                event.remove_callback(getattr(self, 'on_%s' % e), e, player.PLAYER)
            else:
                event.remove_callback(getattr(self, 'on_%s' % e), e)

        event.remove_callback(self.on_option_set, 'plugin_desktopcover_option_set')

        Gtk.Window.destroy(self)

    def set_cover_from_track(self, track):
        """
        Updates the cover image and triggers cross-fading
        """
        cover_data = covers.MANAGER.get_cover(track, set_only=True)

        if cover_data is None:
            self.hide()
            return

        if not self.props.visible:
            self.show()

        size = settings.get_option('plugin/desktopcover/size', 200)
        upscale = settings.get_option('plugin/desktopcover/override_size', False)
        pixbuf = self.image.get_pixbuf()
        next_pixbuf = pixbuf_from_data(cover_data, size=(size, size), upscale=upscale)
        fading = settings.get_option('plugin/desktopcover/fading', False)

        if fading and pixbuf is not None and self._cross_fade_id is None:
            # Prescale to allow for proper crossfading
            width, height = next_pixbuf.get_width(), next_pixbuf.get_height()
            pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
            self.image.set_from_pixbuf(pixbuf)

            duration = settings.get_option('plugin/desktopcover/fading_duration', 50)

            self._cross_fade_id = GLib.timeout_add(
                int(duration), self.cross_fade, pixbuf, next_pixbuf, duration
            )
        else:
            self.image.set_from_pixbuf(next_pixbuf)

    def update_position(self):
        """
        Updates the position based
        on gravity and offsets
        """
        gravity = self.gravity_map[
            settings.get_option('plugin/desktopcover/anchor', 'topleft')
        ]
        cover_offset_x = settings.get_option('plugin/desktopcover/x', 0)
        cover_offset_y = settings.get_option('plugin/desktopcover/y', 0)
        allocation = self.get_allocation()
        workarea = get_workarea_dimensions()
        x, y = workarea.x, workarea.y

        if gravity in (Gdk.Gravity.NORTH_WEST, Gdk.Gravity.SOUTH_WEST):
            x += cover_offset_x
        else:
            x += workarea.width - allocation.width - cover_offset_x

        if gravity in (Gdk.Gravity.NORTH_WEST, Gdk.Gravity.NORTH_EAST):
            y += cover_offset_y
        else:
            y += workarea.height - allocation.height - cover_offset_y

        self.set_gravity(gravity)
        self.move(int(x), int(y))

    def show(self):
        """
        Override for fade-in
        """
        fading = settings.get_option('plugin/desktopcover/fading', False)

        if fading and self._fade_in_id is None:
            self.set_opacity(0)

        Gtk.Window.show(self)

        if fading and self._fade_in_id is None:
            duration = settings.get_option('plugin/desktopcover/fading_duration', 50)
            self._fade_in_id = GLib.timeout_add(int(duration), self.fade_in)

    def hide(self):
        """
        Override for fade-out
        """
        fading = settings.get_option('plugin/desktopcover/fading', False)

        if fading and self._fade_out_id is None:
            duration = settings.get_option('plugin/desktopcover/fading_duration', 50)
            self._fade_out_id = GLib.timeout_add(int(duration), self.fade_out)
        else:
            Gtk.Window.hide(self)
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
            Gtk.Window.hide(self)
            self.image.set_from_pixbuf(None)
            self._fade_out_id = None

            return False

        self.set_opacity(opacity - 0.1)

        return True

    def cross_fade(self, pixbuf, next_pixbuf, duration):
        """
        Fades between two cover images

        :param pixbuf: the current cover image pixbuf
        :type pixbuf: :class:`GdkPixbuf.Pixbuf`
        :param next_pixbuf: the cover image pixbuf to fade to
        :type next_pixbuf: :class:`GdkPixbuf.Pixbuf`
        :param duration: the overall time for the fading
        :type duration: int
        """
        if self._cross_fade_step < duration:
            width, height = pixbuf.get_width(), pixbuf.get_height()
            alpha = (255 / duration) * self._cross_fade_step

            next_pixbuf.composite(
                dest=pixbuf,
                dest_x=0,
                dest_y=0,
                dest_width=width,
                dest_height=height,
                offset_x=0,
                offset_y=0,
                scale_x=1,
                scale_y=1,
                interp_type=GdkPixbuf.InterpType.BILINEAR,
                overall_alpha=int(alpha),
            )

            self.image.queue_draw()
            self._cross_fade_step += 1

            return True

        self._cross_fade_id = None
        self._cross_fade_step = 0

        return False

    def on_draw(self, widget, context):
        """
        Takes care of drawing the window
        transparently, if possible
        """

        context.set_source_rgba(1, 1, 1, 0)
        context.set_operator(cairo.OPERATOR_SOURCE)

        context.paint()

    def on_screen_changed(self, widget, event):
        """
        Updates the colormap
        """
        screen = widget.get_screen()
        visual = screen.get_rgba_visual() or screen.get_rgb_visual()
        self.set_visual(visual)

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

    def on_cover_set(self, type, covers, track):
        """
        Updates the cover image after cover selection
        """
        self.set_cover_from_track(track)
        self.update_position()

    def on_cover_removed(self, type, covers, track):
        """
        Hides the window after cover removal
        """
        self.hide()

    def on_option_set(self, type, settings, option):
        """
        Updates the appearance
        """
        if option in (
            'plugin/desktopcover/anchor',
            'plugin/desktopcover/x',
            'plugin/desktopcover/y',
        ):
            self.update_position()
        elif option in (
            'plugin/desktopcover/override_size',
            'plugin/desktopcover/size',
        ):
            self.set_cover_from_track(player.PLAYER.current)


# vi: et sts=4 sw=4 tw=80
