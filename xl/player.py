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
import gst, gobject, random, time, re, os, md5
import thread
from gettext import gettext as _
from xl import xlmisc, common, media, library, logger
from xl.gui import playlist as playlistgui, information
import xl.path

class Player(gobject.GObject):
    """
        This is the main player interface, other engines will subclass it
    """

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

        return True

    def __notify_source(self, o, s, num):
        s = self.playbin.get_property('source')
        s.set_property('device', num)
        self.playbin.disconnect(self.notify_id)

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
        label.set_markup('<b>' + _('The following errors have occurred') +
            '</b>')
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
        close = gtk.Button(stock=gtk.STOCK_CLOSE)
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
        'pause-toggled': (gobject.SIGNAL_RUN_LAST, None, (media.Track,))
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
        self.equalizer = None
        self.error_window = ExailePlayerErrorWindow(self.exaile.window)

        self.eof_func = self.next
        self.current = None

        self._sink_element_factories = []
        self.add_sink_element_factory(ReplayGainElementFactory)
        self.add_sink_element_factory(EqualizerElementFactory)

    def add_sink_element_factory(self, factory):
        """
            adds a GstElement factory to the audio sink link
        """
        self._sink_element_factories.append(factory)
        # TODO: Check if GstElements are unreferenced and cleaned up
        # TODO: Redesign GstElement management
        self.audio_sink = None

    def del_sink_element_factory(self, factory):
        """
            deletes a GstElement factory from the audio sink link
        """
        self._sink_element_factories.remove(factory)
        self.audio_sink = None

    def get_stop_track(self):
        """
            returns the stop_track (track to stop playback)
        """
        return self._stop_track

    def set_stop_track(self, value):
        """
            sets the stop_track (track to stop playback)
        """
        stop_button = self.exaile.stop_track_button
        if value:
            stop_button.set_sensitive(True)
        else:
            stop_button.set_sensitive(False)
        self._stop_track = value
    
    stop_track = property(get_stop_track, set_stop_track)

    def set_audio_sink(self, sink=None):
        """
            Sets the audio sink up.  It tries the passed in value, and if that
            doesn't work, it tries autoaudiosink
        """

        self.audio_sink = self._create_sink(sink)

        # if the audio_sink is still not set, use a fakesink
        if not self.audio_sink:
            xlmisc.log('Audio sink could not be set up.  Using a fakesink '
               'instead.  Audio will not be available.')
            self.audio_sink = gst.element_factory_make('fakesink')

        self.playbin.set_property('audio-sink', self.audio_sink)

    def _create_sink(self, sink=None):
        """
            Creates an element: equalizer -> replaygain -> named sink.

            If the named sink is None, use the audio_sink setting.
            The equalizer and ReplayGain elements are optional and will not be
            created if they don't exist or are disabled.
        """

        if not sink: sink = self.exaile.settings.get_str('audio_sink',
            'Use GConf Settings')
        sink = sink.lower()
        if "gconf" in sink: sink = 'gconfaudiosink'
        elif "auto" in sink: sink = 'autoaudiosink'
        try:
            asink = gst.element_factory_make(sink)
            if sink == 'gconfaudiosink':
                # The "Music and Movies" profile
                asink.set_property('profile', 1)
        except:
            xlmisc.log("Could not create sink %s.  Trying autoaudiosink." %
                sink)
            asink = gst.element_factory_make('autoaudiosink')

        sinkbin = gst.Bin()
        sink_elements = []

        # iterate through sink element factory list
        for element_factory in self._sink_element_factories:
            if element_factory.is_enabled(self):
                # This should be made a try: except: statement in case creation fails
                sink_elements += element_factory.get_elements(self)
                xlmisc.log(element_factory.name + " support initialized.")
            else:
                xlmisc.log("Not using " + element_factory.name + " disabled by the user")

        # if still empty just use asink and end
        if not sink_elements:
            return asink

        # otherwise put audiosink as last element
        sink_elements.append(asink)

        # add elements to sink and link them
        sinkbin.add(*sink_elements)
        gst.element_link_many(*sink_elements)

        # create sink pad in that links to sink pad of first element
        sinkpad = sink_elements[0].get_static_pad('sink')
        sinkbin.add_pad(gst.GhostPad('sink', sinkpad))

        return sinkbin

    def get_position(self):
        """
            Gets current position 
        """
        position = GSTPlayer.get_position(self)

        return position

    def setup_playbin(self):
        GSTPlayer.setup_playbin(self)
        self.playbin.set_property('volume',
            self.exaile.settings.get_float('volume', .7))

    def set_volume(self, volume):
        GSTPlayer.set_volume(self, volume)

    def toggle_pause(self):
        """
            Toggles pause.  If it's a streaming track, it stops the stream and
            restarts it
        """
        track = self.current

        if not track:
            self.play()
            return

        if self.is_paused():
            if self.current.type == 'stream':
                self.playbin.set_state(gst.STATE_READY)
                self.playbin.set_state(gst.STATE_PLAYING)
                return
            self.exaile.play_button.set_image(self.exaile.get_pause_image())
        else:
            self.exaile.play_button.set_image(self.exaile.get_play_image())
        GSTPlayer.toggle_pause(self)

        if self.exaile.tracks: self.exaile.tracks.queue_draw()
        self.emit('pause-toggled', self.current)

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

    def find_stream_uri(self, track):
        title = track.album[:30]
        if not title: title = None
        self.exaile.playlist_manager.import_playlist(track.io_loc, 
            play=True, title=title, newtab=True)

    def play_track(self, track, from_button=False, ret=True):
        """
            Plays a track. If from_button is True, it means the user double
            clicked on a track or pressed the play button.  In this case if
            there is an error, playback will be stopped, otherwise, it will
            move on to the next track
        """
        self.stop(False)
        lowtrackloc = track.loc.lower()
        if common.any(lowtrackloc.endswith(ext) for ext in xlmisc.PLAYLIST_EXTS):
            self.find_stream_uri(track)
            if ret: return True

        if track.type == 'stream':
            track.start_time = time.time()

