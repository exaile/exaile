# Copyright (C) 2009-2010 Mathias Brodala
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

import os
from egg.trayicon import TrayIcon as EggTrayIcon

from xl import (
    event,
    player,
    providers,
    settings
)
from xl.nls import gettext as _
from xl.trax import Track, is_valid_track
import xlgui
from xlgui.guiutil import get_workarea_size
from xlgui.widgets.playlist import PlaylistPage
from xlgui.tray import BaseTrayIcon

DROPTRAYICON = None

def enable(exaile):
    """
        Enables the drop trayicon plugin
    """
    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)

def _enable(event, exaile, nothing):
    """
        Handles the deferred enable call
    """
    global DROPTRAYICON
    DROPTRAYICON = DropTrayIcon(exaile)

def disable(exaile):
    """
        Disables the drop trayicon plugin
    """
    global DROPTRAYICON
    DROPTRAYICON.destroy()
    DROPTRAYICON = None

class DropTrayIcon(EggTrayIcon, BaseTrayIcon):
    """
        Allows for drop operations on the tray icon
    """
    def __init__(self, exaile):
        EggTrayIcon.__init__(self, 'Exaile Trayicon')

        self.image = Gtk.Image.new_from_icon_name(
          'exaile', Gtk.IconSize.MENU)
        self.eventbox = Gtk.EventBox()
        self.eventbox.add(self.image)
        self.add(self.eventbox)

        builder = Gtk.Builder()
        basedir = os.path.dirname(os.path.abspath(__file__))
        builder.add_from_file(os.path.join(basedir, 'drop_target_window.ui'))

        self.exaile = exaile
        self.drop_target_window = builder.get_object('drop_target_window')
        self.play_target = builder.get_object('play_target')
        self.append_target = builder.get_object('append_target')
        self.new_playlist_target = builder.get_object('new_playlist_target')
        self.description_label = builder.get_object('description_label')

        self._drag_motion_id = None
        self._drag_leave_id = None

        BaseTrayIcon.__init__(self, self.exaile.gui.main)

        self.setup_drag_destinations()
        self.show_all()

    def destroy(self):
        """
            Hides the tray icon
        """
        EggTrayIcon.destroy(self)
        BaseTrayIcon.destroy(self)

    def setup_drag_destinations(self):
        """
            Sets up drag destinations of
            various contained widgets
        """
        widgets = [
            self,
            self.play_target,
            self.append_target,
            self.new_playlist_target
        ]

        for widget in widgets:
            widget.drag_dest_set(
                Gtk.DestDefaults.ALL,
                [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
                Gdk.DragAction.COPY |
                Gdk.DragAction.DEFAULT |
                Gdk.DragAction.MOVE
            )

        # Required to allow the window to be
        # integrated into the drag process
        self.drop_target_window.drag_dest_set(
            Gtk.DestDefaults.MOTION,
            [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
            Gdk.DragAction.COPY |
            Gdk.DragAction.DEFAULT |
            Gdk.DragAction.MOVE
        )

    def connect_events(self):
        """
            Connects various events
            with callbacks
        """
        self.connect('size-allocate',
            self.on_size_allocate)

        self.connect('drag-motion',
            self.on_drag_motion)
        self.connect('drag-leave',
            self.on_drag_leave)
        self.connect('drag-data-received',
            self.on_drag_data_received)

        self.drop_target_window.connect('drag-motion',
            self.on_drag_motion)
        self.drop_target_window.connect('drag-leave',
            self.on_drag_leave)

        self.play_target.connect('drag-motion',
            self.on_drag_motion)
        self.play_target.connect('drag-data-received',
            self.on_drag_data_received)

        self.append_target.connect('drag-motion',
            self.on_drag_motion)
        self.append_target.connect('drag-data-received',
            self.on_drag_data_received)

        self.new_playlist_target.connect('drag-motion',
            self.on_drag_motion)
        self.new_playlist_target.connect('drag-data-received',
            self.on_drag_data_received)

        BaseTrayIcon.connect_events(self)

    def set_from_icon_name(self, icon_name):
        """
            Updates the tray icon
        """
        self.image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)

    def set_tooltip(self, tooltip_text):
        """
            Updates the tray icon tooltip
        """
        self.set_tooltip_text(tooltip_text)

    def set_visible(self, visible):
        """
            Shows or hides the tray icon
        """
        if visible:
            self.show_all()
        else:
            self.hide()

    def get_menu_position(self, menu, icon):
        """
            Returns coordinates for
            the best menu position
        """
        workarea_width, workarea_height = get_workarea_size()
        icon_x, icon_y, icon_width, icon_height = icon.get_allocation()
        icon_x, icon_y = icon.get_window().get_origin()
        menu_x, menu_y, menu_width, menu_height = menu.get_allocation()

        x = icon_x + icon_width
        y = icon_y + icon_height

        if workarea_width - icon_x < menu_width:
            # Tray icon on the right: insufficient space
            x -= menu_width

        if workarea_height - icon_y < menu_height:
            # Tray icon on the bottom: insufficient space
            y -= menu_height

        return (x, y, False)

    def update_drop_target_window_location(self):
        """
            Makes sure the drop target
            is always fully visible
        """
        workarea_width, workarea_height = get_workarea_size()
        icon_x, icon_y, icon_width, icon_height = self.get_allocation()
        icon_x, icon_y = self.get_window().get_origin()
        target_width, target_height = self.drop_target_window.size_request()

        # TODO: Align drop targets vertically if required

        # Tray icon on the left
        if icon_x < target_width / 2:
            # Insufficient space: leftmost
            x = icon_width
        # Tray icon on the right
        elif workarea_width - icon_x < target_width / 2:
            # Insufficient space: rightmost
            x = workarea_width - target_width
        # Tray icon in between
        else:
            x = icon_x + icon_width / 2 - target_width / 2

        # Tray icon on the top
        if icon_y < target_height / 2:
            # Insufficient space: topmost
            y = icon_height
        # Tray icon on the bottom
        elif workarea_height - icon_y < target_height / 2:
            # Insufficient space: bottommost
            y = workarea_height - target_height
        # Tray icon in between
        else:
            y = icon_y + icon_height / 2 - target_height / 2

        self.drop_target_window.move(x, y)

    def on_size_allocate(self, widget, allocation):
        """
            Takes care of resizing the icon if necessary
        """
        icon_sizes = (
            Gtk.IconSize.MENU, # 1
            Gtk.IconSize.SMALL_TOOLBAR, # 2
            Gtk.IconSize.LARGE_TOOLBAR, # 3
            Gtk.IconSize.BUTTON, # 4
            Gtk.IconSize.DND, # 5
            Gtk.IconSize.DIALOG # 6
        )
        # Retrieve pixel dimensions of stock icon sizes
        sizes = [(Gtk.icon_size_lookup(i)[1], i) for i in icon_sizes]
        # Only look at sizes lower than the current dimensions
        sizes = [(s, i) for s, i in sizes if s <= allocation.width]
        # Get the closest fit
        target_size = max(sizes)[1]

        # Avoid setting the same size over and over again
        if self.image.props.icon_size is not target_size.real:
            GLib.idle_add(self.image.set_from_icon_name,
                self.image.props.icon_name, target_size)

    def on_drag_motion(self, widget, context, x, y, timestamp):
        """
            Prepares to show the drop target
        """
        description = _('Drop to Choose')

        if widget is self.play_target:
            description = _('Append and Play')
        if widget is self.append_target or widget is self:
            description = _('Append')
        if widget is self.new_playlist_target:
            description = _('New Playlist')

        self.description_label.set_text(description)

        # Defer display of drop target
        if self._drag_motion_id is None:
            self._drag_motion_id = GLib.timeout_add(500,
                self.drag_motion_finish)

        # Prevent hiding of drop target
        if self._drag_leave_id is not None:
            GLib.source_remove(self._drag_leave_id)
            self._drag_leave_id = None

    def drag_motion_finish(self):
        """
            Shows the drop target
        """
        self._drag_motion_id = None
        self.update_drop_target_window_location()
        self.drop_target_window.show()

    def on_drag_leave(self, widget, context, timestamp):
        """
            Prepares to hide the drop target
        """
        # Enable display of drop target on re-enter
        if self._drag_motion_id is not None:
            GLib.source_remove(self._drag_motion_id)
            self._drag_motion_id = None

        # Defer hiding of drop target
        if self._drag_leave_id is not None:
            GLib.source_remove(self._drag_leave_id)
        self._drag_leave_id = GLib.timeout_add(500,
            self.drag_leave_finish)

    def drag_leave_finish(self):
        """
            Hides the drop target
        """
        self._drag_leave_id = None
        self.drop_target_window.hide()

    def on_drag_data_received(self, widget, context, x, y, selection, info, time):
        """
            Handles dropped data
        """
        # Enable display of drop target on re-enter
        if self._drag_motion_id is not None:
            GLib.source_remove(self._drag_motion_id)
            self._drag_motion_id = None

        # Enable hiding of drop target on re-enter
        if self._drag_leave_id is not None:
            GLib.source_remove(self._drag_leave_id)
            self._drag_leave_id = None

        self.drop_target_window.hide()

        uris = selection.get_uris()
        page = xlgui.main.get_selected_page()

        if widget is self.play_target:
            event.add_callback(self.on_playlist_tracks_added,
                'playlist_tracks_added')

        if widget is self.new_playlist_target:
            playlist_notebook = xlgui.main.get_playlist_notebook()
            page = playlist_notebook.create_new_playlist().page

        if not isinstance(page, PlaylistPage):
            return

        page.view.emit('drag-data-received',
            context, x, y, selection, info, time)

    def on_playlist_tracks_added(self, event_name, playlist, tracks):
        """
            Starts playing the newly added tracks
        """
        if tracks:
            position, track = tracks[0]
            playlist.current_position = position
            player.QUEUE.play(track)

        event.remove_callback(self.on_playlist_tracks_added,
            'playlist_tracks_added')

