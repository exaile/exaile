# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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

from xl.nls import gettext as _
import os, time, urlparse
from copy import deepcopy
from urlparse import urlparse
from xl import common
import xl.metadata as metadata
from xl.common import lstrip_special
import logging, traceback
import urlparse
import urllib
import urllib2
from xl import settings, event
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

def get_tracks_from_uri(uri):
    """
        Returns all valid tracks located at uri
    """
    tracks = []
    uri = "file://" + uri if urlparse.urlparse(uri).scheme == "" else uri
    if uri.startswith("file://") and os.path.isdir(uri[7:]):
        tracks = [
                    Track(os.path.join(uri, file))
                    for file in os.listdir(uri[7:])
                    if is_valid_track(file)
                 ]
    else:
        tracks = [Track(uri)]
        tracks[0]['artist'] = tracks[0]['artist'] or uri
        tracks[0]['title'] = tracks[0]['title'] or uri
    return tracks


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
        self._dirty = False
        if _unpickles:
            self._unpickles(_unpickles)
            self._scan_valid = True # allow tag event firing
        elif uri:
            self.set_loc(uri)
            if self.read_tags():
                self._scan_valid = True

    def set_loc(self, loc):
        """
            Sets the location. 
            
            loc: the location [string]
        """
        split = urlparse.urlsplit(loc)
        if split[0] == "":
            loc = os.path.abspath(loc)
            loc = urlparse.urlunsplit(('file', split[1], loc, '', ''))
        self['__loc'] = loc
       
    def get_loc(self):
        """
            Gets the location as unicode (might contain garbled characters) in
            full absolute url form, i.e. "file:///home/foo/bar baz". If you are
            trying to get the path for a local file, use local_file_name(..)

            returns: the location [unicode]
        """
        try:
            return common.to_unicode(self['__loc'],
                common.get_default_encoding())
        except:
            return self['__loc']

    def exists(self):
        """
            Returns if the file exists
        """
        if self.is_local():
            return os.path.exists(self.local_file_name())
        else:
            return  #FIXME: how to handle hanging on missing servers?

            try:
                urllib2.urlopen(self.get_loc_for_io())
            except urllib2.URLError, urllib2.HTTPError:
                return False
            else:
                return True

    def local_file_name(self):
        """
            If the file is a local file, return a standard path to it, i.e.
            "/home/foo/bar", If the file is not local, return None
        """
        if not self.is_local():
            return None
        return common.local_file_from_url(self.get_loc_for_io())

    def get_loc_for_io(self):
        """
            Gets the location in its original form. should always be correct.

            returns: the location [string]
        """
        return self['__loc']

    def get_album_tuple(self):
        """
            Returns the album tuple for use in the coverdb
        """
        # TODO: support albumartist tags in id3 somehow, right now only ogg is
        # supported. See collection.Collection._check_compilations for how
        # we're currently supporting compilations for tracks that don't have
        # this tag
        if self['albumartist']:
            # most of the cover stuff is expecting a 2 item tuple, so we just
            # return the albumartist twice
            return (metadata.j(self['albumartist']),
                metadata.j(self['albumartist']))
        elif self['__compilation']:
            # this should be a 2 item tuple, containing the basedir and the
            # album.  It is populated in
            # collection.Collection._check_compilations
            return self['__compilation']
        else:
            return (metadata.j(self['artist']), 
                metadata.j(self['album']))

    def get_type(self):
        b = self['__loc'].find('://')
        if b == -1: 
            return 'file'
        return self['__loc'][:b]

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
        if not values:
            try:
                del self.tags[tag]
            except KeyError:
                pass
        else:
            self.tags[tag] = values

        self._dirty = True
        if self._scan_valid:
            event.log_event("track-tags-changed", self, tag)
        
    def __getitem__(self, tag):
        """
            Allows retrieval of tags via Track[tag] syntax.
        """
        if tag == '__basedir':
            return [self.get_tag(tag)]
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
            f = metadata.get_format(self.get_loc_for_io())
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
            f = metadata.get_format(self.get_loc_for_io())
            if f is None:
                return False # nto a supported type
            ntags = f.read_all()
            for k,v in ntags.iteritems():
                self[k] = v
                

            # fill out file specific items
            split = urlparse.urlsplit(self.get_loc_for_io())
            path = self.local_file_name()
            mtime = os.path.getmtime(path)
            self['__modified'] = mtime
            self['__basedir'] = os.path.dirname(path)
            self._dirty = True
            return f
        except:
            common.log_exception()
            return False

    def is_local(self):
        return urlparse.urlsplit(self.get_loc()).scheme == "file"

    def get_track(self):
        """
            Gets the track number in int format.  
        """
        t = self.get_tag('tracknumber')
    
        try:
            if type(t) == tuple or type(t) == list:
                t = t[0]

            if t == None:
                return -1
            t = t.split("/")[0]
            return int(t)
        except ValueError:
            return t

    def get_rating(self):
        """
            Returns the current track rating.  Default is 2
        """
        try:
            rating = float(self['__rating'])
        except TypeError:
            return 0
        except KeyError:
            return 0
        except ValueError:
            return 0

        steps = settings.get_option("miscellaneous/rating_steps", 5)
        rating = int(round(rating*float(steps)/100.0))

        if rating > steps: return int(steps)
        elif rating < 0: return 0

        return rating

    def set_rating(self, rating):
        """
            Sets the current track rating
        """
        steps = settings.get_option("miscellaneous/rating_steps", 5)

        try:
            rating = min(rating, steps)
            rating = max(0, rating)
            rating = float(rating * 100.0 / float(steps))
        except TypeError: return
        except KeyError: return
        except ValueError: return
        self['__rating'] = rating

    def get_bitrate(self): 
        """
            Returns the bitrate
        """
        if self.get_type() != 'file':
            if self['__bitrate']:
                try:
                    return "%sk" % self['__bitrate'].replace('k', '')
                except AttributeError:
                    return str(self['__bitrate']) + "k"
            else:
                return ''
        try:
            rate = int(self['__bitrate']) / 1000
            if rate: return "%dk" % rate
            else: return ""
        except:
            return self['__bitrate']

    def get_size(self):
        return os.path.getsize(self.get_loc())

    def get_duration(self):
        """
            Returns the length of the track as an int in seconds
        """
        l = self['__length'] or 0
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
                artist = lstrip_special(self['artist'][0], True)
            except:
                artist = u""
            return artist
        elif field == '__length':
            return self.get_duration()
        elif field in ['__last_played', '__date_added', '__playcount']:
            try:
                return int(self[field])
            except:
                return 0
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
        """
        return deepcopy(self.tags)

    def _unpickles(self, pickle_obj):
        """
            restores the state from the pickle-able repr

            internal use only please
        """
        self.tags = deepcopy(pickle_obj)


def parse_stream_tags(track, tags):
    """
        Called when a tag is found in a stream.
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

        if key == '__bitrate': track['__bitrate'] = int(value[0]) / 1000

        # if there's a comment, but no album, set album to the comment
        elif key == 'comment' and not track.get_loc().endswith('.mp3'): 
            track['album'] = value

        elif key == 'album': track['album'] = value
        elif key == 'artist': track['artist'] = value
        elif key == 'duration': track['__length'] = float(value[0])/1000000000
        elif key == 'track-number': track['tracknumber'] = value
        elif key == 'genre': track['genre'] = value

        elif key == 'title': 
            try:
                if track['__rawtitle'] != value:
                    track['__rawtitle'] = value
                    newsong = True
            except AttributeError:
                track['__rawtitle'] = value
                newsong = True

            title_array = value[0].split(' - ', 1)
            if len(title_array) == 1 or (track.get_loc().endswith(".mp3") and \
                    not track.get_loc().endswith("lastfm.mp3")): # FIXME: HACK!
                track['title'] = value
            else:
                track['artist'] = [title_array[0]]
                track['title'] = [title_array[1]]

    if newsong:
        log.append(_('  New song, fetching cover.'))

    for line in log:
        logger.debug(line)
    return newsong


# vim: et sts=4 sw=4

