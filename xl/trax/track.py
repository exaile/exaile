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
import logging
import operator
import re
import time
from typing import Dict, Generic, List, Optional, TypeVar, Union
import unicodedata
import weakref

from gi.repository import Gio
from gi.repository import GLib

from xl.metadata._base import BaseFormat
import xl.unicode
from xl import event, metadata, settings
from xl.metadata.tags import disk_tags
from xl.nls import gettext as _
from xl.unicode import shave_marks

logger = logging.getLogger(__name__)

_K = TypeVar('_K')
_V = TypeVar('_V')

# map chars to appropriate subsitutes for sorting
_sortcharmap = {
    'ß': 'ss',  # U+00DF
    'æ': 'ae',  # U+00E6
    'ĳ': 'ij',  # U+0133
    'ŋ': 'ng',  # U+014B
    'œ': 'oe',  # U+0153
    'ƕ': 'hv',  # U+0195
    'ǆ': 'dz',  # U+01C6
    'ǉ': 'lj',  # U+01C9
    'ǌ': 'nj',  # U+01CC
    'ǳ': 'dz',  # U+01F3
    'ҥ': 'ng',  # U+04A5
    'ҵ': 'ts',  # U+04B5
}

# Cache these here because calling gettext inside get_tag_display
# is two orders of magnitude slower.
_VARIOUSARTISTSSTR = _("Various Artists")
_UNKNOWNSTR = _("Unknown")
# TRANSLATORS: String multiple tag values will be joined by
_JOINSTR = _(' / ')

_no_set_raw = {'__basename', '__loc'} | disk_tags

_unset = object()


class _MetadataCacher(Generic[_K, _V]):
    """Time- and size-limited LRU cache"""

    class Entry:
        value: _V
        time: float

        def __init__(self, value: _V, time: float):
            self.value = value
            self.time = time

        def __lt__(self, other: 'Entry'):
            return self.time < other.time

    _cache: Dict['Track', '_MetadataCacher.Entry']
    timeout: float
    maxentries: int
    _cleanup_id: Optional[int]

    def __init__(self, timeout: float = 10, maxentries: int = 20):
        """
        :param timeout: time (in s) until the cached obj gets removed.
        :param maxentries: maximum number of objects to cache
        """
        self._cache = {}
        self.timeout = timeout
        self.maxentries = maxentries
        self._cleanup_id = None

    def __cleanup(self):
        if self._cleanup_id is not None:
            GLib.source_remove(self._cleanup_id)
            self._cleanup_id = None
        current = time.time()
        thresh = current - self.timeout
        self._cache = {k: v for k, v in self._cache.items() if v.time >= thresh}
        if self._cache:
            next_expiry = min(self._cache.values()).time
            timeout = int((next_expiry + self.timeout) - current)
            self._cleanup_id = GLib.timeout_add_seconds(timeout, self.__cleanup)

    def add(self, key: _K, value: _V) -> None:
        if key in self._cache:
            return
        item = self.Entry(value, time.time())
        self._cache[key] = item
        if len(self._cache) > self.maxentries:
            oldest_key = min(self._cache.items(), key=operator.itemgetter(1))[0]
            del self._cache[oldest_key]
        if self._cleanup_id is None:
            self._cleanup_id = GLib.timeout_add_seconds(self.timeout, self.__cleanup)

    def remove(self, key: _K) -> None:
        try:
            del self._cache[key]
        except KeyError:
            pass

    def get(self, key: _K) -> Optional[_V]:
        item = self._cache.get(key)
        if item is None:
            return None
        item.time = time.time()
        return item.value


#: Cache of metadata format objects to speed up get_tag_disk
_CACHER: _MetadataCacher['Track', BaseFormat] = _MetadataCacher()


