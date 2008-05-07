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

import pygst, gtk
pygst.require('0.10')
import gst, random, time, re, os, md5
import thread, common, event

def get_default_player():
    return GSTPlayer

class Player:
    """
        This is the main player interface, other engines will subclass it
    """
    def __init__(self):
        pass

    def play(self, track):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def get_progress(self):
        raise NotImplementedError

    def get_time(self):
        raise NotImplementedError

    def is_playing(self):
        raise NotImplementedError

    def is_paused(self):
        raise NotImplementedError

    def seek(self, value, wait=True):
        raise NotImplementedError

    def toggle_pause(self):
        raise NotImplementedError

        


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
        self.bus.enable_sync_message_emission()
        self.audio_sink = None

    def set_volume(self, vol):
        """
            Sets the volume for the player
        """
        self.playbin.set_property('volume', vol)

    def set_audio_sink(self, arg):
        """
        """
        pass

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

    def on_message(self, bus, message, reading_tag = False):
        """
            Called when a message is received from gstreamer
        """
        if message.type == gst.MESSAGE_TAG and self.tag_func:
            self.tag_func(message.parse_tag())
        elif message.type == gst.MESSAGE_EOS and not self.is_paused() \
            and self.eof_func:
            self.eof_func()
        elif message.type == gst.MESSAGE_ERROR:
            print message, dir(message)

        return True

    def __notify_source(self, o, s, num):
        s = self.playbin.get_property('source')
        s.set_property('device', num)
        self.playbin.disconnect(self.notify_id)

    def play(self, track):
        """
            Plays the specified Track
        """
        uri = track.get_loc_for_io()
        if not self.audio_sink:
            self.set_audio_sink('')

        if not self.connections and not self.is_paused() and not \
            uri.find("lastfm://") > -1:

            self.connections.append(self.bus.connect('message', self.on_message))
            self.connections.append(self.bus.connect('sync-message::element',
                self.on_sync_message))

            if '://' not in uri: 
                if not os.path.isfile(uri):
                    raise Exception('File does not exist: ' + uri)
                uri = 'file://%s' % uri # FIXME: Wrong.
            uri = uri.replace('%', '%25')

            # for audio cds
            if uri.startswith("cdda://"):
                num = uri[uri.find('#') + 1:]
                uri = uri[:uri.find('#')]
                self.notify_id = self.playbin.connect('notify::source',
                    self.__notify_source, num)

            self.playbin.set_property('uri', uri.encode(common.get_default_encoding()))

        self.playbin.set_state(gst.STATE_PLAYING)
        event.log_event('playback_start', self, track)

    def on_sync_message(self, bus, message):
        """
            called when gstreamer requests a video sync
        """
        if message.structure.get_name() == 'prepare-xwindow-id' and \
            VIDEO_WIDGET:
            common.log('Gstreamer requested video sync')
            VIDEO_WIDGET.set_sink(message.src)

    def seek(self, value, wait=True):
        """
            Seeks to a specified location (in seconds) in the currently
            playing track
        """
        value = int(gst.SECOND * value)

        if wait: self.playbin.get_state(timeout=50*gst.MSECOND)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH|gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, value, gst.SEEK_TYPE_NONE, 0)

        res = self.playbin.send_event(event)
        if res:
            self.playbin.set_new_stream_time(0L)
        else:
            common.log("Couldn't send seek event")
        if wait: self.playbin.get_state(timeout=50*gst.MSECOND)

        self.last_seek_pos = value

    def pause(self):
        """
            Pauses the currently playing track
        """
        self.playbin.set_state(gst.STATE_PAUSED)
        event.log_event('playback_pause', self, track)        

    def toggle_pause(self):
        if self.is_paused():
            self.playbin.set_state(gst.STATE_PLAYING)
            event.log_event('playback_resume', self, track)
        else:
            self.playbin.set_state(gst.STATE_PAUSED)
            event.log_event('playback_start', self, track)

    def stop(self):
        """
            Stops the playback of the currently playing track
        """
        for connection in self.connections:
            self.bus.disconnect(connection)
        self.connections = []

        self.playbin.set_state(gst.STATE_NULL)
        event.log_event('playback_end', self, track)


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
