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

import glib
import gtk
import logging
import pango

from xl import (
    event,
    player,
    providers,
    settings
)
from xl.formatter import (
    Formatter,
    TrackFormatter,
    ProgressTextFormatter
)
from xl.player.adapters import (
    PlaybackAdapter,
    QueueAdapter
)
from xl.nls import gettext as _
from xlgui.guiutil import gtk_widget_replace
from xlgui.widgets.common import AttachedWindow
from xlgui.widgets.info import TrackToolTip
from xlgui.widgets.playback import SeekProgressBar
from xlgui.widgets.playlist import (
    PlaylistModel,
    PlaylistView
)
from xlgui.widgets.rating import RatingWidget

logger = logging.getLogger(__name__)

def suppress(signal):
    """
        Decorator which prevents the emission of a GObject signal
    """
    def wrapper(function):
        def wrapped_function(self, *args, **kwargs):
            def on_event(sender, *args):
                sender.stop_emission(signal)
                return True

            handler_id = self.connect(signal, on_event)
            function(self, *args, **kwargs)
            self.disconnect(handler_id)
        return wrapped_function
    return wrapper

class ControlBox(gtk.HBox, providers.ProviderHandler):
    """
        A box for minimode controls which
        updates itself based on settings
    """
    __gsignals__ = {'show': 'override'}

    def __init__(self):
        gtk.HBox.__init__(self)
        providers.ProviderHandler.__init__(self, 'minimode-controls')

        self.__dirty = True
        self.__controls = {}

        event.add_callback(self.on_option_set,
            'plugin_minimode_option_set')

    def destroy(self):
        """
            Cleanups
        """
        for control in self.__controls.itervalues():
            control.destroy()

    def __contains__(self, item):
        """
            Allows for checking for control ids
        """
        if item in self.__controls:
            return True
        
        return False

    def __getitem__(self, name):
        """
            Returns the control specified by name
        """
        return self.__controls[name]

    def __setitem__(self, name, control):
        """
            Sets the control specified by name
        """
        if name in self.__controls:
            self.remove(self.__controls[name])
            del self.__controls[name]

        self.__controls[name] = control
        self.pack_start(control, False)
        control.show_all()

    def __delitem__(self, name):
        """
            Destroys the control specified by name
        """
        self.__controls[name].destroy()
        del self.__controls[name]

    def update(self):
        """
            Updates the controls to display
        """
        selected_controls = settings.get_option(
            'plugin/minimode/selected_controls',
            ['previous', 'play_pause', 'next', 'playlist_button',
             'progress_bar', 'restore'])

        added_controls = [c for c in selected_controls \
            if c not in self]

        for name in added_controls:
            try:
                provider = self.get_provider(name)()
            except Exception: # Not found, initialization error, ...
                import traceback
                traceback.print_exc()
                logger.warning('Failed to add control provider "%s"' % name)
                selected_controls.remove(name)
            else:
                self[name] = provider

        removed_controls = [c.name for c in self \
            if c.name not in selected_controls]

        for name in removed_controls:
            del self[name]

        for name in selected_controls:
            self.reorder_child(self[name], -1)

    def do_show(self):
        """
            Updates the appearance if
            settings have been changed
        """
        if self.__dirty:
            self.update()
            self.__dirty = False

        gtk.HBox.do_show(self)

    def on_provider_removed(self, provider):
        """
            Removes controls on provider removal
        """
        if provider.name in self:
            del self[provider.name]

    def on_option_set(self, event, settings, option):
        """
            Flags changes
        """
        if option == 'plugin/minimode/selected_controls':
            if self.props.visible:
                glib.idle_add(self.update)
            else:
                self.__dirty = True

# Control definitions
class BaseControl(object):
    """
        Base control provider
    """
    name = None
    title = None
    description = None
    fixed = False

class ButtonControl(gtk.Button, BaseControl):
    """
        Basic button control
    """
    __gsignals__ = {'clicked': 'override'}

    def __init__(self):
        gtk.Button.__init__(self)
        BaseControl.__init__(self)

        self.set_image(gtk.Image())
        self.set_relief(gtk.RELIEF_NONE)
        self.set_focus_on_click(False)

    def set_image_from_stock(self, stock_id):
        """
            Sets the image to the specified stock id

            :param stock_id: 
        """
        self.props.image.set_from_stock(stock_id, gtk.ICON_SIZE_BUTTON)

