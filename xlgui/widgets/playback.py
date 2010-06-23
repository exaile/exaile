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

from xl.nls import gettext as _
from xl import player, formatter, event, settings


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
