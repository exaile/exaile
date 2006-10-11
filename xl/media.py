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


import mutagen, mutagen.id3, mutagen.flac, mutagen.oggvorbis
import mutagen.mp3, subprocess, common
from gettext import gettext as _
import sys, time, re, os.path, os
import httplib
from traceback import print_exc
import urllib, xlmisc
import pygst
pygst.require("0.10")
import gst, gst.interfaces, gobject

# FORMAT and SUPPORTED_MEDIA are set up at the end of this file
FORMAT = dict()
exaile_instance = None

player = gst.element_factory_make("playbin")
bus = player.get_bus()
bus.add_signal_watch()
tag_bin = gst.element_factory_make("playbin")
tag_bus = tag_bin.get_bus()
tag_bus.add_signal_watch()

import scrobbler, thread, urllib

try:
    import gpod
except ImportError:
    pass

SCROBBLER_SESSION = None

## this sets up the supported types

def get_scrobbler_session(exaile=None, username="", password="", new=False): 
    """
        If there is no audio scrobbler session, one is created and returned,
        else the current one is returned
    """
    global SCROBBLER_SESSION

    if (SCROBBLER_SESSION == None or new) and \
        (username != "" and password != ""):
        SCROBBLER_SESSION = scrobbler.Scrobbler(exaile, username, password,
            client="exa")
        try:
            SCROBBLER_SESSION.handshake()
        except SyntaxError:
            xlmisc.log_exception()
            return None
        except:
            return None
    return SCROBBLER_SESSION

def set_audio_sink(sink): 
    """
        Sets the default audio sink
    """
    global audio_sink, stream_audio_sink
    if "win" in sys.platform: return
    if not sink:
        sink = "GConf"
    if sink.lower().find("gconf") > -1: 
        audio_sink = gst.parse_launch("gconfaudiosink") 
    else: 
        audio_sink = gst.element_factory_make(sink)
    player.set_property("audio-sink", audio_sink)


def set_volume(vol): 
    """
        Sets the volume (value between 0 and 1.5)
    """
    if "win" in sys.platform: return
    player.set_property("volume", vol)


def get_volume(): 
    """
        Returns the current volume level
    """
    return player.get_property("volume")

class MetaIOException(Exception):
    """
        Raised when there is a problem writing metadata to one of the
        filetypes
    """
    def __init__(self, reason):
        """
            Initializes the exception with a reason
        """
        Exception.__init__(self)
        self.reason = reason

class timetype(long):
    """
        I am just extending long so that we know when to convert a long to a
        time when displaying the tracklist. I don't just send the trackslist
        the time in the 00:00 format because it won't sort correctly (I want
        it to sort numerically instead of alphabetically.
    """
    def __init__(self, num=None):
        """
            Initializes the class
        """
        long.__init__(self, num)
        self.stream = False

