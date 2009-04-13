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

from xl.nls import gettext as _

import pygst
pygst.require('0.10')
import gst

import gobject

from xl import common, event, playlist, settings
import random, time, os, logging, urllib
import urlparse


try:
    import cPickle as pickle
except:
    import pickle

settings = settings.SettingsManager.settings

logger = logging.getLogger(__name__)

class PlayQueue(playlist.Playlist):
    """
        Manages the queue of songs to be played
    """
    def __init__(self, player, location=None):
        self.current_playlist = None
        self.current_pl_track = None
        playlist.Playlist.__init__(self, name="Queue")
        self.player = player
        player.set_queue(self)
        self.stop_track = -1
        if location is not None:
            self.load_from_location(location)

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

    def next(self, player=True, track=None):
        """
            Goes to the next track, either in the queue, or in the current
            playlist.  If a track is passed in, that track is played

            @param player: play the track in addition to returning it
            @param track: if passed, play this track
        """
        if not track:
            if player:
                if self.player.current == self.stop_track:
                    self.player.stop()
                    event.log_event('stop_track', self, self.stop_track)
                    self.stop_track = -1
                    return

            if not self.ordered_tracks:
                if self.current_playlist:
                    track = self.current_playlist.next()
                    self.current_playlist.current_playing = True
                    self.current_playing = False
            else:
                track = self.ordered_tracks.pop(0)
                self.current_pos = 0
                self.current_playing = True
                if self.current_playlist:
                    self.current_playlist.current_playing = False
        if player:
            self.player.play(track)
        return track

    def prev(self):
        track = None
        if self.player.current:
            if self.player.get_time() < 5:
                if self.current_playlist:
                    track = self.current_playlist.prev()
            else:
                track = self.player.current
        else:
            track = self.get_current()
        self.player.play(track)
        return track

    def get_current(self):
        if self.player.current and self.current_pos > 0:
            current = self.player.current
        else:
            current = playlist.Playlist.get_current(self)
            if current == None and self.current_playlist:
                current = self.current_playlist.get_current()
        return current

    def get_current_pos(self):
        return 0

    def play(self, track=None):
        """
            start playback, either from the passed track or from already 
            queued tracks
        """
        if self.player.is_playing() and not track:
            return
        if not track:
            track = self.get_current()
        if track:
            self.player.play(track)
        else:
            self.next()

    def _save_player_state(self, location):
        state = {}
        state['state'] = self.player.get_state()
        state['position'] = self.player.get_time()
        state['playtime_stamp'] = self.player.playtime_stamp
        f = open(location, 'wb')
        pickle.dump(state, f, protocol = 2)
        f.close()

    @common.threaded
    def _restore_player_state(self, location):
        if not settings.get_option("player/resume_playback", True):
            return

        try:
            f = open(location, 'rb')
            state = pickle.load(f)
            f.close()
        except:
            return

        for req in ['state', 'position', 'playtime_stamp']:
            if req not in state:
                return

        if state['state'] != 'stopped':
            vol = self.player.get_volume()
            self.player.set_volume(0)
            self.play()
            time.sleep(0.5) # let the player settle
            self.player.seek(state['position'])
            if state['state'] == 'paused' or \
                    settings.get_option("player/resume_paused", False):
                self.player.toggle_pause()
            self.player.set_volume(vol)
            self.player.playtime_stamp = state['playtime_stamp']


