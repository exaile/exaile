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
from xl.media import flac, mp3, mp4, mpc, ogg, tta, wma, wv, default

from xl.common import lstrip_special

#TODO: find a way to remove this
from mutagen.mp3 import HeaderNotFoundError

import logging, traceback
logger = logging.getLogger(__name__)

# map file extensions to tag modules
formats = {
    'aac' : mp4,
    'ac3' : default,
    'flac': flac,
    'm4a' : mp4,
    'mp+' : mpc,
    'mp2' : mp3,
    'mp3' : mp3,
    'mp4' : mp4,
    'mod' : default,
    'mpc' : mpc,
    'oga' : ogg,
    'ogg' : ogg,
    's3m' : default,
    'tta' : tta,
    'wav' : default,
    'wma' : wma,
    'wv'  : wv,
}

SUPPORTED_MEDIA = ['.' + ext for ext in formats.iterkeys()]

def is_valid_track(loc):
    """
        Returns whether the file at loc is a valid track,
        right now determines based on file extension but
        possibly could be extended to actually opening
        the file and determining
    """
    sections = loc.split('.');
    return sections[-1] in formats

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
            if self.read_tags() is not None:
                self._scan_valid = True

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
        self['loc'] = loc
       
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
            # if we are trying to fetch the title, and there's no title, no
            # album, and no artist, return the location of the file
            if tag == 'title' and not tag in self.tags:
                if not self.get_tag('album') and not self.get_tag('artist'):
                    return self.get_loc()

            values = self.tags[tag]
            if type(values) == unicode and u'\x00' in values:
                values = values.split(u'\x00')
            return values
        except:
            return None

    def set_tag(self, tag, values, append=False):
        """
            Common function for setting a tag.
            
            tag: tag to set [string]
            values: list of values for the tag [list]
            append: whether to append to existing values [bool]
        """
        # handle values tat aren't lists
        if not isinstance(values, list):
            if append:
                values = [values]
            else:
                if type(values) == str:
                    values = unicode(values)

        # for lists, filter out empty values and convert to unicode
        if isinstance(values, list):
            values = [common.to_unicode(x, self['encoding']) for x in values
                if x not in (None, '')]
            if append:
                values = list(self.get_tag(tag)).extend(values)
            values = u'\x00'.join(values)

        # don't bother storing it if its a null value. this saves us a 
        # little memory
        if values in [None, u""]:
            return
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
        if not self.is_local():
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

        #TODO: it might be better to pass these exceptions up to whatever
        # is calling rather than just failing, since then we can do things
        # like showing files that create warnings in the UI.
        try:
            format.fill_tag_from_path(self)
        except HeaderNotFoundError:
            logger.warning("Possibly corrupt file: " + self.get_loc())
            return None
        except:
            common.log_exception(logger)
            return None
        return self

    def is_local(self):
        return urlparse(self.get_loc())[0] == ""

    def get_track(self):
        """
            Gets the track number in int format.  
        """
        t = self.get_tag('tracknumber')
        if t == None:
            return -1
        t = t.split("/")[0]
        return int(t)

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
            artist = lstrip_special(self['artist'])
            if artist == None:
                artist = u""
            if artist.startswith('the '): #TODO: allow custom stemming
                artist = artist[4:]
            return artist
        elif field == 'length':
            try:
                return int(self[field])
            except ValueError:
                return 0
        else: 
            return lstrip_special(unicode(self[field]))

    def __repr__(self):
        return str(self)

    def __str__(self):
        """
            returns a string representing the track
        """
        title = self['title']
        album = self['album']
        artist = self['artist']
        if title and title.strip():
            ret = "'"+title+"'"
        else:
            ret = "'Unknown'"
        if artist and artist.strip():
            ret += " by '%s'" % artist
        if album and album.strip():
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
        self.tags = pickle_str


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

        if key == 'bitrate': track['bitrate'] = int(value) / 1000

        # if there's a comment, but no album, set album to the comment
        elif key == 'comment' and not track.get_loc().endswith('.mp3'): 
            track['album'] = value
        elif key == 'album': track['album'] = value
        elif key == 'artist': track['artist'] = value
        elif key == 'duration': track['length'] = value
        elif key == 'track-number': 
            track['tracknumber'] = value
        elif key == 'genre': track['genre'] = value
        elif key == 'title': 
            try:
                if track['rawtitle'] != value:
                    track['rawtitle'] = value
                    newsong = True
            except AttributeError:
                track['rawtitle'] = value
                newsong = True

            title_array = value.split(' - ', 1)
            if len(title_array) == 1 or (track.get_loc().endswith(".mp3") and \
                not track.get_loc().endswith("lastfm.mp3")):
                track['title'] = value
            else:
                track['artist'] = title_array[0]
                track['title'] = title_array[1]

    if newsong:
        log.append('  New song, fetching cover.')

    for line in log:
        logger.debug(line)
    return newsong


# vim: et sts=4 sw=4