class Track(object): 
    """
        Represents a generic single track
    """

    def __init__(self, loc="", title="", artist="",  
        album="", genre="",
        track=0, length=0, bitrate=0, year="", 
        modified=0, user_rating=0, blacklisted=0, the_track=''):
        """
            Loads an initializes the tag information
            Expects the path to the track as an argument
        """
        self.set_info(loc, title, artist, album, genre,
            track, length, bitrate, year, modified, user_rating, 
            blacklisted, the_track)

        self.time_played = 0
        self.read_from_db = False
        self.blacklisted = 0
        self.ipod_playlist = None
        self.next_func = None
        self.type = 'track'

    def set_info(self, loc="", title="", artist="",
        album="", genre="", track=0, length=0, bitrate=0, year="", 
        modified=0, user_rating=0, blacklisted=0, the_track=''):
        """
            Sets track information
        """

        self.loc = loc
        self._bitrate = bitrate
        self._title = title
        self.artist = artist
        self.album = album

        # attempt to set the track number as an integer
        try:
            self._track = int(track)
        except:
            self._track = track
        self._len = length
        self.connections = []
        self.year = year
        self.playing = 0
        self.genre = genre
        self.submitting = False
        self.last_position = 0
        self.modified = modified
        self.blacklisted = blacklisted
        self.rating = user_rating
        self.user_rating = user_rating
        self.the_track = the_track

    def ipod_track(self):
        """
            Returns an ipod compatable track
        """
        track = gpod.itdb_track_new()
        track.title = str(self.title)
        track.album = str(self.album)
        track.artist = str(self.artist)
        track.tracklen = self.duration * 1000

        try: track.bitrate = int(self._bitrate)
        except: pass
        try: track.track_nr = int(self.track)
        except: pass
        try: track.year = int(self.year)
        except: pass

        info = os.stat(self.loc)
        track.size = info[6]

        track.time_added = int(time.time()) + 2082844800
        track.time_modified = track.time_added
        track.genre = str(self.genre)

        return track 

    def found_tag_cb(self, play, src, tags):
        """
            Called by gstreamer when metadata is found in the stream
        """
        for tag in tags.keys():
            nick = gst.tag_get_nick(tag)
            if nick == "genre": self.genre = tags[tag]
            elif nick == "title": self._title = tags[tag]
            elif nick == "bitrate": self.bitrate = tags[tag]
            elif nick == "artist" and isinstance(self, GSTTrack): 
                self.artist = tags[tag]
            elif nick == "comment" and isinstance(self, StreamTrack):
                self.artist = tags[tag]
            elif nick == "album": self.album = tags[tag]
            elif nick == "track number": self._track = tags[tag]

        if isinstance(self, StreamTrack): self.album = self.loc
        exaile_instance.tracks.queue_draw()

    def on_message(self, bus, message, reading_tag=False):
        """
            Called when a message occurs from gstreamer
        """
        if message.type == gst.MESSAGE_TAG:
            if isinstance(self, StreamTrack) or isinstance(self, GSTTrack):
                self.found_tag_cb(None, None, message.parse_tag())

        elif message.type == gst.MESSAGE_EOS and not reading_tag:
            if not self.is_paused():
                self.next()    

        return True

    def full_status(self): 
        """
            Returns a string representing the status of the current track
        """
        status = "playing"
        if self.is_paused(): status = "paused"

        value = self.current_position()
        duration = self.duration * gst.SECOND

        if duration == -1:
            real = 0
        else:
            real = value * duration / 100
        seconds = real / gst.SECOND

        return "status: %s self: %s artist: %s " \
            "album: %s length: %s position: %%%d [%d:%02d]" % (status,
                self.title,
                self.artist, self.album, self.length,
                value, seconds / 60, seconds % 60)
    

    def set_track(self, t): 
        """
            Sets the track number
        """
        self._track = t
    

    def get_track(self): 
        """
            attempts to convert the track number to an int, otherwise it
            just returns -1
        """
        try:
            return int(self._track)
        except:
            return -1
    

    def get_bitrate(self): 
        """
            Returns the bitrate
        """
        try:
            rate = int(self._bitrate) / 1000
            if rate: return "%dk" % rate
            else: return ""
        except:
            return self._bitrate
    

    def get_rating(self): 
        """
            Gets the rating
        """
        return "* " * self._rating
    

    def set_rating(self, rating): 
        """
            Sets the rating
        """
        self._rating = rating
        self.user_rating = rating

    def get_title(self): 
        """
            Returns the title of the track from the id3 tag
        """

        if self._title == "" and not self.album and not self.artist:
            return re.sub(".*%s" % os.sep, "", self.loc)
        try:
            return self._title.decode("utf-8")
        except:
            return self._title
    
    def set_title(self, value): 
        """
            Sets the title
        """
        self._title = value

    def set_artist(self, value):
        """
            Sets the artist
        """
        self._artist = value

    def get_artist(self):
        """
            Gets the artist
        """
        return "%s%s" % (self.the_track, self._artist)

    def get_len(self): 
        """
            Returns the length of the track in the format minutes:seconds
        """

        l = self._len
        tup = time.localtime(float(l))

        return "%s:%02d" % (tup[4], tup[5])
    

    def set_len(self, value): 
        """
            Sets the length
        """
        if value == "": value = 0
        self._len = value
     

    def get_duration(self): 
        """
            Gets the duration as an integer
        """
        return timetype(self._len)
    

    def get_position(self): 
        """
            Gets the current position in the track
        """
        if self.last_audio_sink == None: return 0
        if self.playing == 2: return self.last_position
        try:
            self.last_position = player.query_position(gst.FORMAT_TIME)[0] 
        except gst.QueryError:
            self.last_position = 0
        return self.last_position
    

    def current_position(self): 
        """
            Gets the current position as a percent
        """
        value = 0
        duration = self.duration * 1000 * 1000 * 1000

        if duration:
            value = self.position * 100.0 / duration

        return value
    

    def next(self): 
        """
            Called by EOS on the playbin
        """
        if self.next_func:
            gobject.idle_add(self.next_func)
    

    def play(self,  next_func=None): 
        """
            Starts playback of the track
        """
        self.last_audio_sink = audio_sink

        if not self.is_paused():
            self.connections.append(bus.connect('message', self.on_message))
            if self.type != 'stream': prefix = "file://"
            else: prefix = ""

            loc = self.loc
            if not isinstance(self, StreamTrack):
                loc = urllib.quote(str(loc))
            else:
                if self.stream_loc: loc = self.stream_loc
            player.set_property("uri", "%s%s" % (prefix, loc))
            self.next_func = next_func
            self.submitting = False
        self.playing = 1
        player.set_state(gst.STATE_PLAYING)
    

    def is_playing(self):
        """
            Returns True if the track is playing, False if it is paused or
            stopped
        """
        if self.playing == 1: return True
        else: return False

    def is_paused(self):
        """
            Returns True if the track is paused, False if it is stopped or
            playing
        """
        if self.playing == 2: return True
        else: return False

    def seek(self, value):
        """
            Seeks to a position in the track
        """
        if player == None: return

        value = value * gst.SECOND
        event = gst.event_new_seek(
            1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, value, gst.SEEK_TYPE_NONE, 0)
        player.send_event(event)
        self.last_position = value

    def pause(self):
        """
            Pauses the track
        """
        if player == None: return
        self.playing = 2

        # we don't actually pause streams, they are stopped.  If streamripper
        # was involved, it will continue to download the stream normally
        if isinstance(self, StreamTrack):
            player.set_state(gst.STATE_NULL)
        else:
            player.set_state(gst.STATE_PAUSED)

    def stop(self):
        """
            Stops playback of the track
        """

        self.playing = 0
        xlmisc.log("playing has been stopped on '%s'" % self._title)
        if player == None: return
        for i in self.connections:
            bus.disconnect(i)
        self.connections = []

        player.set_state(gst.STATE_READY)
        if self.type == 'stream': self.submitting = False

    def write_tag(self, db=None):
        """
            Writes the tag information to the database
        """

        if db:
            mod = os.stat(self.loc).st_mtime

            db.execute("UPDATE tracks SET title=?, artist=?, " \
                "album=?, genre=?, year=?, modified=?, track=? WHERE path=?",
                (self.title, self.artist, self.album, self.genre,
                self.year, mod, self.track, self.loc))

    def __str__(self):
        """
            Returns a string representation of the track
        """
        return "%s from %s by %s" % (self._title, self.album, self.artist)

    def submit_to_scrobbler(self):
        """
            Submits this track to last.fm
        """
        if self.submitting or self.type == 'stream': return

        if self._title == "" or self.artist == "": return

        session = get_scrobbler_session()
        if not session: return
        self.submitting = True
        thread.start_new_thread(session.submit,([self],))

    def set_bitrate(self, rate):
        """
            Gets the bitrate for this track
        """
        self._bitrate = rate

    title = property(get_title, set_title)
    artist = property(get_artist, set_artist)
    length = property(get_len, set_len)
    position = property(get_position)
    duration = property(get_duration)
    rating = property(get_rating, set_rating)
    bitrate = property(get_bitrate, set_bitrate)
    track = property(get_track, set_track)

    def get_scrobbler_session(self):
        """
            Returns the current scrobbler session
        """
        global SCROBBLER_SESSION
        return SCROBBLER_SESSION

