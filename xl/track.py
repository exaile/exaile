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

from copy import deepcopy
import os

try:
    import cPickle as pickle
except:
    import pickle as pickle

import pygst
pygst.require('0.10')
import gst

from xl import common, event
from mutagen.mp3 import HeaderNotFoundError

from xl.media import flac, mp3, mp4, mpc, ogg, tta, wav, wma, wv

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
            Expects the path to the track as an argument
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
        if uri:
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
            characters (ie the value should be exactly identical to the one given)
        """
        self.info['loc'] = common.to_unicode(loc, 
                common.get_default_encoding())
    
    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters)
        """
        return self.info['loc']

    def get_loc_for_io(self):
        """
            Gets the location as ascii. Should always be correct, see set_loc.
        """
        return self.info['loc'].encode(common.get_default_encoding())


    def _pickles(self):
        return deepcopy((self.tags, self.info))

    def _unpickles(self, pickle_str):
        self.tags, self.info = pickle_str

    def get_tag(self, tag):
        """
            Common function for getting a tag.
            Simplifies a list into a single string separated by " / ".
        """
        values = self.tags.get(tag)
        if values:
            values = (common.to_unicode(x, self.info['encoding']) for x in values
                if x not in (None, ''))
            return u" / ".join(values)
        return u""

    def set_tag(self, tag, values, append=False):
        """
            Common function for setting a tag.
            Expects a list (even for a single value)
        """
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
            common.log("Writing metadata to type '%s' is not supported" % 
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
            common.log('%s format is not understood' % ext)
            return None

        format = formats.get(ext)
        if not format: 
            return None

        try:
            format.fill_tag_from_path(self)
        except HeaderNotFoundError:
            print "Possibly corrupt file: " + self.get_loc()
            return None
        except:
            common.log_exception()
            return None
        return self
