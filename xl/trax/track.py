# -*- coding: utf-8
# Copyright (C) 2008-2010 Adam Olsen
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

from copy import deepcopy
from gi.repository import Gio
from gi.repository import GLib
import logging
import time
import unicodedata
import weakref
import re

from xl import (
    common,
    event,
    metadata,
    settings
)
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

# map chars to appropriate subsitutes for sorting
_sortcharmap = {
        u'ß': u'ss', # U+00DF
        u'æ': u'ae', # U+00E6
        u'ĳ': u'ij', # U+0133
        u'ŋ': u'ng', # U+014B
        u'œ': u'oe', # U+0153
        u'ƕ': u'hv', # U+0195
        u'ǆ': u'dz', # U+01C6
        u'ǉ': u'lj', # U+01C9
        u'ǌ': u'nj', # U+01CC
        u'ǳ': u'dz', # U+01F3
        u'ҥ': u'ng', # U+04A5
        u'ҵ': u'ts', # U+04B5
        }

# Cache these here because calling gettext inside get_tag_display
# is two orders of magnitude slower.
_VARIOUSARTISTSSTR = _("Various Artists")
_UNKNOWNSTR = _("Unknown")
#TRANSLATORS: String multiple tag values will be joined by
_JOINSTR = _(u' / ')


class _MetadataCacher(object):
    """
        Cache metadata Format objects to speed up get_tag_disk
    """
    def __init__(self, timeout=10, maxentries=20):
        """
            :param timeout: time (in s) until the cached obj gets removed.
            :param maxentries: maximum number of format objs to cache
        """
        self._cache = []
        self.timeout = timeout
        self.maxentries = maxentries
        self._cleanup_id = None

    def __cleanup(self):
        if self._cleanup_id:
            GLib.source_remove(self._cleanup_id)
            self._cleanup_id = None
        current = time.time()
        thresh = current - self.timeout
        for item in self._cache[:]:
            if item[2] < thresh:
                self._cache.remove(item)
        if self._cache:
            next_expiry = min([i[2] for i in self._cache])
            timeout = int((next_expiry + self.timeout) - current)
            self._cleanup_id = GLib.timeout_add_seconds(timeout,
                    self.__cleanup)

    def add(self, trackobj, formatobj):
        for item in self._cache:
            if item[0] == trackobj:
                return
        item = [trackobj, formatobj, time.time()]
        self._cache.append(item)
        if len(self._cache) > self.maxentries:
            least = min([(i[2], i) for i in self._cache])[1]
            self._cache.remove(least)
        if not self._cleanup_id:
            self._cleanup_id = GLib.timeout_add_seconds(self.timeout,
                    self.__cleanup)

    def remove(self, trackobj):
        for item in self._cache:
            if item[0] == trackobj:
                self._cache.remove(item)
                break

    def get(self, trackobj):
        for item in self._cache:
            if item[0] == trackobj:
                item[2] = time.time()
                return item[1]


_CACHER = _MetadataCacher()