class StreamTrack(Track):
    """
        Represents a non-local, non-library track
    """
    def __init__(self, loc):
        """
            Expects the URL and the current exaile instance
        """
        Track.__init__(self, loc)
        self.album = loc
        self.title = "Stream: %s" % loc
        self.connections = []
        self.track = ""
        self.start_time = 0
        self.type = 'stream'
        self.streamripper_pid = None
        self.streamripper_out = None
        self.stream_loc = ''
    
    def play(self, next_func=None):
        """
            Starts playback in a thread
        """
        thread = xlmisc.ThreadRunner(self._play)
        thread.next_func = next_func
        thread.start()

    def _play(self, thread):
        """
            Starts playback of the track
        """
        next_func = thread.next_func

        self.last_audio_sink = audio_sink

        # set up streamripper if needed
        if not self.is_paused() and \
            exaile_instance.settings.get_boolean('use_streamripper'):
            settings = exaile_instance.settings 
            savedir = settings.get('streamripper_save_location',
                os.getenv('HOME'))
            port = settings.get_int('streamripper_relay_port', 8000)
            outfile = exaile_instance.get_settings_dir() + "/streamripper.out"
            self.streamripper_out = open(outfile, "w+", 0)
            self.streamripper_out.write("Streamripper log file started: %s\n" %
                time.strftime("%c", time.localtime()))
            self.streamripper_out.write(
                "-------------------------------------------------\n\n\n")

            if settings.get_boolean("kill_streamripper", True):
                xlmisc.log("Killing any current streamripper processes")
                os.system("killall -9 streamripper")

            sub = subprocess.Popen(['streamripper', self.loc, '-r', str(port),
                '-d', savedir], stderr=self.streamripper_out)
            ret = sub.poll()
            self.streamripper = sub

            xlmisc.log("Streamripper return value was %s" % ret)
            xlmisc.log("Using streamripper to play location: %s" % self.loc)
            exaile_instance.status.set_first("Streamripping location: %s..." %
                self.loc, 4000)
            if ret != None:
                common.error(exaile_instance.window, _("There was an error"
                    " executing streamripper."))
                return
            self.streamripper_pid = sub.pid

            # wait half a second to make sure streamripper has started up
            time.sleep(.5)
            self.stream_loc = "http://localhost:%d" % port

        if not self.is_paused():
            self.start_time = time.time()
        Track.play(self, next_func)

    def check_streamripper_pid(self):
        """
            If we're using streamripper, make sure it didn't die.
        """
        if self.streamripper_pid:
            if self.streamripper.poll() != None:
                common.error(exaile_instance.window, _("Streamripper "
                    "died unexpectedly."))
                self.stop()
                exaile_instance.on_next()

    def get_duration(self):
        """
            Returns 0 - we don't know the duration of streams
        """
        t = timetype(0)
        t.stream = True
        return t

    def stop(self):
        """
            Stops playback
        """
        if self.streamripper_pid:
            os.system("kill -9 %d" % self.streamripper_pid)
            self.streamripper_out.close()
            self.stream_loc = None
            self.streamripper_pid = None
        self.start_time = 0
        Track.stop(self)

    def get_length(self):
        """
            Returns M/A - we don't know the duration of streams
        """
        return "N/A"

    length = property(get_length)

