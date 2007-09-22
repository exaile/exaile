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

# TODO implement option "remove duplicates" to the edit menu in exaile

from UserDict import UserDict
import sys, os, gtk, time, subprocess, tempfile
# if used outside exaile, import threading
# import threading
# exaile imports
from xl import common, xlmisc
from gettext import gettext as _
import xl.plugins as plugins

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
    """
        Main Client interface
        Other clients will subclass it
    """
    def __init__(self, app):
        self.app = app # player that holds a reference to the current song being played
        self.current_track = None # Our players current track

    def is_playing(self):
		return False

    def get_current_track(self):
   		return None

    def get_next_track(self):
        return None

    def get_track_metadata(self):
        """
            Metadata to send to the server
        """
        return self.get_current_track()

    def close(self):
        """
            Do any operations needed when the client is closed
        """
        self.current_track = None

  	# if no log facility, just print s
    def log(self, s):
        """
            Log to client's log facility or stdout
        """
        print s

# Reusable abstract class
# You don't like lame? implement your own encoder!
# TODO it should contain the name of the track to encode as a class member
class Encoder(UserDict):
    """
        Main Encoder interface
        Other encoders will be its childs
    """
	# A basic encoder only needs bitrate and samplerate, everything else is optional
    def __init__(self):
        UserDict.__init__(self)
        self["bitrate"] = 128
        self["samplerate"] = 44100
        self.format = "none"
        self.pid = None
        self._dump = None

    def encode(self):
        pass

    def stop_encode(self):
        """
            Stop encoding
        """
        if self.pid:
            subprocess.call("kill -9 %d" % self.pid, shell=True)
            self.pid = None

    def get_dump(self):
        return self._dump

    # This might not be enough at some point with slow computers,
    # we need to get a way to know the size of the file and exit
    # until enough data's been written by the encoder
    def sync(self):
        """
            Give some time to the encoder to write necessary data
        """
        while True:
            if self.pid:
                time.sleep(1.0)
                break
            time.sleep(0.01)
    
    # TODO this should be private, it'll be possible when encode gets implemented here
    def create_dump(self):
        if self._dump:
            self._dump.close()
        self._dump = tempfile.NamedTemporaryFile(suffix=".%s" \
                % self.format)

# TODO only support MP3 and OGG, other formats might be supported in the future
# (actually just need someone to reimplement the LameEncoder() provided)
# Reusable class
class Icast(UserDict):
    """
        Stream music to an icecast/shoutcast server
    """
    class LameEncoder(Encoder):
        """
           Lame MP3 Encoder
        """
        def __init__(self):
            Encoder.__init__(self)
            self.format = "mp3"

        # THIS IS HARD ON CPU SINCE IT NEEDS TO REENCODE THE SONG BEING CURRENTLY PLAYED BY THE CLIENT ON THE FLY,
        # WELL, SLOW ONLY WHILE IT'S ENCODING
        # TODO Improve so it gets deeepeer on the cpu
        # TODO this can be placed in the Encoder abstract class, making it easier to implement new encoders
        def encode(self, input):
            # The dump has to be created everytime we encode
            self.create_dump()
            #p1 = subprocess.Popen('arecord -t wav -f cd -D copy >> /dev/stdout', stdout=subprocess.PIPE, shell=True)
            p1 = subprocess.Popen('cat "%s"' % input, stdout=subprocess.PIPE, shell=True)
            p2 = subprocess.Popen('lame --mp3input --cbr -b %d --resample %d - - > %s' \
                    % (self["bitrate"], self["samplerate"],  self.get_dump().name), \
                    stdin=p1.stdout, stdout=subprocess.PIPE, shell=True)
            self.pid = p1.pid
            p1.wait()
            self.pid = None

    # Don't use me, I'm buggy :)
    class OggEncoder(Encoder):
        """
            Oggenc interface
        """
        def __init__(self):
            Encoder.__init__(self)
            self.format = "ogg"
        
        def encode(self, input):
            self.create_dump()
            # I don't know how to reencode an ogg track on the fly... 
            p1 = subprocess.Popen('oggdec "%s" >> /dev/stdout' \
                    % input, stdout=subprocess.PIPE, shell=True)
            p2 = subprocess.Popen('oggenc --managed -b %d --resample %d - > "%s"' \
                    % (self["bitrate"], self["samplerate"], self.get_dump().name), \
                    stdin=p1.stdout, stdout=subprocess.PIPE, shell=True)
            self.pid = p1.pid
            p1.wait()
            self.pid = None

    def __init__(self):
        UserDict.__init__(self)
        self._server = shout.Shout()
        self.client = Client(None)
        self.connected = False
        self.current_track = None
        self.reencode = False
        self.broadcasting_live = False
    	# Default encoder
        self.encoder = self.LameEncoder()
        #self.encoder = self.OggEncoder()
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
        """
            Connect to server
        """
        if not self.connected:
            self.client.log("Connecting to server %s:%d" % (self["host"], self["port"]))
            self._server.host = self["host"]
            self._server.port = self["port"]
            self._server.user = self["user"]
            self._server.password = self["pass"]
            self._server.mount = self["mount"]
            self._server.protocol = self["protocol"]
            self._server.format = self["format"]