class PreviousButtonControl(ButtonControl):
    """
        Button which allows for going to the previous track
    """
    name = 'previous'
    title = _('Previous')
    description = _('Go to the previous track')

    def __init__(self):
        ButtonControl.__init__(self)

        self.set_image_from_stock(gtk.STOCK_MEDIA_PREVIOUS)
        self.set_tooltip_text(_('Previous track'))

    def do_clicked(self):
        """
            Goes to the previous track
        """
        player.QUEUE.prev()

class NextButtonControl(ButtonControl):
    """
        Button which allows for going to the next track
    """
    name = 'next'
    title = _('Next')
    description = _('Go to the next track')

    def __init__(self):
        ButtonControl.__init__(self)

        self.set_image_from_stock(gtk.STOCK_MEDIA_NEXT)
        self.set_tooltip_text(_('Next track'))

    def do_clicked(self):
        """
            Goes to the next track
        """
        player.QUEUE.next()

class PlayPauseButtonControl(ButtonControl, PlaybackAdapter):
    """
        Button which allows for starting,
        pausing and resuming of playback
    """
    name = 'play_pause'
    title = _('Play/Pause')
    description = _('Start, pause or resume the playback')

    def __init__(self):
        ButtonControl.__init__(self)
        PlaybackAdapter.__init__(self, player.PLAYER)

        self.update_state()

    def destroy(self):
        """
            Cleanups
        """
        PlaybackAdapter.destroy(self)
        ButtonControl.destroy(self)

    def update_state(self):
        """
            Updates the appearance of this button
        """
        stock_id = gtk.STOCK_MEDIA_PLAY
        tooltip_text = _('Start playback')

        if not player.PLAYER.is_stopped():
            if player.PLAYER.is_paused():
                tooltip_text = _('Continue playback')
            elif player.PLAYER.is_playing():
                stock_id = gtk.STOCK_MEDIA_PAUSE
                tooltip_text = _('Pause playback')

        glib.idle_add(self.set_image_from_stock, stock_id)
        glib.idle_add(self.set_tooltip_text, tooltip_text)

    def do_clicked(self):
        """
            Starts, pauses or resumes the playback
        """
        if player.PLAYER.is_stopped():
            player.QUEUE.play()
        else:
            player.PLAYER.toggle_pause()

    def on_playback_track_start(self, event, player, track):
        """
            Updates state
        """
        self.update_state()

    def on_playback_player_end(self, event, player, track):
        """
            Updates state
        """
        self.update_state()

    def on_playback_toggle_pause(self, event, player, track):
        """
            Updates state
        """
        self.update_state()

class StopButtonControl(ButtonControl):
    """
        Button which allows for stopping the playback
        and toggling the SPAT feature
    """
    name = 'stop'
    title = _('Stop')
    description = _('Stop the playback')
    __gsignals__ = {
        'motion-notify-event': 'override',
        'leave-notify-event': 'override',
        'focus-out-event': 'override',
        'key-press-event': 'override',
        'key-release-event': 'override'
    }

    def __init__(self):
        ButtonControl.__init__(self)

        self.set_image_from_stock(gtk.STOCK_MEDIA_STOP)
        self.set_tooltip_text(_('Stop playback'))

        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK |
                        gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.KEY_PRESS_MASK |
                        gtk.gdk.KEY_RELEASE_MASK)

        self._queue_spat = False
        self._hovered = False

    def update_state(self):
        """
            Updates the appearance of this button
        """
        stock_id = gtk.STOCK_MEDIA_STOP
        tooltip_text = _('Stop playback')

        if self._queue_spat:
            stock_id = gtk.STOCK_STOP

            if player.QUEUE.current_playlist.spat_position > 0:
                tooltip_text = _('Continue playback after current track')
            else:
                tooltip_text = _('Stop playback after current track')

        self.set_image_from_stock(stock_id)
        self.set_tooltip_text(tooltip_text)

    def do_clicked(self):
        """
            Stops the playback
        """
        player.PLAYER.stop()

    def do_motion_notify_event(self, event):
        """
            Indicates SPAT
        """
        if event.state & gtk.gdk.SHIFT_MASK:
            self._queue_spat = True
            self.update_state()

        self._hovered = True

    def do_leave_notify_event(self, event):
        """
            Returns to regular state
        """
        if self._queue_spat and not self.is_focus():
            self._queue_spat = False
            self.update_state()

        self._hovered = False

        ButtonControl.do_leave_notify_event(self, event)

    def do_focus_out_event(self, event):
        """
            Returns to regular state
        """
        if not self._hovered:
            self._queue_spat = False
            self.update_state()

    def do_key_press_event(self, event):
        """
            Indicates SPAT
        """
        if event.keyval in (gtk.keysyms.Shift_L, gtk.keysyms.Shift_R):
            self._queue_spat = True
            self.update_state()

    def do_key_release_event(self, event):
        """
            Returns to regular state
        """
        if event.keyval in (gtk.keysyms.Shift_L, gtk.keysyms.Shift_R):
            self._queue_spat = False
            self.update_state()

