# -*- coding: utf-8
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

import logging
import os
import time
import weakref
import unicodedata
from functools import wraps
from copy import deepcopy
import gio
import gobject
from xl.nls import gettext as _
from xl import common, settings, event, metadata
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
_JOINSTR =_(u' & ')


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
        self._cleanup_id = 0

    def __cleanup(self):
        if self._cleanup_id:
            gobject.source_remove(self._cleanup_id)
        current = time.time()
        thresh = current - self.timeout
        for item in self._cache[:]:
            if item[2] < thresh:
                self._cache.remove(item)
        if self._cache:
            next = min([i[2] for i in self._cache])
            timeout = ((next + self.timeout) - current)
            self._cleanup_id = gobject.timeout_add(timeout*1000,
                    self.__cleanup)

    def add(self, trackobj, formatobj):
        for item in self._cache:
            if item[0] == trackobj:
                return
        item = [trackobj, formatobj, time.time()]
        self._cache.append(item)
        if len(self._cache) > self.maxentries:
            least = min([(i[2],i) for i in self._cache])[1]
            self._cache.remove(least)
        if not self._cleanup_id:
            self._cleanup_id = gobject.timeout_add(self.timeout*1000,
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
        uri = None
        if len(args) > 0:
            uri = args[0]
        else:
            uri = kwargs.get("uri")
        if uri is not None:
            uri = gio.File(uri).get_uri()
            try:
                tr = cls.__tracksdict[uri]
                tr._init = False
            except KeyError:
                tr = object.__new__(cls)
                cls.__tracksdict[uri] = tr
                tr._init = True
            return tr
        else:
            tr = object.__new__(cls)
            tr._init = True
            return tr

    def __init__(self, uri=None, scan=True, _unpickles=None):
        """
            :param uri:  The path to the track.
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
            raise ValueError, "Cannot create a Track from nothing"

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
        gloc = gio.File(loc)
        self.__tags['__loc'] = gloc.get_uri()
        self.__register()

    def exists(self):
        """
            Returns whether the file exists
            This can be very slow, use with caution!
        """
        return gio.File(self.get_loc_for_io()).query_exists()

    def local_file_name(self):
        """
            If the file is accessible on the local filesystem, returns a
            standard path to it (e.g. "/home/foo/bar"), otherwise,
            returns None.

            If a path is returned, it is safe to use for IO operations.
            Existence of a path does *not* guarantee file existence.
        """
        return gio.File(self.__tags['__loc']).get_path()

    def get_loc_for_io(self):
        """
            Gets the location as a full uri.

            Safe for IO operations via gio, not suitable for display to users
            as it may be in non-utf-8 encodings.
        """
        return self.__tags['__loc']

    def get_type(self):
        """
            Get the URI schema the file uses, e.g. file, http, smb.
        """
        return gio.File(self.get_loc_for_io()).get_uri_scheme()

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
        except:
            common.log_exception()
            return False

    def read_tags(self):
        """
            Reads tags from the file for this Track.

            Returns False if unsuccessful, and a Format object from
            `xl.metadata` otherwise.
        """
        try:
            f = metadata.get_format(self.get_loc_for_io())
            if f is None:
                self._scan_valid = False
                return False # not a supported type
            ntags = f.read_all()
            for k,v in ntags.iteritems():
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
            gloc = gio.File(self.get_loc_for_io())
            mtime = gloc.query_info("time::modified").get_modification_time()
            self.set_tag_raw('__modified', mtime)
            # TODO: this probably breaks on non-local files
            path = gloc.get_parent().get_path()
            self.set_tag_raw('__basedir', path)
            self._dirty = True
            self._scan_valid = True
            return f
        except:
            self._scan_valid = False
            common.log_exception()
            return False

    def is_local(self):
        """
            Determines whether a file is accessible on the local filesystem.
        """
        # TODO: determine this better
        if self.local_file_name():
            return True
        return False

    def get_size(self):
        """
            Get the raw size of the file. Potentially slow.
        """
        f = gio.File(self.get_loc_for_io())
        return f.query_info("standard::size").get_size()

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
        return self.__tags.keys()

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
        # handle values that aren't lists
        if not isinstance(values, list):
            if not tag.startswith("__"): # internal tags dont have to be lists
                values = [values]

        # TODO: is this needed? why?
        # for lists, filter out empty values and convert to unicode
        if isinstance(values, list):
            values = [common.to_unicode(x, self.__tags.get('__encoding'))
                for x in values if x not in (None, '')]

        # save some memory by not storing null values.
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
        val = self.__tags.get(tag)
        if join and val:
            return self.join_values(val)
        return val

    def get_tag_sort(self, tag, join=True, artist_compilations=True):
        """
            Get a tag value in a form suitable for sorting.

            :param tag: The name of the tag to get
            :param join: If True, joins lists of values into a
                single value.
            :param artist_compilations: If True, automatically handle
                albumartist and other compilations detections when
                tag=="artist".
        """
        # The two magic values here are to ensure that compilations
        # and unknown values are always sorted below all normal
        # values.
        retval = None
        sorttag = self.__tags.get(tag + "sort")
        if sorttag and tag != "artist":
            retval = sorttag
        elif tag == "artist":
            if artist_compilations and self.__tags.get('__compilation'):
                retval = self.__tags.get('albumartist',
                        u"\uffff\uffff\uffff\ufffe")
            else:
                retval = self.__tags.get('artist',
                        u"\uffff\uffff\uffff\uffff")
            if sorttag and retval not in (u"\uffff\uffff\uffff\ufffe",
                    u"\uffff\uffff\uffff\uffff"):
                retval = sorttag
            else:
                sorttag = None
        elif tag in ('tracknumber', 'discnumber'):
            retval = self.split_numerical(self.__tags.get(tag))[0]
        elif tag in ('__length', '__playcount'):
            retval = self.__tags.get('__length', 0)
        else:
            retval = self.__tags.get(tag)

        if not retval:
            retval = u"\uffff\uffff\uffff\uffff" # unknown
        elif not tag.startswith("__") and \
                tag not in ('tracknumber', 'discnumber'):
            if not sorttag:
                retval = self.format_sort(retval)
            else:
                if isinstance(retval, list):
                    retval = [self.lower(v) for v in retval]
                else:
                    retval = self.lower(retval)
            if join:
                retval = self.join_values(retval)

        return retval

    def get_tag_display(self, tag, join=True, artist_compilations=True):
        """
            Get a tag value in a form suitable for display.

            :param tag: The name of the tag to get
            :param join: If True, joins lists of values into a
                single value.
            :param artist_compilations: If True, automatically handle
                albumartist and other compilations detections when
                tag=="artist".
        """
        if tag == '__loc':
            uri = gio.File(self.__tags['__loc']).get_parse_name()
            return uri.decode('utf-8')

        retval = None
        if tag == "artist":
            if artist_compilations and self.__tags.get('__compilation'):
                retval = self.__tags.get('albumartist', _VARIOUSARTISTSSTR)
            else:
                retval = self.__tags.get('artist', _UNKNOWNSTR)
        elif tag in ('tracknumber', 'discnumber'):
            retval = self.split_numerical(self.__tags.get(tag))[0]
        elif tag == '__length':
            retval = self.__tags.get('__length', 0)
        elif tag == '__bitrate':
            try:
                retval = int(self.__tags['__bitrate']) / 1000
                if retval == -1:
                    retval = " "
                else:
                    retval = str(retval) + "k"
            except:
                retval = " "
        else:
            retval = self.__tags.get(tag)

        if not retval:
            if tag in ('tracknumber', 'discnumber', '__rating',
                    '__playcount'):
                retval = "0"
            else:
                retval = _UNKNOWNSTR

        if isinstance(retval, list):
            retval = [unicode(x) for x in retval]
        else:
            retval = unicode(retval)

        if join:
            retval = self.join_values(retval, _JOINSTR)

        return retval

    def get_tag_search(self, tag, format=True, artist_compilations=True):
        """
            Get a tag value suitable for passing to the search system.

            :param format: pre-format into a search query.
            :param artist_compilations: If True, automatically handle
                albumartist and other compilations detections when
                tag=="artist".
        """
        extraformat = ""
        if tag == "artist":
            if artist_compilations and self.__tags.get('__compilation'):
                retval = self.__tags.get('albumartist', '__null__')
                tag = 'albumartist'
                extraformat += " ! __compilation==__null__"
            else:
                retval = self.__tags.get('artist', '__null__')
        elif tag in ('tracknumber', 'discnumber'):
            retval = self.split_numerical(self.__tags.get(tag))[0]
        elif tag == '__length':
            retval = self.__tags.get('__length', 0)
        elif tag == '__bitrate':
            try:
                retval = int(self.__tags['__bitrate']) / 1000
                if retval != -1:
                    retval = str(retval) + "k"
            except:
                retval = -1
        else:
            retval = self.__tags.get(tag, '__null__')

        if format:
            if isinstance(retval, list):
                retval = " ".join(["%s==\"%s\""%(tag, val) for val in retval])
            else:
                retval = "%s==\"%s\""%(tag, retval)
            if extraformat:
                retval += extraformat

        # hack to make things work - discnumber breaks without it.
        # TODO: figure out why this happens, cleaner solution
        if not isinstance(retval, list) and not tag.startswith("__"):
            retval = unicode(retval)

        return retval

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
            except:
                return None
        _CACHER.add(self, f)
        return f.read_tags([tag])[tag]

    def list_tags_disk(self):
        """
            List all the tags directly from file metadata. Can be slow,
            use with caution.
        """
        f = _CACHER.get(self)
        if not f:
            try:
                f = metadata.get_format(self.get_loc_for_io())
            except:
                return None
        _CACHER.add(self, f)
        return f._get_raw().keys()

    ### convenience funcs for rating ###
    # these dont fit in the normal set of tag access methods,
    # but are sufficiently useful to warrant inclusion here

    def get_rating(self):
        """
            Returns the current track rating as an integer, as
            determined by the ``miscellaneous/rating_steps`` setting.
        """
        try:
            rating = float(self.get_tag_raw('__rating'))
        except (TypeError, KeyError, ValueError):
            return 0

        steps = settings.get_option("miscellaneous/rating_steps", 5)
        rating = int(round(rating*float(steps)/100.0))

        if rating > steps: return int(steps)
        elif rating < 0: return 0

        return rating

    def set_rating(self, rating):
        """
            Sets the current track rating from an integer, on the
            scale determined by the ``miscellaneous/rating_steps`` setting.
        """
        steps = settings.get_option("miscellaneous/rating_steps", 5)

        try:
            rating = min(rating, steps)
            rating = max(0, rating)
            rating = float(rating * 100.0 / float(steps))
        except (TypeError, KeyError, ValueError):
            return
        self.set_tag_raw('__rating', rating)

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
        return glue.join(values)

    @staticmethod
    def split_numerical(values):
        """
            this is used to split a tag like tracknumber that is in int/int
            format into its separate parts.

            input should be a string of the content, and may also
            be wrapped in a list.
        """
        if not values:
            return 0, 0
        if isinstance(values, list):
            val = values[0]
        else:
            val = values
        split = val.split("/")[:2]
        try:
            one = int(split[0])
        except ValueError:
            one = 0
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
        stripped = value.lstrip(" `~!@#$%^&*()_+-={}|[]\\\";'<>?,./")
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
    def _the_cuts_cb(cls, name, obj, data):
        """
            PRIVATE

            update the cached the_cutter values
        """
        if data == "collection/strip_list":
            cls.__the_cuts = settings.get_option('collection/strip_list', [])


event.add_callback(Track._the_cuts_cb, 'collection_option_set')

