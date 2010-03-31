# -*- coding: utf-8 -*-
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

import copy, gobject, gtk, pango
from datetime import date
from string import Template
from xl import event, settings
from xl.nls import gettext as _
from xl.trax import Track
from xlgui.guiutil import get_workarea_size
from xlgui.playlist import Playlist

class MenuItem(gtk.ImageMenuItem):
    """
        Convenience wrapper, allows switching to mini mode
    """
    def __init__(self, callback):
        gtk.ImageMenuItem.__init__(self, stock_id='exaile-minimode')
        self.child.set_label(_('Mini Mode'))

        self._activate_id = self.connect('activate', callback)

    def destroy(self):
        """
            Various cleanups
        """
        self.disconnect(self._activate_id)
        gtk.ImageMenuItem.destroy(self)

class KeyExistsError(KeyError):
    def __init__(self, error):
        KeyError.__init__(self, error)

class WidgetBox(gtk.HBox):
    """
        Wrapper class, allows for identification
        of and simple access to contained widgets
        Keeps track of registered types
    """
    def __init__(self, homogeneous=False, spacing=0):
        gtk.HBox.__init__(self, homogeneous, spacing)

        self.__register = {}
        self.__widgets = {}

    def destroy(self):
        """
            Various cleanups
        """
        for widget in self.__widgets:
            widget.destroy()

        gtk.HBox.destroy(self)

    def register_widget(self, id, type, arguments=[]):
        """
            Registers a widget
        """
        if id in self.__register:
            raise KeyExistsError, id

        self.__register[id] = (type, arguments)

    def register_widgets(self, widgets):
        """
            Registers multiple widgets at once
        """
        for id, (type, arguments) in widgets.iteritems():
            self.register_widget(id, type, arguments)

    def add_widget(self, id):
        """
            Adds a widget to the box, moves
            it to the end if already present
        """
        if id not in self.__register:
            raise KeyError, id

        if id in self.__widgets:
            widget = self.__widgets[id]
            self.reorder_child(widget, -1)
        else:
            type, arguments = self.__register[id]
            widget = type(*arguments)
            self.__widgets[id] = widget
            self.pack_start(widget, expand=False, fill=False)

    def remove_widget(self, id):
        """
            Removes a widget from the box
        """
        if id not in self.__register:
            raise KeyError, id

        if id not in self.__widgets:
            raise KeyError, id

        self.remove(self.__widgets[id])
        self.__widgets[id].destroy()
        del self.__widgets[id]

    def update_widgets(self, ids):
        """
            Updates display and order of widgets
        """
        for id in self.__register.iterkeys():
            if id not in ids:
                try:
                    self.remove_widget(id)
                except KeyError:
                    pass

        for id in ids:
            try:
                self.add_widget(id)
            except KeyError:
                pass

    def __getitem__(self, id):
        """
            Returns a widget, allows for box['id']
        """
        return self.__widgets[id]

class Button(gtk.Button):
    """
        Convenience wrapper around gtk.Button
    """
    def __init__(self, stock_id, tooltip_text, callback):
        gtk.Button.__init__(self)

        self.image = gtk.image_new_from_stock(stock_id, gtk.ICON_SIZE_BUTTON)
        self.set_image(self.image)
        self.set_tooltip_text(tooltip_text)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)

        self._clicked_id = self.connect('clicked', callback)

    def destroy(self):
        """
            Various cleanups
        """
        self.disconnect(self._clicked_id)

        gtk.Button.destroy(self)

