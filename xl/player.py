# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

# FIXME: needs documentation badly

import pygst
pygst.require('0.10')
import gst
import gobject

from xl import common, event, playlist, settings
import random, time, re, os, md5, thread, logging
from urlparse import urlparse

settings = settings.SettingsManager.settings

logger = logging.getLogger(__name__)

class PlayQueue(playlist.Playlist):
    """
        Manages the queue of songs to be played
    """
    def __init__(self, player, location=None, pickle_attrs=[]):
        self.current_playlist = None
        playlist.Playlist.__init__(self, location=location,
                pickle_attrs=pickle_attrs)
        self.player = player
        player.set_queue(self)
        self.stop_track = None

    def set_current_playlist(self, playlist):
        self.current_playlist = playlist

    def set_current_pl_track(self, track):
        self.current_pl_track = track

    def peek(self):
        track = playlist.Playlist.peek(self)
        if track == None:
            if self.current_playlist:
                track = self.current_playlist.peek()
        return track

    def next(self, player=True):
        if player:
            if self.player.current == self.stop_track:
                self.player.stop()
                event.log_event('stop_track', self, self.stop_track)
                self.stop_track = None
                return

        track = playlist.Playlist.next(self)
        if track == None:
            if self.current_playlist:
                track = self.current_playlist.next()
                self.current_playlist.current_playing = True
                self.current_playing = False
        else:
            self.ordered_tracks = self.ordered_tracks[1:]
            self.current_pos -= 1
            self.current_playing = True
            if self.current_playlist:
                self.current_playlist.current_playing = False
        if player:
            self.player.play(track)
        return track

    def prev(self):
        track = None
        if self.current_pos == -1:
            if self.current_playlist:
                track = self.current_playlist.prev()
        else:
            track = self.get_current()
        self.player.play(track)
        return track

    def get_current(self):
        if self.player.current and self.current_pos != 0:
            current = self.player.current
        else:
            current = playlist.Playlist.get_current(self)
            if current == None and self.current_playlist:
                current = self.current_playlist.get_current()
        return current

    def get_current_pos(self):
        return 0

    def play(self, track=None):
        if self.player.is_playing() and not track:
            return
        if not track:
            track = self.get_current()
        if track:
            self.player.play(track)
        else:
            self.next()


def get_player():
    if settings.get_option("player/gapless", False):
        return GaplessPlayer
    else:
        return GSTPlayer

