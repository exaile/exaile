# Copyright (C) 2008-2010 Adam Olsen
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import glib
import gtk

from xl import (
    event,
    formatter,
    player,
    settings,
    xdg
)
from xl.nls import gettext as _
from xlgui.widgets import menu

class ProgressBarFormatter(formatter.ProgressTextFormatter):
    """
        A formatter for progress bars
    """
    def __init__(self):
        formatter.ProgressTextFormatter.__init__(self, self.get_option_value())

        event.add_callback(self.on_option_set, 'gui_option_set')

    def format(self, current_time=None, total_time=None):
        """
            Returns a string suitable for progress indicators

            :param current_time: the current progress
            :type current_time: float
            :param total_time: the total length of a track
            :type total_time: float
            :returns: The formatted text
            :rtype: string
        """
        playlist = player.QUEUE.current_playlist

        if playlist.current_position < 0:
            return ''

        tracks = playlist[playlist.current_position:]
        duration = sum([t.get_tag_raw('__length') for t in tracks \
            if t.get_tag_raw('__length')])
        duration -= player.PLAYER.get_time()

        self._substitutions['total_remaining_time'] = \
            formatter.LengthTagFormatter.format_value(duration)

        return formatter.ProgressTextFormatter.format(self, current_time, total_time)

    def get_option_value(self):
        """
            Returns the current option value
        """
        return settings.get_option('gui/progress_bar_text_format',
            '$current_time / $remaining_time')

    def on_option_set(self, event, settings, option):
        """
            Updates the internal format on setting change
        """
        if option == 'gui/progress_bar_text_format':
            self.props.format = self.get_option_value()

class PlaybackProgressBar(gtk.ProgressBar):
    """
        Progress bar which automatically follows playback
    """
    def __init__(self):
        gtk.ProgressBar.__init__(self)

        self.reset()

        self._formatter = ProgressBarFormatter()
        self.__timer_id = None
        self.__events = ['playback_track_start', 'playback_player_end',
                         'playback_toggle_pause', 'playback_error']

        for e in self.__events:
            event.add_callback(getattr(self, 'on_%s' % e), e)

    def destroy(self):
        """
            Cleanups
        """
        for e in self.__events:
            event.remove_callback(getattr(self, 'on_%s' % e), e)

    def reset(self):
        """
            Resets the progress bar appearance
        """
        self.set_fraction(0)
        self.set_text(_('Not Playing'))

    def __enable_timer(self):
        """
            Enables the update timer
        """
        if self.__timer_id is not None:
            return

        interval = settings.get_option('gui/progress_update_millisecs', 1000)

        if interval % 1000 == 0:
            self.__timer_id = glib.timeout_add_seconds(
                interval / 1000, self.on_timer)
        else:
            self.__timer_id = glib.timeout_add(
                interval, self.on_timer)

        self.on_timer()

    def __disable_timer(self):
        """
            Disables the update timer
        """
        if self.__timer_id is not None:
            glib.source_remove(self.__timer_id)
            self.__timer_id = None

    def on_timer(self):
        """
            Updates progress bar appearance
        """
        if player.PLAYER.current is None:
            self.__disable_timer()
            self.reset()
            return False

        self.set_fraction(player.PLAYER.get_progress())
        self.set_text(self._formatter.format())

        return True

    def on_playback_track_start(self, event_type, player, track):
        """
            Starts update timer
        """
        self.reset()
        self.__enable_timer()

    def on_playback_player_end(self, event_type, player, track):
        """
            Stops update timer
        """
        self.__disable_timer()
        self.reset()

    def on_playback_toggle_pause(self, event_type, player, track):
        """
            Starts or stops update timer
        """
        if player.is_playing():
            self.__enable_timer()
        elif player.is_paused():
            self.__disable_timer()

    def on_playback_error(self, event_type, player, message):
        """
            Stops update timer
        """
        self.__disable_timer()
        self.reset()