#            if self.broadcasting_live:
#                self._server.nonblocking = True
            self._server.name = self["name"]
            self._server.genre = self["genre"]
            self._server.url = self["url"]
            self._server.description = self["description"]
            self._server.audio_info = {"bitrate":str(self["bitrate"]), 
                    "samplerate":str(self["samplerate"])}
            # We still don't support ogg reencoding
            if self.reencode and self["format"] == "ogg":
                self.reencode = False
            try:
                self._server.open()
            except shout.ShoutException:
                self.client.log("Failed connecting to server")
                raise Exception
            self.connected = True
            self.client.log("Connection with server established")

    def disconnect(self):
        """
            Disconnect from server
        """
        if self.connected:
            self._server.close()
            self.connected = False
            self.client.close()
            if self.reencode:
                self.encoder.stop_encode()
            self.client.log("Disconnected from server")
    
    @common.threaded
    def _reencode_track(self):
        """
            Call encoder to reencode current track
        """
        # We make sure we are the only thread reencoding
        self.encoder.stop_encode()
        self.encoder["bitrate"] = self["bitrate"]
        self.encoder["samplerate"] = self["samplerate"]
        self.client.log("Reencoding track with bittrate %skbps and samplerate %shz"
                % (self.encoder["bitrate"], self.encoder["samplerate"]))
        self.encoder.encode(self.client.get_current_track())
        self.client.log("Done reencoding '%s'" \
                % self.current_track)
  
    # data requested from the file can be changed to increase time to wait for the server, this is the key to make 
	# reencoding go easier on the cpu by pausing the encode_stream() thread
    # icecast/shoutcast only support mp3 and ogg, (maybe mp4 too), that should be implemented (but the encoder can 
	# accept any format, it won't be affected since the dump file it returns should be one of the two supported formats =)
	
    def _send_data(self, f):
        """
            Send data to the server
        """
        buf = f.read(4096)
        if len(buf) == 0:
            self.client.log("Done sending '%s'" \
                    % self.current_track)
            return False
        try:
            self._server.send(buf)
        except shout.ShoutException:
            self.disconnect()
            return False
        self._server.sync()
        return True

    def _update_info(self, f):
        """
            Update info for data to be streamed
        """
        self.current_track = self.client.get_next_track()
        if not self.current_track: return None
        # TODO this should appear in clients window too
        self.client.log("Streaming song %s" % self.current_track)
        try:
            self._server.set_metadata({
		        "song": str(self.client.get_track_metadata())
			})
        except shout.ShoutException:
            self.client.log("Sending metadata to the server not available" )
        if f:
            if self.broadcasting_live:
                return f
            else:
                f.close()
        if self.reencode:
            self._reencode_track()
            # give the encoder time to write necessary data before streaming
            self.encoder.sync()
            return self.encoder.get_dump()
        return open(self.current_track)

    def _close_stream(self, f = None):
        """
            Close the current stream
        """
        # TODO this should appear in clients window too
        self.client.log("Closing the stream...")
        if f:
            f.close()
        self.disconnect()

    # TODO method should provide a way to exit grecefully
    def icast_main(self):
        """
            Main Icast method, loops forever
        """
        change_data = False
        streaming = False
        connect_retry = False
        retry_delay = 3 #seconds
        f = None
        done = False
        while True:
            if self.client.is_playing() \
                    and not done:
                # Connect if needed
                if not self.connected:
                    if connect_retry:
                        # Something happened, maybe just give the server some time to settle down
                        time.sleep(retry_delay)
                        connect_retry = False
                    # TODO handle exceptions properly
                    try:
                        self.connect()
                    except Exception:
                        change_data = False
                        self.client.log("Connection retry count: 1")
                        connect_retry = True
                    else:
                        change_data = True
                if change_data:
                    # Update information
                    f = self._update_info(f)
                    if not f: 
                        self.client.log("Finished sending data")
                        self._close_stream()
                        done = True
                    else: 
                        streaming = True
                    change_data = False
                if streaming:
                    # Send data (and only do that! don't close the file!)
                    streaming = self._send_data(f)
                    if not streaming:
                        # If sending data is done, send another track
                        change_data = True
                # TODO if someone wants to stream the same song twice (why would you freak?) this won't work