#        if track.type == 'podcast':
#            if not track.download_path:
#                common.error(self.exaile.window, _('Podcast has not yet been '
#                    'downloaded'))
#                return

        self.exaile.play_button.set_image(self.exaile.get_pause_image())

        try:
            play_loc = track.loc
            if track.type == 'podcast' and track.download_path:
                play_loc = track.download_path
            GSTPlayer.play(self, play_loc)
        except Exception, e:
            logger.log_exception()
            self.error_window.log(str(e))
            self.error_window.show_all()
            if from_button: self.exaile.player.stop()
            else: 
                self.stop()
                self.current = track
                self.next()
            if ret: return False

        self.current = track
        self.exaile.update_track_information()
        track.submitted = False

        self.emit('play-track', track)

        # update information tab if it's open and set to do so
        if self.exaile.settings.get_boolean('ui/information_autoswitch',
            False):
            information.update_info(self.exaile.playlists_nb, track)

        artist_id = library.get_column_id(self.exaile.db, 'artists', 'name', track.artist)
        library.get_album_id(self.exaile.db, artist_id, track.album)

        if track.type != 'stream':
            self.exaile.cover_manager.fetch_cover(track)

        self.exaile.show_osd()
        if self.exaile.tracks: self.exaile.tracks.queue_draw()

        if self.exaile.settings.get_boolean('ui/ensure_visible', False):
            self.exaile.goto_current()

        playlistgui.update_queued(self.exaile)

        # if we're in dynamic mode, find some tracks to add
        if self.exaile.dynamic.get_active():
            thread.start_new_thread(self.exaile.get_suggested_songs, tuple())

        track.last_played = time.strftime("%Y-%m-%d %H:%M:%S",
            time.localtime())

        path_id = library.get_column_id(self.exaile.db, 'paths', 'name', track.loc)
        self.exaile.db.execute("UPDATE tracks SET last_played=? WHERE path=?",
            (track.last_played, track.loc))
        self.exaile.rewind_track = 0
        if ret: return True

    def play(self):
        """
            Plays the currently selected track
        """
        try:
            self.stop()

            if self.exaile.tracks == None: 
                self.exaile.tracks = self.exaile.playlists_nb.get_nth_page(0)
                self.exaile.songs = self.exaile.tracks.songs

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
        except Exception, e:
            xlmisc.log_exception()
            common.error(self.exaile.window, str(e))
            self.stop()
        
    def next(self):
        """
            Plays the next track in the playlist
        """
        if self.current != None:
            if self.get_current_position() < 50:
                self.exaile.update_rating(self.current, rating=-1)

        self.stop(False)
        if self.exaile.tracks == None: return
        if self.stop_track:
            if self.current == self.stop_track:
                self.stop_track = None
                self.stop()
                return
      
        track = self.exaile.tracks.get_next_track(self.current)

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
        if self.exaile.tracks: self.exaile.tracks.queue_draw()

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
        if self.exaile.tracks:  self.exaile.tracks.queue_draw()

    def stop(self, reset_current=True):
        """
            Stops the currently playing track
        """
        exaile = self.exaile

        exaile.status.set_first(None)
        exaile.cover.set_image(xl.path.get_data('images', 'nocover.png'))
        exaile.cover_manager.stop_cover_thread()

        if self.current: self.current.start_time = 0
        current = self.current
        self.emit('stop-track', current)
        if reset_current: self.current = None
        GSTPlayer.stop(self)

        exaile.playing = False

        title = _('Exaile Music Player')
        exaile.window.set_title(title)
        if exaile.tray_icon:
            exaile.tray_icon.set_tooltip(title)

        exaile.play_button.set_image(exaile.get_play_image())
        if exaile.tracks: exaile.tracks.queue_draw()
        exaile.update_track_information(None)
        exaile.new_progressbar.set_text('0:00 / 0:00')

