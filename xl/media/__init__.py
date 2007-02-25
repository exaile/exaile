from xl.media import mp3, ogg, flac
from xl import xlmisc
from mutagen.mp3 import HeaderNotFoundError
import os.path, gobject, re

__all__ = ['flac', 'mp3', 'm4a', 'ogg', 'wma']

formats = {
    'mp3':      mp3,
    'mp2':      mp3,
    'ogg':      ogg,
    'flac':     flac,
}

# for m4a support
try:
    from xl.media import m4a
    formats['m4a'] = m4a
except ImportError: pass

# for wma support
try:
    from xl.media import wma
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
        xlmisc.log('%s format is not understood' % ext)
        return

    tr = Track(uri)
    tr.type = ext

    try:
        formats[ext].fill_tag_from_path(tr)
    except HeaderNotFoundError:
        print "Possibly corrupt file: " + uri
    except:
        xlmisc.log_exception()
        return None
    return tr

def write_tag(tr):
    """
        Writes a tag
    """
    (path, ext) = os.path.splitext(tr.loc.lower())
    ext = ext.replace('.', '')

    if not formats.has_key(ext):
        raise Exception("Writing metadata to type '%s' is not supported" %
            ext)

    formats[ext].write_tag(tr)

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
    def __init__(self, *args, **kwargs):
        """
            Loads an initializes the tag information
            Expects the path to the track as an argument
        """
        gobject.GObject.__init__(self)
        self.set_info(*args, **kwargs)


        self.time_played = 0
        self.read_from_db = False
        self.blacklisted = 0
        self.next_func = None
        self.start_time = 0

    def set_info(self,loc="", title="", artist="",  
        album="", disc_id=0, genre="",
        track=0, length=0, bitrate=0, year="", 
        modified=0, user_rating=0, blacklisted=0, time_added='', encoding="latin1"):
    
    
        """
            Sets track information
        """

        # Doesn't matter what charset we use here, as long as we use
        # the same one when we decode (or encode as it were)
        if type(loc) is unicode:
            self._loc = loc
        else:        
            self._loc = unicode(loc, "latin1")

        self._bitrate = bitrate

        # This would be more nicely written using conditional expressions
        # but that is Python 2.5 only
        if type(title) is unicode:
            self._title = title
        else:
            self._title = unicode(title, encoding)

        if type(artist) is unicode:
            self._artist = artist
        else:
            self._artist = unicode(artist, encoding)

        if type(album) is unicode:
            self._album = album
        else:
            self._album = unicode(album, encoding)

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
        self._rating = user_rating
        self.user_rating = user_rating
        self.time_added = time_added
        self._encoding = encoding

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
                return "%sk" % self._bitrate.replace('k', '')
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
    
    def get_title(self): 
        """
            Returns the title of the track from the id3 tag
        """

        if self._title == "":
            return re.sub(".*%s" % os.sep, "", self.loc)
        else:
            return self._title
    
    def set_title(self, value): 
        """
            Sets the title
        """
        if type(value) is unicode:
            self._title = value
        else:
            self._title = unicode(value, self._encoding)

    def set_artist(self, value):
        """
            Sets the artist
        """
        if type(value) is unicode:
            self._artist = value
        else:
            self._artist = unicode(value, self._encoding)

    def get_artist(self):
        """
            Gets the artist
        """
        return self._artist

    def set_album(self, value):
        """
            Sets the album
        """
        if type(value) is unicode:
            self._album = value
        else:
            self._album = unicode(value, self._encoding)

    def get_album(self):
        """
            Gets the album
        """
        return self._album

    def get_encoding(self):
        """
            Gets the encoding used for the metadata
        """
        return self._encoding

    def set_encoding(self, value):
        """
            Sets the encoding, translating from the previous one
        """
        title = self._title.encode(self.encoding)
        album = self._album.encode(self.encoding)
        artist = self._artist.encode(self.encoding)

        self._title = unicode(title, value)
        self._album = unicode(album, value)
        self._artist = unicode(artist, value)

        self._encoding = value

    def get_len(self): 
        """
            Returns the length of the track in the format minutes:seconds
        """
        sec = int(round(float(self._len)))
        return "%s:%02d" % divmod(sec, 60)
    

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

    def get_loc(self):
        return self._loc

    def get_loc_for_io(self):
        return self._loc.encode("latin1")

    def set_loc(self, value):
        if type(value) is unicode:
            self._loc = value
        else:
            self._loc = unicode(value, "latin1")

    title = property(get_title, set_title)
    artist = property(get_artist, set_artist)
    album = property(get_album, set_album)
    length = property(get_len, set_len)
    duration = property(get_duration)
    rating = property(get_rating, set_rating)
    bitrate = property(get_bitrate, set_bitrate)
    track = property(get_track, set_track)
    encoding = property(get_encoding, set_encoding)
    loc = property(get_loc, set_loc)
    io_loc = property(get_loc_for_io, None)
