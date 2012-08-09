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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from __future__ import division
import cairo
from collections import namedtuple
import glib
import gtk
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
    OSDWINDOW = OSDWindow(exaile)

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

class OSDWindow(gtk.Window, PlaybackAdapter):
    """
        A popup window showing information
        of the currently playing track
    """
    __gsignals__ = {}

    def __init__(self, exaile):
        """
            Initializes the window
        """
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)

        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_NOTIFICATION)
        self.set_title('Exaile OSD')
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_pager_hint(True)
        self.set_skip_taskbar_hint(True)
        self.set_resizable(True)
        self.set_app_paintable(True)
        self.stick()
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.POINTER_MOTION_MASK)

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

        gtk.Window.destroy(self)

    def hide(self):
        """
            Starts fadeout of the window
        """
        if self.get_data('fadeout-id') is None:
            self.set_data('fadeout-id', glib.timeout_add(50, self.__fade_out))

    def show(self):
        """
            Stops fadeout and immediately shows the window
        """
        try:
            glib.source_remove(self.get_data('fadeout-id'))
        except:
            pass

        self.set_data('fadeout-id', None)
        self.set_opacity(1)
        gtk.Window.show_all(self)

    def __fade_out(self):
        """
            Constantly decreases the opacity to fade out the window
        """
        opacity = self.get_opacity()

        if opacity == 0:
            glib.source_remove(self.get_data('fadeout-id'))
            self.set_data('fadeout-id', None)

            gtk.Window.hide(self)

            return False

        self.set_opacity(opacity - 0.1)

        return True

    def do_expose_event(self, event):
        """
            Draws the background of the window
        """
        context = self.window.cairo_create()
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

        gtk.Window.do_expose_event(self, event)

    def do_screen_changed(self, screen):
        """
            Updates the used colormap
        """
        colormap = screen.get_rgba_colormap() or \
                   screen.get_rgb_colormap()
        
        self.unrealize()
        self.set_colormap(colormap)
        self.realize()

    def do_size_allocate(self, allocation):
        """
            Applies the non-rectangular shape
        """
        width, height = allocation.width, allocation.height
        mask = gtk.gdk.Pixmap(None, width, height, 1)
        context = mask.cairo_create()

        context.set_source_rgb(0, 0, 0)
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()

        radius = self.__options['border_radius']
        inner = gtk.gdk.Rectangle(radius, radius, width - radius, height - radius)

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

        gtk.Window.do_size_allocate(self, allocation)

    def do_configure_event(self, e):
        """
            Stores the window size
        """
        width, height = self.get_size()

        settings.set_option('plugin/osd/width', width)
        settings.set_option('plugin/osd/height', height)

        gtk.Window.do_configure_event(self, e)

    def do_button_press_event(self, e):
        """
            Starts the dragging process
        """
        if e.button == 1:
            self.set_data('drag-origin', Point(e.x, e.y))
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))

            return True
        elif e.button == 3 and e.state & gtk.gdk.MOD1_MASK:
            self.begin_resize_drag(gtk.gdk.WINDOW_EDGE_SOUTH_EAST, 3, int(e.x_root), int(e.y_root), e.time)

    def do_button_release_event(self, e):
        """
            Finishes the dragging process and
            saves the window position
        """
        if e.button == 1:
            settings.set_option('plugin/osd/position', list(self.get_position()))

            self.set_data('drag-origin', None)
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.ARROW))

            return True

    def do_motion_notify_event(self, e):
        """
            Moves the window while dragging, makes sure 
            the window is always visible upon mouse hover
        """
        drag_origin = self.get_data('drag-origin')

        if drag_origin is not None:
            position = Point(e.x_root, e.y_root)

            self.move(
                int(position.x - drag_origin.x),
                int(position.y - drag_origin.y)
            )


        try:
            glib.source_remove(self.get_data('hide-id'))
        except:
            pass

        self.show()

    def do_leave_notify_event(self, e):
        """
            Hides the window upon mouse leave
        """
        try:
            glib.source_remove(self.get_data('hide-id'))
        except:
            pass

        self.set_data('hide-id', glib.timeout_add_seconds(
            self.__options['display_duration'], self.hide))

        gtk.Window.do_leave_notify_event(self, e)

    def on_playback_track_start(self, e, player, track):
        """
            Shows the OSD upon track change
        """
        glib.idle_add(self.show)

        try:
            glib.source_remove(self.get_data('hide-id'))
        except:
            pass

        self.set_data('hide-id', glib.timeout_add_seconds(
            self.__options['display_duration'], self.hide))

    def on_playback_toggle_pause(self, e, player, track):
        """
            Shows the OSD after resuming playback
        """
        if not player.is_playing(): return

        glib.idle_add(self.show)

        try:
            glib.source_remove(self.get_data('hide-id'))
        except:
            pass

        self.set_data('hide-id', glib.timeout_add_seconds(
            self.__options['display_duration'], self.hide))

    def on_playback_player_end(self, e, player, track):
        """
            Hides the OSD upon playback end
        """
        glib.idle_add(self.hide)

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
            self.__options['background'] = alphacolor_parse(settings.get_option(option, '#333333cc'))
            glib.idle_add(self.queue_draw)
        elif option == 'plugin/osd/display_duration':
            self.__options['display_duration'] = settings.get_option(option, 4)
        elif option == 'plugin/osd/show_progress':
            self.info_area.set_display_progress(settings.get_option(option, True))
        elif option == 'plugin/osd/position':
            position = Point._make(settings.get_option(option, [20, 20]))
            glib.idle_add(self.move, position.x, position.y)
        elif option == 'plugin/osd/border_radius':
            value = settings.get_option(option, 10)
            self.set_border_width(max(6, int(value / 2)))
            self.__options['border_radius'] = value
            self.emit('size-allocate', self.get_allocation())