class PlayPauseButton(Button):
    """
        Special Button which automatically sets its
        appearance depending on the current playback state
    """
    def __init__(self, player, callback):
        Button.__init__(self, 'gtk-media-play',
            _('Start Playback'), callback)

        self.player = player
        self.update_state()

        event.add_callback(self.on_playback_state_change, 'playback_player_start')
        event.add_callback(self.on_playback_state_change, 'playback_toggle_pause')
        event.add_callback(self.on_playback_state_change, 'playback_player_end')

    def destroy(self):
        """
            Various cleanups
        """
        event.remove_callback(self.on_playback_state_change, 'playback_player_start')
        event.remove_callback(self.on_playback_state_change, 'playback_toggle_pause')
        event.remove_callback(self.on_playback_state_change, 'playback_player_end')

        Button.destroy(self)

    def update_state(self):
        """
            Updates the appearance of this button
        """
        stock_id = 'gtk-media-play'
        tooltip_text = _('Start Playback')

        if self.player.current is not None:
            if self.player.is_paused():
                tooltip_text = _('Continue Playback')
            elif self.player.is_playing():
                stock_id = 'gtk-media-pause'
                tooltip_text = _('Pause Playback')

        self.image.set_from_stock(stock_id, gtk.ICON_SIZE_BUTTON)
        self.set_tooltip_text(tooltip_text)

    def on_playback_state_change(self, event, player, track):
        """
            Updates appearance on playback state change
        """
        self.update_state()

class VolumeButton(gtk.VolumeButton):
    """
        Wrapper class around gtk.VolumeButton
    """
    def __init__(self, player, callback):
        gtk.VolumeButton.__init__(self)

        self.player = player

        adjustment = gtk.Adjustment(upper=1, step_incr=0.1, page_incr=0.2)
        self.set_adjustment(adjustment)

        self._changed_callback = callback
        self._value_changed_id = self.connect('value-changed', self.on_change)
        self._expose_event_id = self.connect('expose-event', self.on_expose)

    def destroy(self):
        """
            Various cleanups
        """
        self.disconnect(self._value_changed_id)
        self.disconnect(self._expose_event_id)

        gtk.VolumeButton.destroy(self)

    def on_change(self, *e):
        """
            Wrapper function to prevent race conditions
        """
        if not self._updating:
            self._changed_callback(*e)

    def on_expose(self, volume_button, event):
        """
            Updates value on repaint requests
        """
        self._updating = True
        self.set_value(self.player.get_volume() / 100.0)
        self._updating = False

class AttachedWindow(gtk.Window):
    """
        A window attachable to arbitrary widgets,
        follows the movement of its parent
    """
    def __init__(self, parent):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)

        self.set_decorated(False)
        self.set_property('skip-taskbar-hint', True)
        self.set_size_request(350, 400)

        self.parent_widget = parent

        self._configure_id = None
        self._parent_realize_id = self.parent_widget.connect(
            'realize', self.on_parent_realize)

    def destroy(self):
        """
            Various cleanups
        """
        if self._configure_id is not None:
            self.disconnect(self._configure_id)

        self.disconnect(self._parent_realize_id)

        gtk.Window.destroy(self)

    def update_location(self):
        """
            Makes sure the window is
            always fully visible
        """
        workarea_width, workarea_height = get_workarea_size() # 1280, 974
        width, height = self.size_request() #  350, 400
        # FIXME: AttributeError: 'NoneType' object has no attribute 'get_origin'
        parent_window_x, parent_window_y = self.parent_widget.get_window().get_origin()
        parent_x, parent_y, parent_width, parent_height = self.parent_widget.get_allocation()
        parent_x, parent_y = parent_window_x + parent_x, parent_window_y + parent_y

        # E.g.       1280 - 1000    < 350
        if workarea_width - parent_x < width:
            #           1000 + 150          - 350 = 800
            x = parent_x + parent_width - width # Aligned right
        else:
            x = parent_x # Aligned left

        # E.g.         974 - 800     < 400
        if workarea_height - parent_y < height:
            #            800 - 400 = 400
            y = parent_y - height # Aligned top
        else:
            y = parent_y + parent_height # Aligned bottom

        self.move(x, y)

    def on_parent_realize(self, parent):
        """
            Prepares the window to
            follow its parent window
        """
        if self._configure_id is None:
            self._configure_id = parent.get_toplevel().connect(
                'configure-event', self.on_parent_window_configure)

    def on_parent_window_configure(self, *e):
        """
            Handles movement of the topmost window
        """
        self.update_location()