class CDTrack(Track):
    """
        Represents a track on an audio cd
    """
    def __init__(self, tracknum, length=0):
        """
            Initializes the track
        """
        Track.__init__(self, tracknum, length=length)
        self.title = "Track %s" % tracknum
        self.type = 'cd'

    def read_tag(self):
        pass

    def write_tag(self, db=None):
        pass

    def play(self,  next_func=None): 
        """
            Starts playback of the track
        """
        self.last_audio_sink = audio_sink

        if not self.is_paused():
            self.connections.append(bus.connect('message', self.on_message))
            prefix = "cdda://"

            player.set_property("uri", "%s%s" % (prefix, self.loc))
            self.next_func = next_func
            self.submitting = False
        self.playing = 1
        player.set_state(gst.STATE_PLAYING)

class RadioTrack(StreamTrack):
    """
        Describes a track scanned from a radio stream, like shoutcase
    """
    def __init__(self, info):
        """
            Expects a dictionary containing information about the track

            At least "url" is required, but the following information can
            also be passed in the "info" dictionary: description, playing,
            listeners, bitrate, and location
        """
        StreamTrack.__init__(self, info['url'])

        for field in ('artist', 'url', 'bitrate', 
            'title', 'album', 'year', 'podcast_duration'):
            if field in info: self.__setattr__(field, info[field])
            else: self.__setattr__(field, "")

        self.location = self.loc
        self.uri = self.loc
        self.streamripper_pid = None
        if not isinstance(self, PodcastTrack):
            self.album = self.location

    def found_tag_cb(self, play, src, tags):
        """
            Called by gstreamer when metadata is found in the stream
        """
        for tag in tags.keys():
            nick = gst.tag_get_nick(tag)
            if nick == "bitrate": self.bitrate = int(tags[tag])/1000
            elif nick == "comment": self.artist = tags[tag]
            elif nick == "title": self.title = tags[tag]
            xlmisc.log("%s: %s" % (gst.tag_get_nick(tag), tags[tag]))
        exaile_instance.tracks.refresh_row(self)
        exaile_instance.update_track_information()

    def current_position(self):
        """
            Returns M/A - we don't know the duration of streams
        """
        return 0

    def get_duration(self):
        """
            Returns the duration of the track
        """
        return StreamTrack.get_duration(self)

    def play(self, next_func=None):
        """
            Starts playback in a thread
        """
        thread = xlmisc.ThreadRunner(self._play)
        thread.next_func = next_func
        thread.start()

    def _play(self, thread):
        """
            Plays the track.  If the "url" is a .m3u or .pls, it reads the
            file until it finds the first valid url, and uses that as
            the location of the track
        """
        next_func = thread.next_func
        if self.loc.endswith(".pls") or self.loc.endswith(".m3u"):
            t = self.title
            self.title = "Opening URL..."
            exaile_instance.tracks.queue_draw()
            xlmisc.finish()
            f = urllib.urlopen(self.uri)
            loc = ""
            for line in f.readlines():
                line = line.strip()
                if line.startswith("#") or line == "[playlist]": continue
                if line.find("=") > -1:
                    if not line.startswith("File"): continue
                    line = re.sub("File\d+=", "", line)
                    loc = line
                    break
                
            xlmisc.log("Found location: %s" % loc)
            self.loc = loc
            self.location = loc
            self.title = t
            exaile_instance.tracks.queue_draw()

        StreamTrack._play(self, thread)

    def get_bitrate(self):
        """
            returns the bitrate of the track
        """
        self._bitrate = str(self._bitrate)
        self._bitrate = re.sub("\D", "", self._bitrate)
        if self._bitrate: return "%sk"  % self._bitrate
        else: return ""

    def set_bitrate(self, rate):
        """
            sets the bitrate of the track
        """
        rate = str(rate)
        rate = re.sub("\D", "", rate)
        self._bitrate = rate

    duration = property(get_duration)
    bitrate = property(get_bitrate, set_bitrate)