class VolumeButtonControl(gtk.VolumeButton, BaseControl):
    """
        Button which allows for changing the volume
    """
    name = 'volume'
    title = _('Volume')
    description = _('Change the volume')
    __gsignals__ = {'value-changed': 'override'}

    def __init__(self):
        gtk.VolumeButton.__init__(self)
        BaseControl.__init__(self)

        adjustment = gtk.Adjustment(upper=1, step_incr=0.1, page_incr=0.2)
        self.set_adjustment(adjustment)

        # Slightly beautify the control buttons
        plus_button = self.get_plus_button()
        plus_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON))
        plus_button.set_label('')
        minus_button = self.get_minus_button()
        minus_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_REMOVE, gtk.ICON_SIZE_BUTTON))
        minus_button.set_label('')

        event.add_callback(self.on_option_set, 'player_option_set')
        self.on_option_set('player_option_set', settings, 'player/volume')

    def destroy(self):
        """
            Cleanups
        """
        event.remove_callback(self.on_option_set, 'player_option_set')

        ButtonControl.destroy(self)
        gtk.VolumeButton.destroy(self)

    def set_value(self, value):
        """
            Override to take care of preventing
            signal handling and endless loops
        """
        self.set_data('updating', True)
        gtk.VolumeButton.set_value(self, value)
        self.set_data('updating', False)

    def do_value_changed(self, value):
        """
            Changes the volume except if done internally
        """
        if not self.get_data('updating'):
            settings.set_option('player/volume', value)

    def on_option_set(self, event, settings, option):
        """
            Reflects external volume changes
        """
        if option == 'player/volume':
            glib.idle_add(self.set_value,
                float(settings.get_option(option)))

class RestoreButtonControl(ButtonControl):
    """
        Button which allows for restoring the main window
    """
    name = 'restore'
    title = _('Restore')
    description = _('Restore the main window')
    fixed = True
    __gsignals__ = {'hierarchy-changed': 'override'}

    def __init__(self):
        ButtonControl.__init__(self)

        self.set_image_from_stock(gtk.STOCK_LEAVE_FULLSCREEN)
        self.set_tooltip_text(_('Restore main window'))

    def do_clicked(self):
        """
            Restores the main window
        """
        self.get_toplevel().set_active(False)

    def do_hierarchy_changed(self, previous_toplevel):
        """
            Sets up accelerators
        """
        accel_group = gtk.AccelGroup()

        try:
            self.get_toplevel().add_accel_group(accel_group)
        except AttributeError:
            pass
        else:
            key, modifier = gtk.accelerator_parse('<Control><Alt>M')
            self.add_accelerator('clicked', accel_group, key, modifier,
                gtk.ACCEL_VISIBLE)

class RatingControl(RatingWidget, BaseControl):
    """
        Control which allows for viewing and
        changing the rating of the current track
    """
    name = 'rating'
    title = _('Rating')
    description = _('Select rating of the current track')

    def __init__(self):
        RatingWidget.__init__(self, player=player.PLAYER)
        BaseControl.__init__(self)

    def do_rating_changed(self, rating):
        """
            Updates the rating of the currently playing track
        """
        if player.PLAYER.current is not None:
            player.PLAYER.current.set_rating(rating)
            maximum = settings.get_option('rating/maximum', 5)
            event.log_event('rating_changed', self, rating / maximum * 100)