class PlaylistButton(gtk.ToggleButton):
    """
        Displays the current track title and
        the current playlist on activation
        Also allows for drag and drop of files
        to add them to the playlist
    """
    def __init__(self, main, queue, formatter, change_callback):
        gtk.ToggleButton.__init__(self, '')

        self.set_focus_on_click(False)
        self.set_size_request(150, -1)
        box = gtk.HBox()
        self.arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_OUT)
        box.pack_start(self.arrow, expand=False)
        self.label = gtk.Label('')
        self.label.set_property('ellipsize', pango.ELLIPSIZE_END)
        box.pack_start(self.label)
        self.remove(self.child)
        self.add(box)

        self.main = main
        self.formatter = formatter
        playlist = self.main.get_selected_playlist()
        self.playlist = Playlist(main, queue, playlist.playlist)
        self.playlist.model = playlist.model
        self.playlist.list.set_model(self.playlist.model)
        self.playlist.scroll.set_property('shadow-type', gtk.SHADOW_IN)
        self.popup = AttachedWindow(self)
        self.popup.add(self.playlist)

        self._dirty = False
        self._drag_shown = False
        self._parent_hide_id = None
        self._drag_motion_id = None

        self.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            self.playlist.list.targets,
            gtk.gdk.ACTION_COPY |
            gtk.gdk.ACTION_DEFAULT |
            gtk.gdk.ACTION_MOVE)

        self._track_changed_id = self.connect('track-changed',
            change_callback)
        self._scroll_event_id = self.connect('scroll-event',
            self.on_scroll)
        self._toggled_id = self.connect('toggled',
            self.on_toggled)
        self._drag_leave_id = self.connect('drag-leave',
            self.on_drag_leave)
        self._drag_motion_id = self.connect('drag-motion',
            self.on_drag_motion)
        self._drag_data_received_id = self.playlist.list.connect('drag-data-received',
            self.on_playlist_drag_data_received)
        self._switch_page_id = self.main.playlist_notebook.connect('switch-page',
            self.on_playlist_notebook_switch)
        self._format_changed_id = self.formatter.connect('format-changed',
            self.on_format_changed)

        event.add_callback(self.on_track_start, 'playback_track_start')
        event.add_callback(self.on_playback_start, 'playback_player_start')
        event.add_callback(self.on_playback_start, 'playback_player_resume')
        event.add_callback(self.on_playback_end, 'playback_player_end')

    def destroy(self):
        """
            Various cleanups
        """
        self.disconnect(self._track_changed_id)
        self.disconnect(self._scroll_event_id)
        self.disconnect(self._toggled_id)
        self.disconnect(self._drag_leave_id)
        self.disconnect(self._drag_motion_id)
        self.playlist.list.disconnect(self._drag_data_received_id)
        self.main.playlist_notebook.disconnect(self._switch_page_id)
        self.formatter.disconnect(self._format_changed_id)

        event.remove_callback(self.on_track_start, 'playback_track_start')
        event.remove_callback(self.on_playback_start, 'playback_player_start')
        event.remove_callback(self.on_playback_start, 'playback_player_resume')
        event.remove_callback(self.on_playback_end, 'playback_player_end')

        gtk.ToggleButton.destroy(self)

    def set_label(self, text):
        """
            Sets the label of the button
        """
        self.label.set_text(text)
        self.set_tooltip_text(text)

    def set_arrow_direction(self, direction):
        """
            Sets the direction of the arrow
        """
        self.arrow.set(direction, gtk.SHADOW_OUT)

    def on_format_changed(self, formatter, format):
        """
            Updates the playlist button
            on track title format changes
        """
        track = self.playlist.playlist.get_current()

        if track:
            self.set_label(self.formatter.format(track))

    def on_track_start(self, event, player, track):
        """
            Updates appearance and cursor position
        """
        self.set_label(self.formatter.format(track))

        if track in self.playlist.playlist.ordered_tracks:
            path = (self.playlist.playlist.index(track),)

            if settings.get_option('gui/ensure_visible', True):
                self.playlist.list.scroll_to_cell(path)

            gobject.idle_add(self.playlist.list.set_cursor, path)

    def on_playback_start(self, event, player, track):
        """
            Updates appearance on playback start/resume
        """
        self.set_label(self.formatter.format(track))

    def on_playback_end(self, event, player, track):
        """
            Clears label
        """
        self.set_label('')

    def on_parent_hide(self, parent):
        """
            Makes sure to hide the popup
        """
        self.set_active(False)

    def on_scroll(self, togglebutton, event):
        """
            Switches tracks on scrolling
        """
        track = None

        if event.direction == gtk.gdk.SCROLL_UP:
            track = self.playlist.playlist.prev()
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            track = self.playlist.playlist.next()

        self.emit('track-changed', track)

    def on_toggled(self, togglebutton):
        """
            Displays or hides the playlist on toggle
        """
        if self.popup.get_transient_for() is None:
            self.popup.set_transient_for(self.get_toplevel())

        if self._parent_hide_id is None:
            self._parent_hide_id = self.get_toplevel().connect(
                'hide', self.on_parent_hide)

        if self.get_active():
            self.popup.update_location()
            self.set_arrow_direction(gtk.ARROW_DOWN)
            self.popup.show()
        else:
            self.popup.hide()
            self.set_arrow_direction(gtk.ARROW_RIGHT)

    def on_drag_leave(self, togglebutton, context, timestamp):
        """
            Prevents showing the playlist if the
            pointer leaves the button prematurely
        """
        if self._drag_motion_id is not None:
            gobject.source_remove(self._drag_motion_id)
            self._drag_motion_id = None

    def on_drag_motion(self, togglebutton, context, x, y, timestamp):
        """
            Sets up a timeout to show the playlist
        """
        if self._drag_motion_id is None:
            self._drag_motion_id = gobject.timeout_add(500,
                self.drag_motion_finish)

    def drag_motion_finish(self):
        """
            Shows the playlist
        """
        self.set_active(True)
        self._drag_shown = True

    def on_playlist_drag_data_received(self, *e):
        """
            Hides the playlist if it has
            been opened via drag events
        """
        if self._drag_shown:
            self.set_active(False)
            self._drag_shown = False

    def on_playlist_notebook_switch(self, notebook, page, page_num):
        """
            Updates the internal playlist
        """
        playlist = notebook.get_nth_page(page_num)

        if playlist is not None:
            self.playlist.model = playlist.model
            self.playlist.list.set_model(self.playlist.model)

