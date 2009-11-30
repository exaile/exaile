# Copyright (C) 2009 Mathias Brodala
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

import gobject, gtk, os
from egg.trayicon import TrayIcon as EggTrayIcon
from xl import event, playlist, providers, settings
from xl.nls import gettext as _
from xl.track import Track, is_valid_track
from xlgui.guiutil import get_workarea_size
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
    if DROPTRAYICON:
        DROPTRAYICON.destroy()
        DROPTRAYICON = None

class DropTrayIcon(EggTrayIcon, BaseTrayIcon):
    """
        Allows for drop operations on the tray icon
    """
    def __init__(self, exaile):
        EggTrayIcon.__init__(self, 'Exaile Trayicon')

        self.image = gtk.image_new_from_icon_name(
          'exaile', gtk.ICON_SIZE_MENU)
        self.eventbox = gtk.EventBox()
        self.eventbox.add(self.image)
        self.add(self.eventbox)

        builder = gtk.Builder()
        basedir = os.path.dirname(os.path.abspath(__file__))
        builder.add_from_file(os.path.join(basedir, 'drop_target_window.ui'))

        self.exaile = exaile
        #self.restore_icon = None
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
                gtk.DEST_DEFAULT_ALL,
                [("text/uri-list", 0, 0)],
                gtk.gdk.ACTION_COPY |
                gtk.gdk.ACTION_DEFAULT |
                gtk.gdk.ACTION_MOVE
            )
        
        # Required to allow the window to be
        # integrated into the drag process
        self.drop_target_window.drag_dest_set(
            gtk.DEST_DEFAULT_MOTION,
            [("text/uri-list", 0, 0)],
            gtk.gdk.ACTION_COPY |
            gtk.gdk.ACTION_DEFAULT |
            gtk.gdk.ACTION_MOVE
        )

    def connect_events(self):
        """
            Connects various events
            with callbacks
        """
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

        #event.add_callback(self.on_setting_change,
        #    'option_set')
        #event.add_callback(self.on_tray_icon_toggled,
        #    'tray_icon_toggled')

        BaseTrayIcon.connect_events(self)

    def destroy(self):
        """
            Restores the default trayicon if required
        """
        #self.set_active(False)
        self.hide_all()

    def set_from_icon_name(self, icon_name):
        """
            Updates the tray icon
        """
        self.image.set_from_icon_name(icon_name, gtk.ICON_SIZE_MENU)

    def set_tooltip(self, tooltip_text):
        """
            Updates the tray icon tooltip
        """
        self.set_tooltip_text(tooltip_text)

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

    def set_active(self, active):
        """
            Toggles activation state of the tray icon
        """
        if self.exaile.gui.tray_icon is None:
            return

        if not isinstance(self.exaile.gui.tray_icon, type(self)):
            self.restore_icon = self.exaile.gui.tray_icon

        self.exaile.gui.tray_icon.set_visible(False)

        if active:
            self.exaile.gui.tray_icon = self
        else:
            self.exaile.gui.tray_icon = self.restore_icon

        self.exaile.gui.tray_icon.set_visible(True)

    def set_visible(self, visible):
        """
            Toggles visibility of the tray icon
        """
        if visible:
            self.show_all()
        else:
            self.hide_all()

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

    def on_drag_motion(self, widget, context, x, y, timestamp):
        """
            Prepares to show the drop target
        """
        description = _('Drop to Choose')

        if widget == self.play_target:
            description = _('Append and Play')
        if widget == self.append_target or widget == self:
            description = _('Append')
        if widget == self.new_playlist_target:
            description = _('New Playlist')

        self.description_label.set_text(description)

        # Defer display of drop target
        if self._drag_motion_id is None:
            self._drag_motion_id = gobject.timeout_add(500,
                self.drag_motion_finish)

        # Prevent hiding of drop target
        if self._drag_leave_id is not None:
            gobject.source_remove(self._drag_leave_id)
            self._drag_leave_id = None

    def drag_motion_finish(self):
        """
            Shows the drop target
        """
        self.update_drop_target_window_location()
        self.drop_target_window.show()

    def on_drag_leave(self, widget, context, timestamp):
        """
            Prepares to hide the drop target
        """
        # Enable display of drop target on re-enter
        if self._drag_motion_id is not None:
            gobject.source_remove(self._drag_motion_id)
            self._drag_motion_id = None

        # Defer hiding of drop target
        if self._drag_leave_id is not None:
            gobject.source_remove(self._drag_leave_id)
        self._drag_leave_id = gobject.timeout_add(500,
            self.drag_leave_finish)

    def drag_leave_finish(self):
        """
            Hides the drop target
        """
        self.drop_target_window.hide()

    def on_drag_data_received(self, widget, context, x, y, selection, info, timestamp):
        """
            Handles dropped data
        """
        # Enable display of drop target on re-enter
        if self._drag_motion_id is not None:
            gobject.source_remove(self._drag_motion_id)
            self._drag_motion_id = None

        # Enable hiding of drop target on re-enter
        if self._drag_leave_id is not None:
            gobject.source_remove(self._drag_leave_id)
            self._drag_leave_id = None

        self.drop_target_window.hide()

        uris = selection.get_uris()
        playlist = self.exaile.gui.main.get_selected_playlist()

        if widget == self.play_target:
            event.add_callback(self.on_tracks_added, 'tracks_added')

        if widget == self.new_playlist_target:
            playlist = self.exaile.gui.main.add_playlist()

        playlist.drag_data_received(None, context,
            x, y, selection, info, timestamp)

    def on_setting_change(self, event_name, object, option):
        if option == 'gui/use_tray':
            print 'GOT INTO plugins.droptrayicon'
            #print 'Tray option active: %s' % settings.get_option(option)

    def on_tray_icon_toggled(self, event_name, tray_icon, active):
        """
            Updates tray appearance
        """
        #print 'Tray active: %s' % active
        self.set_active(active)

    def on_tracks_added(self, event_name, playlist, tracks):
        """
            Starts playing the newly added tracks
        """
        if tracks[0] is not None:
            index = playlist.index(tracks[0])
            playlist.set_current_pos(index)
            self.exaile.queue.play(tracks[0])

        event.remove_callback(self.on_tracks_added, 'tracks_added')