def get_player():
    if settings.get_option("player/gapless", False):
        logger.debug(_("Gapless enabled"))
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
        """
            setup the playbin to use for playback
            needs to be overridden in subclasses
        """
        raise NotImplementedError

    def setup_bus(self):
        """
            setup the gstreamer message bus and callacks
        """
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()
        self.bus.connect('message', self.on_message)

    def _on_setting_change(self, name, object, data):
        """
            handle setting change events
        """
        if 'player/volume' == data:
            self._load_volume()
        elif 'equalizer/band-' in data:
            self._load_equalizer_values()

    def _load_equalizer_values(self):
        """
            load EQ values from settings
        """
        if self.equalizer:
            for band in range(0, 10):
                value = settings.get_option("equalizer/band-%s"%band, 0.0)
                self.equalizer.set_property("band%s"%band, value)

    def _load_volume(self):
        """
            load volume from settings
        """
        volume = settings.get_option("player/volume", .7)
        self.set_volume(volume)

    def setup_gst_elements(self):
        """
            sets up additional gst elements
        """
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
                logger.warning(_("Failed to enable equalizer"))
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
                logger.warning(_("Failed to enable replaygain"))
                self.replay_gain = None
        else:
            self.replay_gain = None
        
        # add volume control element
        self.volume_control = gst.element_factory_make("volume", "vol")
        self._load_volume()
        elements.append(self.volume_control)

        # set up the link to the sound card
        name = settings.get_option("player/sink", "autoaudiosink")
        # this setting is a list of strings of the form "param=value"
        options = settings.get_option("player/sink_options", [])
        if not gst.element_factory_find(name):
            logger.warning(_("Could not find playback sink %s, falling back to autoaudiosink")%name)
            name = 'autoaudiosink'
            options = []
        logger.debug(_("Using %s for playback")%name)
        self.audio_sink = gst.element_factory_make(name, "sink")
        for option in options:
            try:
                param, value = option.split("=", 1)
                self.audio_sink.set_property(param, value)
            except:
                logger.warning(_("Could not set parameter %s for %s")%(param, name))
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
        """
            called at the end of a stream
            override in subclasses
        """
        raise NotImplementedError

    def set_queue(self, queue):
        """
            sets the queue object to use for playback
        """
        self.queue = queue

    def set_volume(self, vol):
        """
            sets the volume

            this does NOT save the volume to settings. modifying the volume in 
            setings however will call this automatically
        """
        self.volume_control.set_property("volume", vol)

    def get_volume(self):
        return self.volume_control.get_property('volume')

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
            a = message.parse_error()[0]
            self._on_playback_error(a.message)
        elif message.type == gst.MESSAGE_BUFFERING:
            percent = message.parse_buffering()
            if percent < 100:
                self.playbin.set_state(gst.STATE_PAUSED)
            else:
                logger.info(_('Buffering complete'))
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
            progress = self.get_time()/float(self.current.get_duration())
        except ZeroDivisionError:
            progress = 0
        return progress

    def update_playtime(self):
        """
            updates the total playtime for the currently playing track
        """
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
        return uri

    def __notify_source(self, *args):
        # this is for handling multiple CD devices properly
        source = self.playbin.get_property('source')
        device = self.current.get_loc_for_io().split("#")[-1]
        source.set_property('device', device)
        self.playbin.disconnect(self.notify_id)

    def _on_playback_error(self, message):
        """
            Called when there is an error during playback
        """
        event.log_event('playback_error', self, message)

    def play(self, track):
        """
            plays the specified track, overriding any currently playing track

            if the track cannot be played, playback stops completely
        """
        self.stop()

        if track is None:
            return False

        # make sure the file exists if this is supposed to be a local track
        if track.is_local():
            if not track.exists():
                logger.error(_("File does not exist: %s") % 
                    track.get_loc())
                return False
       
        self.current = track
        
        uri = self._get_track_uri(track)
        logger.info(_("Playing %s") % uri)
        self.reset_playtime_stamp()

        self.playbin.set_property("uri", uri)
        if urlparse.urlsplit(uri).scheme == "cdda":
            self.notify_id = self.playbin.connect('notify::source',
                    self.__notify_source)

        self.playbin.set_state(gst.STATE_PLAYING)
        event.log_event('playback_start', self, track)

    def stop(self):
        """
            stop playback
        """
        if self.is_playing() or self.is_paused():
            self.update_playtime()
            current = self.current
            self.playbin.set_state(gst.STATE_NULL)
            self.current = None
            event.log_event('playback_end', self, current)

    def pause(self):
        """
            pause playback. DOES NOT TOGGLE
        """
        if self.is_playing():
            self.update_playtime()
            self.playbin.set_state(gst.STATE_PAUSED)
            self.reset_playtime_stamp()
            event.log_event('playback_pause', self, self.current)
 
    def unpause(self):
        """
            unpause playback
        """
        if self.is_paused():
            self.reset_playtime_stamp()

            # gstreamer does not buffer paused network streams, so if the user
            # is unpausing a stream, just restart playback
            if not self.current.is_local():
                self.playbin.set_state(gst.STATE_READY)

            self.playbin.set_state(gst.STATE_PLAYING)
            event.log_event('playback_resume', self, self.current)

    def toggle_pause(self):
        """
            toggle playback pause state
        """
        if self.is_paused():
            self.unpause()
        else:
            self.pause()

        event.log_event('playback_toggle_pause', self, self.current)

    def seek(self, value):
        """
            seek to the given position in the current stream
        """
        value = int(gst.SECOND * value)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH|gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, value, gst.SEEK_TYPE_NONE, 0)

        res = self.playbin.send_event(event)
        if res:
            self.playbin.set_new_stream_time(0L)
        else:
            logger.debug(_("Couldn't send seek event"))

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
        self.playbin.connect('audio-changed', self.on_changed)

    def on_finish(self, *args):
        gobject.idle_add(self._on_finish)

    def _on_finish(self, *args):
        """
            called when a track is about to finish, so we can make it gapless
        """
        # this really should be peek(), but since the 'audio-changed'
        # signal isn't functional we have to do it this way.
        next = self.queue.next()
        if next is None:
            self.stop() #does this cut off part of the track?
            return
        uri = self._get_track_uri(next)
        self.playbin.set_property('uri', uri) #playbin2 takes care of the rest

    def on_changed(self, *args):
        gobject.idle_add(self._on_changed)

    def _on_changed(self, *args):
        logger.debug(_("GST AUDIO CHANGED"))
    

# vim: et sts=4 sw=4

