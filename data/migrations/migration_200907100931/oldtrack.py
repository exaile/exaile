import os.path
import gobject
import re
import xlmisc
from xl import common
import logging
logger = logging.getLogger(__name__)


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
        long.__init__(self)
        self.stream = False


def to_unicode(x, default_encoding=None):
    if isinstance(x, unicode):
        return x
    elif default_encoding and isinstance(x, str):
        # This unicode constructor only accepts "string or buffer".
        return unicode(x, default_encoding)
    else:
        return unicode(x)


def get_default_encoding():
    """
        Returns the encoding to be used when dealing with file paths.  Do not
        use for other purposes.
    """
    # return 'utf-8'
    return sys.getfilesystemencoding() or sys.getdefaultencoding()


class ldict(dict):
    """
        A dict that only handles lists
    """

    def __init__(self):
        dict.__init__(self)

    def __setitem__(self, item, value):
        if not isinstance(value, list):
            value = [value]
        dict.__setitem__(self, item, value)

    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            return []


class Track(object):
    """
        Represents a generic single track.
    """
    type = 'track'

    def __init__(self, *args, **kwargs):
        """
            Loads and initializes the tag information
            Expects the path to the track as an argument
        """
        self.tags = ldict()
        self.time_played = 0
        self.read_from_db = False
        self.blacklisted = 0
        self.next_func = None
        self.start_time = 0

        self.set_info(*args, **kwargs)

        try:
            self.ext = os.path.splitext(self.loc.lower())[1]
            self.ext = self.ext.replace('.', '')
        except:
            self.ext = None

    def is_file(self):
        return self.type == "file"

    def is_multi(self):
        """
            Does the track support multiple tag values?
        """
        return formats[self.ext].is_multi()

    def set_info(self, loc="", title="", artist="",
                 album="", disc_id=0, genre="",
                 track=0, length=0, bitrate=0, year="",
                 modified=0, user_rating=0, rating=0, blacklisted=0, time_added='',
                 encoding=xlmisc.get_default_encoding(), playcount=0):
        """
            Sets track information
        """
        # Doesn't matter what charset we use here, as long as we use
        # the same one when we decode (or encode as it were)
        if isinstance(loc, unicode):
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
        self.system_rating = rating
        self.time_added = time_added
        self.playcount = playcount

        for tag, val in {'title': title, 'artist': artist, 'album': album,
                         'genre': genre, 'discnumber': disc_id,
                         'tracknumber': track}.iteritems():
            self.set_tag(tag, val)

   # ========== Getters and setters ============

    def set_tag(self, tag, values, append=False):
        """
            Common function for setting a tag.
            Expects a list (even for a single value)
        """
        if not isinstance(values, list):
            values = [values]
        # filter out empty values and convert to unicode
        values = (to_unicode(x, self.encoding) for x in values
                  if x not in (None, ''))
        if append:
            self.tags[tag].extend(values)
        else:
            self.tags[tag] = list(values)

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
        if isinstance(t, int):
            return t

        b = t.find('/')

        if b > -1:
            t = t[0:b]

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
            if rate:
                return "%dk" % rate
            else:
                return ""
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
        for tag in xlmisc.VALID_TAGS:
            try:
                self.tags[tag] = unicode(self.tags[tag].encode(self.encoding), value)
            except AttributeError:
                pass

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
        if value == "":
            value = 0
        self._len = value

    def get_duration(self):
        """
            Gets the duration as an integer
        """
        if self._len == '':
            self._len = 0
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

    def get_tag(self, tag):
        """
            Common function for getting a tag.
            Simplifies a list into a single string separated by " / ".
        """
        values = self.tags.get(tag)
        if values:
            values = (to_unicode(x, self.encoding) for x in values
                      if x not in (None, ''))
            return u" / ".join(values)
        return u""

    def set_loc(self, value):
        """
            Sets the location. It is always in unicode.
            If the value is not unicode, convert it into unicode using some
            default mapping. This way, when we want to access the file, we
            decode it back into the ascii and don't worry about botched up
            characters (ie the value should be exactly identical to the one given)
        """
        self._loc = to_unicode(value, xlmisc.get_default_encoding())

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

    bitrate = property(get_bitrate, set_bitrate)
    duration = property(get_duration)
    encoding = property(get_encoding, set_encoding)
    filename = property(get_filename)
    io_loc = property(get_loc_for_io, None)
    length = property(get_len, set_len)
    loc = property(get_loc, set_loc)
    rating = property(get_rating, set_rating)

    # Data written to tags
    album = property(get_album, set_album)
    artist = property(get_artist, set_artist)
    copyright = property(get_copyright, set_copyright)
    date = property(get_date, set_date)
    disc_id = property(get_disc, set_disc)
    genre = property(get_genre, set_genre)
    isrc = property(get_isrc, set_isrc)
    performer = property(get_performer, set_performer)
    publisher = property(get_publisher, set_publisher)
    title = property(get_title, set_title)
    track = property(get_track, set_track)
    version = property(get_version, set_version)
    year = property(get_date, set_date)  # backwards compatibility


def read_from_path(uri, track_type=Track):
    """
        Reads tags from a specified uri
    """
    (path, ext) = os.path.splitext(uri.lower())
    ext = ext[1:]

    # if ext not in formats:
    #    xlmisc.log('%s format is not understood' % ext)
    #    return None

    tr = track_type(uri)

    if tr.type != 'device':
        tr.type = 'file'

    format = formats.get(ext)
    if not format:
        return tr

    try:
        format.fill_tag_from_path(tr)
    except HeaderNotFoundError:
        logger.debug("Possibly corrupt file: " + uri)
        return None
    except:
        common.log_exception(log=logger)
        return None

    return tr