gobject.type_register(PlaylistButton)
gobject.signal_new('track-changed', PlaylistButton,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_PYOBJECT, ))

class TrackSelector(gtk.ComboBox):
    """
        Control which updates its content automatically
        on playlist actions, track display is configurable
    """
    def __init__(self, main, queue, formatter, changed_callback):
        gtk.ComboBox.__init__(self)

        self.main = main
        self.queue = queue
        self.formatter = formatter
        self.list = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        self.set_model(self.list)
        self.set_size_request(150, 0)

        textrenderer = gtk.CellRendererText()
        self.pack_start(textrenderer, expand=True)
        self.set_attributes(textrenderer, text=0)
        self.set_cell_data_func(textrenderer, self.text_data_func)

        self._updating = False
        self._dirty = False

        self.update_track_list(self.queue.current_playlist)

        self._track_changed_id = self.connect('track-changed',
            changed_callback)
        self._expose_event_id = self.connect('expose-event',
            self.on_expose)
        self._changed_id = self.connect('changed',
            self.on_change)
        self._switch_page_id = self.main.playlist_notebook.connect('switch-page',
            self.on_playlist_notebook_switch)
        self._format_changed_id = self.formatter.connect('format-changed',
            self.on_format_changed)

        event.add_callback(self.on_playlist_current_changed, 'playlist_current_changed')
        event.add_callback(self.on_tracks_added, 'tracks_added')
        event.add_callback(self.on_tracks_removed, 'tracks_removed')
        event.add_callback(self.on_tracks_reordered, 'tracks_reordered')

    def destroy(self):
        """
            Various cleanups
        """
        self.disconnect(self._track_changed_id)
        self.disconnect(self._expose_event_id)
        self.disconnect(self._changed_id)
        self.main.playlist_notebook.disconnect(self._switch_page_id)
        self.formatter.disconnect(self._format_changed_id)

        event.remove_callback(self.on_playlist_current_changed, 'playlist_current_changed')
        event.remove_callback(self.on_tracks_added, 'tracks_added')
        event.remove_callback(self.on_tracks_removed, 'tracks_removed')
        event.remove_callback(self.on_tracks_reordered, 'tracks_reordered')

        gtk.ComboBox.destroy(self)

    def update_track_list(self, playlist=None, tracks=None):
        """
            Populates the track list based
            on the current playlist
        """
        if playlist is None:
            playlist = self.queue.current_playlist
            if playlist is None:
                self.list.clear()
                return
            tracks = playlist.get_tracks()

        if tracks is None:
            tracks = playlist.get_tracks()

        current_track = playlist.get_current()

        self._updating = True
        self.list.clear()
        for track in tracks:
            iter = self.list.append([track, self.formatter.format(track)])
            if track == current_track:
                self.set_active_iter(iter)
        self._updating = False

    def get_active_track(self):
        """
            Returns the currently selected track
        """
        try:
            iter = self.get_active_iter()
            return self.list.get_value(iter, 0)
        except TypeError:
            return None

    def set_active_track(self, active_track):
        """
            Sets the currently selected track
        """
        iter = self.list.get_iter_first()

        self._updating = True
        while iter is not None:
            track = self.list.get_value(iter, 0)

            if track == active_track:
                self.set_active_iter(iter)
                break

            iter = self.list.iter_next(iter)
        self._updating = False

    def text_data_func(self, celllayout, cell, model, iter):
        """
            Updates track titles and highlights
            the current track if the popup is shown
        """
        active_iter = self.get_active_iter()

        if active_iter is not None:
            track = model.get_value(iter, 1)
            active_track = model.get_value(active_iter, 1)
            weight = pango.WEIGHT_NORMAL

            if self.get_property('popup-shown'):
                if track == active_track:
                    weight = pango.WEIGHT_BOLD

            cell.set_property('weight', weight)

    def on_expose(self, widget, event):
        """
            Performs deferred tasks
        """
        if self._dirty:
            self.update_track_list()
            self._dirty = False

    def on_change(self, *e):
        """
            Wrapper function to prevent race conditions
        """
        if not self._updating:
            self.emit('track-changed', self.get_active_track())

    def on_format_changed(self, formatter, format):
        """
            Updates the track list
            on track title format changes
        """
        self.update_track_list()

    def on_playlist_current_changed(self, event, playlist, track):
        """
            Updates the currently selected track
        """
        self.set_active_track(track)

    def on_tracks_added(self, event, playlist, tracks):
        """
            Triggers update of the track list on track addition
        """
        if self.get_toplevel().get_property('visible'):
            self.update_track_list(playlist, tracks)
        else:
            self._dirty = True

    def on_tracks_removed(self, event, playlist, (start, end, removed)):
        """
            Triggers update of the track list on track removal
        """
        if self.get_toplevel().get_property('visible'):
            self.update_track_list(playlist)
        else:
            self._dirty = True

    def on_tracks_reordered(self, event, playlist, tracks):
        """
            Triggers update of the track list on track reordering
        """
        if self.get_toplevel().get_property('visible'):
            self.update_track_list(playlist, tracks)
        else:
            self._dirty = True

    def on_playlist_notebook_switch(self, notebook, page, page_num):
        """
            Updates the internal playlist
        """
        if self.get_toplevel().get_property('visible'):
            page = notebook.get_nth_page(page_num)
            if page is not None:
                self.update_track_list(page.playlist)
        else:
            self._dirty = True

