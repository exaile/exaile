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
from string import Template
from xl import event, settings
from xl.nls import gettext as _
from xl.track import Track
from xlgui.guiutil import get_workarea_size
from xlgui.playlist import Playlist

class MenuItem(gtk.ImageMenuItem):
    """
        Convenience wrapper, allows switching to mini mode
    """
    def __init__(self, callback):
        gtk.ImageMenuItem.__init__(self, stock_id='exaile-minimode')
        self.child.set_label(_('Mini Mode'))

        self._callback_id = self.connect('activate', callback)
        event.add_callback(self.on_stock_icon_added, 'stock_icon_added')

    def on_stock_icon_added(self, iconmanager, stock_id):
        """
            Handles deferred icon load
        """
        if stock_id == 'exaile-minimode':
            self.set_image(gtk.gdk.image_new_from_stock(stock_id))
            event.remove_callback(self.on_stock_icon_added, 'stock_icon_added')

    def destroy(self):
        """
            Does cleanup
        """
        self.disconnect(self._callback_id)
        self.image.destroy()
        gtk.ImageMenuItem.destroy(self)

class KeyExistsError(Exception):
    pass

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
        #del self.__widgets[id]
        self.__widgets[id].destroy()
        del self.__widgets[id]

    def get_ids(self):
        """
            Returns all registered IDs
        """
        return self.__register.keys()

    def get_id_iter(self):
        """
            Returns an iterator over
            all registered IDs
        """
        return self.__register.iterkeys()

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

        self.connect('clicked', callback)

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

        self.connect('value-changed', self.on_change)
        self.connect('expose-event', self.on_expose)

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
    def __init__(self, parent, child):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)

        self.set_decorated(False)
        self.set_property('skip-taskbar-hint', True)
        self.set_size_request(350, 400)
        self.add(child)

        self.configure_id = None
        self.parent_widget = parent
        self.parent_widget.connect('realize', self.on_parent_realize)

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
        if self.configure_id is None:
            self.configure_id = parent.get_toplevel().connect(
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
    def __init__(self, main, queue, playlist, change_callback, format_callback=None):
        gtk.ToggleButton.__init__(self, '')

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
        self.formatter = TrackFormatter()
        self.playlist = Playlist(main, queue, playlist)
        self.popup = AttachedWindow(self, self.playlist)

        self._dirty = False
        self._drag_shown = False
        self._parent_hide_id = None
        self._drag_motion_id = None

        try:
            self.formatter.connect('format-request', format_callback)
        except TypeError:
            pass

        self.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            self.playlist.list.targets,
            gtk.gdk.ACTION_COPY |
            gtk.gdk.ACTION_DEFAULT |
            gtk.gdk.ACTION_MOVE)

        self.connect('expose-event', self.on_expose)
        self.connect('track-changed', change_callback)
        self.connect('scroll-event', self.on_scroll)
        self.connect('toggled', self.on_toggled)
        self.connect_object('drag-data-received',
            self.playlist.drag_data_received, self.playlist.list)
        self.connect('drag-leave', self.on_drag_leave)
        self.connect('drag-motion', self.on_drag_motion)
        self.playlist.list.connect('drag-data-received',
            self.on_playlist_drag_data_received)
        self.main.playlist_notebook.connect('switch-page',
            self.on_playlist_notebook_switch)
        event.add_callback(self.on_playlist_current_changed, 'playlist_current_changed')
        event.add_callback(self.on_playback_start, 'playback_player_start')
        event.add_callback(self.on_playback_end, 'playback_player_end')
        event.add_callback(self.on_track_start, 'playback_track_start')
        event.add_callback(self.on_tracks_changed, 'tracks_added')
        event.add_callback(self.on_tracks_changed, 'tracks_removed')
        event.add_callback(self.on_tracks_changed, 'tracks_reordered')

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

    def on_playlist_current_changed(self, event, playlist, track):
        """
            Updates the currently selected track
        """
        if playlist != self.playlist.playlist:
            try:
                pos = self.playlist.playlist.index(track)
            except ValueError:
                return
            self.playlist.playlist.set_current_pos(pos)

    def on_playback_start(self, event, player, track):
        """
            Updates appearance on playback start
        """
        self.set_label(self.formatter.format(track))

    def on_playback_end(self, event, player, track):
        """
            Updates appearance on playback state change
        """
        self.set_label('')

    def on_track_start(self, event, player, track):
        """
            Updates the cursor position
        """
        if track in self.playlist.playlist.ordered_tracks:
            path = (self.playlist.playlist.index(track),)
        
            if settings.get_option('gui/ensure_visible', True):
                self.playlist.list.scroll_to_cell(path)

            gobject.idle_add(self.playlist.list.set_cursor, path)

    def on_tracks_changed(self, event, playlist, *args):
        """
            Updates the local playlist as well as the
            currently selected playlist in the main window
        """
        tracks = playlist.get_tracks()

        if playlist == self.playlist.playlist:
            self.main.get_selected_playlist()._set_tracks(tracks)
            self.main.get_selected_playlist().playlist._set_ordered_tracks(tracks)
        else:
            if self.get_toplevel().get_property('visible'):
                self.update_track_list(tracks)
            else:
                self._dirty = True

    def update_track_list(self, tracks=None):
        """
            Updates track list on exposure
        """
        if tracks is None:
            playlist = self.main.get_selected_playlist().playlist
            tracks = playlist.get_tracks()

        self.playlist._set_tracks(tracks)
        self.playlist.playlist._set_ordered_tracks(tracks)

    def on_parent_hide(self, parent):
        """
            Makes sure to hide the popup
        """
        self.set_active(False)

    def on_expose(self, togglebutton, event):
        """
            Performs deferred tasks
        """
        if self._dirty:
            self.update_track_list()
            self._dirty = False

    def on_scroll(self, togglebutton, event):
        """
            Handles scrolling on the button
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
        page = notebook.get_nth_page(page_num)
        if page is not None:
            tracks = page.playlist.get_tracks()
            self.playlist._set_tracks(tracks)

gobject.type_register(PlaylistButton)
gobject.signal_new('track-changed', PlaylistButton,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_PYOBJECT, ))

class TrackSelector(gtk.ComboBox):
    """
        Control which updates its content automatically
        on playlist actions, track display is configurable
    """
    def __init__(self, main, queue, changed_callback, format_callback=None):
        gtk.ComboBox.__init__(self)

        self.queue = queue
        self.list = gtk.ListStore(gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
        self.formatter = TrackFormatter()
        self._updating = False
        self._dirty = False
        #self._changed_callback = changed_callback

        self.set_model(self.list)
        self.set_size_request(150, 0)

        textrenderer = gtk.CellRendererText()
        self.pack_start(textrenderer, expand=True)
        self.set_cell_data_func(textrenderer, self.text_data_func)

        try:
            self.formatter.connect('format-request', format_callback)
        except TypeError:
            pass

        self.update_track_list(self.queue.current_playlist)

        self.connect('expose-event', self.on_expose)
        self.connect('changed', self.on_change)
        self.connect('track-changed', changed_callback)
        main.playlist_notebook.connect('switch-page',
            self.on_playlist_notebook_switch)
        event.add_callback(self.on_playlist_current_changed, 'playlist_current_changed')
        event.add_callback(self.on_tracks_added, 'tracks_added')
        event.add_callback(self.on_tracks_removed, 'tracks_removed')
        event.add_callback(self.on_tracks_reordered, 'tracks_reordered')

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
        title = model.get_value(iter, 1)

        if title is None:
            return

        cell.set_property('text', title)

        active_iter = self.get_active_iter()

        if active_iter is not None:
            track = model.get_value(iter, 0)
            active_track = model.get_value(active_iter, 0)
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
            #self._changed_callback(*e)
            self.emit('track-changed', self.get_active_track())

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

        self.connect('track-seeked', callback)

        event.add_callback(self.on_playback_state_change, 'playback_player_start')
        event.add_callback(self.on_playback_state_change, 'playback_toggle_pause')
        event.add_callback(self.on_playback_state_change, 'playback_player_end')

        self.bar.add_events(gtk.gdk.BUTTON_PRESS_MASK |
            gtk.gdk.BUTTON_RELEASE_MASK |
            gtk.gdk.POINTER_MOTION_MASK)

        self.bar.connect('button-press-event', self.on_button_press)
        self.bar.connect('button-release-event', self.on_button_release)
        self.bar.connect('motion-notify-event', self.on_motion_notify)

    def update_state(self):
        """
            Updates the appearance of this progress bar
        """
        fraction = 0.0
        text = _('Not Playing')

        track = self.player.current

        if track is not None:
            total = track.get_duration()
            current = self.player.get_progress() * total
            text = '%d:%02d / %d:%02d' % \
                (current // 60, current % 60,
                 total // 60, total % 60)

            if self.player.is_paused():
                self.disable_timer()
                fraction = self.bar.get_fraction()
            elif self.player.is_playing():
                if track['__length']:
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

        self._timer = gobject.timeout_add(1000, self.update_state)

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
           not self.player.current['__length']:
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
        'format-request': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_STRING, ()),
        'rating-steps-request': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_INT, ()),
    }

    def __init__(self):
        gobject.GObject.__init__(self)

        self._format = '$tracknumber - $title'
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

    def format(self, track):
        """
            Returns the formatted title of a track
        """
        if not isinstance(track, Track):
            return None

        template = Template(self.emit('format-request') or self._format)
        text = template.safe_substitute(self.__get_substitutions(track))

        return text

    def __get_substitutions(self, track):
        """
            Returns a map for keyword to tag value mapping
        """
        substitutions = self._substitutions.copy()

        for keyword, tagname in substitutions.iteritems():
            try:
                #TRANSLATORS: String multiple tag values will be joined by
                substitutions[keyword] = _(' & ').join(track[tagname])
            except TypeError:
                substitutions[keyword] = track[tagname]

            try:
                formatter = self._formattings[keyword]
                substitutions[keyword] = formatter(substitutions[keyword])
            except KeyError:
                pass

            if substitutions[keyword] is None:
                substitutions[keyword] = _('Unknown')

        return substitutions

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

        rating_steps = self.emit('rating-steps-request') or self._rating_steps
        rating = rating_steps * rating

        return '%s%s' % (
            '★' * int(rating),
            '☆' * int(rating_steps - rating)
        )

    def __format_bitrate(self, bitrate):
        """
            Returns a properly formatted bitrate
        """
        try:
            bitrate = int(bitrate)
        except TypeError:
            bitrate = 0

        return '%d kbit/s' % (bitrate / 1000)

    def __format_last_played(self, last_played):
        """
            Returns a properly formatted last play time
        """
        text = _('Never')

        if last_played is not None:
            import time
            ct = time.time()
            now = time.localtime(ct)
            yday = time.localtime(ct - 86400)
            ydaytime = time.mktime((yday.tm_year, yday.tm_mon, yday.tm_mday, \
                0, 0, 0, yday.tm_wday, yday.tm_yday, yday.tm_isdst))
            lptime = time.localtime(last_played)
            if now.tm_year == lptime.tm_year and \
               now.tm_mon == lptime.tm_mon and \
               now.tm_mday == lptime.tm_mday:
                text = _('Today')
            elif ydaytime <= last_played:
                text = _('Yesterday')
            else:
                text = _('%(year)d-%(month)02d-%(day)02d') % {
                    'year' : lptime.tm_year,
                    'month' : lptime.tm_mon,
                    'day' : lptime.tm_mday
                }

        return text

