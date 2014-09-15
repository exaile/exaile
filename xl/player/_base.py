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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

import logging
import time

import gst
import glib

from xl.nls import gettext as _
from xl import event, settings, common
from xl.player import pipe
logger = logging.getLogger(__name__)


class ExailePlayer(object):
    """
        Base class all players must inherit from and implement.
    """
    def __init__(self, name, pre_elems=[]):
        self.queue = None
        self._name = name
        self._playtime_stamp = None
        self._delay_id = None
        self._stop_id = None

        self._mainbin = pipe.MainBin(self, pre_elems=pre_elems)
        self._pipe = None
        self._bus = None

        self._setup_pipe()
        self._setup_bus()

        self._load_volume()
        event.add_callback(self._on_option_set, '%s_option_set' % self._name)
        event.add_callback(self._on_track_end, 'playback_track_end', self)

    def _on_option_set(self, name, object, data):
        if data == "%s/volume" % self._name:
            self._load_volume()
        elif data == '%s/audiosink_device' % self._name or \
             data == '%s/audiosink' % self._name:
            self._mainbin.setup_audiosink()
        
    def _on_track_end(self, name, obj, track):
        if not track:
            return
        try:
            i = int(track.get_tag_raw('__playcount'))
        except:
            i = 0
        track.set_tag_raw('__playcount', i + 1)
        track.set_tag_raw('__last_played', time.time())

    def _load_volume(self):
        """
            load volume from settings
        """
        volume = settings.get_option("%s/volume" % self._name, 1)
        self._set_volume(volume)

    def _setup_pipe(self):
        """
            Needs to create self._pipe, an instance of gst.Pipeline
            that will control playback.
        """
        raise NotImplementedError

    def _setup_bus(self):
        """
            setup the gstreamer message bus and callbacks
        """
        self._bus = self._pipe.get_bus()
        self._bus.add_signal_watch()
        self._bus.enable_sync_message_emission()
        self._bus.connect('message', self._on_message)

    def _on_message(self, bus, message, reading_tag=False):
        if not message:  # TODO: GI: Sometimes happens?
            return True
        handled = self._handle_message(bus, message, reading_tag)
        if handled:
            pass
        elif message.type == gst.MESSAGE_TAG:
            """ Update track length and optionally metadata from gstreamer's parser.
                Useful for streams and files mutagen doesn't understand. """
            parsed = message.parse_tag()
            event.log_event('tags_parsed', self, (self.current, parsed))
            if self.current and not self.current.get_tag_raw('__length'):
                try:
                    raw_duration = self._pipe.query_duration(gst.FORMAT_TIME, None)[0]
                except gst.QueryError:
                    logger.error("Couldn't query duration")
                    raw_duration = 0
                duration = float(raw_duration)/gst.SECOND
                if duration > 0:
                    self.current.set_tag_raw('__length', duration)
        elif message.type == gst.MESSAGE_EOS and not self.is_paused():
            self._eos_func()
        elif message.type == gst.MESSAGE_ERROR:
            logger.error("%s %s" %(message, dir(message)) )
            message_text = message.parse_error()[1]
            # The most readable part is always the last..
            message_text = message_text[message_text.rfind(':') + 1:]
            # .. unless there's nothing in it.
            if ' ' not in message_text:
                if message_text.startswith('playsink'):
                    message_text += _(': Possible audio device error, is it plugged in?')
            event.log_event('playback_error', self, message_text)
            self._error_func()
        return True

    def _handle_message(self, bus, message, reading_tag):
        pass # for overriding

    def _eos_func(self):
        logger.warning("Unhandled EOS message!")

    def _error_func(self):
        self.stop()

    def _set_queue(self, queue):
        self.queue = queue

    def _get_volume(self):
        """
            Gets the current actual volume.  This does not reflect what is
            shown to the user, see the player/volume setting for that.
        """
        return self._mainbin.get_volume()

    def _set_volume(self, volume):
        """
            Sets the volume. This does NOT update the setting value,
            and should be used only internally.
        """
        self._mainbin.set_volume(volume)

    def get_volume(self):
        """
            Gets the current volume

            :returns: the volume percentage
            :type: int
        """
        return (settings.get_option("%s/volume" % self._name, 1) * 100)

    def set_volume(self, volume):
        """
            Sets the current volume

            :param volume: the volume percentage
            :type volume: int
        """
        volume = min(volume, 100)
        volume = max(0, volume)
        settings.set_option("%s/volume" % self._name, volume / 100.0)

    
    def modify_volume(self, diff):
        """
            Changes the current volume

            :param diff: the volume differance (pos or neg) percentage units
            :type volume: int
        """
        v = self.get_volume()
        self.set_volume(v + diff)
        
    def _get_current(self):
        raise NotImplementedError

    def __get_current(self):
        return self._get_current()
    current = property(__get_current)

    def _cancel_delayed_start(self):
        if self._delay_id is not None:
            glib.source_remove(self._delay_id)
            self._delay_id = None
    
    def _should_delay_start(self):
        delay = settings.get_option('%s/auto_advance_delay' % self._name, 0)
        if delay <= 0:
            return False
        self.pause()
        self._delay_id = glib.timeout_add(int(delay), self._unpause) 
        return True
    
    def _cancel_stop_offset(self):
        if self._stop_id is not None:
            glib.source_remove(self._stop_id)
            self._stop_id = None
    
    def _setup_startstop_offsets(self, track):
        
        start_offset = track.get_tag_raw('__startoffset')
        stop_offset = track.get_tag_raw('__stopoffset')
        
        if start_offset > 0:
            
            # wait up to 1s for the state to switch, else this fails
            if self._pipe.get_state(timeout=1000*gst.MSECOND)[0] != gst.STATE_CHANGE_SUCCESS:
                event.log_event('playback_error', self, "Could not start at specified offset")
                self._error_func()
                return
            
            self.seek(start_offset)
            
        # there's probably a better way to implement this... 
        if stop_offset > 0:
            self._stop_id = glib.timeout_add(250, self._monitor_for_stop, track, stop_offset)
    
            
    def _monitor_for_stop(self, track, stop_offset):
        
        if track == self.current and self.get_position() >= stop_offset * gst.SECOND and self.is_playing():
            
            # send eos to pipe
            self._pipe.send_event(gst.event_new_eos())
        
            self._stop_id = None
            return False
        
        return True
    
    def play(self, track, **kwargs):
        """
            Starts the playback with the provided track
            or stops the playback it immediately if none

            :param track: the track to play
            :type track: :class:`xl.trax.Track`

            .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

                * `playback_player_start`: indicates the start of playback overall
                * `playback_track_start`: indicates playback start of a track
        """
        raise NotImplementedError

    def stop(self, _fire=True, **kwargs):
        """
            Stops the playback

            :param fire: Send the 'playback_player_end' event. Used by engines
                to avoid spurious playback_end events. Not public API.

            .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

                * `playback_player_end`: indicates the end of playback overall
                * `playback_track_end`: indicates playback end of a track
        """
        self._cancel_delayed_start()
        self._cancel_stop_offset()
        
        if self.is_playing() or self.is_paused():
            prev_current = self._stop(**kwargs)

            if _fire:
                event.log_event('playback_player_end', self, prev_current)
            return True
        return False

    def _stop(self, **kwargs):
        raise NotImplementedError

    def pause(self):
        """
            Pauses the playback, does not toggle it

            .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

                * `playback_player_pause`: indicates that the playback has been paused
        """
        self._cancel_delayed_start()
        if self.is_playing():
            self._pause()
            event.log_event('playback_player_pause', self, self.current)
            return True
        return False

    def _pause(self):
        raise NotImplementedError

    def unpause(self):
        """
            Resumes the playback, does not toggle it

            .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

                * `playback_player_resume`: indicates that the playback has been resumed
        """
        self._cancel_delayed_start()
        if self.is_paused():
            self._unpause()
            event.log_event('playback_player_resume', self, self.current)
            return True
        return False

    def _unpause(self):
        raise NotImplementedError

    def toggle_pause(self):
        """
            Toggles between playing and paused state

            .. note:: The following :doc:`events </xl/event>` will be emitted by this method:

                * `playback_toggle_pause`: indicates that the playback has been paused or resumed
        """
        if self.is_paused():
            self.unpause()
        else:
            self.pause()

        event.log_event("playback_toggle_pause", self, self.current)

    def seek(self, value):
        """
            Seek to a position in the currently playing stream

            :param value: the position in seconds
            :type value: int
        """
        raise NotImplementedError

    def get_position(self):
        """
            Gets the current playback position of the playing track

            :returns: the playback position in nanoseconds 
            :rtype: int
        """
        raise NotImplementedError

    def get_time(self):
        """
            Gets the current playback time

            :returns: the playback time in seconds
            :rtype: int
        """
        return self.get_position()/gst.SECOND

    def get_progress(self):
        """
            Gets the current playback progress

            :returns: the playback progress as [0..1]
            :rtype: float
        """
        try:
            progress = self.get_position()/float(
                    self.current.get_tag_raw("__length")*gst.SECOND)
        except TypeError: # track doesnt have duration info
            progress = 0
        except AttributeError: # no current track
            progress = 0
        else:
            if progress < 0:
                progress = 0
            elif progress > 1:
                progress = 1
        return progress

    def set_progress(self, progress):
        """
            Seeks to the progress position

            :param progress: value ranged at [0..1]
            :type progress: float
        """
        seek_position = 0

        try:
            length = self.current.get_tag_raw('__length')
            seek_position = length * progress
        except TypeError, AttributeError:
            pass

        self.seek(seek_position)
        
    def modify_time(self, diff):
        """
            Modifies the current position backwards or forwards.
            
            If posision ends up after the end or before the start of the track
            it is trunctated to lay inside the track.

            :param diff: value in seconds
            :type diff: int
        """
        try:
            length = self.current.get_tag_raw('__length')
        except TypeError, AttributeError:
            return
        
        if length == None: return
        
        pos = self.get_time()
        seek_pos = pos + diff
            
        # Make sure we dont seek outside the current track. Substract a little
        # from length, player seems to hang sometimes if we seek to the end of
        # a track.
        seek_pos = max(0, min(seek_pos, length - 2))
        
        self.seek(seek_pos)

    def _get_gst_state(self):
        """
            Returns the raw GStreamer state
        """
        return self._pipe.get_state(timeout=50*gst.MSECOND)[1]

    def get_state(self):
        """
            Gets the player state

            :returns: one of *playing*, *paused* or *stopped*
            :rtype: string
        """
        state = self._get_gst_state()
        if state == gst.STATE_PLAYING:
            return 'playing'
        elif state == gst.STATE_PAUSED:
            return 'paused'
        else:
            return 'stopped'

    def is_playing(self):
        """
            Convenience method to find out if the player is currently playing

            :returns: whether the player is currently playing
            :rtype: bool
        """
        return self._get_gst_state() == gst.STATE_PLAYING

    def is_paused(self):
        """
            Convenience method to find out if the player is currently paused

            :returns: whether the player is currently paused
            :rtype: bool
        """
        return self._get_gst_state() == gst.STATE_PAUSED

    def is_stopped(self):
        """
            Convenience method to find out if the player is currently stopped

            :returns: whether the player is currently stopped
            :rtype: bool
        """
        return self._get_gst_state() == gst.STATE_NULL

    @staticmethod
    def parse_stream_tags(track, tags):
        """
            Called when a tag is found in a stream.
        """
        newsong=False

        for key in tags.keys():
            value = tags[key]
            try:
                value = common.to_unicode(value)
            except UnicodeDecodeError:
                logger.debug('  ' + key + " [can't decode]: " + `str(value)`)
                continue # TODO: What encoding does gst give us?

            value = [value]

            if key == '__bitrate' or key == 'bitrate':
                track.set_tag_raw('__bitrate', int(value[0]))

            # if there's a comment, but no album, set album to the comment
            elif key == 'comment' and not track.get_tag_raw('album'):
                track.set_tag_raw('album', value)

            elif key == 'album': track.set_tag_raw('album', value)
            elif key == 'artist': track.set_tag_raw('artist', value)
            elif key == 'duration': track.set_tag_raw('__length',
                    float(value[0])/1000000000)
            elif key == 'track-number': track.set_tag_raw('tracknumber', value)
            elif key == 'genre': track.set_tag_raw('genre', value)

            elif key == 'title':
                try:
                    if track.get_tag_raw('__rawtitle') != value:
                        track.set_tag_raw('__rawtitle', value)
                        newsong = True
                except AttributeError:
                    track.set_tag_raw('__rawtitle', value)
                    newsong = True

                title_array = value[0].split(' - ', 1)
                if len(title_array) == 1 or \
                        track.get_loc_for_io().lower().endswith(".mp3"):
                    track.set_tag_raw('title', value)
                else:
                    track.set_tag_raw('artist', [title_array[0]])
                    track.set_tag_raw('title', [title_array[1]])



        return newsong

