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

import gobject, gtk, pango
from xl import event
from xl.nls import gettext as _

class MMWidget(gtk.Widget):
    """
        Wrapper for gtk.Widget,
        allows for identification of widgets
    """
    def __init__(self, id):
        gtk.Widget.__init__(self)
        self.id = id

class MMBox(gtk.HBox):
    """
        Convenience wrapper around gtk.HBox, allows
        for simple access of contained widgets
    """
    def __init__(self, homogeneous=False, spacing=0):
        gtk.HBox.__init__(self, homogeneous, spacing)

        self._removed_widgets = []

    def pack_start(self, child):
        if not isinstance(child, MMWidget):
            raise TypeError(
                '%s is not instance of %s' % (child, MMWidget))
        gtk.HBox.pack_start(self, child, expand=False, fill=False)

    def __getitem__(self, id):
        """
            Returns a contained widget
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
            Shows a contained widget
        """
        for widget in self._removed_widgets:
            if widget.id == id:
                self.pack_start(widget)
                self._removed_widgets.remove(widget)
                return
        raise KeyError('No widget with id %s' % id)

    def show_all_children(self):
        """
            Shows all contained widgets
        """
        for widget in self:
            self.show_child(widget.id)

    def hide_child(self, id):
        """
            Hides a contained child
        """
        for widget in self:
            if widget.id == id:
                self._removed_widgets.append(widget)
                self.remove(widget)
                return
        raise KeyError('No widget with id %s' % id)

    def hide_all_children(self):
        """
            Hides all contained children
        """
        for widget in self:
            self.hide_child(widget.id)

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

    def set_tooltip_text(self, tooltip_text):
        """
            Convenience wrapper, automatically
            trys a fallback for GTK < 2.12
        """
        try:
            gtk.Button.set_tooltip_text(tooltip_text)
        except:
            tooltip = gtk.Tooltips()
            tooltip.set_tip(self, tooltip_text)

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

class MMTrackSelector(MMWidget, gtk.ComboBox):
    """
        Wrapper class which updates its content
        automatically on playlist actions
        Track display is configurable
    """
    def __init__(self, queue, callback):
        self.queue = queue
        self.list = gtk.ListStore(gobject.TYPE_PYOBJECT)
        self.render_items = ['tracknumber', '-', 'title']
        self.items_mapping = {
            'length': '__length',
            'rating': '__rating',
            'bitrate': '__bitrate',
            'location': '__loc'
        }
        self.items_fallback = {
            'tracknumber': '',
            'length': '0:00'
        }

        MMWidget.__init__(self, 'track_selector')
        gtk.ComboBox.__init__(self, self.list)
        self.set_size_request(150, 0)

        textrenderer = gtk.CellRendererText()
        self.pack_start(textrenderer, True)
        self.set_cell_data_func(textrenderer, self.text_data_func)

        self.update_track_list()

        self.connect('changed', callback)
        event.add_callback(self.on_playlist_current_changed, 'playlist_current_changed')
        event.add_callback(self.on_tracks_added, 'tracks_added')
        event.add_callback(self.on_tracks_removed, 'tracks_removed')

    def update_track_list(self):
        """
            Populates the track list based
            on the current playlist
        """
        self.list.clear()
        playlist = self.queue.current_playlist
        if playlist is not None:
            tracks = playlist.get_tracks()
            current_track = playlist.get_current()
            for track in tracks:
                iter = self.list.append([track])
                if track == current_track:
                    self.set_active_iter(iter)

    def get_active_track(self):
        """
            Returns the currently selected track
        """
        try:
            iter = self.get_active_iter()
            return self.list.get_value(iter, 0)
        except TypeError:
            return None

    def map_item(self, item):
        """
            Maps items to internal representations
        """
        try:
            return self.items_mapping[item]
        except KeyError:
            return item

    def text_data_func(self, celllayout, cell, model, iter):
        """
            Allows customization of the
            track data to be rendered
        """
        track = model.get_value(iter, 0)

        if track is None:
            return

        render_items = map(self.map_item, self.render_items)
        text = ''
        for item in render_items:
            try:
                try:
                    values = [str(value) for value in track.tags[item]]
                except TypeError:
                    values = [str(track.tags[item])]
                # TRANSLATORS: String multiple tag values will be joined with
                text += _(' & ').join(values)
            except KeyError:
                try:
                    text += self.items_fallback[item]
                except KeyError:
                    text += item
            text += ' '
        cell.set_property('text', text)

        active_iter = self.get_active_iter()

        if active_iter is not None:
            active_track = model.get_value(self.get_active_iter(), 0)

            if track == active_track:
                cell.set_property('weight', pango.WEIGHT_BOLD)
            else:
                cell.set_property('weight', pango.WEIGHT_NORMAL)

        return

    def on_playlist_current_changed(self, event, playlist, track):
        """
            Triggers change of the currently active track
        """
        self.update_track_list()

    def on_tracks_added(self, event, playlist, tracks):
        """
            Triggers update of the track list on track removal
        """
        self.update_track_list()

    def on_tracks_removed(self, event, playlist, (start, end, removed)):
        """
            Triggers update of the track list on track addition
        """
        self.update_track_list()

class MMProgressBar(MMWidget, gtk.ProgressBar):
    """
        Wrapper class which updates itself
        based on the current track
    """
    def __init__(self, player, callback):
        MMWidget.__init__(self, 'progress_bar')
        gtk.ProgressBar.__init__(self)
        self.set_size_request(150, 0)

        self.player = player
        self._timer = None
        self._press_event = None
        self.update_state()

        gobject.type_register(type(self))
        gobject.signal_new('track-seeked', self,
            gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
            (gobject.TYPE_FLOAT, ))

        self.connect('track-seeked', callback)

        event.add_callback(self.on_playback_state_change, 'playback_player_start')
        event.add_callback(self.on_playback_state_change, 'playback_toggle_pause')
        event.add_callback(self.on_playback_state_change, 'playback_player_end')

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK |
            gtk.gdk.BUTTON_RELEASE_MASK |
            gtk.gdk.POINTER_MOTION_MASK)

        self.connect('button-press-event', self.on_button_press)
        self.connect('button-release-event', self.on_button_release)
        self.connect('motion-notify-event', self.on_motion_notify)

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
                fraction = self.get_fraction()
            elif self.player.is_playing():
                if track.is_local() and track['__length']:
                    self.enable_timer()
                    fraction = self.player.get_progress()
                else:
                    self.disable_timer()
                    text = _('Streaming...')

        self.set_fraction(fraction)
        self.set_text(text)
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

        posx, posy, width, height = self.get_allocation()
        event.x = float(max(0, event.x))
        event.x = float(min(event.x, width - 1))

        self.set_fraction(event.x / width)
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

        posx, posy, width, height = self.get_allocation()
        event.x = float(max(0, event.x))
        event.x = float(min(event.x, width))

        if event.x == self._press_event.x:
            return True

        self.disable_timer()

        total = self.player.current.get_duration()
        seekpos = (event.x / width) * total
        text = _('Seeking:')
        text += '%d:%02d' % (seekpos // 60, seekpos % 60)

        self.set_fraction(event.x / width)
        self.set_text(text)

class MMTrackBar(MMTrackSelector, MMProgressBar):
    """
        Track selector + progress bar = WIN
    """
    pass
