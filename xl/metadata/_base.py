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

from collections import namedtuple
import copy
import threading
from typing import Any, ClassVar, Mapping, Sequence

import logging

logger = logging.getLogger(__name__)

from xl import version
import mutagen

version.register('Mutagen', mutagen.version_string)


INFO_TAGS = ['__bitrate', '__length']

_compute_lock = threading.Lock()

# Generic description of cover images
# - type is a number corresponding to the cover type of ID3 APIC tags,
#   desc is a string describing the image, mime is a type,
#   data is the img data
# -> if type is None, then the type is not changeable
CoverImage = namedtuple('CoverImage', 'type desc mime data')


class NotWritable(Exception):
    pass


class NotReadable(Exception):
    pass


class BaseFormat:
    """
    Base class for handling loading of metadata from files.

    subclasses using mutagen should set MutagenType and overload
    the _get_tag, _set_tag, and _del_tag methods as needed.

    subclasses not using mutagen should leave MutagenType as None
    """

    MutagenType = None

    # This should contain ALL keys supported by this filetype, unless 'others'
    # is set to True. If others is True, then anything not in tag_mapping will
    # be written using the Exaile tag name
    # -> dict k: exaile tag name, v: native tag name
    tag_mapping: ClassVar[Mapping[str, Any]] = {}
    others: ClassVar[bool] = True
    writable: ClassVar[bool] = False
    case_sensitive: ClassVar[bool] = True

    # Whether _compute_mappings has run
    _computed: ClassVar[bool]
    # Reverse of tag_mapping, populated in _compute_mappings
    _reverse_mapping: ClassVar[Mapping[Any, str]]

    @classmethod
    def _compute_mappings(cls):
        with _compute_lock:
            # this only needs to be run once per class
            if hasattr(cls, '_computed'):
                return

            if cls.case_sensitive:
                cls._reverse_mapping = {v: k for k, v in cls.tag_mapping.items()}
            else:
                cls._reverse_mapping = {
                    v.lower(): k for k, v in cls.tag_mapping.items()
                }

            from .tags import disk_tags

            cls.ignore_tags = set(disk_tags)

            # This comes last to indicate success
            cls._computed = True

    def __init__(self, loc):
        """
        Raises :class:`NotReadable` if the file cannot be
        opened for some reason.

        :param loc: absolute path to the file to read
            (note - this may change to accept gio uris in the future)
        """
        self.loc = loc
        self.open = False
        self.mutagen = None
        try:
            self._computed
        except AttributeError:
            self.__class__._compute_mappings()

        self.load()

    def load(self):
        """
        Loads the tags from the file.
        """
        if self.MutagenType:
            try:
                self.mutagen = self.MutagenType(self.loc)
            except Exception:
                raise NotReadable

    def save(self):
        """
        Saves any changes to the tags.
        """
        if self.writable and self.mutagen:
            self.mutagen.save()

    def _del_tag(self, raw, tag):
        """
        :param tag: The native tag name
        """
        if tag in raw:
            del raw[tag]

    def _get_raw(self):
        if self.MutagenType or self.mutagen:
            return self.mutagen
        else:
            return {}

    def _get_tag(self, raw, tag):
        """
        :param tag: The native tag name
        """
        try:
            return raw[tag]
        except KeyError:
            return None

    def _set_tag(self, raw, tag, value):
        """
        :param tag: The native tag name
        :param value: If None, delete the tag
        """
        raw[tag] = value

    def get_keys_disk(self) -> Sequence[str]:
        """
        Returns keys of all tags that can be read from disk
        """
        return [self._reverse_mapping.get(k, k) for k in self._get_raw().keys()]

    def read_all(self):
        """
        Reads all non-blacklisted tags from the file.

        Blacklisted tags include lyrics, covers, and any field starting
        with __. If you need to read these, call read_tags directly.
        """
        tags = INFO_TAGS[:]
        for t in self.get_keys_disk():
            if t in self.ignore_tags:
                continue
            # __ is used to denote exaile's internal tags, so we skip
            # loading them to avoid conflicts. usually this shouldn't be
            # an issue.
            if t.startswith("__"):
                continue
            tags.append(t)
        alltags = self.read_tags(tags)
        return alltags

    def read_tags(self, tags):
        """
        get the values for the specified tags.

        returns a dict of the found values. if no value was found for a
        requested tag it will not exist in the returned dict.

        :param tags: a list of exaile tag names to read
        :returns: a dictionary of tag/value pairs.
        """
        raw = self._get_raw()
        td = {}
        for tag in tags:
            t = None
            if tag in INFO_TAGS:
                try:
                    t = self.get_info(tag)
                except KeyError:
                    pass
            if t is None and tag in self.tag_mapping:
                try:
                    t = self._get_tag(raw, self.tag_mapping[tag])
                    if isinstance(t, (str, bytes)):
                        t = [t]
                    elif isinstance(t, list):
                        pass
                    elif t is not None:
                        t = [str(u) for u in t]
                except (KeyError, TypeError):
                    logger.debug("Unexpected error reading `%s`", tag, exc_info=True)
            if t is None and self.others and tag not in self.tag_mapping:
                try:
                    t = self._get_tag(raw, tag)
                    if isinstance(t, (str, bytes)):
                        t = [t]
                    elif t is not None:
                        t = [str(u) for u in t]
                except (KeyError, TypeError):
                    logger.debug("Unexpected error reading `%s`", tag, exc_info=True)

            if t:
                td[tag] = t
        return td

    def write_tags(self, tagdict):
        """
        Write a set of tags to the file. Raises a NotWritable exception
        if the format does not support writing tags.

        When calling this function, we assume the following:

        * tagdict has all keys that you wish to write, keys are exaile tag
          names or custom tag names and values are the tags to write (lists
          of unicode strings)
        * if a value is None, then that tag will be deleted from the file
        * Will not modify/delete tags that are NOT in tagdict
        * Will not write tags that start with '__'

        :param tagdict: A dictionary of tag/value pairs to write.
        """
        if not self.MutagenType or not self.writable:
            raise NotWritable
        else:
            tagdict = copy.deepcopy(tagdict)
            raw = self._get_raw()
            # Add tags if it doesn't have them. Mutagen will throw an exception
            # if the file already contains tags.
            if getattr(raw, 'tags', None) is None:
                try:
                    raw.add_tags()
                except Exception:
                    # XXX: Not sure needed since we're already checking for
                    # existence of tags.
                    pass

            # tags starting with __ are internal and should not be written
            # -> this covers INFO_TAGS, which also shouldn't be written
            for tag in list(tagdict.keys()):
                if tag.startswith("__"):
                    del tagdict[tag]

            # Only modify the tags we were told to modify
            # -> if the value is None, delete the tag
            for tag, value in tagdict.items():
                rtag = self.tag_mapping.get(tag)
                if rtag:
                    if value is not None:
                        self._set_tag(raw, rtag, value)
                    else:
                        self._del_tag(raw, rtag)
                elif self.others:
                    if value is not None:
                        self._set_tag(raw, tag, value)
                    else:
                        self._del_tag(raw, tag)

            self.save()

    def get_info(self, info):
        # TODO: add sample rate? filesize?
        if info == "__length":
            return self.get_length()
        elif info == "__bitrate":
            return self.get_bitrate()
        else:
            raise KeyError

    def get_length(self):
        try:
            return self.mutagen.info.length
        except AttributeError:
            try:
                return self._get_raw()['__length']
            except (KeyError, TypeError):
                return None

    def get_bitrate(self):
        try:
            return self.mutagen.info.bitrate
        except AttributeError:
            try:
                return self._get_raw()['__bitrate']
            except (KeyError, TypeError):
                return None


class CaseInsensitveBaseFormat(BaseFormat):
    case_sensitive = False

    def get_keys_disk(self):
        """
        Returns keys of all tags that can be read from disk
        """
        return [self._reverse_mapping.get(k.lower(), k) for k in self._get_raw().keys()]


# vim: et sts=4 sw=4
