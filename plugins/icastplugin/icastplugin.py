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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


from xl import common, xlmisc
from UserDict import UserDict
import sys, os, gtk, time, subprocess, threading
import xl.plugins as plugins
import gtk.glade

try:
    import shout
    SHOUT_AVAIL = True
except ImportError:
    SHOUT_AVAIL = False

# Code taken from exaile src
# if you want to reuse the code, you'll need this
#def threaded(f):
#    """
#        A decorator that will make any function run in a new thread
#    """
#    def wrapper(*args, **kwargs):
#        t = threading.Thread(target=f, args=args, kwargs=kwargs)
#        t.setDaemon(True)
#        t.start()
#
#    wrapper.__name__ = f.__name__
#    wrapper.__dict__ = f.__dict__
#    wrapper.__doc__ = f.__doc__
#
#    return wrapper

# Reusable abstract class
# This is needed to make the class Icast not depend on exaile
class Client:
    def __init__(self, player):
        self.player = player # player that holds a reference to the current song being played

    def is_playing(self):
        pass

    def get_current_track(self):
   		pass

    def get_track_metadata(self):
        pass

  	# if no log facility, just print s
    def log(self, s):
        pass

# Reusable abstract class
# You don't like lame? implement your own encoder!
class Encoder(UserDict):
	# A basic encoder only needs bitrate and samplerate, everything else is optional
    def __init__(self):
        UserDict.__init__(self)
        self["bitrate"] = 0
        self["samplerate"] = 0
        # TODO use os.tmpfile() to create temporal dump
        self.dump = "/tmp/encode.dump"

    def encode(self):
        pass

    def get_dum(self):
        return self.dump

    def remove_dump(self):
        os.remove(self.dump)    

# TODO support paused state, is this really needed?
# TODO only support MP3 and OGG, other formats might be supported in the future
# (actually just need someone to reimplement the LameEncoder() provided)
# Reusable class
class Icast(UserDict):
    class LameEncoder(Encoder):
        def __init__(self):
            Encoder.__init__(self)
            self["bitrate"] = 128
            self["samplerate"] = 44100

        # THIS IS HARD ON CPU SINCE IT NEEDS TO REENCODE THE SONG BEING CURRENTLY PLAYED BY THE CLIENT ON THE FLY,
        # WELL, SLOW ONLY WHILE IT'S ENCODING
        # TODO Improve so it gets deeepeer on the cpu
        def encode(self, input):
    	    cmdline = 'cat "%s" | lame --mp3input --cbr -b %d --resample %d - - > %s' \
                    % (input, self["bitrate"], self["samplerate"],  self.dump)
            subprocess.call(cmdline, shell=True)

    def __init__(self):
        UserDict.__init__(self)
        self.__server = shout.Shout()
        self.client = Client(None)
    	self.connected = False
        self.current_track = None
        self.streaming = False
        self.reencode = False
    	# Default encoder
        self.encoder = self.LameEncoder()
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
            self.__server.host = self["host"]
            self.__server.port = self["port"]
            self.__server.user = self["user"]
            self.__server.password = self["pass"]
            self.__server.mount = self["mount"]
            self.__server.protocol = self["protocol"]
            self.__server.format = self["format"]
            self.__server.name = self["name"]
            self.__server.genre = self["genre"]
            self.__server.url = self["url"]
            self.__server.description = self["description"]
            self.__server.audio_info = {"bitrate":str(self["bitrate"]), 
                    "samplerate":str(self["samplerate"])}
            # We still don't support ogg reencoding
            if self.reencode and self["format"] == "ogg":
                self.reencode = False
            try:
                self.__server.open()
            except shout.ShoutException:
                self.client.log("Couldn't connect to server")
                raise Exception
            self.connected = True
            self.client.log("Connection with server established")

    def disconnect(self):
        if self.connected:
            self.__server.close()
            self.connected = False
            self.streaming = False
        if self.reencode:
            self.encoder.remove_dump()
            self.client.log("Disconnected from server")
    
    @common.threaded
    def __encode_stream(self):
        # this is temporal, killing the previous thread would do much better
        subprocess.call("killall lame", shell=True)
        self.encoder["bitrate"] = self["bitrate"]
        self.encoder["samplerate"] = self["samplerate"]
        self.client.log("Reencoding track with bittrate %skbps and samplarate %shz"
                % (self.encoder["bitrate"], self.encoder["samplerate"]))
        self.encoder.encode(self.client.get_current_track())
  
    # data requested can be changed to increase time to wait for the server, this is the key to make reencoding
    # go easier on the cpu by pausing the encode_stream() thread
    def __stream_data(self, f):
        buf = f.read(4096)
        if len(buf) == 0:
            f.close()
            return False
        self.__server.send(buf)
        self.__server.sync()
        return True

    def __update_info(self, f):
        self.current_track = self.client.get_current_track()
        if f:
            f.close()
        # TODO this should appear in clients window too
        self.client.log("Streaming song %s" % self.current_track)
        try:
            self.__server.set_metadata({
                "song":self.client.get_track_metadata()
            })
        except shout.ShoutException:
            self.client.log("Sending metadata to the server not available" )
        if self.reencode:
            self.__encode_stream()
            time.sleep(1)
            return open(self.encoder.get_dump())
        return open(self.current_track)

    def __close_stream(self, f):
        # TODO this should appear in clients window too
        self.client.log("Streaming stopped")
        f.close()
        self.disconnect()

    def icast_main(self):
        change_data = False
        streaming = False
        f = None
        while True:
            if self.client.is_playing():
                # Connect if needed
                if not self.connected:
                    try: 
                        self.connect()
                    except Exception:
                        change_data = False
                    else:
                        change_data = True
                if change_data:
                    # Update information
                    f = self.__update_info(f)
                    change_data = False
                    streaming = True
                if streaming:
                    # Stream and check if data should be updated
                    if not self.__stream_data(f):
                        change_data = True
                        self.current_track = None
                if not change_data and \
                        self.current_track != self.client.get_current_track():
                    # Song changed
                    change_data = True
    		# if not playing
            else:
                if self.connected:
                    streaming = False
                    time.sleep(1)
                    # if client stopped, disconnect from server
                    if not self.client.is_playing():
                        self.__close_stream(f)
                        change_data = False
            time.sleep(0.1)
  
