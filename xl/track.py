# Track
#
# contains Track which represents a single Track for playback

from copy import deepcopy
import os

try:
    import cPickle as pickle
except:
    import pickle as pickle

import pygst
pygst.require('0.10')
import gst
from mutagen.mp3 import HeaderNotFoundError
from urlparse import urlparse

import common, event
from xl.media import flac, mp3, mp4, mpc, ogg, tta, wav, wma, wv

import logging
logger = logging.getLogger(__name__)

formats = {
    'aac': mp4,
    'ac3': None,
    'flac': flac,
    'm4a': mp4,
    'mp+': mpc,
    'mp2': mp3,
    'mp3': mp3,
    'mp4': mp4,
    'mod': None,
    'mpc': mpc,
    'oga': ogg,
    'ogg': ogg,
    's3m': None,
    'tta': tta,
    'wav': wav,
    'wma': wma,
    'wv': wv,
}

SUPPORTED_MEDIA = ['.' + ext for ext in formats.iterkeys()]



class Track:
    """
        Represents a single track.
    """
    def __init__(self, uri=None, _unpickles=None):
        """
            loads and initializes the tag information
            
            uri: path to the track [string]
            _unpickles: unpickle data [tuple] # internal use only!
        """
        self.tags = dict(map(lambda x: (x, ''), common.VALID_TAGS))
        self.info = {
                'playcount':0,
                'bitrate':0,
                'length':0,
                'blacklisted':False,
                'rating':0,
                'loc':'',
                'encoding':''}

        self._scan_valid = False
        if uri and urlparse(uri)[0] in ['', 'file']:
            self.set_loc(uri)
            if self.read_tags() is not None:
                self._scan_valid = True

        elif _unpickles:
            self._unpickles(_unpickles)

    def set_loc(self, loc):
        """
            Sets the location. It is always in unicode.

            If the value is not unicode, convert it into unicode using some
            default mapping. This way, when we want to access the file, we
            decode it back into the ascii and don't worry about botched up
            characters (ie the value should be exactly identical to the 
            one given)

            loc: the location [string]
        """
        loc = common.to_unicode(loc, 
                common.get_default_encoding())
        if loc.startswith("file://"):
            loc = loc[7:]
        self.info['loc'] = loc
    
    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters)

            returns: the location [string]
        """
        return self.info['loc']

    def get_loc_for_io(self):
        """
            Gets the location as ascii. Should always be correct, see 
            set_loc.

            returns: the location [string]
        """
        return self.info['loc'].encode(common.get_default_encoding())


    def _pickles(self):
        """
            returns a data repr of the track suitable for pickling

            internal use only please

            returns: (tags, info) [tuple of dicts]
        """
        return deepcopy((self.tags, self.info))

    def _unpickles(self, pickle_str):
        """
            restores the state from the pickle-able repr

            internal use only please

            pickle_str: the pickle repr [tuple of dicts]
        """
        self.tags, self.info = pickle_str

    def get_tag(self, tag):
        """
            Common function for getting a tag.
            
            tag: tag to get [string]
        """
        if tag.startswith("xl_"):
            tag = tag[3:]
            try:
                return self.info[tag]
            except:
                return u""
        values = self.tags.get(tag)
        if values:
            values = (common.to_unicode(x, self.info['encoding']) for x in values
                if x not in (None, ''))
            return u" / ".join(values)
        return u""

    def set_tag(self, tag, values, append=False):
        """
            Common function for setting a tag.
            
            tag: tag to set [string]
            values: list of values for the tag [list]
            append: whether to append to existing values [bool]
        """
        if tag.startswith("xl_"):
            tag = tag[3:]
            try:
                if len(values) == 1 and \
                        type(values[0]) == type(self.info[tag]):
                    self.info[tag] = values[0]
                    return
            except:
                return
        if not isinstance(values, list): values = [values]
        # filter out empty values and convert to unicode
        values = (common.to_unicode(x, self.info['encoding']) for x in values
            if x not in (None, ''))
        if append:
            self.tags[tag].extend(values)
        else:
            self.tags[tag] = list(values)
        event.log_event('track_updated', self, self.get_loc())

    def __getitem__(self, tag):
        """
            Allows retrieval of tags via Track[tag] syntax.
            Returns a list of values for the tag, even for single values.
        """
        return self.get_tag(tag)

    def __setitem__(self, tag, values):
        """
            Allows setting of tags via Track[tag] syntax.
            Expects a list of values, even for single values.

            Use set_tag if you want to do appending instead of
            always overwriting.
        """
        self.set_tag(tag, values, False)

    def write_tags(self):
        """
            Writes tags to file
        """
        (path, ext) = os.path.splitext(self.get_loc().lower())
        ext = ext[1:]

        if not formats.get(ext):
            logger.info("Writing metadata to type '%s' is not supported" % 
                    ext)
        else:
            formats[ext].write_tag(self)

    def read_tags(self):
        """
            Reads tags from file
        """
        (path, ext) = os.path.splitext(self.get_loc().lower())
        ext = ext[1:]

        if ext not in formats:
            common.debug('%s format is not understood' % ext)
            return None

        format = formats.get(ext)
        if not format: 
            return None

        try:
            format.fill_tag_from_path(self)
        except HeaderNotFoundError:
            logger.warning("Possibly corrupt file: " + self.get_loc())
            return None
        except:
            common.log_exception(__name__)
            return None
        return self

    def __repr__(self):
        return str(self) #for debugging, remove later

    def __str__(self):
        """
            returns a string representing the track
        """
        title = self['title']
        album = self['album']
        artist = self['artist']
        ret = "'"+title+"'"
        if artist.strip():
            ret += " by '%s'" % artist
        if album.strip():
            ret += " from '%s'" % album
        return ret