class BaseGSTPlayer(object):
    """
        base player object
        player implementations will subclass this
    """
    def __init__(self):
        self.current = None
        self.playing = False
        self.last_position = 0
        self.queue = None
        self.playtime_stamp = None

        self.connections = []
        self.playbin = None
        self.bus = None
        self.audio_sink = None
        self.volume_control = None

        self.equalizer = None
        self.replaygain = None

        self.setup_playbin()
        self.setup_bus()
        self.setup_gst_elements()

        event.add_callback(self._on_setting_change, 'option_set')

    def setup_playbin(self):
        raise NotImplementedError

    def setup_bus(self):
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('message', self.on_message)

    def _on_setting_change(self, name, object, data):
        if 'player/volume' == data:
            self._load_volume()
        elif 'equalizer/band-' in data:
            self._load_equalizer_values()

    def _load_equalizer_values(self):
        if self.equalizer:
            for band in range(0, 10):
                value = settings.get_option("equalizer/band-%s"%band, 0.0)
                self.equalizer.set_property("band%s"%band, value)

    def _load_volume(self):
        volume = settings.get_option("player/volume", 1.0)
        self.set_volume(volume)

    def setup_gst_elements(self):
        """
            sets up additional gst elements
        """
        # TODO: implement eq, replaygain

        elements = []

        # equalizer
        if settings.get_option("player/equalizer", False):
            try:
                self.equalizer = gst.element_factory_make("equalizer-10bands",
                        "equalizer")
                self._load_equalizer_values()
                elements.append(self.equalizer)
                elements.append(gst.element_factory_make('audioconvert'))
            except:
                logger.warning("Failed to enable equalizer")
                self.equalizer = None
        else:
            self.equalizer = None

        # replaygain
        if settings.get_option("player/replaygain", False):
            try:
                self.replay_gain = gst.element_factory_make("rgvolume", 
                        "replaygain")
                self.replay_gain.set_property(
                        settings.get_option("replaygain/album_mode", False) )
                self.replay_gain.set_property(
                        settings.get_option("replaygain/preamp", 0.0) )
                self.replay_gain.set_property(
                        settings.get_option("replaygain/fallback", 0.0) )
                elements.append(self.replaygain)
            except:
                logger.warning("Failed to enable replaygain")
                self.replay_gain = None
        else:
            self.replay_gain = None
        
        # add volume control element
        self.volume_control = gst.element_factory_make("volume", "vol")
        self._load_volume()
        elements.append(self.volume_control)

        # set up the link to the sound card
        name = settings.get_option("player/sink", "autoaudiosink")
        if not gst.element_factory_find(name):
            logger.warning("Could not find playback sink %s, falling back to autoaudiosink"%name)
            name = 'autoaudiosink'
            options = []
        logger.debug("Using %s for playback"%name)
        self.audio_sink = gst.element_factory_make(name, "sink")
        # this setting is a list of strings of the form "param=value"
        options = settings.get_option("player/sink_options", [])
        for option in options:
            try:
                param, value = option.split("=", 1)
                self.audio_sink.set_property(param, value)
            except:
                logger.warning("Could not set parameter %s for %s"%(param, name))
        elements.append(self.audio_sink)


        # join everything together into a Bin to use as the playbin's sink
        sinkbin = gst.Bin()
        sinkbin.add(*elements)
        gst.element_link_many(*elements)
        sinkpad = elements[0].get_static_pad("sink")
        sinkbin.add_pad(gst.GhostPad('sink', sinkpad))

        
        self.playbin.set_property("audio-sink", sinkbin)

    def tag_func(self, *args):
        event.log_event('tags_parsed', self, (self.current, args[0]))

    def eof_func(self, *args):
        raise NotImplementedError

    def set_queue(self, queue):
        self.queue = queue

    def set_volume(self, vol):
        """
            sets the volume
        """
        self.volume_control.set_property("volume", vol)

    def on_message(self, bus, message, reading_tag = False):
        """
            Called when a message is received from gstreamer
        """
        if message.type == gst.MESSAGE_TAG and self.tag_func:
            self.tag_func(message.parse_tag())
        elif message.type == gst.MESSAGE_EOS and not self.is_paused():
            self.eof_func()
        elif message.type == gst.MESSAGE_ERROR:
            logger.error("%s %s" %(message, dir(message)) )
        elif message.type == gst.MESSAGE_BUFFERING:
            percent = message.parse_buffering()
            if percent < 100:
                self.playbin.set_state(gst.STATE_PAUSED)
            else:
                logger.info('Buffering complete')
                self.playbin.set_state(gst.STATE_PLAYING)
            if percent % 5 == 0:
                event.log_event('playback_buffering', self, percent)
        return True

    def _get_gst_state(self):
        """
            Returns the raw GStreamer state
        """
        return self.playbin.get_state(timeout=50*gst.MSECOND)[1]

    def get_state(self):
        """
            Returns the player state: 'playing', 'paused', or 'stopped'.
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
            Returns True if the player is currently playing
        """
        return self._get_gst_state() == gst.STATE_PLAYING

    def is_paused(self):
        """
            Returns True if the player is currently paused
        """
        return self._get_gst_state() == gst.STATE_PAUSED

    def get_position(self):
        """
            Gets the current playback position of the playing track
        """
        if self.is_paused(): return self.last_position
        try:
            self.last_position = \
                self.playbin.query_position(gst.FORMAT_TIME)[0]
        except gst.QueryError:
            self.last_position = 0

        return self.last_position

    def get_time(self):
        """
            Gets current playback time in seconds
        """
        return self.get_position()/gst.SECOND

    def get_progress(self):
        """
            Gets current playback progress in percent
        """
        try:
            progress = self.get_time()/float(self.current['length'])
        except ZeroDivisionError:
            progress = 0
        return progress

    def update_playtime(self):
        if self.current and self.playtime_stamp:
            last = self.current['playtime']
            if type(last) == str:
                try:
                    last = int(last)
                except:
                    last = 0
            elif type(last) != int:
                last = 0
            self.current['playtime'] = last + int(time.time() - \
                    self.playtime_stamp)
            self.playtime_stamp = None

    def reset_playtime_stamp(self):
        self.playtime_stamp = int(time.time())

    def _get_track_uri(self, track):
        uri = track.get_loc_for_io()
        parsed = urlparse(uri)
        if parsed[0] == "":
            uri = "file://%s"%uri #TODO: is there a better way to do this?
        uri = uri.encode(common.get_default_encoding())
        return uri

    def __notify_source(self, *args):
        source = self.playbin.get_property('source')
        device = self.current.get_loc_for_io().split("#")[-1]
        source.set_property('device', device)
        self.playbin.disconnect(self.notify_id)

    def play(self, track):
        self.stop()
       
        if track == None:
            return False
        self.current = track
        
        uri = self._get_track_uri(track)
        self.reset_playtime_stamp()

        self.playbin.set_property("uri", uri)
        if uri.startswith("cdda://"):
            self.notify_id = self.playbin.connect('notify::source',
                    self.__notify_source)

        self.playbin.set_state(gst.STATE_PLAYING)
        event.log_event('playback_start', self, track)

    def stop(self):
        if self.is_playing() or self.is_paused():
            self.update_playtime()
            current = self.current
            self.playbin.set_state(gst.STATE_NULL)
            self.current = None
            event.log_event('playback_end', self, current)

    def pause(self):
        if self.is_playing():
            self.update_playtime()
            self.playbin.set_state(gst.STATE_PAUSED)
            self.reset_playtime_stamp()
            event.log_event('playback_pause', self, self.current)
 
    def unpause(self):
        if self.is_paused():
            self.reset_playtime_stamp()
            self.playbin.set_state(gst.STATE_PLAYING)
            event.log_event('playback_resume', self, self.current)

    def toggle_pause(self):
        if self.is_paused():
            self.unpause()
        else:
            self.pause()

        event.log_event('playback_toggle_pause', self, self.current)

    def seek(self, value):
        value = int(gst.SECOND * value)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH|gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, value, gst.SEEK_TYPE_NONE, 0)

        res = self.playbin.send_event(event)
        if res:
            self.playbin.set_new_stream_time(0L)
        else:
            logger.debug("Couldn't send seek event")

        self.last_seek_pos = value
    

