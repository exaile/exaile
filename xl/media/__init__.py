from xl.media import mp3, ogg, flac, wav, wv, mpc, tta
import pygst
pygst.require('0.10')
import gst
from xl import xlmisc
import xl.common
from mutagen.mp3 import HeaderNotFoundError
import os.path, gobject, re

__all__ = ['flac', 'mp3', 'm4a', 'ogg', 'wma', 'mpc', 'wv', 'tta']

formats = {
    'mp3':      mp3,
    'mp2':      mp3,
    'ogg':      ogg,
    'flac':     flac,
    'wav':      wav,
    'mpc':      mpc,
    'mp+':      mpc,
    'tta':      tta
}

# Optional formats

try:
    from xl.media import mpc
    formats['mpc'] = mpc
except ImportError: pass

try:
    from xl.media import mp4
    formats['m4a'] = mp4
    formats['aac'] = mp4
    formats['mp4'] = mp4
except ImportError: pass

try:
    from xl.media import wma
    formats['wma'] = wma
except ImportError: pass

SUPPORTED_MEDIA = ['.%s' % x for x in formats.keys()]

# Generic functions

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
        Represents a generic single track.
    """
    type = 'track'
    def __init__(self, *args, **kwargs):
        """
            Loads and initializes the tag information
            Expects the path to the track as an argument
        """
        gobject.GObject.__init__(self)
        
        self.tags = xl.common.ldict()

        self.set_info(*args, **kwargs)

        try:
            self.ext = os.path.splitext(self.loc.lower())[1]
            self.ext = self.ext.replace('.', '')
        except:
            self.ext = None 

        self.time_played = 0
        self.read_from_db = False
        self.blacklisted = 0
        self.next_func = None
        self.start_time = 0

    def full_status(self, player):
        """
            Returns a string representing the status of the current track
        """
        status = "playing"
        if player.is_paused(): status = "paused"

        value = player.get_current_position()
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

    def is_file(self):
        return self.type == "file"

    def is_multi(self):
        """
            Does the track support multiple tag values?
        """
        return formats[self.ext].is_multi()

    def set_info(self,loc="", title="", artist="",  
        album="", disc_id=0, genre="",
        track=0, length=0, bitrate=0, year="", 
        modified=0, user_rating=0, blacklisted=0, time_added='', encoding=xlmisc.get_default_encoding()):
    
    
        """
            Sets track information
        """
        
        # Doesn't matter what charset we use here, as long as we use
        # the same one when we decode (or encode as it were)
        if type(loc) is unicode:
            self._loc = loc
        else:        
            try:
                self._loc = unicode(loc, xlmisc.get_default_encoding())
            except (UnicodeDecodeError, TypeError):
                self._loc = loc

        self._encoding = encoding
        self._bitrate = bitrate
        self._len = length
        self.connections = []
        self.date = year
        self.playing = 0
        self.submitted = False
        self.last_position = 0
        self.bitrate = bitrate
        self.modified = modified
        self.blacklisted = blacklisted
        self._rating = user_rating
        self.user_rating = user_rating
        self.time_added = time_added
    
        for tag, val in {'title': title, 'artist': artist, 'album':album,\
                        'genre': genre, 'discnumber':disc_id,\
                        'tracknumber':track}.iteritems():
            self.set_tag(tag, val)

    def can_change(self, tag):
        """
            If the tag in question is supported by the file format, return True
        """
        return formats[self.ext].can_change(tag)

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
                self.date, mod, self.track, path_id))

    def __str__(self):
        """
            Returns a string representation of the track.

            Note that for now this string is only suitable for logging because
            it is not translated and does not take into account when album or
            artist is empty.
        """
        return "%s from %s by %s" % (self.title, self.album, self.artist)
   
    def get_tag(self, tag):
        """
            Common function for getting a tag.
            Simplifies a list into a single string
        """
        try:
            ret = filter(lambda x: x or x == 0, self.tags[tag])
            return " / ".join(ret)
        except KeyError:
            return u""

    def set_tag(self, tag, value, append=False):
        """
            Common function for setting a tag.
            Expects a list (even for a single value)
        """
        def xlunicode(x):
            if type(x) is unicode:
                return x
            else:
                return unicode(str(x), self.encoding)

        if type(value) is not list: value = [value]
        # filter out empty values and convert to unicode
        value = map(xlunicode, filter(lambda x: x or x == 0, value))
        if append:
            self.tags[tag].extend(value)
        else:
            self.tags[tag] = value

   # ========== Getters and setters ============

    def get_filename(self):
        """
            Returns the base filename of the track location
        """
        return os.path.basename(self.io_loc)

    def set_track(self, t): 
        """
            Sets the track number
        """
        self.set_tag('tracknumber', t)
    
    def get_track(self): 
        """
            attempts to convert the track number to an int, otherwise it
            just returns -1
        """
        if self.type == 'stream':   
            return -1

        t = self.get_tag('tracknumber')
        if type(t) is int: return t

        b = t.find('/')

        if b > -1: t = t[0:b]

        try:
            return int(t)
        except:
            return -1
    
    def get_bitrate(self): 
        """
            Returns the bitrate
        """
        if self.type == 'stream':
            if self._bitrate:
                try:
                    return "%sk" % self._bitrate.replace('k', '')
                except AttributeError:
                    return str(self._bitrate) + "k"
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
        try:
            return "* " * self._rating
        except TypeError:
            return ""
    
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
        ret = self.get_tag('title')
        if not ret:
            return os.path.basename(self.loc)
        else:
            return ret
    
    def set_title(self, value): 
        """
            Sets the title
        """
        self.set_tag('title', value)

    def set_artist(self, value):
        """
            Sets the artist
        """
        self.set_tag('artist', value)

    def get_artist(self):
        """
            Gets the artist
        """
        return self.get_tag('artist')

    def set_album(self, value):
        """
            Sets the album
        """
        self.set_tag('album', value)

    def get_album(self):
        """
            Gets the album
        """
        return self.get_tag('album')

    def get_encoding(self):
        """
            Gets the encoding used for the metadata
        """
        return self._encoding

    def set_encoding(self, value):
        """
            Sets the encoding, translating info from the previous one
        """
        for tag in VALID_TAGS:
            self.tags[tag] = unicode(self.tags[tag].encode(self.encoding), value)

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
    
    def set_bitrate(self, rate):
        """
            Gets the bitrate for this track
        """
        self._bitrate = rate

    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters)
        """
        return self._loc

    def get_loc_for_io(self):
        """
            Gets the location as ascii. Should always be correct, see set_loc.
        """
        return self._loc.encode(xlmisc.get_default_encoding())

    def set_loc(self, value):
        """
            Sets the location. It is always in unicode.
            If the value is not unicode, convert it into unicode using some
            default mapping. This way, when we want to access the file, we
            decode it back into the ascii and don't worry about botched up
            characters (ie the value should be exactly identical to the one given)
        """
        if type(value) is unicode:
            self._loc = value
        else:
            self._loc = unicode(value, xlmisc.get_default_encoding())

    def get_disc(self):
        """
            Gets the disc number
        """
        return self.get_tag('discnumber')


    def set_disc(self, value):
        """
            Sets the disc number
        """
        self.set_tag('discnumber', value)

    def get_version(self):
        """
            Get the version (ie "remixed by" etc)
        """
        return self.get_tag('version')

    def set_version(self, value):
        """
            Set the version
        """
        self.set_tag('version', value)

    def get_performer(self):
        """
            Get the lead performer/soloist
        """
        return self.get_tag('performer')

    def set_performer(self, value):
        """
            Set performer
        """
        self.set_tag('performer', value)

    def get_copyright(self):
        """
            Get copyright information
        """
        return self.get_tag('copyright')

    def set_copyright(self, value):
        """
            Set copyright
        """
        self.set_tag('copyright', value)

    def get_publisher(self):
        """
            Get the publisher (ie record label etc)
        """
        return self.get_tag('publisher')

    def set_publisher(self, value):
        """
            Set the publisher
        """
        self.set_tag('publisher', value)

    def get_date(self):
        """
            Get the recording date
        """
        return self.get_tag('date')

    def set_date(self, value):
        """
            Set the date
        """
        # FIXME: check if the value is a valid ISO 8601 date
        self.set_tag('date', value)

    def get_isrc(self):
        """
            Get the isrc (international standard recording code)
        """
        return self.get_tag('isrc')

    def set_isrc(self, value):
        """
            Set the isrc
        """
        self.set_tag('isrc', value)

    def get_genre(self):
        """
            Get the genre
        """
        return self.get_tag('genre')

    def set_genre(self, value):
        """
            Set the genre
        """
        self.set_tag('genre', value)

    encoding = property(get_encoding, set_encoding)
    duration = property(get_duration)
    length = property(get_len, set_len)
    rating = property(get_rating, set_rating)
    bitrate = property(get_bitrate, set_bitrate)
    loc = property(get_loc, set_loc)
    io_loc = property(get_loc_for_io, None)
    filename = property(get_filename)

    # data written to tags
    title = property(get_title, set_title)
    artist = property(get_artist, set_artist)
    album = property(get_album, set_album)
    track = property(get_track, set_track)
    date = property(get_date, set_date)
    year = property(get_date, set_date) # backwards compatibility
    genre = property(get_genre, set_genre)
    disc_id = property(get_disc, set_disc)
    version = property(get_version, set_version)
    performer = property(get_performer, set_performer)
    copyright = property(get_copyright, set_copyright)
    publisher = property(get_publisher, set_publisher)
    isrc = property(get_isrc, set_isrc)



def read_from_path(uri, track_type=Track):
    """
        Reads tags from a specified uri
    """
    (path, ext) = os.path.splitext(uri.lower())
    ext = ext.replace('.', '')

    if not formats.has_key(ext):
        xlmisc.log('%s format is not understood' % ext)
        return

    tr = track_type(uri)

    if tr.type != 'device':
        tr.type = 'file' 

    try:
        formats[ext].fill_tag_from_path(tr)
    except HeaderNotFoundError:
        print "Possibly corrupt file: " + uri
        return None
    except:
        xlmisc.log_exception()
        return None

    return tr

