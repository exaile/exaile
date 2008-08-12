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

import os, time
from copy import deepcopy

from urlparse import urlparse

from xl import common
import xl.metadata as metadata

from xl.common import lstrip_special

import logging, traceback
logger = logging.getLogger(__name__)


def is_valid_track(loc):
    """
        Returns whether the file at loc is a valid track,
        right now determines based on file extension but
        possibly could be extended to actually opening
        the file and determining
    """
    sections = loc.split('.');
    return sections[-1] in metadata.formats

class Track(object):
    """
        Represents a single track.
    """
    def __init__(self, uri=None, _unpickles=None):
        """
            loads and initializes the tag information
            
            uri: path to the track [string]
        """
        self.tags = {}

        self._scan_valid = False
        if _unpickles:
            self._unpickles(_unpickles)
        elif uri:
            self.set_loc(uri)
            if self.read_tags():
                self._scan_valid = True

    def set_loc(self, loc):
        """
            Sets the location. 
            
            loc: the location [string]
        """
        if loc.startswith("file://"):
            loc = loc[7:]
        self['loc'] = loc
       
    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters)

            returns: the location [unicode]
        """
        try:
            return common.to_unicode(self['loc'],
                    common.get_default_encoding())
        except:
            return self['loc']

    def get_loc_for_io(self):
        """
            Gets the location in its original form. should always be correct.

            returns: the location [string]
        """
        return self['loc']

    def get_type(self):
        b = self['loc'].find('://')
        if b == -1: 
            return 'file'
        return self['loc'][:b]

    def get_tag(self, tag):
        """
            Common function for getting a tag.
            
            tag: tag to get [string]
        """
        try:
            values = self.tags[tag]
            return values
        except KeyError:
            return None

    def set_tag(self, tag, values, append=False):
        """
            Common function for setting a tag.
            
            tag: tag to set [string]
            values: list of values for the tag [list]
            append: whether to append to existing values [bool]
        """
        # handle values that aren't lists
        if not isinstance(values, list):
            if tag in common.VALID_TAGS:
                values = [values]

        # for lists, filter out empty values and convert to unicode
        if isinstance(values, list):
            values = [common.to_unicode(x, self['encoding']) for x in values
                if x not in (None, '')]
            if append:
                values = list(self.get_tag(tag)).extend(values)

        # don't bother storing it if its a null value. this saves us a 
        # little memory
        if values in [None, u"", []]:
            try:
                del self.tags[tag]
            except KeyError:
                pass
        else:
            self.tags[tag] = values
        
    def __getitem__(self, tag):
        """
            Allows retrieval of tags via Track[tag] syntax.
        """
        return self.get_tag(tag)

    def __setitem__(self, tag, values):
        """
            Allows setting of tags via Track[tag] syntax.

            Use set_tag if you want to do appending instead of
            always overwriting.
        """
        self.set_tag(tag, values, False)

    def write_tags(self):
        """
            Writes tags to file
        """
        if not self.is_local():
            return False #not a local file
        try:
            f = metadata.getFormat(self.get_loc_for_io())
            if f is None:
                return False # nto a supported type
            f.write_tags(self.tags)
            return f
        except:
            common.log_exception()
            return False

    def read_tags(self):
        """
            Reads tags from file
        """
        if not self.is_local():
            return False #not a local file

        try:
            f = metadata.getFormat(self.get_loc_for_io())
            if f is None:
                return False # nto a supported type
            ntags = f.read_all()
            for k,v in ntags.iteritems():
                self[k] = v
            return f
        except:
            common.log_exception()
            return False

    def is_local(self):
        return urlparse(self.get_loc())[0] == ""

    def get_track(self):
        """
            Gets the track number in int format.  
        """
        t = self.get_tag('tracknumber')
    
        try:
            if type(t) is tuple:
                return int(t[0])

            if t == None:
                return -1
            t = t[0].split("/")[0]
            return int(t)
        except ValueError:
            return t

    def get_bitrate(self): 
        """
            Returns the bitrate
        """
        if self.get_type() != 'file':
            if self['bitrate']:
                try:
                    return "%sk" % self['bitrate'].replace('k', '')
                except AttributeError:
                    return str(self['bitrate']) + "k"
            else:
                return ''
        try:
            rate = int(self['bitrate']) / 1000
            if rate: return "%dk" % rate
            else: return ""
        except:
            return self['bitrate']

    def get_duration(self):
        """
            Returns the length of the track as an int in seconds
        """
        l = self['length'] or 0
        return int(float(l))

    def sort_param(self, field):
        """ 
            Returns a sortable of the parameter given (some items should be
            returned as an int instead of unicode)
        """
        if field == 'tracknumber': 
            return self.get_track()
        elif field == 'artist':
            try:
                artist = lstrip_special(self['artist'][0])
            except:
                artist = None
            if artist == None:
                artist = u""
            if artist.startswith('the '): #TODO: allow custom stemming
                artist = artist[4:]
            return artist
        elif field == 'length':
            return self.get_duration()
        else: 
            try:
                return lstrip_special(unicode(self[field][0]))
            except:
                return u""

    def __repr__(self):
        return str(self)

    def __str__(self):
        """
            returns a string representing the track
        """
        if self['title']:
            title = " / ".join(self['title'])
            ret = "'"+str(title)+"'"
        else:
            ret = "'Unknown'"
        if self['artist']:
            artist = " / ".join(self['artist'])
            ret += " by '%s'" % artist
        if self['album']:
            album = " / ".join(self['album'])
            ret += " from '%s'" % album
        return ret

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
        self.tags = deepcopy(pickle_str)


def parse_stream_tags(track, tags):
    """
        Called when a tag is found in a stream
    """

    log = ['Stream tag:']
    newsong=False

    for key in tags.keys():
        value = tags[key]
        try:
            value = common.to_unicode(value)
        except UnicodeDecodeError:
            log.append('  ' + key + " [can't decode]: " + `str(value)`)
            continue # TODO: What encoding does gst give us?

        log.append('  ' + key + ': ' + value)

        value = [value]

        if key == 'bitrate': track['bitrate'] = int(value[0]) / 1000

        # if there's a comment, but no album, set album to the comment
        elif key == 'comment' and not track.get_loc().endswith('.mp3'): 
            track['album'] = value

        elif key == 'album': track['album'] = value
        elif key == 'artist': track['artist'] = value
        elif key == 'duration': track['length'] = value
        elif key == 'track-number': track['tracknumber'] = value
        elif key == 'genre': track['genre'] = value

        elif key == 'title': 
            try:
                if track['rawtitle'] != value:
                    track['rawtitle'] = value
                    newsong = True
            except AttributeError:
                track['rawtitle'] = value
                newsong = True

            title_array = value[0].split(' - ', 1)
            if len(title_array) == 1 or (track.get_loc().endswith(".mp3") and \
                not track.get_loc().endswith("lastfm.mp3")):
                track['title'] = value
            else:
                track['artist'] = [title_array[0]]
                track['title'] = [title_array[1]]

    if newsong:
        log.append('  New song, fetching cover.')

    for line in log:
        logger.debug(line)
    return newsong


# vim: et sts=4 sw=4