class GSTPlayer(BaseGSTPlayer):
    """
        Gstreamer engine
    """
    def __init__(self):
        BaseGSTPlayer.__init__(self)

    def setup_playbin(self):
        self.playbin = gst.element_factory_make("playbin", "player")

    def eof_func(self, *args):
        self.queue.next()

class GaplessPlayer(BaseGSTPlayer):
    """
        Gstreamer engine, using playbin2 for gapless
    """
    def __init__(self):
        BaseGSTPlayer.__init__(self)

    def eof_func(self, *args):
        self.queue.next()

    def setup_playbin(self):
        self.playbin = gst.element_factory_make('playbin2', "player")
        self.playbin.connect('about-to-finish', self.on_finish)
        
        # This signal doesn't work yet (as of gst 0.10.19)
        # self.playbin.connect('audio-changed', self.on_changed)


    def on_finish(self, *args):
        gobject.idle_add(self._on_finish)

    def _on_finish(self, *args):
        """
            called when a track is about to finish, so we can make it gapless
        """
        # this really should be peek(), but since the 'audio-changed'
        # signal isn't functional we have to do it this way.
        next = self.queue.next()
        uri = self._get_track_uri(next)
        self.playbin.set_property('uri', uri) #playbin2 takes care of the rest
    

# vim: et sts=4 sw=4

