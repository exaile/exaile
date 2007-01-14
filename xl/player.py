# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import pygst
pygst.require('0.10')
import gst, gobject, random, time, urllib, re
from xl import xlmisc, common
random.seed(time.time())

class Player(object):
    """
        This is the main player interface, other engines will subclass it
    """
    def __init__(self):
        pass

class GSTPlayer(Player):
    """
        Gstreamer engine
    """

    def __init__(self):
        Player.__init__(self)
        self.playing = False
        self.connections = []
        self.last_position = 0
        self.eof_func = None
        self.tag_func = None
        self.setup_playbin()

    def setup_playbin(self):
        self.playbin = gst.element_factory_make('playbin')
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()

        self.audio_sink = None

    def set_audio_sink(self, sink):
        """
            Sets the audio sink up.  It tries the passed in value, and if that
            doesn't work, it tries autoaudiosink
        """
        if sink.lower().find("gconf"): sink = 'gconfaudiosink'
        sink = sink.lower()
        try:
            self.audio_sink = gst.element_factory_make(sink)
        except:
            xlmisc.log_exception()
            self.audio_sink = gst.element_factory_make('autoaudiosink')

        # if the audio_sink is still not set, use a fakesink
        if not self.audio_sink:
            xlmisc.log('Audio Sink could not be set up.  Using a fakesink '
               'instead.  Audio will not be available.')
            self.audio_sink = gst.element_factory_make('fakesink')

    def set_volume(self, vol):
        """
            Sets the volume for the player
        """
        self.playbin.set_property('volume', vol)

    def is_playing(self):
        """
            Returns True if the player is currently playing
        """
        return self.playbin.get_state()[1] == gst.STATE_PLAYING

    def is_paused(self):
        """
            Returns True if the player is currently paused
        """
        return self.playbin.get_state()[1] == gst.STATE_PAUSED

    def on_message(self, bus, message, reading_tag = False):
        """
            Called when a message is recieved from gstreamer
        """
        if message.type == gst.MESSAGE_TAG and self.tag_func:
            self.tag_func(message.parse_tag())
        elif message.type == gst.MESSAGE_EOS and not self.is_paused() \
            and self.eof_func:
            self.eof_func()

        return True

    def play(self, uri):
        """
            Plays the specified uri
        """
        if not self.audio_sink:
            self.set_audio_sink('')

        if not self.connections and not self.is_paused():
            self.connections.append(self.bus.connect('message', self.on_message))

            if uri.find('://') == -1: uri = 'file://%s' % uri
            self.playbin.set_property('uri', uri)

        self.playbin.set_state(gst.STATE_PLAYING)

    def seek(self, value):
        """
            Seeks to a specified location (in seconds) in the currently
            playing track
        """
        value *= gst.SECOND
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH|gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, value, gst.SEEK_TYPE_NONE, 0)

        self.playbin.send_event(event)
        self.last_seek_pos = value

    def pause(self):
        """
            Pauses the currently playing track
        """
        self.playbin.set_state(gst.STATE_PAUSED)

    def toggle_pause(self):
        if self.is_paused():
            self.playbin.set_state(gst.STATE_PLAYING)
        else:
            self.playbin.set_state(gst.STATE_PAUSED)

    def stop(self):
        """
            Stops the playback of the currently playing track
        """
        for connection in self.connections:
            self.bus.disconnect(connection)
        self.connections = []

        self.playbin.set_state(gst.STATE_READY)

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

