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
        import xlgui
        playlist = xlgui.main.get_selected_page().playlist

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
    def __init__(self):
        gtk.ProgressBar.__init__(self)
        self.timer_id = None
        self.seeking = False
        self.formatter = ProgressBarFormatter()

        self.set_text(_('Not Playing'))

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self.add_events(gtk.gdk.BUTTON_MOTION_MASK)

        self.connect('button-press-event', self.seek_begin)
        self.connect('button-release-event', self.seek_end)
        self.connect('motion-notify-event', self.seek_motion_notify)

        event.add_callback(self.playback_start,
            'playback_player_start', player.PLAYER)
        event.add_callback(self.playback_toggle_pause,
            'playback_toggle_pause', player.PLAYER)
        event.add_callback(self.playback_end,
            'playback_player_end', player.PLAYER)

    def destroy(self):
        event.remove_callback(self.playback_start,
                'playback_player_start', player.PLAYER)
        event.remove_callback(self.playback_end,
                'playback_player_end', player.PLAYER)

    def seek_begin(self, *e):
        self.seeking = True

    def seek_end(self, widget, event):
        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_allocation()

        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1

        tr = player.PLAYER.current
        if not tr or not (tr.is_local() or \
                tr.get_tag_raw('__length')): return
        length = tr.get_tag_raw('__length')

        seconds = float(value * length)
        player.PLAYER.seek(seconds)
        self.seeking = False
        self.set_fraction(value)
        self.set_text(self.formatter.format(seconds, length))
#        self.emit('seek', seconds)

    def seek_motion_notify(self, widget, event):
        tr = player.PLAYER.current
        if not tr or not(tr.is_local() or \
                tr.get_tag_raw('__length')): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.get_allocation()

        value = mouse_x / progress_loc.width

        if value < 0: value = 0
        if value > 1: value = 1

        self.set_fraction(value)
        length = tr.get_tag_raw('__length')
        seconds = float(value * length)
        remaining_seconds = length - seconds
        self.set_text(self.formatter.format(seconds, length))

    def playback_start(self, type, player, object):
        if self.timer_id:
            glib.source_remove(self.timer_id)
            self.timer_id = None
        self.__add_timer_update()

    def playback_toggle_pause(self, type, player, object):
        if self.timer_id:
            glib.source_remove(self.timer_id)
            self.timer_id = None
        if not player.is_paused():
            self.__add_timer_update()

    def __add_timer_update(self):
        freq = settings.get_option("gui/progress_update_millisecs", 1000)
        if freq % 1000 == 0:
            self.timer_id = glib.timeout_add_seconds(freq/1000, self.timer_update)
        else:
            self.timer_id = glib.timeout_add(freq, self.timer_update)

    def playback_end(self, type, player, object):
        if self.timer_id: glib.source_remove(self.timer_id)
        self.timer_id = None
        self.set_text(_('Not Playing'))
        self.set_fraction(0)

    def timer_update(self, *e):
        tr = player.PLAYER.current
        if not tr: return
        if self.seeking: return True

        if not tr.is_local() and not tr.get_tag_raw('__length'):
            self.set_fraction(0)
            self.set_text(_('Streaming...'))
            return True

        self.set_fraction(player.PLAYER.get_progress())

        seconds = player.PLAYER.get_time()
        length = tr.get_tag_raw('__length')
        self.set_text(self.formatter.format(seconds, length))

        return True

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

