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
from xl import event
from xl.track import Track
from xl.nls import gettext as _
from xlgui.playlist import Playlist
from minimodeprefs import get_workarea_size

class MMMenuItem(gtk.ImageMenuItem):
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

class MMBox(gtk.HBox):
    """
        Convenience wrapper around gtk.HBox, allows
        for simple access of contained widgets
    """
    def __init__(self, homogeneous=False, spacing=0):
        gtk.HBox.__init__(self, homogeneous, spacing)

        self._removed_widgets = []

    def pack_start(self, child):
        """
            Inserts a child into this box
        """
        if not isinstance(child, MMWidget):
            raise TypeError(
                '%s is not instance of %s' % (child, MMWidget))
        gtk.HBox.pack_start(self, child, expand=False, fill=False)

    def __getitem__(self, id):
        """
            Returns a contained child
        """
        all_widgets = []
        all_widgets += [widget for widget in self]
        all_widgets += self._removed_widgets
        for widget in all_widgets:
            if widget.id == id:
                return widget
        raise KeyError

    def show_child(self, id):
        """
            Shows a contained child
        """
        for widget in self._removed_widgets:
            if widget.id == id:
                self.pack_start(widget)
                self._removed_widgets.remove(widget)
                return
        raise KeyError('No widget with id %s' % id)

    def show_all_children(self):
        """
            Shows all contained children
        """
        for widget in self.get_children():
            self.show_child(widget.id)

    def hide_child(self, id):
        """
            Hides a contained child
        """
        for widget in self.get_children():
            if widget.id == id:
                self._removed_widgets.append(widget)
                self.remove(widget)
                return
        raise KeyError('No widget with id %s' % id)

    def hide_all_children(self):
        """
            Hides all contained children
        """
        for widget in self.get_children():
            self.hide_child(widget.id)

class MMWidget(gtk.Widget):
    """
        Wrapper for gtk.Widget,
        allows for identification of widgets
    """
    def __init__(self, id):
        gtk.Widget.__init__(self)
        self.id = id

class MMButton(MMWidget, gtk.Button):
    """
        Convenience wrapper around gtk.Button
    """
    def __init__(self, id, stock_id, tooltip_text, callback):
        MMWidget.__init__(self, id)
        gtk.Button.__init__(self)

        self.image = gtk.image_new_from_stock(stock_id, gtk.ICON_SIZE_BUTTON)
        self.set_image(self.image)
        self.set_tooltip_text(tooltip_text)
        self.set_relief(gtk.RELIEF_NONE)

        self.connect('clicked', callback)