class TrackSelectorControl(gtk.ComboBox, BaseControl, QueueAdapter):
    name = 'track_selector'
    title = _('Track selector')
    description = _('Simple track list selector')
    __gsignals__ = {'changed': 'override'}
    
    def __init__(self):
        gtk.ComboBox.__init__(self)
        BaseControl.__init__(self)
        QueueAdapter.__init__(self, player.QUEUE)

        self.formatter = TrackFormatter('')
        self.model = gtk.ListStore(object)
        self.set_model(self.model)

        self.synchronize()

        renderer = gtk.CellRendererText()
        self.pack_start(renderer, expand=True)
        self.set_cell_data_func(renderer, self.data_func)
        self.set_size_request(200, 0)

        event.add_callback(self.on_option_set,
            'plugin_minimode_option_set')
        self.on_option_set('plugin_minimode_option_set', settings,
            'plugin/minimode/track_title_format')

    def destroy(self):
        """
            Cleanups
        """
        QueueAdapter.destroy(self)
        gtk.ComboBox.destroy(self)

    def data_func(self, column, cell, model, iter, user_data):
        """
            Updates track titles and highlights
            the current track if the popup is shown
        """
        track = model.get_value(iter, 0)

        if track is None:
            return

        cell.props.text = self.formatter.format(track)

        active_iter = self.get_active_iter()

        if active_iter is not None:
            active_track = model.get_value(active_iter, 0)
            weight = pango.WEIGHT_NORMAL

            if self.props.popup_shown and track == active_track:
                weight = pango.WEIGHT_BOLD

            cell.props.weight = weight

    @suppress('changed')
    def synchronize(self):
        """
            Synchronizes the model data with
            the current content of the queue
        """
        self.set_model(None)
        self.model.clear()

        for i, track in enumerate(player.QUEUE.current_playlist):
            iter = self.model.append([track])

            if track is player.QUEUE.current_playlist.current:
                # Not using iter since model is detached
                self.set_active(i)

        self.set_model(self.model)

    def do_changed(self):
        """
            Starts playing the selected track. Should only be
            triggered by user action to prevent race conditions
        """
        active_index = self.get_active()

        if active_index > -1:
            player.QUEUE.current_playlist.current_position = active_index
            player.QUEUE.play(player.QUEUE.current_playlist[active_index])

    def add_tracks(self, tracks):
        """
            Adds tracks to the internal storage
        """
        if not tracks:
            return

        self.set_model(None)

        for position, track in tracks:
            self.model.insert(position, [track])

        self.set_model(self.model)

    def remove_tracks(self, tracks):
        """
            Removes tracks from the internal storage
        """
        if not tracks:
            return

        self.set_model(None)
        tracks.reverse()
        
        for position, track in tracks:
            del self.model[position]

        self.set_model(self.model)

    def on_queue_current_playlist_changed(self, event, queue, playlist):
        """
            Updates the list on queue changes
        """
        self.synchronize()

    @suppress('changed')
    def on_queue_current_position_changed(self, event, playlist, positions):
        """
            Updates the list on queue changes
        """
        if positions[0] < 0:
            return

        glib.idle_add(self.set_active, positions[0])

    def on_queue_tracks_added(self, event, queue, tracks):
        """
            Updates the list on queue changes
        """
        glib.idle_add(self.add_tracks, tracks)

    def on_queue_tracks_removed(self, event, queue, tracks):
        """
            Updates the list on queue changes
        """
        glib.idle_add(self.remove_tracks, tracks)

    def on_option_set(self, event, settings, option):
        """
            Updates control upon setting change
        """
        if option == 'plugin/minimode/track_title_format':
            glib.idle_add(self.formatter.set_property,
                'format',
                settings.get_option(option, _('$tracknumber - $title'))
            )