class ReplayGainElementFactory(object):
    name = u"ReplayGain"
    
    @staticmethod
    def is_enabled(exaileplayer):
        return exaileplayer.exaile.settings.get_boolean('replaygain/enabled', True)
    
    @staticmethod
    def get_elements(exaileplayer):
        replaygain = None

        try:
            replaygain = gst.element_factory_make('rgvolume')
        except gst.PluginNotFoundError:
            xlmisc.log("ReplayGain support requires gstreamer-plugins-bad 0.10.5")

        if replaygain:
            replaygain.set_property('album-mode',
                exaileplayer.exaile.settings.get_boolean('replaygain/album_mode', True))
            replaygain.set_property('pre-amp',
                exaileplayer.exaile.settings.get_float('replaygain/preamp'))
            replaygain.set_property('fallback-gain',
                exaileplayer.exaile.settings.get_float('replaygain/fallback'))
            
            # Using the ugly method for returing a 1-element tuple
            return replaygain,

        return ()

class EqualizerElementFactory(object):
    name = u"Equalizer"
    
    @staticmethod
    def is_enabled(exaileplayer):
        if not exaileplayer.exaile.settings.get_boolean('equalizer/enabled',
            False): 
            return False
        return not exaileplayer.exaile.options.noeq
    
    @staticmethod
    def get_elements(exaileplayer):
        try: # Equalizer element is still not very common 
            exaileplayer.equalizer = gst.element_factory_make('equalizer-10bands')
        except gst.PluginNotFoundError:
            xlmisc.log("Equalizer support requires gstreamer-plugins-bad 0.10.5")

        elements = []
        if exaileplayer.equalizer:
            elements.append(exaileplayer.equalizer)
            elements.append(gst.element_factory_make('audioconvert'))

            bands = exaileplayer.exaile.settings.get_list('equalizer/band-values', [0] * 10)
            for i, v in enumerate(bands):
                exaileplayer.equalizer.set_property(('band' + str(i)), v)
        return elements

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
        self.set_title(_("Exaile Music Player"))

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
        play_track = False
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