class PodcastTrack(RadioTrack):
    """
        Podcasts
    """
    def __init__(self, info):
        """
            Initialize
        """
        self.download_path = info['download_path']
        self.real_url = info['url']
        RadioTrack.__init__(self, info)
        self.type = 'podcast'

    def found_tag_cb(self, *params):
        """
            Do nothing
        """
        pass

    def play(self, next_func=None):
        """
            Tries to play the podcast
        """
        self.loc = self.download_path
        RadioTrack.play(self, next_func)

    def stop(self):
        """
            Stops playback of the track
        """
        self.loc = self.real_url
        RadioTrack.stop(self)

    def get_len(self): 
        """
            Returns the length of the track in the format minutes:seconds
        """

        l = self._len
        tup = time.localtime(float(l))

        return "%s:%02d" % (tup[4], tup[5])
    

    def set_len(self, value): 
        """
            Sets the length
        """
        if value == "": value = 0
        self._len = value

    length = property(get_len, set_len)

class GSTTrack(Track):
    """
        Generic gstreamer track. Use only if the format isn't currently
        supported in mutagen (this method is slower)
    """
    def __init__(self, loc="", title="", artist="", album="", genre="",
        track=0, length=0, bitrate=0, year=""):
        """
            Initializes the track"
        """
        Track.__init__(self, loc, title, artist, album, genre, track,
            length, bitrate, year)

        self.done = False
        self.eos = False
        self.is_tagged = False

    def on_message_proxy(self, bus, message):
        """
            Called by gstreamer on message
        """
        Track.on_message(self, bus, message, True)
        if message.type == gst.MESSAGE_TAG:
            exaile_instance.tracks.queue_draw() 
            self.is_tagged = True
        elif message.type == gst.MESSAGE_EOS:
            self.eos = True

    def write_tag(self, db=None):
        """
            Writes the tags to the database
        """
        raise MetaIOException("Track %s: writing metadata to this filetype is"
            " not currently supported." % self.loc)

    def read_tag(self):
        """
            Reads the tag using GStreamer
        """
        self.sink = gst.element_factory_make('fakesink')
        self.connect_id = tag_bus.connect('message', self.on_message_proxy)
        tag_bin.set_property('audio-sink', self.sink)

        tag_bin.set_property('uri', "file://%s" % self.loc)
        ret = tag_bin.set_state(gst.STATE_PLAYING)
        timeout = 10
        state = None
        while ret == gst.STATE_CHANGE_ASYNC and timeout > 0 and not self.eos \
            and not self.is_tagged:
            ret, state, pending = tag_bin.get_state(gst.SECOND)
            tag_bus.poll(gst.MESSAGE_TAG, gst.SECOND)
            timeout -= 1

        try:
            query = gst.query_new_duration(gst.FORMAT_TIME)
            tag_bin.query(query)
            time = query.parse_duration()[1]
            time //= gst.SECOND
            self._len = time

            if exaile_instance.tracks: exaile_instance.tracks.queue_draw()
        except gst.QueryError:
            xlmisc.log_exception()
            pass

        tag_bin.set_state(gst.STATE_NULL)
        tag_bus.disconnect(self.connect_id)