# ------------------------------------------------------------------------------------------------------------------------- #
# Plugin code starts here. START HERE IF YOU NEED TO CHANGE ANY OPTION

PLUGIN_NAME = "Icast Streamer"
PLUGIN_AUTHORS = ['Edgar Merino <donvodka at gmail dot com>']

# this needs to be this way because the plugin repository looks for this
# format in order to add the plugin to the list of available plugins
PLUGIN_VERSION = "0.4.1"
__version__ = PLUGIN_VERSION
PLUGIN_DESCRIPTION = r"""Stream to an icecast/shoutcast server"""
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

    def get_track_metadata(self):
        return "song: %s - %s" \
                % (self.player.current.get_artist(), \
                self.player.current.get_title())

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
        # if you want to set an encoder different than LameEncoder, this is the place to do it
        #self.encoder = self.LameEncoder()
        #self["bitrate"] = 128 # in kbps
        #self["samplerate"] = 44000 # in Hz

    @common.threaded
    def main(self):
        self.icast_main()

FIELDS = {
    'host': 'localhost',
    'port': 8000,
    'pass': 'hackme',
    'user': 'source',
    'mount': '/icast',
    'protocol': 'protocol',
    'format': 'mp3',
    'name': 'Icast Stream',
    'genre': 'none',
    'url': 'http://localhost:8000',
    'bitrate': 128,
    'samplerate': 44100
}

INTS = (8000, 128, 44100)

def configure():
    """
        Allows for configuration of the icastplugin
    """
    global PLUGIN
    xml = gtk.glade.xml_new_from_buffer(XML_STRING, len(XML_STRING))
    dialog = xml.get_widget('ConfigDialog')

    for k, v in FIELDS.iteritems():
        func = 'get_str'
        if v in INTS: func = 'get_int'
        func = getattr(APP.settings, func)

        value = func(k, default=v, plugin=plugins.name(__file__))
        widget = xml.get_widget(k)

        if isinstance(widget, gtk.ComboBox):
            i = 0; selected = 0
            for item in widget.get_model():
                if item == v: selected = i
                i += 1

            widget.set_active(selected)
        else:
            widget.set_text(str(value))

    result = dialog.run()
    dialog.hide()

    if result == gtk.RESPONSE_OK:
        for k, v in FIELDS.iteritems():
            func = 'set_str'
            if v in INTS: func = 'set_int'
            func = getattr(APP.settings, func)

            widget = xml.get_widget(k)
            if isinstance(widget, gtk.ComboBox):
                value = widget.get_active_text()
            else:
                value = widget.get_text()

            if v in INTS: value = int(value)
            func(k, value, plugin=plugins.name(__file__))

        if PLUGIN:
            PLUGIN.disconnect()
            PLUGIN = setup_plugin()
            PLUGIN.main()

def setup_plugin():
    """
        Sets up the plugin with the values in the settings
    """
    plugin = IcastPlugin()

    for k, v in FIELDS.iteritems():
        func = 'get_str'
        if v in INTS: func = 'get_int'
        func = getattr(APP.settings, func)

        value = func(k, default=v, plugin=plugins.name(__file__))
        plugin[k] = value

    return plugin

def initialize():
    global PLUGIN

    exaile = APP
    if not SHOUT_AVAIL:
        common.error(APP.window, "shout library could not be loaded. You need "
            " libshout 2 and shout python bindings. Streaming will not be available")
        return False
    PLUGIN = setup_plugin()
    PLUGIN.main()

    return True

def destroy():
    global PLUGIN

    if PLUGIN:
        PLUGIN.disconnect()

    PLUGIN = None

XML_STRING = None
def load_data(zip):
    global XML_STRING
    XML_STRING = zip.get_data('gui.glade')
