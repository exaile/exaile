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
import gst, gobject, random, time, urllib, urllib2, re, os, md5
from gettext import gettext as _
from xl import xlmisc, common, media
random.seed(time.time())

ASX_REGEX = re.compile(r'href ?= ?([\'"])(.*?)\1', re.DOTALL|re.MULTILINE)

# CREDITS FOR LAST.FM SOURCE:
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Philippe Normand <phil at base-art dot net>
class LastFMSource(gst.BaseSrc):
    __gsttemplates__ = (
        gst.PadTemplate("src",
                        gst.PAD_SRC,
                        gst.PAD_ALWAYS,
                        gst.caps_new_any()),
        )

    __gstdetails__ = ("Last.FM radios plugin",
                      "Source/File", "Read data on Last.FM radios quoi",
                      "Philippe Normand <philippe@fluendo.com>")

    blocksize = 4096
    fd = None
    
    def __init__(self, name, user=None, password=None):
        self.__gobject_init__()
        self.curoffset = 0
        self.set_name(name)
        self.user = user
        self.password = password
        self.update_func = None
        if user and password:
            self.handshake()

        pad = self.get_pad("src")
        pad.add_buffer_probe(self.buffer_probe)

    def set_update_func(self, func):
        self.update_func = func

    def buffer_probe(self, pad, buffer):
        if buffer and buffer.data:
            if buffer.data.find('SYNC') > -1:
                self.update()
        return True

    def _urlopen(self, url, params):
        if url.startswith('/'):
            url = "http://%s%s%s" % (self.params['base_url'],
                                     self.params['base_path'], url)
            
        params = urllib.urlencode(params)
        url = "%s?%s" % (url, params)
        try:
            result = urllib2.urlopen(url).readlines()
        except Exception, ex:
            self.debug(ex)
            result = None
        else:
            self.debug(result)
        return result
        
    def set_property(self, name, value):
        if name == 'uri':
            self.tune_station(value)

    def do_create(self, offset, size):
        if self.fd:
            data = self.fd.read(self.blocksize)
            if data:
                self.curoffset += len(data)
                return gst.FLOW_OK, gst.Buffer(data)
            else:
                return gst.FLOW_UNEXPECTED, None
        else:
            return gst.FLOW_UNEXPECTED, None
            
    def debug(self, msg):
        print "[Last.FM] %s" % msg

    def handshake(self):
        self.logged = False
        self.debug("Handshaking...")

        passw = md5.md5(self.password).hexdigest()
        url = "http://ws.audioscrobbler.com/radio/handshake.php"
        params = {'version': '0.1', 'platform':'linux',
                  'username': self.user, 'passwordmd5': passw, 'debug':'0'}

        result = self._urlopen(url, params)

        if result:
            self.params = {}
            for line in result:
                if line.endswith('\n'):
                    line = line[:-1]
                parts = line.split('=')
                if len(parts) > 2:
                    parts = [parts[0], '='.join(parts[1:])]
                self.params[parts[0]] = parts[1]
            if self.params['session'] != 'FAILED':
                self.logged = True
                self.update()
                
    def tune_station(self, station_uri):
        if not self.logged:
            self.debug('Error: %s' % self.params.get('msg'))
            # TODO: raise some exception? how to tell gst not to go further?
            return
        
        self.debug("Tuning to %s" % station_uri)
        
        url = "/adjust.php"
        params = {"session": self.params['session'], "url": station_uri,
                  "debug": '0'}

        result = self._urlopen(url, params)
        if result:
            response = result[0][:-1].split('=')[1]
            if response == 'OK':
                self.fd = urllib2.urlopen(self.params['stream_url']).fp
                self.update()
                
    def update(self):
        """
        Update current track metadata to `self.track_infos` dictionary which
        looks like:

        ::
           {'album': str
            'albumcover_large': uri (str),
            'albumcover_small': uri (str),
            'albumcover_medium': uri (str),
            'shopname': str, 'artist': str,
            'track': str,
            'price': str, 'trackduration': int,
            'streaming': boolean ('true'/'false'),
            'artist_url': uri (str),
            'album_url': uri (str),
            'station': str,
            'radiomode': int, 'station_url': uri (str),
            'recordtoprofile': int,  'clickthrulink': str, 'discovery': int
           }
        """
        url = "/np.php"
        params = {'session': self.params['session'], 'debug':'0'}
        result = self._urlopen(url, params)
        self.track_infos = {}
        if result:
            for line in result:
                # strip ending \n
                if line.endswith('\n'):
                    line = line[:-1]
                parts = line.split('=')
                if len(parts) > 2:
                    parts = [parts[0], '='.join(parts[1:])]
                try:
                    value = int(parts[1])
                except:
                    value = parts[1]
                self.track_infos[parts[0]] = value
            self.debug(self.track_infos)
            if self.update_func:
                self.update_func()

    @common.threaded
    def control(self, command):
        """
	Send control command to last.fm to skip/love/ban the currently
	played track or enable/disable recording tracks to profile.

        `command` can be one of: "love", "skip", "ban", "rtp" and "nortp"
        """
        url = "/control.php"
        params = {'session': self.params['session'], 'command': command,
                  'debug':'0'}
        result = self._urlopen(url, params)
        if result:
            response = result[0][:-1].split('=')[1]
            if response == 'OK':
                self.update()
                return True
        return False

    def set_discover(self, value):
        """

        """
        uri = "lastfm://settings/discovery/%s"
        if value:
            uri = uri % "on"
        else:
            uri = uri % "off"
        self.tune_station(uri)

    def love(self):
        return self.control('love')

    def skip(self):
        return self.control('skip')

    def ban(self):
        return self.control('ban')

    def set_record_to_profile(self, value):
        if value:
            cmd = 'rtp'
        else:
            cmd = 'nortp'
        return self.command(cmd)
    
