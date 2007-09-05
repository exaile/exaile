#!/usr/bin/env python
# Copyright (C) 2007 Edgar Merino <donvodka at gmail dot com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


from UserDict import UserDict
from xl import common, xlmisc
import sys, os, gtk, time, subprocess

try:
    import shout
    SHOUT_AVAIL = True
except ImportError:
    SHOUT_AVAIL = False

# Reusable abstract class
# This is needed to make the class Icast not depend on exaile
class Client:
    def __init__(self, player=None):
        self.player = player # player that holds a reference to the current song being player

    def is_playing(self):
        pass

    def get_current_track(self):
        pass

    # if no log facility, just print s
    def log(self, s):
        pass

# Reusable abstract class
# You don't like lame? implement your own encoder!
# TODO Encoder should provide a way to know it's configuration parameters
class Encoder:
    def __init__(self, br, sr):
        self.bitrate = br
        self.samplerate = sr
        # TODO use os.tmpfile() to create temporal dump
        self.dump = "/tmp/encode.dump"
    
    def encode(self):
        pass

    def get_dump(self):
        return self.dump

    # when using os.tmpfile() this is not needed
    def remove_dump(self):
        try:
            os.remove(self.dump)
        except OSError:
            pass

# TODO support paused state, is this really needed?
# TODO copiar codigo del decorador common.threaded
# Reusable class
class Icast(UserDict):    
    class LameEncoder(Encoder):
        def __init__(self, br, sr):
            Encoder.__init__(self, br, sr)

        # THIS IS HARD ON CPU SINCE IT NEEDS TO REENCODE THE SONG BEING CURRENTLY PLAYED BY THE CLIENT ON THE FLY,
        # WELL, SLOW ONLY WHILE IT'S ENCODING
        # TODO Improve so it gets deeepeer on the cpu
        def encode(self, input):
            cmdline = 'cat "%s" | lame --mp3input --cbr -b %d --resample %d - - > %s' \
                    % (input, self.bitrate, self.samplerate,    self.dump)
            subprocess.call(cmdline, shell=True)

    def __init__(self):
        UserDict.__init__(self)
        self.server = shout.Shout()
        self.client = Client()
        self.connected = False
        self.current_track = None
        self.streaming = False
        self.reencode = False
        self.encoder = None
        self["host"] = "localhost"
        self["port"] = 8000
        self["pass"] = "hackme"
        self["user"] = "source"
        self["mount"] = "/icast"
        self["protocol"] = "http"
        self["format"] = "mp3"
        self["name"] = "Icast Stream"
        self["genre"] = "none"
        self["url"] = "none"
        self["description"] = "none"
        self["bitrate"] = 128
        self["samplerate"] = 44100

    def connect(self):
        if not self.connected:
            self.client.log("Connecting to server %s:%d" % (self["host"], self["port"]))
            self.server.host = self["host"]
            self.server.port = self["port"]
            self.server.user = self["user"]
            self.server.password = self["pass"]
            self.server.mount = self["mount"]
            self.server.protocol = self["protocol"]
            self.server.format = self["format"]
            self.server.name = self["name"]
            self.server.genre = self["genre"]
            self.server.url = self["url"]
            self.server.description = self["description"]
            self.server.audio_info = {"bitrate":str(self["bitrate"]), 
                    "samplerate":str(self["samplerate"])}
            # We still don't support ogg reencoding
            if self.reencode and self["format"] == "ogg":
                self.reencode = False
            try:
                self.server.open()
            except shout.ShoutException:
                self.client.log("Couldn't connect to server")
                raise Exception
            self.connected = True
            self.client.log("Connection with server established")

    def disconnect(self):
        if self.connected:
            self.server.close()
            self.connected = False
            self.streaming = False
            if self.encoder:
                self.encoder.remove_dump()
            self.client.log("Disconnected from server")

    @common.threaded
    def encode_stream(self):
        # this is temporal, killing the previous thread would do much better
        subprocess.call("killall lame", shell=True)
        self.client.log("Reencoding track with bittrate %skbps and samplarate %shz"
                % (self.encoder.bitrate, self.encoder.samplerate))
        self.encoder.encode(self.client.get_current_track())
    
    # TODO can this be improved?
    def stream(self):
        f = None
        change_data = False
        while True:
            # if client is playing
            if self.client.is_playing():
                if not self.connected:
                    try:
                        self.connect()
                    except Exception:
                        change_data = False
                    else:
                        change_data = True
                if change_data:
                    self.current_track = self.client.get_current_track()
                    if f:
                        f.close()
                    if self.reencode:
                        # is this safe?
                        self.encode_stream()
                        time.sleep(1)
                        f = open(self.encoder.get_dump())
                    else:
                        f = open(self.current_track)
                    change_data = False
                    self.streaming = True
                    # TODO this should appear in clients window too
                    self.client.log("Streaming song %s" % self.current_track)
                    try:
                        # TODO Send nice formatted information from id tags
                        self.server.set_metadata(
                            {
                                "song":"%s - %s" % (self.current_track.artist,
                                                    self.current_track.title)
                            })
                    except shout.ShoutException:
                     self.client.log("Sending metadata to the server not available" )
                if self.streaming:
                    buf = f.read(4096)
                    if len(buf) == 0:
                        change_data = True
                        self.streaming = False
                    else:
                        self.server.send(buf)
                        self.server.sync()
                # Song changed
                if self.current_track != self.client.get_current_track():
                    change_data = True
                    self.streaming = False
            # if not playing
            else:
                if self.connected:
                    self.streaming = False
                    time.sleep(1)
                    # if client stopped, disconnect from server
                    if not self.client.is_playing():
                        # TODO this should appear in clients window too
                        self.client.log("Streaming stopped")
                        f.close()
                        change_data = False
                        self.disconnect()
            time.sleep(0.1)

