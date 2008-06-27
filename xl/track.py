# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

from copy import deepcopy
import os, time, os.path

from mutagen.mp3 import HeaderNotFoundError
from urlparse import urlparse

from xl import common, event
from xl.media import flac, mp3, mp4, mpc, ogg, tta, wav, wma, wv


import logging
logger = logging.getLogger(__name__)

# map file extensions to tag modules
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

TRACK_EVENTS = event.EventManager(use_logger=False)

def track_updated(track, tag, value):
    global TRACK_EVENTS
    e = event.Event(track.get_loc(), track, (tag, value))
    TRACK_EVENTS.emit_async(e)

def set_track_update_callback(function, track_loc):
    global TRACK_EVENTS
    TRACK_EVENTS.add_callback(function, track_loc)

def remove_track_update_callback(function, track_loc):
    global TRACK_EVENTS
    TRACK_EVENTS.remove_callback(function, track_loc)


class Track(object):
    """
        Represents a single track.
    """
    def __init__(self, uri=None, _unpickles=None):
        """
            loads and initializes the tag information
            
            uri: path to the track [string]
            _unpickles: unpickle data [tuple] # internal use only!
        """
        self.tags = {
                'playcount':0,
                'bitrate':0,
                'length':0,
                'blacklisted':False,
                'rating':0,
                'loc':'',
                'encoding':'',
                'modified': 0} 

        self._scan_valid = False
        if uri:
            self.set_loc(uri)
            if self.read_tags() is not None:
                self._scan_valid = True

        elif _unpickles:
            self._unpickles(_unpickles)

    def _track_update_callback(self, track_loc, track_obj, tag_info):
        if track_obj == self:
            return
        elif track_loc != self.get_loc():
            return
        else:
            tag, value = tag_info
            self[tag] = value

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
        try:
            remove_track_update_callback(self._track_update_callback, 
                    self.get_loc())
        except:
            pass

        loc = common.to_unicode(loc, 
                common.get_default_encoding())
        if loc.startswith("file://"):
            loc = loc[7:]
        self['loc'] = loc
       
        set_track_update_callback(self._track_update_callback, 
                self.get_loc())


    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters)

            returns: the location [string]
        """
        return self['loc']

    def get_loc_for_io(self):
        """
            Gets the location as ascii. Should always be correct, see 
            set_loc.

            returns: the location [string]
        """
        return self['loc'].encode(common.get_default_encoding())


    def _pickles(self):
        """
            returns a data repr of the track suitable for pickling

            internal use only please

            returns: (tags, info) [tuple of dicts]
        """
        return deepcopy(self.tags)

    def _unpickles(self, pickle_str):
        """
            restores the state from the pickle-able repr

            internal use only please

            pickle_str: the pickle repr [tuple of dicts]
        """
        self.tags = pickle_str

    def get_tag(self, tag):
        """
            Common function for getting a tag.
            
            tag: tag to get [string]
        """
        values = self.tags.get(tag)
        if values not in [None, "", [] ]:
            if isinstance(values, list):
                values = [ common.to_unicode(x, self.tags['encoding']) \
                        for x in values if x not in (None, '') ]
                return u" / ".join(values)
            else:
                return values
        return u""

    def set_tag(self, tag, values, append=False):
        """
            Common function for setting a tag.
            
            tag: tag to set [string]
            values: list of values for the tag [list]
            append: whether to append to existing values [bool]
        """
        #if tag in common.VALID_TAGS:
        #    values = [values]
        if not isinstance(values, list):
            if append:
                values = [values]
            else:
                self.tags[tag] = values
        # filter out empty values and convert to unicode
        if isinstance(values, list):
            values = [common.to_unicode(x, self.tags['encoding']) for x in values
                if x not in (None, '')]
            if append:
                self.tags[tag].extend(values)
            else:
                self.tags[tag] = list(values)

        track_updated(self, tag, values)

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
        if urlparse(self.get_loc())[0] != "":
            return None #not a local file
        (path, ext) = os.path.splitext(self.get_loc().lower())
        ext = ext[1:]

        if ext not in formats:
            logger.debug('%s format is not understood' % ext)
            return None

        format = formats.get(ext)
        if not format: 
            return None

        try:
            self['modified'] = os.path.getmtime(self.get_loc_for_io())
        except OSError:
            pass
        try:
            format.fill_tag_from_path(self)
        except HeaderNotFoundError:
            logger.warning("Possibly corrupt file: " + self.get_loc())
            return None
        except:
            common.log_exception(__name__)
            return None
        return self

    def get_track(self):
        """
            Gets the track number in int format.  
        """
        t = self.get_tag('tracknumber')
        if t.find('/') > -1:
            t = t[:t.find('/')]
        if t == '':
            t = -1

        return int(t)

    def get_duration(self):
        """
            Returns the length of the track as an int in seconds
        """
        if not self['length']: self['length'] = 0
        return int(float(self['length']))

    def sort_param(self, field):
        """ 
            Returns a sortable of the parameter given (some items should be
            returned as an int instead of unicode)
        """
        if field == 'tracknumber': return self.get_track()
        else: return self[field]

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

# vim: et sts=4 sw=4