class ExailePlayer(GSTPlayer):
    """
        Exaile interface to the GSTPlayer
    """
    def __init__(self, exaile):
        GSTPlayer.__init__(self)
        self.exaile = exaile
        self.last_played = None
        self.played = []
        self.queued = []
        self.history = []
        self.next_track = None
        self.shuffle = False
        self.repeat = False

        self.eof_func = self.next
        self.current = None

    def get_next_queued(self):
        if self.next_track == None:
            self.next_track = self.current
        track = self.queued[0]
        if not track in self.exaile.tracks.songs:
            self.exaile.tracks.append_song(track)
        self.queued = self.queued[1:len(self.queued)]
        xlmisc.log('Playing queued track "%s"' % track)

        return track

    def get_next_shuffle_track(self):
        """
            Returns the next random track that hasn't already been played
        """
        count = 0

        while True:
            if len(self.exaile.songs) == 0: return
            current_index = random.randint(0, len(self.exaile.songs) -
                1)
            track = self.exaile.tracks.songs[current_index]
            if count >= 500 or track not in \
                self.played:
                
                if track in self.played:
                    for track in self.exaile.tracks.songs:
                        if not track in self.played:
                            break
                    self.played = []
                    if not self.repeat:
                        return

                break

            count += 1

        return track

    def get_current_position(self):
        """
            Gets the current position relative to the playing track's length
        """
        value = 0
        duration = self.current.duration * gst.SECOND
        if duration:
            value = self.get_position() * 100.0 / duration

        return value

    @common.threaded
    def find_stream_uri(self, track):
        h = urllib.urlopen(track.loc)
        loc = ''

        for i, line in enumerate(h.readlines()):
            line = line.strip()
            xlmisc.log('Line %d: %s' % (i, line.strip()))
            if line.startswith('#') or line == '[playlist]': 
                continue
            if line.find('=') > -1:
                if not line.startswith('File'): continue
                line = re.sub('File\d+=', '', line)
                loc = line
                break

        if loc:
            xlmisc.log('Found location: %s' % loc)
            gobject.idle_add(GSTPlayer.play, self, loc)
            return

        xlmisc.log('Could not find a stream location')

    def play_track(self, track):
        if track.loc.endswith('.pls') or track.loc.endswith('.m3u'):
            self.find_stream_uri(track)
            return

        GSTPlayer.play(self, track.loc)

    def play(self):
        """
            Plays the currently selected track
        """
        self.stop()

        if self.exaile.tracks == None: return

        self.last_played = self.current

        track = self.exaile.tracks.get_selected_track()
        if not track:
            if self.tracks.songs:
                self.next()
                return
            return

        if track in self.queued: del self.queued[self.queued.index(track)]
        self.current = track

        self.played = [track]
        self.history.append(track)
        self.play_track(track)
        
    def next(self):
        self.stop(False)
        if self.exaile.tracks == None: return
        
        track = self.exaile.tracks.get_next_track(self.current)

        print 'next track was reported as ', track
        if not track:
            if not self.exaile.tracks.get_songs():
                if not self.queued: return
            else: track = self.exaile.tracks.get_songs()[0]

        if self.next_track != None and not self.queued:
            track = self.exaile.tracks.get_next_track(self.next_track)
            if not track: track = self.exaile.tracks.get_songs()[0]
            self.next_track = None

        # for queued tracks
        if len(self.queued) > 0:
            track = self.get_next_queued()
            self.play_track(track)
            self.current = track
            self.played.append(track)
            return
        else:
            # for shuffle mode
            if self.shuffle:
                track = self.get_next_shuffle_track()

        if not self.shuffle and \
            not self.exaile.tracks.get_next_track(self.current):
            if self.repeat:
                self.current = self.tracks.get_songs()[0]
            else:
                self.played = []
                self.current = None
        
        self.history.append(track)
        self.played.append(track)

        if track: self.play_track(track)
        self.current = track

    def previous(self):
        """
            Go to the previous track
        """

        # if the current track has been playing for less than 5 seconds, 
        # just restart it
        if self.exaile.rewind_track >= 6:
            track = self.current
            if track:
                self.stop()
                self.play_track(track)
                self.exaile.rewind_track = 0
            return

        if self.history:
            self.stop()
            track = self.history.pop()
        else:
            track = self.exaile.tracks.get_previous_track(self.current)

        self.play_track(track)
        self.current = track

    def stop(self, reset_current=True):
        """
            Stops the currently playing track
        """
        GSTPlayer.stop(self)
        if reset_current: self.current = None