class PlaylistButtonControl(gtk.ToggleButton, BaseControl, QueueAdapter):
    name = 'playlist_button'
    title = _('Playlist button')
    description = _('Access the current playlist')
    __gsignals__ = {'scroll-event': 'override'}
    
    def __init__(self):
        gtk.ToggleButton.__init__(self)
        BaseControl.__init__(self)
        QueueAdapter.__init__(self, player.QUEUE)

        self.set_focus_on_click(False)
        self.set_size_request(200, -1)
        box = gtk.HBox()
        self.arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_OUT)
        box.pack_start(self.arrow, expand=False)
        self.label = gtk.Label('')
        self.label.props.ellipsize = pango.ELLIPSIZE_END
        box.pack_start(self.label)
        self.add(box)

        self.formatter = TrackFormatter(
            settings.get_option('plugin/minimode/track_title_format',
                                '$tracknumber - $title'))

        self.view = PlaylistView(player.QUEUE.current_playlist, player.PLAYER)
        self.popup = AttachedWindow(self)
        self.popup.set_default_size(
            settings.get_option('plugin/minimode/'
                'playlist_button_popup_width', 350),
            settings.get_option('plugin/minimode/'
                'playlist_button_popup_height', 400)
        )
        scrollwindow = gtk.ScrolledWindow()
        scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrollwindow.set_shadow_type(gtk.SHADOW_IN)
        scrollwindow.add(self.view)
        self.popup.add(scrollwindow)
        self.popup.connect('configure-event', self.on_popup_configure_event)

        accel_group = gtk.AccelGroup()
        key, modifier = gtk.accelerator_parse('<Control>J')
        accel_group.connect_group(key, modifier, gtk.ACCEL_VISIBLE,
            self.on_accelerator_activate)
        self.popup.add_accel_group(accel_group)

        self.tooltip = TrackToolTip(self, player.PLAYER)
        self.tooltip.set_auto_update(True)

        if player.PLAYER.current is not None:
            self.label.set_text(self.formatter.format(player.PLAYER.current))

        self._drag_motion_timeout_id = None
        self._drag_leave_timeout_id = None
        self._toplevel_hide_id = None
        self._toplevel_window_state_event_id = None

        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.view.targets,
            gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_DEFAULT |
            gtk.gdk.ACTION_MOVE)

        self.connect('drag-motion', self.on_drag_motion)
        self.connect('drag-leave', self.on_drag_leave)
        self.connect('drag-data-received', self.on_drag_data_received)
        self.view.connect('drag-motion', self.on_drag_motion)
        self.view.connect('drag-leave', self.on_drag_leave)
        event.add_callback(self.on_track_tags_changed,
            'track_tags_changed')
        event.add_callback(self.on_option_set,
            'plugin_minimode_option_set')
        self.on_option_set('plugin_minimode_option_set', settings,
            'plugin/minimode/track_title_format')

    def destroy(self):
        """
            Cleanups
        """
        self.tooltip.destroy()
        QueueAdapter.destroy(self)
        gtk.ToggleButton.destroy(self)

    def update_playlist(self, playlist):
        """
            Updates the internally stored playlist
        """
        columns = self.view.get_model().columns
        model = PlaylistModel(playlist, columns, player.PLAYER)
        self.view.set_model(model)

    def do_hierarchy_changed(self, previous_toplevel):
        """
            Sets up automatic hiding on parent hide
        """
        if self._toplevel_hide_id is not None:
            previous_toplevel.disconnect(
                self._toplevel_hide_id)
            previous_toplevel.disconnect(
                self._toplevel_window_state_event_id)

        toplevel = self.get_toplevel()

        if isinstance(toplevel, gtk.Window):
            self._toplevel_hide_id = toplevel.connect(
                'hide', self.on_toplevel_hide)
            self._toplevel_window_state_event_id = toplevel.connect(
                'window-state-event', self.on_toplevel_window_state_event)
            self.popup.set_transient_for(toplevel)

    def do_scroll_event(self, event):
        """
            Changes the current track
        """
        if event.direction == gtk.gdk.SCROLL_UP:
            self.view.playlist.prev()
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            self.view.playlist.next()
        else:
            return

        position = self.view.playlist.current_position

        try:
            track = self.view.playlist[position]
        except IndexError:
            pass
        else:
            player.QUEUE.play(track)

    def do_toggled(self):
        """
            Shows or hides the playlist
        """
        if self.get_active():
            self.arrow.props.arrow_type = gtk.ARROW_DOWN
            self.popup.show_all()
        else:
            self.popup.hide()
            self.arrow.props.arrow_type = gtk.ARROW_RIGHT

    def on_accelerator_activate(self, accel_group, acceleratable,
                                keyval, modifier):
        """
            Shows the current track
        """
        self.view.scroll_to_cell(self.view.playlist.current_position)
        self.view.set_cursor(self.view.playlist.current_position)

    def on_drag_motion(self, widget, context, x, y, time):
        """
            Prepares to show the playlist
        """
        # Defer display of the playlist
        if self._drag_motion_timeout_id is None:
            self._drag_motion_timeout_id = glib.timeout_add(
                500, lambda: self.set_active(True))

        # Prevent hiding of the playlist
        if self._drag_leave_timeout_id is not None:
            glib.source_remove(self._drag_leave_timeout_id)
            self._drag_leave_timeout_id = None

    def on_drag_leave(self, widget, context, time):
        """
            Prepares to hide the playlist
        """
        # Enable display of the playlist on re-enter
        if self._drag_motion_timeout_id is not None:
            glib.source_remove(self._drag_motion_timeout_id)
            self._drag_motion_timeout_id = None

        if self._drag_leave_timeout_id is not None:
            glib.source_remove(self._drag_leave_timeout_id)

        # Defer hiding of the playlist
        self._drag_leave_timeout_id = glib.timeout_add(
            500, lambda: self.set_active(False))

    def on_drag_data_received(self, widget, context, x, y,
                              selection, info, time):
        """
            Handles dropped data
        """
        # Enable display of the playlist on re-enter
        if self._drag_motion_timeout_id is not None:
            glib.source_remove(self._drag_motion_timeout_id)
            self._drag_motion_timeout_id = None

        # Enable hiding of the playlist on re-enter
        if self._drag_leave_timeout_id is not None:
            glib.source_remove(self._drag_leave_timeout_id)
            self._drag_leave_timeout_id = None

        self.view.emit('drag-data-received', context, x, y,
            selection, info, time)

    def on_toplevel_hide(self, widget):
        """
            Hides the playlist
        """
        self.set_active(False)

    def on_toplevel_window_state_event(self, widget, event):
        """
            Hides the playlist
        """
        self.set_active(False)

    def on_popup_configure_event(self, widget, event):
        """
            Saves the window size after resizing
        """
        width = settings.get_option('plugin/minimode/'
            'playlist_button_popup_width', 350)
        height = settings.get_option('plugin/minimode/'
            'playlist_button_popup_height', 400)

        if event.width != width:
            settings.set_option('plugin/minimode/'
                'playlist_button_popup_width', event.width)

        if event.height != height:
            settings.set_option('plugin/minimode/'
                'playlist_button_popup_height', event.height)

    def on_queue_current_playlist_changed(self, event, queue, playlist):
        """
            Updates the list on queue changes
        """
        glib.idle_add(self.update_playlist, playlist)

    def on_queue_current_position_changed(self, event, playlist, positions):
        """
            Updates the list on queue changes
        """
        try:
            track = playlist[positions[0]]
        except IndexError:
            text = ''
        else:
            text = self.formatter.format(track)

        glib.idle_add(self.label.set_text, text)

    def on_track_tags_changed(self, event, track, tag):
        """
            Updates the button on tag changes
        """
        playlist = self.view.playlist
        track_position = playlist.index(track)

        if track in playlist and track_position == playlist.current_position:
            glib.idle_add(self.label.set_text, self.formatter.format(track))

    def on_option_set(self, event, settings, option):
        """
            Updates control upon setting change
        """
        if option == 'plugin/minimode/track_title_format':
            glib.idle_add(self.formatter.set_property,
                'format',
                settings.get_option(option, _('$tracknumber - $title'))
            )