gobject.type_register(LastFMSource)

class Player(gobject.GObject):
    """
        This is the main player interface, other engines will subclass it
    """
    def __init__(self):
        gobject.GObject.__init__(self)

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

        if not self.connections and not self.is_paused() and not \
            uri.find("lastfm://") > -1:
            self.connections.append(self.bus.connect('message', self.on_message))
            self.connections.append(self.bus.connect('sync-message::element',
                self.on_sync_message))

            if '://' not in uri: 
                if not os.path.isfile(uri.encode(xlmisc.get_default_encoding())):
                    raise Exception('File does not exist: %s' %
                        uri.encode(xlmisc.get_default_encoding()))

                uri = 'file://%s' % uri
            uri = uri.replace('%', '%25')
            self.playbin.set_property('uri', uri.encode(xlmisc.get_default_encoding()))

        self.playbin.set_state(gst.STATE_PLAYING)

    def on_sync_message(self, bus, message):
        """
            called when gstreamer requests a video sync
        """
        if message.structure.get_name() == 'prepare-xwindow-id' and \
            VIDEO_WIDGET:
            xlmisc.log('Gstreamer requested video sync')
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
            xlmisc.log("Couldn't send seek event")
        if wait: self.playbin.get_state(timeout=50*gst.MSECOND)

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

        self.playbin.set_state(gst.STATE_NULL)

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