# ------------------------------------------------------------------------------------------------------------------------- #
# Plugin code starts here. START HERE IF YOU NEED TO CHANGE ANY OPTION

PLUGIN_NAME = "Icast Streamer"
PLUGIN_AUTHORS = ['Edgar Merino <donvodka at gmail dot com>']
PLUGIN_VERSION = '0.2.1'
PLUGIN_DESCRIPTION = r"""Stream to an icecast/shoutcast server\n\nSee
https://bugs.launchpad.net/exaile/+bug/136851 for instructions on how to use
it."""
PLUGIN_ENABLED = False
button = gtk.Button()
PLUGIN_ICON = button.render_icon('gnome-dev-usb', gtk.ICON_SIZE_MENU)
button.destroy()

PLUGIN = None

class ExaileClient(Client):
    def __init__(self, player):
        Client.__init__(self, player)

    def is_playing(self):
        return self.player.is_playing()

    def get_current_track(self):
        return self.player.current.io_loc

    def log(self, s):
        xlmisc.log("IcastPlugin: %s" % s)

class IcastPlugin(Icast):
    def __init__(self):
        Icast.__init__(self)
        self.client = ExaileClient(APP.player)

        # IF YOU NEED TO CHANGE ANY OPTION TO CONNECT TO THE ICECAST SERVER THIS IS THE PLACE TO DO IT
        # AT LEAST THE "PASS" KEY MUST BE CHANGED

        #self["host"] = "localhost"
        #self["port"] = 8000
        #self["user"] = "source"
        self["pass"] = "hackme"
        #self["mount"] = "/icast"

        # PROTOCOLS SUPPORTED:
        # "http" : icecast 2
        # "xaudiocast" : icecast
        # "icy" : shoutcast
        #self["protocol"] = "http"
        
        # FORMATS SUPPORTED:
        # "mp3", "ogg"
        #self["format"] = "mp3"

        #self["name"] = "Icast Station"
        #self["genre"] = "none"
        #self["url"] = "none"
        #self["description"] = "none"

        # ENABLE REENCODING, MP3 ONLY
        self.reencode = False
        # Only _LameEncoder available right now, configuration dialog should avoid design flow
        if self.reencode and self["format"] == "mp3":
            self.encoder = self.LameEncoder(self["bitrate"], self["samplerate"])
        #self["bitrate"] = 128 # in kbps
        #self["samplerate"] = 44000 # in Hz

    @common.threaded
    def stream(self):
        Icast.stream(self)

# TODO cambiar por dialogo de configuracion adecuado
def configure():
    pass

def initialize():
    global PLUGIN

    exaile = APP
    if not SHOUT_AVAIL:
        common.error(APP.window, "shout library could not be loaded. You need "
                " libshout 2 and shout python bindings. Streaming will not be available")
        return False
    PLUGIN = IcastPlugin()
    # TODO is there a better way to wait for music to start?
    PLUGIN.stream()

    return True

def destroy():
    global PLUGIN

    if PLUGIN:
        PLUGIN.disconnect()

    PLUGIN = None