class ProgressButtonFormatter(Formatter):
    """
        Formatter which allows both for display of
        tag data as well as progress information
    """
    def __init__(self):
        Formatter.__init__(self, self.get_option_value())

        self.track_formatter = TrackFormatter('')
        self.progress_formatter = ProgressTextFormatter(
            self.props.format, player.PLAYER)

        event.add_callback(self.on_option_set,
            'plugin_minimode_option_set')

    def format(self, current_time=None, total_time=None):
        """
            Returns a string suitable for progress buttons

            :param current_time: the current progress
            :type current_time: float
            :param total_time: the total length of a track
            :type total_time: float
            :returns: The formatted text
            :rtype: string
        """
        text = self.progress_formatter.format()
        self.track_formatter.props.format = text
        text = self.track_formatter.format(player.PLAYER.current)

        return text

    def get_option_value(self):
        """
            Retrieves the current user format
        """
        return settings.get_option('plugin/minimode/progress_button_title_format',
            _('$title ($current_time / $total_time)'))

    def on_option_set(self, event, settings, option):
        """
            Updates the internal format on setting change
        """
        if option == 'gui/progress_bar_text_format':
            glib.idle_add(self.set_property,
                'format',
                self.get_option_value()
            )

gtk.rc_parse_string('''
    style "progress-button" {
        GtkToggleButton::default-border = {0, 0, 0, 0}
        GtkToggleButton::default-outside-border = {0, 0, 0, 0}
        GtkToggleButton::inner-border = {0, 0, 0, 0}
    }
    widget "*.progressbutton" style "progress-button"
''')
class ProgressButtonControl(PlaylistButtonControl):
    name = 'progress_button'
    title = _('Progress button')
    description = _('Playback progress and access '
                    'to the current playlist')
    # Required to make overrides work
    __gsignals__ = {}
    
    def __init__(self):
        PlaylistButtonControl.__init__(self)
        
        self.set_name('progressbutton')
        self.add_events(gtk.gdk.POINTER_MOTION_MASK)

        self.progressbar = SeekProgressBar(player.PLAYER)
        self.progressbar.set_size_request(-1, 1)
        self.progressbar.formatter = ProgressButtonFormatter()
        gtk_widget_replace(self.label, self.progressbar)
        self.label = self.progressbar

        if player.PLAYER.current is not None:
            self.progressbar.on_playback_track_start(
                'playback_track_start',
                player.PLAYER,
                player.PLAYER.current
            )

        self.tooltip = TrackToolTip(self, player.PLAYER)
        self.tooltip.set_auto_update(True)

    def destroy(self):
        """
            Cleanups
        """
        self.tooltip.destroy()
        PlaylistButtonControl.destroy(self)

    def do_button_press_event(self, event):
        """
            Trigger normal toggle action or seek
        """
        if event.button == 1:
            PlaylistButtonControl.do_button_press_event(self, event)
        elif event.button == 2:
            event.button = 1
            x, y = self.translate_coordinates(self.progressbar,
                int(event.x), int(event.y))
            event.x, event.y = float(x), float(y)
            self.progressbar.emit('button-press-event', event)

    def do_button_release_event(self, event):
        if event.button == 1:
            PlaylistButtonControl.do_button_release_event(self, event)
        elif event.button == 2:
            event.button = 1
            x, y = self.translate_coordinates(self.progressbar,
                int(event.x), int(event.y))
            event.x, event.y = float(x), float(y)
            self.progressbar.emit('button-release-event', event)

    def do_motion_notify_event(self, event):
        x, y = self.translate_coordinates(self.progressbar,
            int(event.x), int(event.y))
        event.x, event.y = float(x), float(y)
        self.progressbar.emit('motion-notify-event', event)

    def do_leave_notify_event(self, event):
        x, y = self.translate_coordinates(self.progressbar,
            int(event.x), int(event.y))
        event.x, event.y = float(x), float(y)
        self.progressbar.emit('leave-notify-event', event)