class ExailePlayerErrorWindow(gtk.Window):
    """
        A simple log that will track errors during playback.  
        This was developed to catch errors like "file was not found" and go to
        the next song instead of interupting playback
    """
    def __init__(self, parent):
        """
            Initializes the window
        """
        gtk.Window.__init__(self)
        self.set_title(_('Errors'))
        self.set_transient_for(parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

        main = gtk.VBox()
        self.connect('delete_event', self.on_delete)
        main.set_border_width(3)
        main.set_spacing(3)
        label = gtk.Label()
        label.set_markup(_('<b>The following errors have occurred</b>'))
        main.pack_start(label, False, False)
        self.add(main)
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        main.pack_start(self.scroll, True, True)

        self.view = gtk.TextView()
        self.view.set_editable(False)
        self.buf = self.view.get_buffer()
        self.scroll.add(self.view)

        buttons = gtk.HBox()
        close = gtk.Button(_('Close'))
        buttons.pack_end(close, False, False)
        main.pack_start(buttons, False, False)

        close.connect('clicked', lambda *e: self.hide())
        self.resize(400, 300)

    def log(self, message, timestamp=None):
        """ 
            Logs a message
        """

        if not timestamp: timestamp = time.time()
        lt = time.localtime(timestamp)
        text = "[%s] %s\n" % (time.strftime("%H:%M:%S", lt), message)
        char = self.buf.get_char_count()
        iter = self.buf.get_iter_at_offset(char + 1)

        self.buf.insert(iter, text)

        char = self.buf.get_char_count()
        iter = self.buf.get_iter_at_offset(char + 1)
        self.view.scroll_to_iter(iter, 0)

    def on_delete(self, *e):
        """
            Hides the window instead of destroying it
        """
        self.hide()

        return True

class ExailePlayer(GSTPlayer):
    """
        Exaile interface to the GSTPlayer
    """
    __gsignals__ = {
        'play-track': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
        'stop-track': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
    }

    def __init__(self, exaile):
        self.exaile = exaile
        GSTPlayer.__init__(self)
        self.last_played = None
        self.played = []
        self.queued = []
        self.history = []
        self._stop_track = None
        self.next_track = None
        self.shuffle = False
        self.repeat = False
        self.last_track = ''
        self.lastfm_play_total = 0
        self.lastfm_last_length = 0
        self.lastfm_first = True
        self.equalizer = None
        self.error_window = ExailePlayerErrorWindow(self.exaile.window)

        self.eof_func = self.exaile.on_next
        self.current = None

    def get_stop_track(self):
        """
            returns the stop_track (track to stop playback)
        """
        return self._stop_track

    def set_stop_track(self, value):
        """
            sets the stop_track (track to stop playback)
        """
        stop_image = self.exaile.xml.get_widget('stop_track_image')
        stop_image.clear()
        if value:
            pixbuf = xlmisc.get_text_icon(self.exaile.window,
                '', 8, 8, 
                    bgcolor='#9b0000', bordercolor='#9b0000')
            stop_image.set_from_pixbuf(pixbuf)
        self._stop_track = value
    
    stop_track = property(get_stop_track, set_stop_track)

    def set_audio_sink(self, sink=None):
        """
            Sets the audio sink up.  It tries the passed in value, and if that
            doesn't work, it tries autoaudiosink
        """

        self.audio_sink = self._get_audio_sink(sink)

        # if the audio_sink is still not set, use a fakesink
        if not self.audio_sink:
            xlmisc.log('Audio Sink could not be set up.  Using a fakesink '
               'instead.  Audio will not be available.')
            self.audio_sink = gst.element_factory_make('fakesink')

        self.playbin.set_property('audio-sink', self.audio_sink)

    def _get_audio_sink(self, sink=None):
        """
            Returns the appropriate audio sink
        """

        if not sink: sink = self.exaile.settings.get_str('audio_sink',
            'Use GConf Settings')
        sink = sink.lower()
        if "gconf" in sink: sink = 'gconfaudiosink'
        elif "auto" in sink: sink = 'autoaudiosink'
        try:
            asink = gst.element_factory_make(sink)
        except:
            xlmisc.log("Could not create sink %s.  Trying autoaudiosink." %
                sink)
            asink = gst.element_factory_make('autoaudiosink')
        sinkbin = gst.Bin()

        try: # Equalizer element is still not very common 
            self.equalizer = gst.element_factory_make('equalizer-10bands')
        except gst.PluginNotFoundError:
            print "Warning: Gstreamer equalizer element not found, please install the latest gst-plugins-bad package"
            self.audiosink = asink
            return self.audiosink
        aconv = gst.element_factory_make('audioconvert')
		
        sinkbin.add(self.equalizer, aconv, asink)
        gst.element_link_many(self.equalizer, aconv, asink)
        sinkpad = self.equalizer.get_static_pad('sink')
        sinkbin.add_pad(gst.GhostPad('sink', sinkpad))

        self.audio_sink = sinkbin

        bands = self.exaile.settings.get_list('equalizer/band-values', [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        i = 0
        for v in bands:
            self.equalizer.set_property(('band'+str(i)), v)
            i = i + 1

        return self.audio_sink

    def get_position(self):
        """
            Gets current position minus current lastfm play time
        """
        position = GSTPlayer.get_position(self)
        if not self.is_paused(): position -= self.lastfm_play_total 

        return position

    def setup_playbin(self):
        self.lastfm = False
        self.lastfmsrc = None
        GSTPlayer.setup_playbin(self)
        self.set_audio_sink
        self.playbin.set_property('volume',
            self.exaile.settings.get_float('volume', .7))

    def set_volume(self, volume):
        if self.lastfmsrc:
            self.vcontrol.set_property('volume', volume)
            return

        GSTPlayer.set_volume(self, volume)

    def setup_lastfm_playbin(self, user, password):
        """
            Sets up a playbin for playing last.fm radio streams
        """
        xlmisc.log('Creating Last.FM Pipe')
        
        gobject.idle_add(self.exaile.status.set_first, 'Preparing Last.FM '
            'stream, please wait...')
        self.playbin = gst.Pipeline('lastfm_pipeline')
        self.vcontrol = gst.element_factory_make('volume')
        self.lastfmsrc = LastFMSource('lastfm_src', user, password)
        self.lastfm = True
        if not self.lastfmsrc.logged:
            gobject.idle_add(common.error, self.exaile.window, _('Error logging in to Last.FM: '
                '%s' % self.lastfmsrc.params.get('msg')))
            self.lastfmsrc = None
            gobject.idle_add(self.exaile.status.set_first, None)
            return
        self.set_volume(self.exaile.settings.get_float("volume", .7))

        decoder = gst.element_factory_make('decodebin')
        queue = gst.element_factory_make('queue')
        convert = gst.element_factory_make('audioconvert')
        sink = self._get_audio_sink(self.exaile.settings.get_str('audio_sink', 'Use GConf '
            'Settings'))
    
        def on_new_decoded_pad(element, pad, last):
            caps = pad.get_caps()
            name = caps[0].get_name()
            apad = convert.get_pad('sink')
            if 'audio' in name:
                if not apad.is_linked():
                    pad.link(apad)

        decoder.connect('new-decoded-pad', on_new_decoded_pad)
        self.playbin.add(self.lastfmsrc, decoder, convert, queue,
            self.vcontrol, sink)
        self.lastfmsrc.link(decoder)
        convert.link(self.vcontrol)
        self.vcontrol.link(sink)

        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.lastfm_play_total = 0

    def toggle_pause(self):
        """
            Toggles pause.  If it's a streaming track, it stops the stream and
            restarts it
        """
        if self.is_paused():
            if self.current.type == 'stream':
                self.playbin.set_state(gst.STATE_READY)
                self.playbin.set_state(gst.STATE_PLAYING)
                return
        GSTPlayer.toggle_pause(self)

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
        """
            Opens a filename like .pls, .m3u, or .asx and finds the playable
            streams in them
        """
        gobject.idle_add(self.exaile.status.set_first, _("Loading stream "
            "sources, please wait..."))
        h = urllib.urlopen(track.loc)
        asx = False
        if track.loc.lower().endswith('.asx'):
            asx = True
        loc = ''

        for i, line in enumerate(h.readlines()):
            line = line.strip()
            xlmisc.log('Line %d: %s' % (i, line.strip()))
            if line.startswith('#') or line == '[playlist]': 
                continue

            # if it's an asx stream
            if asx:
                m = ASX_REGEX.search(line)
                if m:
                    loc = m.group(2)
                    break
                continue
            else:
                if '=' in line:
                    if not line.startswith('File'): continue
                    line = re.sub('File\d+=', '', line)
                    loc = line
                    break

        gobject.idle_add(self.exaile.status.set_first, None)
        if loc:
            xlmisc.log('Found location: %s' % loc)
            track.start_time = time.time()

            gobject.idle_add(self.emit, 'play-track', track)

            try:
                gobject.idle_add(GSTPlayer.play, self, loc)
            except Exception, e:
                gobject.idle_add(common.error, self.exaile.window, str(e))
                gobject.idle_add(self.exaile.stop)

            return

        xlmisc.log('Could not find a stream location')

    def lastfm_update_func(self):
        """
            Sets last.fm track information based on what was recieved by
            last.fm
        """
        info = self.lastfmsrc.track_infos
        track = self.current
        if not track: return
        if not info.has_key('track'): return
        if info['track'] == self.last_track: return
        self.last_track = info['track']

        track.title = info['track']
        if info.has_key('album'): track.album = info['album'] 
        if info.has_key('artist'): track.artist = info['artist']
        if info.has_key('trackduration'): 
            track.length = info['trackduration']
            self.lastfm_play_total += self.get_position()
        gobject.idle_add(self.exaile.tracks.refresh_row, track)
        gobject.idle_add(self.exaile.tracks.queue_draw)

        if info['streaming'] == 'true':
            gobject.idle_add(self.exaile.play_track, self, track)

        if self.lastfm_first:
            gobject.idle_add(self.exaile.status.set_first, None)
            self.lastfm_first = False

    @common.threaded
    def play_lastfm_track(self, track):
        """
            Plays a last.fm track
        """
        self.current = track
        xlmisc.log('Attempting to play last.fm track')
        
        if not self.lastfm:
            xlmisc.log('Setting up Last.FM Source')
            user = self.exaile.settings.get_str('lastfm/user', '')
            password = self.exaile.settings.get_crypted('lastfm/pass', '')
            self.setup_lastfm_playbin(user, password)
            if not self.lastfmsrc: return
            self.lastfmsrc.set_update_func(self.lastfm_update_func)

        self.lastfmsrc.set_property('uri', track.loc)

        try:
            gobject.idle_add(GSTPlayer.play, self, track.loc)
        except Exception, e:
            gobject.idle_add(common.error, self.exaile.window, str(e))
            gobject.idle_add(self.exaile.stop)
            return

        gobject.idle_add(self.emit, 'play-track', track)
        gobject.idle_add(self.exaile.tracks.queue_draw)

    def play_track(self, track, from_button=False, ret=True):
        """
            Plays a track. If from_button is True, it means the user double
            clicked on a track or pressed the play button.  In this case if
            there is an error, playback will be stopped, otherwise, it will
            move on to the next track
        """
        self.stop(False)
        if track.loc.lower().endswith('.pls') or \
            track.loc.lower().endswith('.m3u') or \
            track.loc.lower().endswith('.asx'):
            print "FINDING STREAM URI"
            self.find_stream_uri(track)
            if ret: return True

        if track.loc.find('lastfm://') > -1 and not self.lastfm:
            self.play_lastfm_track(track)
            if ret: return True

        if self.lastfm:
            self.setup_playbin()

        try:
            GSTPlayer.play(self, track.loc)
        except Exception, e:
            self.error_window.log(str(e))
            self.error_window.show_all()
            if from_button: self.exaile.stop()
            else: 
                self.stop()
                self.current = track
                self.next()
            if ret: return False

        self.current = track
        self.emit('play-track', track)
        self.exaile.tracks.queue_draw()
        if ret: return True

    def play(self):
        """
            Plays the currently selected track
        """
        self.stop()

        if self.exaile.tracks == None: 
            self.exaile.tracks = self.exaile.playlists_nb.get_nth_page(0)
            self.exaile.songs = self.exaile.tracks.songs
            return

        self.last_played = self.current

        track = self.exaile.tracks.get_selected_track()
        if not track:
            if self.exaile.tracks.songs:
                self.next()
                return
            return

        if track in self.queued: del self.queued[self.queued.index(track)]
        self.current = track

        self.played = [track]
        self.history.append(track)
        self.play_track(track, from_button=True)
        
    def next(self):
        self.stop(False)
        if self.exaile.tracks == None: return
        if self.stop_track:
            if self.current == self.stop_track:
                self.stop_track = None
                self.stop()
                return
      
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
                self.current = self.exaile.tracks.get_songs()[0]
            else:
                self.played = []
                self.current = None
                return
        
        self.history.append(track)
        self.played.append(track)

        if track: 
            if not self.play_track(track):
                return
        self.current = track

    def previous(self):
        """
            Go to the previous track
        """

        # if the current track has been playing for less than 5 seconds, 
        # just restart it
        if self.exaile.rewind_track >= 4:
            track = self.current
            if track:
                self.stop()
                self.current = track
                self.play_track(track)
                self.exaile.rewind_track = 0
            return

        if self.history:
            self.stop()
            track = self.history.pop()
        else:
            track = self.exaile.tracks.get_previous_track(self.current)
        if not track: track = self.exaile.songs[0]

        self.current = track
        self.play_track(track)

    def stop(self, reset_current=True):
        """
            Stops the currently playing track
        """
        if self.current: self.current.start_time = 0
        current = self.current
        if reset_current: self.current = None
        GSTPlayer.stop(self)
        self.emit('stop-track', current)
        self.lastfm_play_total = 0
        if self.lastfm:
            self.setup_playbin()
            self.lastfm = False

# VideoWidget and VideoArea code taken from Listen media player
# http://listen-gnome.free.fr
class VideoWidget(gtk.Window):
    def __init__(self, exaile):
        gtk.Window.__init__(self)
        self.exaile = exaile
        self.imagesink = None
        self.area = VideoArea()
        self.is_fullscreen = False
        self.ebox = gtk.EventBox()
        self.ebox.add(self.area)
        self.ebox.connect('button-press-event', self.button_press)
        self.add(self.ebox)
        self.resize(700, 500)
        self.loaded = False
        self.connect('delete_event', self.on_delete)
        self.set_title(_("Exaile Media Player"))

    def button_press(self, widget, event):
        """
            Called when the user clicks on the event box
        """
        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.toggle_fullscreen()

    def toggle_fullscreen(self):
        """
            Toggles fullscreen mode
        """
        if not self.is_fullscreen:
            self.is_fullscreen = True
            self.fullscreen()
            self.present()
        else:
            self.is_fullscreen = False
            self.unfullscreen()
            self.present()

    def on_delete(self, *e):
        """
            Called when the window is closed
        """
        global VIDEO_WIDGET
        self.hide()
        VIDEO_WIDGET = None

        track = self.exaile.player.current
        position = 0
        if track is not None and self.exaile.player.is_playing():
            try:
                position = self.exaile.player.playbin.query_position(gst.FORMAT_TIME)[0] 
            except gst.QueryError:
                position = 0
            self.exaile.player.stop(False)
            play_track = True

        self.exaile.player.setup_playbin()
        xlmisc.finish()

        self.exaile.player.playbin.get_state(timeout=50*gst.MSECOND)
        if play_track:
            self.exaile.player.play_track(track)
            if position and track.type != 'stream':
                self.exaile.player.seek(float(position / gst.SECOND))

        return True

    def set_sink(self, sink):
        self.imagesink = sink

        self.set_window_id()
        self.area.set_sink(sink)

        # workaround to launch the visualisation on startup
        # And prevent the "Xerror GC bad" problem when 
        # visualisation start and widget not completey realize
        if not self.loaded:
            self.child.child.do_expose_event(None)
            self.loaded = True

    def set_window_id(self):
        self.imagesink.set_xwindow_id(self.child.child.window.xid)

class VideoArea(gtk.DrawingArea):
    def __init__(self,imagesink=None):
        gtk.DrawingArea.__init__(self)
        self.unset_flags(gtk.DOUBLE_BUFFERED)
        self.imagesink = imagesink

    def set_sink(self,imagesink):
        self.imagesink = imagesink

    def do_expose_event(self, event):
        if self.imagesink:
            self.imagesink.expose()
            return False
        else:
            return True

VIDEO_WIDGET = None
def show_visualizations(exaile):
    """
        Shows the visualizations window
    """
    global VIDEO_WIDGET
    xlmisc.log('Enabling visualizations')
    if VIDEO_WIDGET:
        VIDEO_WIDGET.present()
        return
    track = exaile.player.current
    play_track = False
    position = 0
    if track is not None and exaile.player.is_playing():
        try:
            position = exaile.player.playbin.query_position(gst.FORMAT_TIME)[0] 
        except gst.QueryError:
            position = 0
        exaile.player.stop(False)
        play_track = True

    VIDEO_WIDGET = VideoWidget(exaile)
    VIDEO_WIDGET.show_all()
    xlmisc.finish()
    exaile.player.playbin.get_state(timeout=50*gst.MSECOND)
    video_sink = gst.element_factory_make('xvimagesink')
    vis = gst.element_factory_make('goom')
    exaile.player.playbin.set_property('video-sink', video_sink)
    exaile.player.playbin.set_property('vis-plugin', vis)

    xlmisc.log("Player position is %d" % (position / gst.SECOND))
    if play_track:
        exaile.player.play_track(track)
        exaile.player.current = track
        if position and track.type != 'stream':
            exaile.player.seek(position / gst.SECOND, False)

    return True