class MP3Track(Track):
    """
        An MP3 track
    """
    IDS = { "TIT2": "title",
            "TPE1": "artist",
            "TALB": "album",
            "TRCK": "track",
            "TDRC": "year",
            "TCON": "genre"
            }

    SDI = dict([(v, k) for k, v in IDS.iteritems()])

    def __init__(self, loc="", title="", artist="", album="", genre="",
        track=0, length=0, bitrate=0, year=""):
        """
            Initializes the track
        """
        Track.__init__(self, loc, title, artist, album, genre, track,
            length, bitrate, year)

    def write_tag(self, db=None):
        """
            Writes tags to the file, and optionally saves them to the database
        """
        try:
            id3 = mutagen.id3.ID3(self.loc)
        except mutagen.id3.ID3NoHeaderError:
            id3 = mutagen.id3.ID3()

        for key, id3name in self.SDI.items():
            id3.delall(id3name)

        for k, v in self.IDS.iteritems():
            try:
                frame = mutagen.id3.Frames[k](encoding=3,
                    text=unicode(getattr(self, v)))
                id3.loaded_frame(frame)
            except:
                xlmisc.log_exception()

        id3.save(self.loc)
        Track.write_tag(self, db)

    def get_tag(seld, id3, t):
        """
            Reads a specific id3 tag from the file, and formats it
        """
        tag = id3.get(t)
        if tag == None: return ""
        else:
            if t == "TRCK":
                # parse track information out... they are usually stored in
                # the format "track/all"
                track = str(tag)
                b = track.find("/")
                if b > -1:
                    tag = track[0:b]
                    return int(tag)

            text = unicode(tag.text[len(tag.text) - 1])

            # get rid of any newlines
            text = text.replace("\n", " ").replace("\r", " ")
            return text

    def read_tag(self):
        """
            Reads all id3 tags from the file
        """
        try:
            id3 = mutagen.id3.ID3(self.loc)
            info = mutagen.mp3.MP3(self.loc)
            self.title = self.get_tag(id3, "TIT2")
            self.artist = self.get_tag(id3, "TPE1")
            self.album = self.get_tag(id3, "TALB")
            self.genre = self.get_tag(id3, "TCON")
            self.track = self.get_tag(id3, "TRCK")
            self.year = self.get_tag(id3, "TDRC")
            self.length = info.info.length
            self.bitrate = info.info.bitrate

        except OverflowError:
            pass
        except mutagen.id3.ID3NoHeaderError:
            pass
        except IOError:
            pass
        except: 
            xlmisc.log_exception()