class ProgressBarControl(gtk.Alignment, BaseControl):
    name = 'progress_bar'
    title = _('Progress bar')
    description = _('Playback progress and seeking')

    def __init__(self):
        gtk.Alignment.__init__(self)
        BaseControl.__init__(self)

        self.set_padding(3, 3, 0, 0)
        self.progressbar = SeekProgressBar(player.PLAYER)
        self.progressbar.set_size_request(200, -1)
        self.add(self.progressbar)

        if player.PLAYER.current is not None:
            self.progressbar.on_playback_track_start(
                'playback_track_start',
                player.PLAYER,
                player.PLAYER.current
            )
            
            if player.PLAYER.is_paused():
                self.progressbar.on_playback_toggle_pause(
                    'playback_toggle_pause',
                    player.PLAYER,
                    player.PLAYER.current
                )

    def destroy(self):
        """
            Cleanups
        """
        self.progressbar.destroy()
        gtk.Alignment.destroy(self)

control_types = [
    PreviousButtonControl,
    NextButtonControl,
    PlayPauseButtonControl,
    StopButtonControl,
    VolumeButtonControl,
    RestoreButtonControl,
    RatingControl,
    TrackSelectorControl,
    PlaylistButtonControl,
    ProgressButtonControl,
    ProgressBarControl,
]

def register():
    """
        Registers all control providers
    """
    for control_type in control_types:
        providers.register('minimode-controls', control_type)

def unregister():
    """
        Unregisters all control providers
    """
    for control_type in control_types:
        providers.unregister('minimode-controls', control_type)