class MMPlayPauseButton(MMButton):
    """
        Special MMButton which automatically sets its
        appearance depending on the current playback state
    """
    def __init__(self, player, callback):
        MMButton.__init__(self, 'play_pause', 'gtk-media-play',
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

class MMVolumeButton(MMWidget, gtk.VolumeButton):
    """
        Wrapper class around gtk.VolumeButton
    """
    def __init__(self, player, callback):
        MMWidget.__init__(self, 'volume')
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

class MMPlaylistButton(MMWidget, gtk.ToggleButton):
    """
        Displays the current track title and
        the current playlist on activation
    """
    def __init__(self, main, queue, playlist, change_callback, format_callback=None):
        MMWidget.__init__(self, 'playlist_button')
        gtk.ToggleButton.__init__(self, '')

        self.set_size_request(150, -1)
        self.get_child().set_property('ellipsize', pango.ELLIPSIZE_END)

        self.main = main
        self.queue = queue
        self.formatter = MMTrackFormatter()
        self.popup = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.popup.set_decorated(False)
        self.popup.set_size_request(350, 400)
        self.playlist = Playlist(main, queue, playlist)
        self.popup.add(self.playlist)

        self._updating = False
        self._parent_configure_id = None
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

        self.connect('track-changed', change_callback)
        self.connect('scroll-event', self.on_scroll)
        self.connect('toggled', self.on_toggled)
        self.connect_object('drag-data-received',
            self.playlist.drag_data_received, self.playlist.list)
        self.connect('drag-leave', self.on_drag_leave)
        self.connect('drag-motion', self.on_drag_motion)
        event.add_callback(self.on_playlist_current_changed, 'playlist_current_changed')
        event.add_callback(self.on_playback_start, 'playback_player_start')
        event.add_callback(self.on_playback_end, 'playback_player_end')
        event.add_callback(self.on_tracks_changed, 'tracks_added')
        event.add_callback(self.on_tracks_changed, 'tracks_removed')
        event.add_callback(self.on_tracks_changed, 'tracks_reordered')

    def move_popup(self):
        """
            Makes sure the popup is always fully visible
        """
        workarea_width, workarea_height = get_workarea_size() # 1280, 974
        popup_width, popup_height = self.popup.size_request() #  350, 400
        buttonx, buttony, button_width, button_height = self.get_allocation()
        parentx, parenty = self.get_window().get_origin()
        buttonx, buttony = parentx + buttonx, parenty + buttony

        # E.g.       1280 - 1000    < 350
        if workarea_width - buttonx < popup_width:
            #           1000 + 150          - 350 = 800
            popupx = buttonx + button_width - popup_width # Aligned right
        else:
            popupx = buttonx # Aligned left

        # E.g.         974 - 800     < 400
        if workarea_height - buttony < popup_height:
            #            800 - 400 = 400 
            popupy = buttony - popup_height # Aligned top
        else:
            popupy = buttony + button_height # Aligned bottom

        self.popup.move(popupx, popupy)

    def set_tracks(self, tracks):
        """
            Replaces the tracks of the playlist
        """
        self.playlist._set_tracks(tracks)

    def on_playlist_current_changed(self, event, playlist, track):
        """
            Updates the currently selected track
        """
        pos = self.playlist.playlist.index(track)
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

    def on_tracks_changed(self, event, playlist, *args):
        """
            Updates the local playlist as well as the
            currently selected playlist in the main window
        """
        if playlist == self.playlist.playlist:
            tracks = self.playlist.playlist.get_tracks()
            self.main.get_selected_playlist()._set_tracks(tracks)
            self.main.get_selected_playlist().playlist._set_ordered_tracks(tracks)
        else:
            tracks = playlist.get_tracks()
            self.playlist._set_tracks(tracks)
            self.playlist.playlist._set_ordered_tracks(tracks)

    def on_parent_configure(self, *e):
        """
            Passes parent window movement to the popup
        """
        self.move_popup()

    def on_parent_hide(self, parent):
        """
            Makes sure to hide the popup
        """
        self.set_active(False)
        self.popup.hide()

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

        if self._parent_configure_id is None:
            self._parent_configure_id = self.get_toplevel().connect(
                'configure-event', self.on_parent_configure)

        if self._parent_hide_id is None:
            self._parent_hide_id = self.get_toplevel().connect(
                'hide', self.on_parent_hide)

        if self.get_active():
            self.move_popup()
            self.popup.show()
        else:
            self.popup.hide()

    def on_drag_data_received(self, togglebutton, context, x, y, selection, info, timestamp):
        """
            Appends tracks to the playlist if
            dropped on the button itself
        """
        print selection.get_uris()

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
            Callback function for showing the playlist
        """
        self.set_active(True)

gobject.type_register(MMPlaylistButton)
gobject.signal_new('track-changed', MMPlaylistButton,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_PYOBJECT, ))

class MMTrackSelector(MMWidget, gtk.ComboBox):
    """
        Control which updates its content automatically
        on playlist actions, track display is configurable
    """
    def __init__(self, queue, changed_callback, format_callback=None):
        MMWidget.__init__(self, 'track_selector')
        gtk.ComboBox.__init__(self)

        self.queue = queue
        self.list = gtk.ListStore(gobject.TYPE_PYOBJECT, gobject.TYPE_STRING)
        self.formatter = MMTrackFormatter()
        self._updating = False
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

        self.connect('changed', self.on_change)
        self.connect('track-changed', changed_callback)
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
            #ellipsize = pango.ELLIPSIZE_NONE
            weight = pango.WEIGHT_NORMAL

            if self.get_property('popup-shown'):
                if track == active_track:
                    weight = pango.WEIGHT_BOLD
            #else:
            #    ellipsize = pango.ELLIPSIZE_END

            #cell.set_property('ellipsize', ellipsize)
            cell.set_property('weight', weight)

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
        self.update_track_list(playlist, tracks)

    def on_tracks_removed(self, event, playlist, (start, end, removed)):
        """
            Triggers update of the track list on track removal
        """
        self.update_track_list(playlist)

    def on_tracks_reordered(self, event, playlist, tracks):
        """
            Triggers update of the track list on track reordering
        """
        self.update_track_list(playlist, tracks)

gobject.type_register(MMTrackSelector)
gobject.signal_new('track-changed', MMTrackSelector,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_PYOBJECT, ))

class MMProgressBar(MMWidget, gtk.Alignment):
    """
        Wrapper class which updates itself
        based on the current track
    """
    def __init__(self, player, callback):
        MMWidget.__init__(self, 'progress_bar')
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
                if track.is_local() and track['__length']:
                    self.enable_timer()
                    fraction = self.player.get_progress()
                else:
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

gobject.type_register(MMProgressBar)
gobject.signal_new('track-seeked', MMProgressBar,
    gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
    (gobject.TYPE_FLOAT, ))

class MMTrackBar(MMTrackSelector, MMProgressBar):
    """
        Track selector + progress bar = WIN
    """
    pass

class MMTrackFormatter(gobject.GObject):
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
            'playcount': 'playcount',
            'bpm': 'bpm',
        }
        self._formattings = {
            'tracknumber': self.__format_tracknumber,
            'length': self.__format_length,
            'rating': self.__format_rating,
            'bitrate': self.__format_bitrate,
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