class SeekProgressBar(PlaybackProgressBar):
    """
        Playback progress bar which allows for seeking
    """
    __gsignals__ = {
        'button-press-event': 'override',
        'button-release-event': 'override',
        'motion-notify-event': 'override',
        'key-press-event': 'override',
        'key-release-event': 'override'
    }

    def __init__(self):
        PlaybackProgressBar.__init__(self)

        self.__seeking = False

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK |
                        gtk.gdk.BUTTON_MOTION_MASK)
        self.set_flags(self.flags() | gtk.CAN_FOCUS)

    def do_button_press_event(self, event):
        """
            Prepares seeking
        """
        if event.button == 1:
            if player.PLAYER.current is None:
                return True
            
            length = player.PLAYER.current.get_tag_raw('__length')

            if length is None:
                return True
            
            fraction = event.x / self.allocation.width
            fraction = max(0, fraction)
            fraction = min(fraction, 1)

            self.set_fraction(fraction)
            self.set_text(_('Seeking: %s') % self._formatter.format(
                current_time=length * fraction))
            self.__seeking = True

    def do_button_release_event(self, event):
        """
            Completes seeking
        """
        if event.button == 1 and self.__seeking:
            length = player.PLAYER.current.get_tag_raw('__length')

            fraction = event.x / self.allocation.width
            fraction = max(0, fraction)
            fraction = min(fraction, 1)

            self.set_fraction(fraction)
            player.PLAYER.set_progress(fraction)
            self.set_text(self._formatter.format(
                current_time=length * fraction))
            self.__seeking = False

    def do_motion_notify_event(self, event):
        """
            Updates progress bar while seeking
        """
        if self.__seeking:
            press_event = gtk.gdk.Event(gtk.gdk.BUTTON_PRESS)
            press_event.button = 1
            press_event.x = event.x
            press_event.y = event.y

            self.emit('button-press-event', press_event)

    def do_key_press_event(self, event):
        """
            Prepares seeking via keyboard interaction
            * Alt+Up/Right: seek 1% forward
            * Alt+Down/Left: seek 1% backward
        """
        if self.get_state() & gtk.STATE_INSENSITIVE:
            return

        if not event.state & gtk.gdk.MOD1_MASK:
            return

        if event.keyval in (gtk.keysyms.Up, gtk.keysyms.Right):
            direction = 1
        elif event.keyval in (gtk.keysyms.Down, gtk.keysyms.Left):
            direction = -1
        else:
            return
        
        press_event = gtk.gdk.Event(gtk.gdk.BUTTON_PRESS)
        press_event.button = 1
        new_fraction = self.get_fraction() + 0.01 * direction
        press_event.x = self.allocation.width * new_fraction
        press_event.y = float(self.allocation.y)

        self.emit('button-press-event', press_event)

    def do_key_release_event(self, event):
        """
            Completes seeking via keyboard interaction
        """
        if not event.state & gtk.gdk.MOD1_MASK:
            return

        if event.keyval in (gtk.keysyms.Up, gtk.keysyms.Right):
            direction = 1
        elif event.keyval in (gtk.keysyms.Down, gtk.keysyms.Left):
            direction = -1
        else:
            return

        release_event = gtk.gdk.Event(gtk.gdk.BUTTON_RELEASE)
        release_event.button = 1
        new_fraction = self.get_fraction() + 0.01 * direction
        release_event.x = self.allocation.width * new_fraction
        release_event.y = float(self.allocation.y)

        self.emit('button-release-event', release_event)

    def on_timer(self):
        """
            Prevents update while seeking
        """
        if self.__seeking:
            return True

        return PlaybackProgressBar.on_timer(self)

