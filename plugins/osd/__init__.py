# Copyright (C) 2012 Mathias Brodala
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

from __future__ import division

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

import cairo
from collections import namedtuple
import sys
from math import pi

from xl import (
    event,
    player,
    settings
)
from xl.nls import gettext as _
from xl.player.adapters import PlaybackAdapter
from xlgui.widgets import info

import migration
from alphacolor import alphacolor_parse
import osd_preferences

OSDWINDOW = None


def enable(exaile):
    """
        Enables the on screen display plugin
    """
    migration.migrate_settings()

    global OSDWINDOW
    OSDWINDOW = OSDWindow()


def disable(exaile):
    """
        Disables the on screen display plugin
    """
    global OSDWINDOW
    OSDWINDOW.destroy()
    OSDWINDOW = None


def get_preferences_pane():
    return osd_preferences

Point = namedtuple('Point', 'x y')


class OSDWindow(Gtk.Window, PlaybackAdapter):
    """
        A popup window showing information
        of the currently playing track
    """
    autohide = GObject.property(
        type=GObject.TYPE_BOOLEAN,
        nick='autohide',
        blurb='Whether to automatically hide the window after some time',
        default=True,
        flags=GObject.PARAM_READWRITE
    )
    __gsignals__ = {}

    def __init__(self):
        """
            Initializes the window
        """
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)

        # for whatever reason, calling set_opacity seems
        # to crash on Windows when using PyGTK that comes with
        # the GStreamer SDK. Since this plugin is enabled by
        # default, just don't fade in/out on windows
        #
        # https://bugs.freedesktop.org/show_bug.cgi?id=54682
        self.use_fade = True
        if sys.platform == 'win32':
            self.use_fade = False

        self.fadeout_id = None
        self.drag_origin = None
        self.hide_id = None

        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_title('Exaile OSD')
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_resizable(True)
        self.set_app_paintable(True)
        self.stick()
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK)

        # Cached option values
        self.__options = {
            'background': None,
            'display_duration': None,
            'border_radius': None
        }

        self.info_area = info.TrackInfoPane(player.PLAYER)
        self.info_area.set_default_text('')
        self.info_area.set_auto_update(True)
        self.add(self.info_area)

        event.add_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.add_callback(self.on_option_set, 'plugin_osd_option_set')

        # Trigger initial setup trough options
        for option in ('format', 'background', 'display_duration',
                       'show_progress', 'position', 'width', 'height',
                       'border_radius'):
            self.on_option_set('plugin_osd_option_set', settings,
                               'plugin/osd/{option}'.format(option=option))

        # Trigger color map update
        self.emit('screen-changed', self.get_screen())

        PlaybackAdapter.__init__(self, player.PLAYER)

    def destroy(self):
        """
            Cleanups
        """
        event.remove_callback(self.on_option_set, 'plugin_osd_option_set')
        event.remove_callback(self.on_track_tags_changed, 'track_tags_changed')

        Gtk.Window.destroy(self)

    def hide(self):
        """
            Starts fadeout of the window
        """
        if not self.use_fade:
            Gtk.Window.hide(self)
            return

        if self.fadeout_id is None:
            self.fadeout_id = GLib.timeout_add(50, self.__fade_out)

    def show(self):
        """
            Stops fadeout and immediately shows the window
        """
        if self.use_fade:
            try:
                GLib.source_remove(self.fadeout_id)
            except:
                pass
            finally:
                self.fadeout_id = None

            self.set_opacity(1)

        Gtk.Window.show_all(self)

    def __fade_out(self):
        """
            Constantly decreases the opacity to fade out the window
        """
        opacity = self.get_opacity()

        if opacity == 0:
            GLib.source_remove(self.fadeout_id)
            self.fadeout_id = None

            Gtk.Window.hide(self)

            return False

        self.set_opacity(opacity - 0.1)

        return True

    def do_notify(self, parameter):
        """
            Triggers hiding if autohide is enabled
        """
        if parameter.name == 'autohide':
            if self.props.autohide:
                self.hide()

    def do_expose_event(self, event):
        """
            Draws the background of the window
        """
        context = self.props.window.cairo_create()
        context.rectangle(event.area.x, event.area.y,
                          event.area.width, event.area.height)
        context.clip()

        context.set_source_rgba(
            self.__options['background'].red_float,
            self.__options['background'].green_float,
            self.__options['background'].blue_float,
            self.__options['background'].alpha_float
        )

        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()

        Gtk.Window.do_expose_event(self, event)

    def do_screen_changed(self, screen):
        """
            Updates the used colormap
        """
        visual = screen.get_rgba_visual()
        if visual is None:
            visual = screen.get_system_visual()

        self.unrealize()
        self.set_visual(visual)
        self.realize()

    def do_size_allocate(self, allocation):
        """
            Applies the non-rectangular shape
        """
        width, height = allocation.width, allocation.height
        mask = Gdk.Pixmap(None, width, height, 1)
        context = mask.cairo_create()

        context.set_source_rgb(0, 0, 0)
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()

        radius = self.__options['border_radius']
        inner = (radius, radius, width - radius, height - radius)

        context.set_source_rgb(1, 1, 1)
        context.set_operator(cairo.OPERATOR_SOURCE)
        # Top left corner
        context.arc(inner.x,     inner.y,      radius, 1.0 * pi, 1.5 * pi)
        # Top right corner
        context.arc(inner.width, inner.y,      radius, 1.5 * pi, 2.0 * pi)
        # Bottom right corner
        context.arc(inner.width, inner.height, radius, 0.0 * pi, 0.5 * pi)
        # Bottom left corner
        context.arc(inner.x,     inner.height, radius, 0.5 * pi, 1.0 * pi)
        context.fill()

        self.shape_combine_mask(mask, 0, 0)

        Gtk.Window.do_size_allocate(self, allocation)

    def do_configure_event(self, e):
        """
            Stores the window size
        """
        width, height = self.get_size()

        settings.set_option('plugin/osd/width', width)
        settings.set_option('plugin/osd/height', height)

        Gtk.Window.do_configure_event(self, e)

    def do_button_press_event(self, e):
        """
            Starts the dragging process
        """
        if e.button == 1:
            self.drag_origin = Point(e.x, e.y)
            self.window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.FLEUR))

            return True
        elif e.button == 3 and e.state & Gdk.ModifierType.MOD1_MASK:
            self.begin_resize_drag(Gdk.WindowEdge.SOUTH_EAST, 3, int(
                e.x_root), int(e.y_root), e.time)

    def do_button_release_event(self, e):
        """
            Finishes the dragging process and
            saves the window position
        """
        if e.button == 1:
            settings.set_option('plugin/osd/position',
                                list(self.get_position()))

            self.drag_origin = None
            self.window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.ARROW))

            return True

    def do_motion_notify_event(self, e):
        """
            Moves the window while dragging, makes sure 
            the window is always visible upon mouse hover
        """
        drag_origin = self.drag_origin

        if drag_origin is not None:
            position = Point(e.x_root, e.y_root)

            self.move(
                int(position.x - drag_origin.x),
                int(position.y - drag_origin.y)
            )

        try:
            GLib.source_remove(self.hide_id)
        except:
            pass
        finally:
            self.hide_id = None

        self.show()

    def do_leave_notify_event(self, e):
        """
            Hides the window upon mouse leave
        """
        try:
            GLib.source_remove(self.hide_id)
        except:
            pass
        finally:
            self.hide_id = None

        if self.props.autohide:
            self.hide_id = GLib.timeout_add_seconds(
                self.__options['display_duration'], self.hide)

        Gtk.Window.do_leave_notify_event(self, e)

    def on_track_tags_changed(self, e, track, tag):
        if not tag.startswith('__') and track == player.PLAYER.current:
            self.on_playback_track_start(e, player.PLAYER, track)

    def on_playback_track_start(self, e, player, track):
        """
            Shows the OSD upon track change
        """
        GLib.idle_add(self.show)

        try:
            GLib.source_remove(self.hide_id)
        except:
            pass
        finally:
            self.hide_id = None

        if self.props.autohide:
            self.hide_id = GLib.timeout_add_seconds(
                self.__options['display_duration'], self.hide)

    def on_playback_toggle_pause(self, e, player, track):
        """
            Shows the OSD after resuming playback
        """
        if not player.is_playing():
            return

        GLib.idle_add(self.show)

        try:
            GLib.source_remove(self.hide_id)
        except:
            pass
        finally:
            self.hide_id = None

        if self.props.autohide:
            self.hide_id = GLib.timeout_add_seconds(
                self.__options['display_duration'], self.hide)

    def on_playback_player_end(self, e, player, track):
        """
            Hides the OSD upon playback end
        """
        if self.props.autohide:
            self.hide_id = GLib.timeout_add_seconds(
                self.__options['display_duration'], self.hide)

    def on_option_set(self, event, settings, option):
        """
            Updates appearance on setting change
        """
        if option == 'plugin/osd/format':
            self.info_area.set_info_format(settings.get_option(option,
                                                               _('<span font_desc="Sans 11" foreground="#fff"><b>$title</b></span>\n'
                                                                 'by $artist\n'
                                                                 'from $album')
                                                               ))
        if option == 'plugin/osd/background':
            self.__options['background'] = alphacolor_parse(
                settings.get_option(option, '#333333cc'))
            GLib.idle_add(self.queue_draw)
        elif option == 'plugin/osd/display_duration':
            self.__options['display_duration'] = int(
                settings.get_option(option, 4))
        elif option == 'plugin/osd/show_progress':
            self.info_area.set_display_progress(
                settings.get_option(option, True))
        elif option == 'plugin/osd/position':
            position = Point._make(settings.get_option(option, [20, 20]))
            GLib.idle_add(self.move, position.x, position.y)
        elif option == 'plugin/osd/border_radius':
            value = settings.get_option(option, 10)
            self.set_border_width(max(6, int(value / 2)))
            self.__options['border_radius'] = value
            self.emit('size-allocate', self.get_allocation())