#                if self.current_track != \
#                        self.client.get_current_track():
                    # Song changed
#                    change_data = True
    		# if not playing
            elif done and not self.client.is_playing():
                done = False
            elif self.connected:
                # if client stopped, disconnect from server
                # TODO how can we avoid this? we are suppose to only disconnect, not check if it's playing or not
                time.sleep(0.5)
                if not self.client.is_playing():
                    self._close_stream(f)
                    change_data = False
                    if done: done = False
            time.sleep(0.01)
  
# ----------------------------------------------------------------------------------------------------------------#
# Plugin code starts here. START HERE IF YOU NEED TO CHANGE ANY OPTION

PLUGIN_NAME = _("Icast Streamer")
PLUGIN_AUTHORS = ['Edgar Merino <donvodka at gmail dot com>']
PLUGIN_VERSION = "0.5.1"
__version = PLUGIN_VERSION
PLUGIN_DESCRIPTION = _(r"""Stream to an icecast/shoutcast server""")
PLUGIN_ENABLED = False
button = gtk.Button()
# TODO change with proper icon, is this really needed?
PLUGIN_ICON = button.render_icon('gnome-dev-usb', gtk.ICON_SIZE_MENU)
button.destroy()

PLUGIN = None

class ExaileClient(Client):
    """
        Exaile interface to the Icast Client
    """
    def __init__(self, app):
        Client.__init__(self, app)

    def is_playing(self):
  	    return self.app.player.is_playing()
  
    def get_current_track(self):
        return self.current_track.io_loc

    def get_next_track(self):
        self.current_track = self.app.tracks.get_next_track(self.current_track)
        if not self.current_track: 
            if not self.app.player.current: return None
            self.current_track = self.app.player.current
        return self.current_track.io_loc

    def get_track_metadata(self):
        return "%s - %s" \
                % (self.current_track.get_artist(), \
                self.current_track.get_title())

    def log(self, s):
        xlmisc.log("IcastPlugin: %s" % s)

class IcastPlugin(Icast):
    """
        Icast Plugin for Exaile
    """
    def __init__(self):
        Icast.__init__(self)
        self.client = ExaileClient(APP)

        # IF YOU NEED TO CHANGE ANY OPTION TO CONNECT TO THE ICECAST/SHOUTCAST
        # SERVER THIS IS THE PLACE TO DO IT AT LEAST THE "PASS" KEY MUST BE CHANGED

        #self["host"] = "localhost"
        #self["port"] = 8000
        #self["user"] = "source"
        self["pass"] = "imyourgod"
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
        self.encoder = self.LameEncoder()
        # THERE'S CURRENTLY NO SUPPORT TO SEND LIVE AUDIO FROM SOUNDCARD OUTPUT, DON'T CHANGE THIS
        # self.broadcasting_live = False 
        # if you want to set an encoder different than LameEncoder, this is the place to do it
        # this can be changed anywhere, we support live reencoding
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
        # Long string... Mathias said this won't work for gettext if not done like this
        common.error(APP.window, _("Shout library could not be loaded. You need libshout 2 and shout python bindings. Streaming will not be available"))
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