class Track:
    """
    Represents a single track.
    """

    # save a little memory this way
    __slots__ = ["__tags", "_scan_valid", "_dirty", "__weakref__", "_init"]
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
                    tags = tr.list_tags()
                    to_set = {
                        tag: values
                        for tag, values in unpickles.items()
                        if tag.startswith('__') and tag not in tags
                    }
                    if to_set:
                        tr.set_tags(**to_set)

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
        if self._init is False:
            return

        self.__tags = {}
        self._scan_valid = None  # whether our last tag read attempt worked

        # This is not used by write_tags, this is used by the collection to
        # indicate that the tags haven't been written to the collection
        self._dirty = False

        if _unpickles:
            self._unpickles(_unpickles)
            self.__register()
        elif uri:
            # notify isn't needed here because this is a new track
            self.set_loc(uri, notify_changed=False)
            if scan:
                self.read_tags(notify_changed=False)
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

    def set_loc(self, loc, notify_changed=True):
        """
        Sets the location.

        :param loc: the location, as either a uri or a file path.
        """
        self.__unregister()
        gloc = Gio.File.new_for_commandline_arg(loc)
        self.__tags['__loc'] = gloc.get_uri()
        self.__register()
        if notify_changed:
            event.log_event('track_tags_changed', self, {'__loc'})

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

    def get_basename_display(self) -> str:
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
        return path

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
                return False  # not a supported type
            f.write_tags(self.__tags)

            # now that we've written the tags to disk, remove any tags that the
            # user asked to be deleted
            to_remove = [k for k, v in self.__tags.items() if v is None]
            for rm in to_remove:
                self.__tags.pop(rm)

            return f
        except IOError:
            # error writing to the file, probably
            logger.warning("Could not write tags to file", exc_info=True)
            return False
        except Exception:
            logger.exception("Unknown exception: Could not write tags to file")
            return False

    def read_tags(self, force=True, notify_changed=True):
        """
        Reads tags from the file for this Track.

        :param force: If not True, then only read the tags if the file has
                      be modified.

        Returns False if unsuccessful, and a Format object from
        `xl.metadata` otherwise.
        """
        loc = self.get_loc_for_io()
        try:
            f = metadata.get_format(loc)
            if f is None:
                self._scan_valid = False
                return False  # not a supported type

            # Retrieve file specific metadata
            gloc = Gio.File.new_for_uri(loc)
            if hasattr(Gio.FileInfo, 'get_modification_date_time'):  # GLib >=2.62
                mtime = (
                    gloc.query_info("time::modified", Gio.FileQueryInfoFlags.NONE, None)
                    .get_modification_date_time()
                    .to_unix()
                )
            else:  # Deprecated due to the Year 2038 problem
                mtime = gloc.query_info(
                    "time::modified", Gio.FileQueryInfoFlags.NONE, None
                ).get_modification_time()
                mtime = mtime.tv_sec + (mtime.tv_usec / 100000.0)

            if not force and self.__tags.get('__modified', 0) >= mtime:
                return f

            # Read the tags
            ntags = f.read_all()
            ntags['__modified'] = mtime

            # TODO: this probably breaks on non-local files
            ntags['__basedir'] = gloc.get_parent().get_path()

            # remove tags that could be in the file, but are in fact not
            # in the file. Retain tags in the DB that aren't supported by
            # the file format.

            nkeys = set(ntags.keys())
            ekeys = {k for k in self.__tags if not k.startswith('__')}

            # delete anything that wasn't in the new tags
            to_del = ekeys - nkeys

            # but if not others set, only delete supported tags
            if not f.others:
                to_del &= set(f.tag_mapping.keys())

            for tag in to_del:
                ntags[tag] = None

            self.set_tags(notify_changed=notify_changed, **ntags)

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
        return f.query_info(
            "standard::size", Gio.FileQueryInfoFlags.NONE, None
        ).get_size()

    def __repr__(self):
        return str(self)

    def __str__(self):
        """
        returns a string representing the track
        """
        vals = map(self.get_tag_display, ('title', 'artist', 'album'))
        return "<Track %r by %r from %r>" % tuple(vals)

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
        return [k for k, v in self.__tags.items() if v is not None] + ['__basename']

    def _xform_set_values(self, tag, values):
        # Handle values that aren't lists
        if not isinstance(values, list):
            if not tag.startswith("__"):  # internal tags dont have to be lists
                values = [values]

        # For lists, filter out empty values
        if isinstance(values, list):
            values = [v for v in values if v not in (None, '')]

        if values:
            return values

        return None

    def set_tag_raw(self, tag, values, notify_changed=True):
        """
        Set the raw value of a tag.

        :param tag: The name of the tag to set.
        :param values: The value or values to set the tag to.
        :param notify_changed: whether to send a signal to let other
            parts of Exaile know there has been an update. Only set
            this to False if you know that no other parts of Exaile
            need to be updated.

        .. note:: When setting more than one tag, prefer set_tags instead

        .. warning:: Covers and lyrics tags must be set via set_tag_disk

        :returns: True if changed, False otherwise
        """
        changed = self.set_tags(notify_changed=notify_changed, **{tag: values})
        return bool(changed)

    def set_tags(self, notify_changed=True, **kwargs):
        """
        Set multiple tags on a track.

        :param notify_changed: whether to send a signal to let other
            parts of Exaile know there has been an update. Only set
            this to False if you know that no other parts of Exaile
            need to be updated.

        Prefer this method over calling set_tag_raw multiple times, as this
        method will be more efficient.

        .. warning:: Covers and lyrics tags must be set via set_tag_disk

        :returns: Set of tags that have changed
        """

        # tag changes can cause expensive UI updates, so don't emit the event
        # if the track hasn't actually changed
        changed = set()

        for tag, values in kwargs.items():
            if tag in _no_set_raw:
                if tag == '__loc':
                    logger.warning(
                        'Setting "__loc" directly is forbidden, use set_loc() instead.'
                    )
                elif tag == '__basename':
                    logger.warning('Setting "__basename" directly is forbidden.')
                else:
                    logger.warning(
                        'Cannot set "%s" via set_tag_raw, use set_tag_disk instead', tag
                    )
                continue

            # Transform and set the value. We do NOT delete the value from the tag
            # dict (which was done prior to Exaile 4), otherwise we don't know that
            # the user wanted the tag to be deleted
            new_value = self._xform_set_values(tag, values)
            if self.__tags.get(tag, _unset) != new_value:
                changed.add(tag)
                self.__tags[tag] = new_value

        if changed:
            self._dirty = True
            if notify_changed:
                event.log_event("track_tags_changed", self, changed)

        return changed

    def get_tag_raw(self, tag, join=False):
        """
        Get the raw value of a tag.  For non-internal tags, the
        result will always be a list of unicode strings.

        :param tag: The name of the tag to get
        :param join: If True, joins lists of values into a
            single value.

        :returns: None if the tag is not present
        """
        if tag == '__basename':
            value = self.get_basename()
        elif tag == '__startoffset':
            # TODO: This is only necessary because some places that deal with
            # __startoffset don't check for None. Those need to be fixed.
            value = self.__tags.get(tag, 0)
        else:
            value = self.__tags.get(tag)

        if join and value and not tag.startswith('__'):
            return self.join_values(value)

        return value

    def get_tag_sort(
        self, tag, join=True, artist_compilations=False, extend_title=True
    ):
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
                value = self.__tags.get('albumartist', "\uffff\uffff\uffff\ufffe")
            else:
                value = self.__tags.get('albumartist')
                if value is None:
                    value = self.__tags.get('artist', "\uffff\uffff\uffff\uffff")
            if sorttag and value not in (
                "\uffff\uffff\uffff\ufffe",
                "\uffff\uffff\uffff\uffff",
            ):
                value = sorttag
            else:
                sorttag = None
        elif tag in ('tracknumber', 'discnumber'):
            value = self.split_numerical(self.__tags.get(tag))[0] or 0
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
        elif tag == '__rating':
            value = self.get_rating()
        else:
            value = self.__tags.get(tag)

        if value is None:
            value = "\uffff\uffff\uffff\uffff"  # unknown
            if tag == 'title':
                basename = self.get_basename_display()
                value = "%s (%s)" % (value, basename)
        elif not tag.startswith("__") and tag not in (
            'tracknumber',
            'discnumber',
            'bpm',
        ):
            if not sorttag:
                value = self.format_sort(value)
            else:
                if isinstance(value, list):
                    value = [self.lower(v + " " + v) for v in value]
                else:
                    value = self.lower(value + " " + value)
            if join:
                value = self.join_values(value)

        return value

    def get_tag_display(
        self, tag, join=True, artist_compilations=False, extend_title=True
    ) -> Union[str, List[str]]:
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
            return Gio.File.new_for_uri(self.__tags['__loc']).get_parse_name()

        value = None
        if tag == "albumartist":
            if artist_compilations and self.__tags.get('__compilation'):
                value = self.__tags.get('albumartist', _VARIOUSARTISTSSTR)
            else:
                value = self.__tags.get('albumartist')
                if value is None:
                    value = self.__tags.get('artist', _UNKNOWNSTR)
        elif tag in ('tracknumber', 'discnumber'):
            value = self.split_numerical(self.__tags.get(tag))[0] or ""
        elif tag in ('__length', '__startoffset', '__stopoffset'):
            value = self.__tags.get(tag, "")
        elif tag in ('__rating', '__playcount'):
            value = self.__tags.get(tag, "0")
        elif tag == '__bitrate':
            try:
                value = int(self.__tags['__bitrate']) // 1000
                if value == -1:
                    value = ""
                else:
                    # TRANSLATORS: Bitrate (k here is short for kbps).
                    value = _("%dk") % value
            except (KeyError, ValueError):
                value = ""
        elif tag == '__basename':
            value = self.get_basename_display()
        else:
            value = self.__tags.get(tag)

        if value is None:
            value = ''
            if tag == 'title':
                basename = self.get_basename_display()
                value = "%s (%s)" % (_UNKNOWNSTR, basename)

        # Convert value to str or List[str]
        if isinstance(value, list):
            value = [xl.unicode.to_unicode(x, errors='replace') for x in value]
        else:
            value = xl.unicode.to_unicode(value, errors='replace')

        if join:
            value = self.join_values(value, _JOINSTR)

        return value

    def get_tag_search(
        self, tag, format=True, artist_compilations=False, extend_title=True
    ):
        """
        Get a tag value suitable for passing to the search system.
        This includes quoting and list joining.

        :param format: pre-format into a search query.
        :param artist_compilations: If True, automatically handle
            albumartist and other compilations detections when
            tag=="albumartist".
        :param extend_title: If the title tag is unknown, try to
            add some identifying information to it.

        :returns: unicode string that is used for searching
        """
        extraformat = ""
        if tag == "albumartist":
            if artist_compilations and self.__tags.get('__compilation'):
                value = self.__tags.get('albumartist', None)
                tag = 'albumartist'
                extraformat += " ! __compilation==__null__"
            else:
                value = self.__tags.get('albumartist')
                if value is None:
                    value = self.__tags.get('artist')
        elif tag in ('tracknumber', 'discnumber'):
            value = self.split_numerical(self.__tags.get(tag))[0]
        elif tag in (
            '__length',
            '__playcount',
            '__rating',
            '__startoffset',
            '__stopoffset',
        ):
            value = self.__tags.get(tag, 0)
        elif tag == '__bitrate':
            try:
                value = int(self.__tags['__bitrate']) // 1000
                if value != -1:
                    # TRANSLATORS: Bitrate (k here is short for kbps).
                    value = [_("%dk") % value, self.__tags['__bitrate']]
            except (KeyError, ValueError):
                value = -1
        elif tag == '__basename':
            value = self.get_basename_display()
        else:
            value = self.__tags.get(tag)

        # Quote arguments
        if value is None:
            value = '__null__'
            if tag == 'title':
                extraformat += ' __loc==\"%s\"' % self.__tags['__loc']
        elif format:
            if isinstance(value, list):
                value = ['"%s"' % self.quoter(val) for val in value]
            else:
                value = '"%s"' % self.quoter(value)

        # Join lists
        if format:
            if isinstance(value, list):
                value = " ".join(['%s==%s' % (tag, v) for v in value])
            else:
                value = '%s==%s' % (tag, value)
            if extraformat:
                value += extraformat

        # Shave marks from strings
        if isinstance(value, list):
            value = [shave_marks(v) for v in value]
        else:
            value = shave_marks(value)

        return value

    def _get_format_obj(self):
        f = _CACHER.get(self)
        if not f:
            try:
                f = metadata.get_format(self.get_loc_for_io())
            except Exception:  # TODO: What exception?
                return None
            if not f:
                return None
        _CACHER.add(self, f)
        return f

    def get_tag_disk(self, tag):
        """
        Read a tag directly from disk. Can be slow, use with caution.

        Intended for use with large fields like covers and
        lyrics that shouldn't be loaded to the in-mem db.

        .. warning:: The track instance will not be updated with the new tag

        :returns: None if the tag does not exist
        """
        f = self._get_format_obj()
        if f:
            try:
                return f.read_tags([tag])[tag]
            except KeyError:
                return None

    def set_tag_disk(self, tag, values):
        """
        Set a tag directly to disk. Can be slow, use with caution.

        Intended for use with large fields like covers and
        lyrics that shouldn't be loaded to the in-mem db.

        .. warning:: The track instance will not be updated with the new tag

        :returns: None if the tag does not exist
        """
        f = self._get_format_obj()
        if f:
            values = self._xform_set_values(tag, values)
            f.write_tags({tag: values})

    def list_tags_disk(self):
        """
        List all the tags directly from file metadata. Can be slow,
        use with caution.
        """
        f = self._get_format_obj()
        if f:
            return f.get_keys_disk()

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
        rating = int(round(rating * float(maximum) / 100.0))

        if rating > maximum:
            return int(maximum)
        elif rating < 0:
            return 0

        return rating

    def set_rating(self, rating):
        """
        Sets the current track rating from an integer, on the
        scale determined by the ``rating/maximum`` setting.

        Returns the scaled rating
        """
        maximum = settings.get_option("rating/maximum", 5)
        rating = min(rating, maximum)
        rating = max(0, rating)
        rating = 100 * rating / maximum
        self.set_tags(__rating=rating)
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
    def join_values(values, glue=" / "):
        """
        Exaile's standard method to join tag values
        """
        if isinstance(values, str):
            return values
        if isinstance(values, bytes):
            logger.warning(
                "join_values with bytes object is deprecated", stack_info=True
            )
            return xl.unicode.to_unicode(values)
        return glue.join(map(xl.unicode.to_unicode, values))

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
        if isinstance(val, int):
            return val, 0
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
        stripped = xl.unicode.to_unicode(value).lstrip(
            " `~!@#$%^&*()_+-={}|[]\\\";'<>?,./"
        )
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
                value = value[len(word) :]
                break
        return value

    @staticmethod
    def strip_marks(value):
        """
        Remove accents, diacritics, etc.
        """
        # value is appended afterwards so that like-accented values
        # will sort together.
        normalize = unicodedata.normalize
        category = unicodedata.category
        return (
            ''.join([c for c in normalize('NFD', value) if category(c) != 'Mn'])
            + " "
            + value
        )

    @staticmethod
    def expand_doubles(value):
        """
        turns characters like æ into values suitable for sorting,
        like 'ae'. see _sortcharmap for the mapping.

        value must be a unicode object or this wont replace anything.

        value must be in lower-case
        """
        for k, v in _sortcharmap.items():
            value = value.replace(k, v)
        return value

    # This is slower, don't use it!
    #        return ''.join((_sortcharmap.get(c, c) for c in value))

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