class VolumeControl(gtk.Alignment):
    """
        Encapsulates a button and a slider to
        control the volume indicating the current
        status via icon and tooltip
    """
    def __init__(self):
        gtk.Alignment.__init__(self, xalign=1)

        self.restore_volume = settings.get_option('player/volume', 1)
        self.icon_names = ['low', 'medium', 'high']

        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path('ui', 'widgets',
            'volume_control.ui'))
        builder.connect_signals(self)

        box = builder.get_object('volume_control')
        box.reparent(self)

        self.button = builder.get_object('button')
        self.button.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.button_image = builder.get_object('button_image')
        self.slider = builder.get_object('slider')
        self.slider_adjustment = builder.get_object('slider_adjustment')
        self.__update(self.restore_volume)

        event.add_callback(self.on_option_set, 'player_option_set')

    def __update(self, volume):
        """
            Sets the volume level indicator
        """
        icon_name = 'audio-volume-muted'
        tooltip = _('Muted')

        if volume > 0:
            i = int(round(volume * 2))
            icon_name = 'audio-volume-%s' % self.icon_names[i]
            #TRANSLATORS: Volume percentage
            tooltip = _('%d%%') % (volume * 100)

        if volume == 1.0:
            tooltip = _('Full Volume')

        if volume > 0:
            self.button.set_active(False)

        self.button_image.set_from_icon_name(icon_name, gtk.ICON_SIZE_BUTTON)
        self.button.set_tooltip_text(tooltip)
        self.slider.set_value(volume)
        self.slider.set_tooltip_text(tooltip)

    def on_scroll_event(self, widget, event):
        """
            Changes the volume on scrolling
        """
        page_increment = self.slider_adjustment.page_increment
        step_increment = self.slider_adjustment.step_increment
        value = self.slider.get_value()

        if event.direction == gtk.gdk.SCROLL_DOWN:
            if event.state & gtk.gdk.SHIFT_MASK:
                self.slider.set_value(value - page_increment)
            else:
                self.slider.set_value(value - step_increment)
            return True
        elif event.direction == gtk.gdk.SCROLL_UP:
            if event.state & gtk.gdk.SHIFT_MASK:
                self.slider.set_value(value + page_increment)
            else:
                self.slider.set_value(value + step_increment)
            return True

        return False

    def on_button_toggled(self, button):
        """
            Mutes or unmutes the volume
        """
        if button.get_active():
            self.restore_volume = settings.get_option('player/volume', 1)
            volume = 0
        else:
            volume = self.restore_volume

        if self.restore_volume > 0:
            settings.set_option('player/volume', volume)

    def on_slider_value_changed(self, slider):
        """
            Stores the preferred volume
        """
        settings.set_option('player/volume', slider.get_value())

    def on_slider_key_press_event(self, slider, event):
        """
            Changes the volume on key press
            while the slider is focussed
        """
        page_increment = slider.get_adjustment().page_increment
        step_increment = slider.get_adjustment().step_increment
        value = slider.get_value()

        if event.keyval == gtk.keysyms.Down:
            slider.set_value(value - step_increment)
            return True
        elif event.keyval == gtk.keysyms.Page_Down:
            slider.set_value(value - page_increment)
            return True
        elif event.keyval == gtk.keysyms.Up:
            slider.set_value(value + step_increment)
            return True
        elif event.keyval == gtk.keysyms.Page_Up:
            slider.set_value(value + page_increment)
            return True

        return False

    def on_option_set(self, event, sender, option):
        """
            Updates the volume indication
        """
        if option == 'player/volume':
            self.__update(settings.get_option(option, 1))



def playpause():
    if player.PLAYER.get_state() in ('playing', 'paused'):
        player.PLAYER.toggle_pause()
    else:
        from xlgui import main
        page = main.get_current_playlist()
        if page:
            pl = page.playlist
            if len(pl) == 0:
                return
            try:
                idx = page.view.get_selected_paths()[0][0]
            except IndexError:
                idx = 0
            player.QUEUE.set_current_playlist(pl)
            pl.current_position = idx
            player.QUEUE.play(track=pl.current)


def PlayPauseMenuItem(name, after):
    def factory(menu, parent, context):
        if player.PLAYER.is_playing():
            stock_id = gtk.STOCK_MEDIA_PAUSE
        else:
            stock_id = gtk.STOCK_MEDIA_PLAY

        item = gtk.ImageMenuItem(stock_id)
        item.connect('activate', lambda *args: playpause(), name, parent, context)

        return item
    return menu.MenuItem(name, factory, after=after)

def _next_cb(widget, name, parent, context):
    player.QUEUE.next()

def NextMenuItem(name, after):
    return menu.simple_menu_item(name, after, icon_name=gtk.STOCK_MEDIA_NEXT,
        callback=_next_cb)

def _prev_cb(widget, name, parent, context):
    player.QUEUE.prev()

def PrevMenuItem(name, after):
    return menu.simple_menu_item(name, after, icon_name=gtk.STOCK_MEDIA_PREVIOUS,
        callback=_prev_cb)

def _stop_cb(widget, name, parent, context):
    player.PLAYER.stop()

def StopMenuItem(name, after):
    return menu.simple_menu_item(name, after, icon_name=gtk.STOCK_MEDIA_STOP,
        callback=_stop_cb)