class Track(object):
    """
        Represents a single track.
    """
    # save a little memory this way
    __slots__ = ["__tags", "_scan_valid",
            "_dirty", "__weakref__", "_init"]
    # this is used to enforce the one-track-per-uri rule
    __tracksdict = weakref.WeakValueDictionary()
    # store a copy of the settings values here - much faster (0.25 cpu
    # seconds) (see _the_cuts_cb)
    __the_cuts = settings.get_option('collection/strip_list', [])

    def __new__(cls, *args, **kwargs):
        """
            override the construction of new Track objects so that
            if there is already a Track for a given uri, we just return
            that Track instance instead of creating a new one.
        """
        # subclassing interferes with the one-track-per-uri scheme and
        # with save and restore of tracks, so we disallow it.
        if cls != Track:
            raise TypeError("Track cannot be subclassed!")

        uri = None
        if len(args) > 0:
            uri = args[0]
        else:
            uri = kwargs.get("uri")

        # Restore uri from pickled state if possible.  This means that
        # if a given Track is in more than one TrackDB, the first
        # TrackDB to get loaded takes precedence, and any data in the
        # second TrackDB is consequently ignored. Thus if at all
        # possible, Tracks should NOT be persisted in more than one
        # TrackDB at a time.
        unpickles = None
        if uri is None:
            if len(args) > 2:
                unpickles = args[2]
            else:
                unpickles = kwargs.get("_unpickles")
            if unpickles is not None:
                uri = unpickles.get("__loc")

        if uri is not None:
            uri = Gio.File.new_for_uri(uri).get_uri()
            try:
                tr = cls.__tracksdict[uri]
                tr._init = False
                
                # if the track *does* happen to be pickled in more than one
                # place, then we need to preserve any internal tags that aren't
                # persisted to disk. 
                #
                # See https://bugs.launchpad.net/exaile/+bug/1054637
                if unpickles is None:
                    if len(args) > 2:
                        unpickles = args[2]
                    else:
                        unpickles = kwargs.get("_unpickles")
                
                if unpickles is not None:
                    for tag, values in unpickles.iteritems():
                        tags = tr.list_tags()
                        if tag.startswith('__') and tag not in tags:
                            tr.set_tag_raw(tag, values)
                
            except KeyError:
                tr = object.__new__(cls)
                cls.__tracksdict[uri] = tr
                tr._init = True
            return tr
        else:
            # this should always fail in __init__, and will never be
            # called in well-formed code.
            tr = object.__new__(cls)
            tr._init = True
            return tr

    def __init__(self, uri=None, scan=True, _unpickles=None):
        """
            :param uri: the location, as either a uri or a file path.
            :param scan: Whether to try to read tags from the given uri.
                  Use only if the tags need to be set by a
                  different source.

            :param _unpickles: used internally to restore from a pickled
                state. not for normal use.
        """
        # don't re-init if its a reused track. see __new__
        if self._init == False:
            return

        self.__tags = {}
        self._scan_valid = None # whether our last tag read attempt worked
        self._dirty = False

        if _unpickles:
            self._unpickles(_unpickles)
            self.__register()
        elif uri:
            self.set_loc(uri)
            if scan:
                self.read_tags()
        else:
            raise ValueError("Cannot create a Track from nothing")

    def __register(self):
        """
            Register this instance into the global registry of Track
            objects.
        """
        self.__tracksdict[self.__tags['__loc']] = self

    def __unregister(self):
        """
            Unregister this instance from the global registry of
            Track objects.
        """
        try:
            del self.__tracksdict[self.__tags['__loc']]
        except KeyError:
            pass

    def set_loc(self, loc):
        """
            Sets the location.

            :param loc: the location, as either a uri or a file path.
        """
        self.__unregister()
        gloc = Gio.File.new_for_commandline_arg(loc)
        self.__tags['__loc'] = gloc.get_uri()
        self.__register()
        event.log_event('track_tags_changed', self, '__loc')

    def exists(self):
        """
            Returns whether the file exists
            This can be very slow, use with caution!
        """
        return Gio.File.new_for_uri(self.get_loc_for_io()).query_exists(None)

    def get_loc_for_io(self):
        """
            Gets the location as a full uri.

            Safe for IO operations via gio, not suitable for display to users
            as it may be in non-utf-8 encodings.
        """
        return self.__tags['__loc']

    def local_file_name(self):
        """
            If the file is accessible on the local filesystem, returns a
            standard path to it (e.g. "/home/foo/bar"), otherwise,
            returns None.

            If a path is returned, it is safe to use for IO operations.
            Existence of a path does *not* guarantee file existence.
        """
        raise DeprecationWarning('get_local_path() is '
            'preferred over local_file_name()')
        return self.get_local_path()

    def get_local_path(self):
        """
            If the file is accessible on a local filesystem, retrieves
            the full path to it, otherwise nothing.

            :returns: the file path or None
            :rtype: string or NoneType
        """
        return Gio.File.new_for_uri(self.get_loc_for_io()).get_path()

    def get_basename(self):
        """
            Returns the base name of a resource
        """
        gfile = Gio.File.new_for_uri(self.get_loc_for_io())

        return gfile.get_basename()

    def get_basename_display(self):
        """
            Return the track basename for display purposes (invalid characters
            are replaced).

            :rtype: unicode
        """
        gfile = Gio.File.new_for_uri(self.get_loc_for_io())
        path = gfile.get_path()
        if path:  # Local
            path = GLib.filename_display_basename(path)
        else:  # Non-local
            path = GLib.filename_display_name(gfile.get_basename())
        return path.decode('utf-8')

    def get_type(self):
        """
            Get the URI schema the file uses, e.g. file, http, smb.
        """
        return Gio.File.new_for_uri(self.get_loc_for_io()).get_uri_scheme()

    def write_tags(self):
        """
            Writes tags to the file for this Track.

            Returns False if unsuccessful, and a Format object from
            `xl.metadata` otherwise.
        """
        try:
            f = metadata.get_format(self.get_loc_for_io())
            if f is None:
                return False # not a supported type
            f.write_tags(self.__tags)
            return f
        except IOError as e:
            # error writing to the file, probably
            logger.warning( "Could not write tags to file: %s" % e )
            return False
        except Exception as e:
            logger.exception( "Unknown exception: Could not write tags to file: %s" % e )
            return False

    def read_tags(self):
        """
            Reads tags from the file for this Track.

            Returns False if unsuccessful, and a Format object from
            `xl.metadata` otherwise.
        """
        loc = self.get_loc_for_io()
        try:
            f = metadata.get_format(loc)
            if f is None:
                self._scan_valid = False
                return False # not a supported type
            ntags = f.read_all()
            for k, v in ntags.iteritems():
                self.set_tag_raw(k, v)

            # remove tags that have been deleted in the file, while
            # taking into account that the db may have tags not
            # supported by the file's tag format.
            if f.others:
                supported_tags = [ t for t in self.list_tags() \
                        if not t.startswith("__") ]
            else:
                supported_tags = f.tag_mapping.keys()
            for tag in supported_tags:
                if tag not in ntags.keys():
                    self.set_tag_raw(tag, None)

            # fill out file specific items
            gloc = Gio.File.new_for_uri(loc)
            mtime = gloc.query_info("time::modified", Gio.FileQueryInfoFlags.NONE, None).get_modification_time()
            mtime = mtime.tv_sec + (mtime.tv_usec/100000.0)
            self.set_tag_raw('__modified', mtime)
            # TODO: this probably breaks on non-local files
            path = gloc.get_parent().get_path()
            self.set_tag_raw('__basedir', path)
            self._dirty = True
            self._scan_valid = True
            return f
        except Exception:
            self._scan_valid = False
            logger.exception("Error reading tags for %s", loc)
            return False

    def is_local(self):
        """
            Determines whether a file is accessible on the local filesystem.
        """
        # TODO: determine this better
        # Maybe use Gio.File.is_native()?
        if self.get_local_path():
            return True
        return False

    def get_size(self):
        """
            Get the raw size of the file. Potentially slow.
        """
        f = Gio.File.new_for_uri(self.get_loc_for_io())
        return f.query_info("standard::size", Gio.FileQueryInfoFlags.NONE, None).get_size()

    def __repr__(self):
        return str(self)

    def __str__(self):
        """
            returns a string representing the track
        """
        vals = map(self.get_tag_display, ('title', 'album', 'artist'))
        rets = []
        for v in vals:
            if not v:
                v = "Unknown"
            v = "'" + v + "'"
            rets.append(v)
        ret = "%s from %s by %s" % tuple(rets)
        return ret

    def _pickles(self):
        """
            returns a data repr of the track suitable for pickling

            internal use only please
        """
        return deepcopy(self.__tags)

    def _unpickles(self, pickle_obj):
        """
            restores the state from the pickle-able repr

            internal use only please
        """
        self.__tags = deepcopy(pickle_obj)

    def list_tags(self):
        """
            Returns a list of the names of all tags present in this Track.
        """
        return self.__tags.keys() + ['__basename']

    def set_tag_raw(self, tag, values, notify_changed=True):
        """
            Set the raw value of a tag.

            :param tag: The name of the tag to set.
            :param values: The value or values to set the tag to.
            :param notify_changed: whether to send a signal to let other
                parts of Exaile know there has been an update. Only set
                this to False if you know that no other parts of Exaile
                need to be updated.
        """
        if tag == '__loc':
            logger.warning('Setting "__loc" directly is forbidden, '
                           'use set_loc() instead.')
            return

        if tag in ('__basename',):
            logger.warning('Setting "%s" directly is forbidden.' % tag)
            return

        # Handle values that aren't lists
        if not isinstance(values, list):
            if not tag.startswith("__"): # internal tags dont have to be lists
                values = [values]

        # For lists, filter out empty values and convert string values to Unicode
        if isinstance(values, list):
            values = [
                common.to_unicode(v, self.__tags.get('__encoding'), 'replace')
                    if isinstance(v, basestring) else v
                for v in values
                    if v not in (None, '')
            ]

        # Save some memory by not storing null values.
        if not values:
            try:
                del self.__tags[tag]
            except KeyError:
                pass
        else:
            self.__tags[tag] = values

        self._dirty = True
        if notify_changed:
            event.log_event("track_tags_changed", self, tag)

    def get_tag_raw(self, tag, join=False):
        """
            Get the raw value of a tag.  For non-internal tags, the
            result will always be a list of unicode strings.

            :param tag: The name of the tag to get
            :param join: If True, joins lists of values into a
                single value.
        """
        if tag == '__basename':
            value = self.get_basename()
        elif tag == '__startoffset': # necessary?
            value = self.__tags.get(tag, 0)
        else:
            value = self.__tags.get(tag)

        if join and value and not tag.startswith('__'):
            return self.join_values(value)

        return value

    def get_tag_sort(self, tag, join=True, artist_compilations=False,
            extend_title=True):
        """
            Get a tag value in a form suitable for sorting.

            :param tag: The name of the tag to get
            :param join: If True, joins lists of values into a
                single value.
            :param artist_compilations: If True, automatically handle
                albumartist and other compilations detections when
                tag=="albumartist".
            :param extend_title: If the title tag is unknown, try to
                add some identifying information to it.
        """
        # The two magic values here are to ensure that compilations
        # and unknown values are always sorted below all normal
        # values.
        value = None
        sorttag = self.__tags.get(tag + "sort")
        if sorttag and tag != "albumartist":
            value = sorttag
        elif tag == "albumartist":
            if artist_compilations and self.__tags.get('__compilation'):
                value = self.__tags.get('albumartist',
                        u"\uffff\uffff\uffff\ufffe")
            else:
                value = self.__tags.get('artist',
                        u"\uffff\uffff\uffff\uffff")
            if sorttag and value not in (u"\uffff\uffff\uffff\ufffe",
                    u"\uffff\uffff\uffff\uffff"):
                value = sorttag
            else:
                sorttag = None
        elif tag in ('tracknumber', 'discnumber'):
            value = self.split_numerical(self.__tags.get(tag))[0]
        elif tag in ('__length', '__playcount'):
            value = self.__tags.get(tag, 0)
        elif tag == 'bpm':
            try:
                value = int(self.__tags.get(tag, [0])[0])
            except ValueError:
                digits = re.search(r'\d+\.?\d*', self.__tags.get(tag, [0])[0])
                if digits:
                    value = float(digits.group())
        elif tag == '__basename':
            # TODO: Check if unicode() is required
            value = self.get_basename()
        else:
            value = self.__tags.get(tag)

        if not value:
            value = u"\uffff\uffff\uffff\uffff" # unknown
            if tag == 'title':
                basename = self.get_basename_display()
                value = u"%s (%s)" % (value, basename)
        elif not tag.startswith("__") and \
                tag not in ('tracknumber', 'discnumber', 'bpm'):
            if not sorttag:
                value = self.format_sort(value)
            else:
                if isinstance(value, list):
                    value = [self.lower(v + u" " + v) for v in value]
                else:
                    value = self.lower(value + u" " + value)
            if join:
                value = self.join_values(value)

        return value

    def get_tag_display(self, tag, join=True, artist_compilations=False,
            extend_title=True):
        """
            Get a tag value in a form suitable for display.

            :param tag: The name of the tag to get
            :param join: If True, joins lists of values into a
                single value.
            :param artist_compilations: If True, automatically handle
                albumartist and other compilations detections when
                tag=="albumartist".
            :param extend_title: If the title tag is unknown, try to
                add some identifying information to it.
        """
        if tag == '__loc':
            uri = Gio.File.new_for_uri(self.__tags['__loc']).get_parse_name()
            return uri.decode('utf-8')

        value = None
        if tag == "albumartist":
            if artist_compilations and self.__tags.get('__compilation'):
                value = self.__tags.get('albumartist', _VARIOUSARTISTSSTR)
            else:
                value = self.__tags.get('artist', _UNKNOWNSTR)
        elif tag in ('tracknumber', 'discnumber'):
            value = self.split_numerical(self.__tags.get(tag))[0] or u""
        elif tag in ('__length', '__startoffset', '__stopoffset'):
            value = self.__tags.get(tag, u"")
        elif tag in ('__rating', '__playcount'):
            value = self.__tags.get(tag, u"0")
        elif tag == '__bitrate':
            try:
                value = int(self.__tags['__bitrate']) // 1000
                if value == -1:
                    value = u""
                else:
                    #TRANSLATORS: Bitrate (k here is short for kbps).
                    value = _("%dk") % value
            except (KeyError, ValueError):
                value = u""
        elif tag == '__basename':
            value = self.get_basename_display()
        else:
            value = self.__tags.get(tag)

        if value is None:
            value = ''
            if tag == 'title':
                basename = self.get_basename_display()
                value = u"%s (%s)" % (_UNKNOWNSTR, basename)

        # Convert value to unicode or List[unicode]
        if isinstance(value, list):
            value = [common.to_unicode(x, errors='replace') for x in value]
        else:
            value = common.to_unicode(value, errors='replace')

        if join:
            value = self.join_values(value, _JOINSTR)

        return value

    def get_tag_search(self, tag, format=True, artist_compilations=False,
            extend_title=True):
        """
            Get a tag value suitable for passing to the search system.
            This includes quoting and list joining.

            :param format: pre-format into a search query.
            :param artist_compilations: If True, automatically handle
                albumartist and other compilations detections when
                tag=="albumartist".
            :param extend_title: If the title tag is unknown, try to
                add some identifying information to it.
        """
        extraformat = ""
        if tag == "albumartist":
            if artist_compilations and self.__tags.get('__compilation'):
                value = self.__tags.get('albumartist', None)
                tag = 'albumartist'
                extraformat += " ! __compilation==__null__"
            else:
                value = self.__tags.get('artist')
        elif tag in ('tracknumber', 'discnumber'):
            value = self.split_numerical(self.__tags.get(tag))[0]
        elif tag in ('__length', '__playcount', '__rating', '__startoffset', '__stopoffset'):
            value = self.__tags.get(tag, 0)
        elif tag == '__bitrate':
            try:
                value = int(self.__tags['__bitrate']) // 1000
                if value != -1:
                    #TRANSLATORS: Bitrate (k here is short for kbps).
                    value = _("%dk") % value
            except (KeyError, ValueError):
                value = -1
        elif tag == '__basename':
            value = self.get_basename()
        else:
            value = self.__tags.get(tag)

        # Quote arguments
        if value is None:
            value = '__null__'
            if tag == 'title':
                extraformat += ' __loc==\"%s\"' % self.__tags['__loc']
        elif isinstance(value, list) and format:
            value = ['"%s"' % self.quoter(val) for val in value]
        elif format:
            value = '"%s"' % self.quoter(value)

        # Join lists
        if format:
            if isinstance(value, list):
                value = " ".join(['%s==%s' % (tag, v) for v in value])
            else:
                value = '%s==%s' % (tag, value)
            if extraformat:
                value += extraformat

        # hack to make things work - discnumber breaks without it.
        # TODO: figure out why this happens, cleaner solution
        if not isinstance(value, list) and not tag.startswith("__"):
            value = unicode(value)

        return value

    def get_tag_disk(self, tag):
        """
            Read a tag directly from disk. Can be slow, use with caution.

            Intended for use with large fields like covers and
            lyrics that shouldn't be loaded to the in-mem db.
        """
        f = _CACHER.get(self)
        if not f:
            try:
                f = metadata.get_format(self.get_loc_for_io())
            except Exception: # TODO: What exception?
                return None
            if not f:
                return None
        _CACHER.add(self, f)
        try:
            return f.read_tags([tag])[tag]
        except KeyError:
            return None

    def list_tags_disk(self):
        """
            List all the tags directly from file metadata. Can be slow,
            use with caution.
        """
        f = _CACHER.get(self)
        if not f:
            try:
                f = metadata.get_format(self.get_loc_for_io())
            except Exception: # TODO: What exception?
                return None
            if not f:
                return None
        _CACHER.add(self, f)
        return f._get_raw().keys()

    ### convenience funcs for rating ###
    # these dont fit in the normal set of tag access methods,
    # but are sufficiently useful to warrant inclusion here

    def get_rating(self):
        """
            Returns the current track rating as an integer, as
            determined by the ``rating/maximum`` setting.

            :rtype: int
        """
        try:
            rating = float(self.get_tag_raw('__rating'))
        except (TypeError, KeyError, ValueError):
            return 0

        maximum = settings.get_option("rating/maximum", 5)
        rating = int(round(rating*float(maximum)/100.0))

        if rating > maximum: return int(maximum)
        elif rating < 0: return 0

        return rating

    def set_rating(self, rating):
        """
            Sets the current track rating from an integer, on the
            scale determined by the ``rating/maximum`` setting.
            
            Returns the scaled rating
        """
        rating = float(rating)
        maximum = float(settings.get_option("rating/maximum", 5))
        rating = min(rating, maximum)
        rating = max(0, rating)
        rating = float(rating * 100.0 / maximum)
        self.set_tag_raw('__rating', rating)
        return rating

    ### Special functions for wrangling tag values ###

    @classmethod
    def format_sort(cls, values):
        if isinstance(values, list):
            return [cls.format_sort(v) for v in values]
        # order of these is important, both for speed and behavior!
        values = cls.strip_leading(values)
        values = cls.strip_marks(values)
        values = cls.lower(values)
        values = cls.the_cutter(values)
        values = cls.expand_doubles(values)
        return values

    @staticmethod
    def join_values(values, glue=u" / "):
        """
            Exaile's standard method to join tag values
        """
        if type(values) in (str, unicode):
            return values
        return glue.join(map(common.to_unicode, values))

    @staticmethod
    def split_numerical(values):
        """
            this is used to split a tag like tracknumber that is in int/int
            format into its separate parts.

            input should be a string of the content, and may also
            be wrapped in a list.
        """
        if not values:
            return None, 0
        if isinstance(values, list):
            val = values[0]
        else:
            val = values
        split = val.split("/")[:2]
        try:
            one = int(split[0])
        except ValueError:
            one = None
        try:
            two = int(split[1])
        except (IndexError, ValueError):
            two = 0
        return (one, two)

    @staticmethod
    def strip_leading(value):
        """
            Strip special chars off the beginning of a field. If
            stripping the chars leaves nothing the original field is
            returned with only whitespace removed.
        """
        stripped = common.to_unicode(value).lstrip(
            " `~!@#$%^&*()_+-={}|[]\\\";'<>?,./")
        if stripped:
            return stripped
        else:
            return value.lstrip()

    @staticmethod
    def the_cutter(value):
        """
            Cut common words like 'the' from the beginning of a tag so that
            they sort properly.
        """
        lowered = value.lower()
        for word in Track.__the_cuts:
            if not word.endswith("'"):
                word += ' '
            if lowered.startswith(word):
                value = value[len(word):]
                break
        return value

    @staticmethod
    def strip_marks(value):
        """
            Remove accents, diacritics, etc.
        """
        # value is appended afterwards so that like-accented values
        # will sort together.
        return u''.join([c for c in unicodedata.normalize('NFD', value)
            if unicodedata.category(c) != 'Mn']) + u" " + value

    @staticmethod
    def expand_doubles(value):
        """
            turns characters like æ into values suitable for sorting,
            like 'ae'. see _sortcharmap for the mapping.

            value must be a unicode object or this wont replace anything.

            value must be in lower-case
        """
        for k, v in _sortcharmap.iteritems():
            value = value.replace(k, v)
        return value
# This is slower, don't use it!
#        return u''.join((_sortcharmap.get(c, c) for c in value))


    @staticmethod
    def lower(value):
        """
            Make tag value lower-case.
        """
        # add the original string after the lowered val so that
        # we sort case-sensitively if the case-insensitive value
        # are identical.
        return value.lower() + " " + value

    @classmethod
    def quoter(cls, value):
        """
            Escape quotes so that it's safe to put the value inside a
            "" literal for searches.

            Has no effect on non-string values.
        """
        try:
            return value.replace('"', '\\\"')
        except AttributeError:
            return value


    @classmethod
    def _the_cuts_cb(cls, name, obj, data):
        """
            PRIVATE

            update the cached the_cutter values
        """
        if data == "collection/strip_list":
            cls._Track__the_cuts = settings.get_option('collection/strip_list', [])

    ### Utility method intended for TrackDB ###
    
    @classmethod
    def _get_track_count(cls):
        '''Internal API, returns number of track objects we have'''
        return len(cls._Track__tracksdict)

event.add_callback(Track._the_cuts_cb, 'collection_option_set')