gobject.type_register(TrackSelector)
gobject.signal_new('track-changed', TrackSelector,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_PYOBJECT, ))

class ProgressBar(gtk.Alignment):
    """
        Wrapper class which updates itself
        based on the current track
    """
    def __init__(self, player, callback):
        gtk.Alignment.__init__(self)
        self.set_padding(3, 3, 0, 0)

        self.bar = gtk.ProgressBar()
        self.bar.set_size_request(150, -1)
        self.add(self.bar)

        self.player = player
        self._timer = None
        self._press_event = None
        self.update_state()

        self.bar.add_events(gtk.gdk.BUTTON_PRESS_MASK |
            gtk.gdk.BUTTON_RELEASE_MASK |
            gtk.gdk.POINTER_MOTION_MASK)

        self._track_seeked_id = self.connect('track-seeked',
            callback)
        self._button_press_event_id = self.bar.connect('button-press-event',
            self.on_button_press)
        self._button_release_event_id = self.bar.connect('button-release-event',
            self.on_button_release)
        self._motion_notify_event_id = self.bar.connect('motion-notify-event',
            self.on_motion_notify)

        event.add_callback(self.on_playback_state_change, 'playback_track_start')
        event.add_callback(self.on_playback_state_change, 'playback_toggle_pause')
        event.add_callback(self.on_playback_state_change, 'playback_track_end')

    def destroy(self):
        """
            Various cleanups
        """
        event.remove_callback(self.on_playback_state_change, 'playback_track_start')
        event.remove_callback(self.on_playback_state_change, 'playback_toggle_pause')
        event.remove_callback(self.on_playback_state_change, 'playback_track_end')

        self.disconnect(self._track_seeked_id)
        self.disconnect(self._button_press_event_id)
        self.disconnect(self._button_release_event_id)
        self.disconnect(self._motion_notify_event_id)

        gtk.Alignment.destroy(self)

    def update_state(self):
        """
            Updates the appearance of this progress bar
        """
        fraction = 0.0
        text = _('Not Playing')

        track = self.player.current

        if track is not None:
            total = track.get_tag_raw('__length')
            current = self.player.get_progress() * total
            text = '%d:%02d / %d:%02d' % \
                (current // 60, current % 60,
                 total // 60, total % 60)

            if self.player.is_paused():
                self.disable_timer()
                fraction = self.bar.get_fraction()
            elif self.player.is_playing():
                if track.get_tag_raw('__length'):
                    self.enable_timer()
                    fraction = self.player.get_progress()
                elif not track.is_local():
                    self.disable_timer()
                    text = _('Streaming...')

        self.bar.set_fraction(fraction)
        self.bar.set_text(text)
        return True

    def enable_timer(self):
        """
            Enables the timer, if not already
        """
        if self._timer is not None:
            return

        milliseconds = settings.get_option('gui/progress_update/millisecs', 1000)

        if milliseconds % 1000 == 0:
            self._timer = gobject.timeout_add_seconds(milliseconds / 1000,
                self.update_state)
        else:
            self._timer = gobject.timeout_add(milliseconds,
                self.update_state)

    def disable_timer(self):
        """
            Disables the timer, if not already
        """
        if self._timer is None:
            return

        gobject.source_remove(self._timer)
        self._timer = None

    def on_playback_state_change(self, event, player, track):
        """
            Updates appearance on playback state change
        """
        self.update_state()

    def on_button_press(self, widget, event):
        """
            Prepares seeking
        """
        if self.player.current is None:
            return True

        if not self.player.current.is_local() and \
           not self.player.current.get_tag_raw('__length'):
            return True

        if event.button == 1:
            self._press_event = event.copy()

    def on_button_release(self, widget, event):
        """
            Completes seeking and emits
            the 'track-seeked' event
        """
        if self._press_event is None:
            return True

        posx, posy, width, height = self.bar.get_allocation()
        event.x = float(max(0, event.x))
        event.x = float(min(event.x, width - 1))

        self.bar.set_fraction(event.x / width)
        self.emit('track-seeked', event.x / width)

        self._press_event = None
        self.enable_timer()

    def on_motion_notify(self, widget, event):
        """
            Visually changes the current seeking
            status in the progress bar
        """
        if self._press_event is None:
            return True

        posx, posy, width, height = self.bar.get_allocation()
        event.x = float(max(0, event.x))
        event.x = float(min(event.x, width))

        if event.x == self._press_event.x:
            return True

        self.disable_timer()

        total = self.player.current.get_duration()
        seekpos = (event.x / width) * total
        text = _('Seeking: ')
        text += '%d:%02d' % (seekpos // 60, seekpos % 60)

        self.bar.set_fraction(event.x / width)
        self.bar.set_text(text)

gobject.type_register(ProgressBar)
gobject.signal_new('track-seeked', ProgressBar,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_FLOAT, ))

class PlaylistProgressBar(gtk.HBox):
    """
        A progress bar with a button for
        management of the current playlist
    """
    def __init__(self, main, queue, player, playlist, formatter,
            change_callback, seeked_callback):
        # button, bar
        #button = PlaylistButton(main, queue, playlist, formatter, change_callback)
        #self.pack_start(button, expand=False)
        pass

class TrackBar(TrackSelector, ProgressBar):
    """
        Track selector + progress bar = WIN
    """
    pass

class TrackFormatter(gobject.GObject):
    """
        Formats track titles based on a format string
    """
    __gsignals__ = {
        'format-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,))
    }

    def __init__(self, format):
        gobject.GObject.__init__(self)

        self._format = format
        self._template = Template(self._format)
        self._substitutions = {
            'tracknumber': 'tracknumber',
            'title': 'title',
            'artist': 'artist',
            'composer': 'composer',
            'album': 'album',
            'length': '__length',
            'discnumber': 'discnumber',
            'rating': '__rating',
            'date': 'date',
            'genre': 'genre',
            'bitrate': '__bitrate',
            'location': '__location',
            'filename': 'filename',
            'playcount': '__playcount',
            'last_played': '__last_played',
            'bpm': 'bpm',
        }
        self._formattings = {
            'tracknumber': self.__format_tracknumber,
            'length': self.__format_length,
            'rating': self.__format_rating,
            'bitrate': self.__format_bitrate,
            'last_played': self.__format_last_played,
        }
        self._rating_steps = 5.0

    def set_format(self, format):
        """
            Updates the internal template
        """
        if format == self._format:
            return

        self._format = format
        self._template = Template(self._format)
        self.emit('format-changed', self._format)

    def set_rating_steps(self, rating_steps):
        """
            Updates the rating steps
        """
        if rating_steps == self._rating_steps:
            return

        self._rating_steps = rating_steps
        rating_pattern = '%s%s' % (self._template.delimiter, 'rating')

        if rating_pattern in self._format:
            self.emit('format-changed', self._format)

    def format(self, track):
        """
            Returns the formatted title of a track
        """
        if not isinstance(track, Track):
            return None

        substitutions = self._substitutions.copy()

        for keyword, tagname in substitutions.iteritems():
            substitutions[keyword] = track.get_tag_display(tagname,
                artist_compilations=False)

            try:
                format_callback = self._formattings[keyword]
                substitutions[keyword] = format_callback(substitutions[keyword])
            except KeyError:
                pass

            if substitutions[keyword] is None:
                substitutions[keyword] = _('Unknown')

        return self._template.safe_substitute(substitutions)

    def __format_tracknumber(self, tracknumber):
        """
            Returns a properly formatted tracknumber
        """
        try: # Valid number
            tracknumber = '%02d' % int(tracknumber)
        except TypeError: # None
            tracknumber = '00'
        except ValueError: # 'N/N'
            pass

        return tracknumber

    def __format_length(self, length):
        """
            Returns a properly formatted track length
        """
        try:
            length = float(length)
        except TypeError:
            length = 0

        return '%d:%02d' % (length // 60, length % 60)

    def __format_rating(self, rating):
        """
            Returns a properly formatted rating
        """
        try:
            rating = float(rating) / 100
        except TypeError:
            rating = 0

        rating *= self._rating_steps

        return '%s%s' % (
            '★' * int(rating),
            '☆' * int(self._rating_steps - rating)
        )

    def __format_bitrate(self, bitrate):
        """
            Returns a properly formatted bitrate
        """
        try:
            bitrate = int(bitrate)
        except TypeError:
            bitrate = 0
        except ValueError:
            return bitrate

        return '%d kbit/s' % (bitrate / 1000)

    def __format_last_played(self, last_played):
        """
            Returns a properly formatted last play time
        """
        text = _('Never')

        try:
            last_played = date.fromtimestamp(last_played)
        except TypeError, ValueError:
            text = _('Never')
        else:
            delta = today - last_played
            if delta.day == 0:
                text = _('Today')
            elif delta.day == 1:
                text = _('Yesterday')
            else:
                text = _('%(year)d-%(month)02d-%(day)02d') % {
                    'year': last_played.year,
                    'month': last_played.month,
                    'day': last_played.day
                }

        return text

