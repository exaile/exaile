from xl.media import mp3, ogg, flac
import os.path, gobject, time

__all__ = ['flac', 'mp3', 'm4a', 'ogg', 'wma']

formats = {
    'mp3':      mp3,
    'mp2':      mp3,
    'ogg':      ogg,
    'flac':     flac
}

# for m4a support
try:
    from xl.formats import m4a
    formats['m4a'] = m4a
except ImportError: pass

# for wma support
try:
    from xl.formats import wma
    formats['wma'] = wma
except ImportError: pass

SUPPORTED_MEDIA = ['.%s' % x for x in formats.keys()]
# generic functions
def read_from_path(uri):
    """
        Reads tags from a specified uri
    """
    (path, ext) = os.path.splitext(uri.lower())
    ext = ext.replace('.', '')

    if not formats.has_key(ext):
        raise Exception('%s format is not understood' % ext)

    tr = xl.media.Track(uri)
    tr.type = ext
    formats[ext].fill_tag_from_path(tr)
    return tr


def show_visualizations(*e):
    """
        Shows the visualizations window
    """
    global VIDEO_WIDGET
    if VIDEO_WIDGET:
        VIDEO_WIDGET.hide()
    track = exaile_instance.current_track
    play_track = False
    position = 0
    if track is not None and track.is_playing():
        try:
            position = player.query_position(gst.FORMAT_TIME)[0] 
        except gst.QueryError:
            position = 0
        track.stop()
        play_track = True

    restart_gstreamer()

    VIDEO_WIDGET = VideoWidget(exaile_instance.window)
    video_sink = gst.element_factory_make('xvimagesink')
    vis = gst.element_factory_make('goom')
    player.set_property('video-sink', video_sink)
    player.set_property('vis-plugin', vis)
    VIDEO_WIDGET.show_all()


    xlmisc.log("Player position is %d" % position)
    event = gst.event_new_seek(
        1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
        gst.SEEK_TYPE_SET, position, gst.SEEK_TYPE_NONE, 0)
    if play_track: track.play(track.next_func)
    if not isinstance(track, StreamTrack) and position:
        track.seek(position / gst.SECOND)

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

class Track(gobject.GObject): 
    """
        Represents a generic single track
    """
    type = 'track'
    def __init__(self, *args):
        """
            Loads an initializes the tag information
            Expects the path to the track as an argument
        """
        gobject.GObject.__init__(self)
        self.set_info(*args)


        self.time_played = 0
        self.read_from_db = False
        self.blacklisted = 0
        self.next_func = None

    def set_info(self,loc="", title="", artist="",  
        album="", disc_id=0, genre="",
        track=0, length=0, bitrate=0, year="", 
        modified=0, user_rating=0, blacklisted=0, time_added=''):
    
    
        """
            Sets track information
        """

        self.loc = loc
        self._bitrate = bitrate
        self._title = title
        self.artist = artist
        self.album = album
        self.disc_id = disc_id

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
        self.submitted = False
        self.last_position = 0
        self.bitrate = bitrate
        self.modified = modified
        self.blacklisted = blacklisted
        self.rating = user_rating
        self.user_rating = user_rating
        self.time_added = time_added

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

        if self.type != 'podcast':
            info = os.stat(self.loc)
        else:
            info = os.stat(self.download_path)
        track.size = info[6]

        track.time_added = int(time.time()) + 2082844800
        track.time_modified = track.time_added
        track.genre = str(self.genre)

        return track 

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
        if self.type == 'stream':   
            return -1
        try:
            return int(self._track)
        except:
            return -1
    

    def get_bitrate(self): 
        """
            Returns the bitrate
        """
        if self.type == 'stream':
            if self._bitrate:
                return "%sk" % self._bitrate
            else:
                return ''
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
        return self._artist

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
    
    def write_tag(self, db=None):
        """
            Writes the tag information to the database
        """

        if db:
            mod = os.stat(self.loc).st_mtime
            artist_id = tracks.get_column_id(db, 'artists', 'name',
                self.artist)
            album_id = tracks.get_album_id(db, artist_id, self.album)
            path_id = tracks.get_column_id(db, 'paths', 'name', self.loc)

            db.execute("UPDATE tracks SET title=?, artist=?, " \
                "album=?, disc_id=?, genre=?, year=?, modified=?, track=? WHERE path=?",
                (self.title, artist_id, album_id, self.disc_id, self.genre,
                self.year, mod, self.track, path_id))

    def __str__(self):
        """
            Returns a string representation of the track
        """
        return "%s from %s by %s" % (self._title, self.album, self.artist)

    def set_bitrate(self, rate):
        """
            Gets the bitrate for this track
        """
        self._bitrate = rate

    title = property(get_title, set_title)
    artist = property(get_artist, set_artist)
    length = property(get_len, set_len)
    duration = property(get_duration)
    rating = property(get_rating, set_rating)
    bitrate = property(get_bitrate, set_bitrate)
    track = property(get_track, set_track)