class iPodTrack(MP3Track):

    def __init__(self, loc="", title="", artist="", album="", genre="",
        track=0, length=0, bitrate=0, year=""):
        """
            Initializes the track
        """
        Track.__init__(self, loc, title, artist, album, genre, track,
            length, bitrate, year)

        self.itrack = None
        self.type = 'ipod'

    def ipod_track(self):
        """
            Returns the ipod track
        """
        return self.itrack

    def write_tag(self, db=None):
        """
            Not implemented quite yet
        """
        if self.itrack:
            t = self.itrack
            t.artist = str(self.artist)
            t.album = str(self.album)
            t.genre = str(self.genre)
            t.title = str(self.title)

            try:
                t.year = int(self.year)
            except ValueError:
                pass

            try:
                t.track_nr = int(self.track)
            except ValueError:
                pass

        if db:
            Track.write_tag(self, db)


    def read_track(self):
        """
            Reads the track
        """
        pass

    def get_rating(self): 
        """
            Gets the rating
        """
        # this is an approximate conversion from the iPod's rating system
        return "* " * int(self._rating / 14) 
    
    def set_rating(self, rating):
        """
            Sets the rating
        """
        self._rating = rating

    rating = property(get_rating, set_rating)

class OGGTrack(Track):
    """
        Represents an OGG/Vorbis track
    """
    def __init__(self, loc="", title="", artist="", album="", genre="",
        track=0, length=0, bitrate=0, year=""):
        """
            Initializes the track
        """
        Track.__init__(self, loc, title, artist, album, genre, track,
            length, bitrate, year)

    def get_tag(self, f, tag):
        """
            gets a specific tag and formats it
        """
        try:
            return unicode(f[tag][0])
        except:
            return ""

    def write_tag(self, db=None):
        """
            Writes all tags to the file, and optionally saves them to the
            database
        """
        try:
            com = mutagen.oggvorbis.OggVorbis(self.loc)
        except mutagen.oggvorbis.OggVorbisHeaderError:
            com = mutagen.oggvorbis.OggVorbis()
        com.clear()
        com['artist'] = self.artist
        com['album'] = self.album
        com['title'] = self.title
        com['genre'] = self.genre
        com['tracknumber'] = str(self.track)
        com['date'] = str(self.year)
        com.save(self.loc)
        Track.write_tag(self, db)

    def read_tag(self):
        """
            Reads all tags from the file
        """
        try:
            f = mutagen.oggvorbis.OggVorbis(self.loc)
        except mutagen.oggvorbis.OggVorbisHeaderError:
            return

        self.length = int(f.info.length)
        self.bitrate = int(f.info.bitrate / 1024)

        self.artist = self.get_tag(f, "artist")
        self.album = self.get_tag(f, "album")
        self.title = self.get_tag(f, "title")
        self.genre = self.get_tag(f, "genre")
        self.track = self.get_tag(f, "tracknumber")
        self.year = self.get_tag(f, "date")

class FLACTrack(Track):
    """
        Represents an FLAC (non-lossy) track
    """
    def __init__(self, loc="", title="", artist="", album="", genre="",
        track=0, length=0, bitrate=0, year=""):
        """
            Initializes the track
        """
        Track.__init__(self, loc, title, artist, album, genre, track,
            length, bitrate, year)

    def get_tag(self, flac, tag):
        """
            gets a specific tag from the file and formats it
        """
        try:
            return unicode(flac[tag][0])
        except KeyError:
            return ""

    def read_tag(self):
        """
            Reads all tags from the file
        """
        f = mutagen.flac.FLAC(self.loc)
        self.length = int(f.info.length)

        self.artist = self.get_tag(f, "artist")
        self.album = self.get_tag(f, "album")
        self.track = self.get_tag(f, "tracknumber")
        self.title = self.get_tag(f, "title")
        self.genre = self.get_tag(f, "genre")
        self.year = self.get_tag(f, "date")

    def write_tag(self, db=None):
        """
            Writes all tags to the file
        """
        f = mutagen.flac.FLAC(self.loc)
        if f.vc is None: f.add_vorbiscomment()
        del(f.vc[:])
        f.vc['artist'] = self.artist
        f.vc['album'] = self.album
        f.vc['title'] = self.title
        f.vc['genre'] = self.genre
        f.vc['track'] = str(self.track)
        f.vc['date'] = str(self.year)
        f.save()

        Track.write_tag(self, db)

# sets up the formats dict
for format in ('.mpc', '.m4a', '.aac', '.m4b', '.wma'):
    FORMAT[format] = GSTTrack
FORMAT['.flac'] = FLACTrack
FORMAT['.ogg'] = OGGTrack
FORMAT['.mp3'] = MP3Track
SUPPORTED_MEDIA = FORMAT.keys()
