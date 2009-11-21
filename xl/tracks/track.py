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

import logging, os, weakref
from copy import deepcopy
import gio
from xl.nls import gettext as _
from xl import common, settings, event
import xl.metadata as metadata
logger = logging.getLogger(__name__)



class Track(object):
    """
        Represents a single track.
    """
    # save a little memory this way
    __slots__ = ["tags", "_scan_valid", "_scanning",
            "_dirty", "__weakref__", "__init"]
    # this is used to enforce the one-track-per-uri rule
    __tracksdict = weakref.WeakValueDictionary()

    def __new__(cls, *args, **kwargs):
        """
            override the construction of new Track objects so that
            if there is already a Track for a given uri, we just return
            that Track instance instead of creating a new one.
        """
        uri = None
        if len(args) > 0:
            uri = args[0]
        elif kwargs.has_key("uri"):
            uri = kwargs["uri"]
        if uri is not None:
            try:
                tr = cls.__tracksdict[uri]
                tr.__init = False
            except KeyError:
                tr = object.__new__(cls)
                cls.__tracksdict[uri] = tr
                tr.__init = True
            return tr
        else:
            tr = object.__new__(cls)
            tr.__init = True
            return tr

    def __init__(self, uri=None, scan=True, _unpickles=None):
        """
            uri:  The path to the track.
            scan: Whether to try to read tags from the given uri.
                  Use only if the tags need to be set by a
                  different source.

            _unpickles: used internally to restore from a pickled
                state. not for normal use.
        """
        # don't re-init if its a reused track. see __new__
        if self.__init == False:
            return

        self.tags = {}

        self._scan_valid = None # whether our last tag read attempt worked
        self._scanning = False  # flag to avoid sending tag updates on mass
                                # load
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
        self.__tracksdict[self.tags['__loc']] = self

    def __unregister(self):
        try:
            del self.__tracksdict[self.tags['__loc']]
        except KeyError:
            pass

    def set_loc(self, loc):
        """
            Sets the location.

            loc: the location [string], as either a uri or a file path.
        """
        self.__unregister()
        gloc = gio.File(loc)
        self.tags['__loc'] = gloc.get_uri()
        self.__register()

    def exists(self):
        """
            Returns if the file exists
            This can be very slow, use with caution!
        """
        return gio.File(self.get_loc_for_io()).query_exists()

    def local_file_name(self):
        """
            If the file is accessible on the local filesystem, return a
            standard path to it i.e. "/home/foo/bar". Otherwise, return None

            If a path is returned, it is safe to use for IO operations.
        """
        return gio.File(self.tags['__loc']).get_path()

    def get_loc_for_io(self):
        """
            Gets the location as a full uri.

            Safe for IO operations via gio, not suitable for display to users
            as it may be in non-utf-8 encodings.

            returns: the location [string]
        """
        return self.tags['__loc']

    def get_type(self):
        """
            Get the URI schema the file uses
        """
        return gio.File(self.get_loc_for_io()).get_uri_scheme()

    def write_tags(self):
        """
            Writes tags to file
        """
        try:
            f = metadata.get_format(self.get_loc_for_io())
            if f is None:
                return False # not a supported type
            f.write_tags(self.tags)
            return f
        except:
            common.log_exception()
            return False

    def read_tags(self):
        """
            Reads tags from file
        """
        try:
            self._scan_valid = False
            f = metadata.get_format(self.get_loc_for_io())
            if f is None:
                return False # not a supported type
            ntags = f.read_all()
            for k,v in ntags.iteritems():
                self.set_tag_raw(k, v)

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
            common.log_exception()
            self._scanning = False
            return False

    def is_local(self):
        # TODO: determine this better
        if self.local_file_name():
            return True
        return False

    def get_size(self):
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
        return deepcopy(self.tags)

    def _unpickles(self, pickle_obj):
        """
            restores the state from the pickle-able repr

            internal use only please
        """
        self.tags = deepcopy(pickle_obj)

    def set_tag_raw(self, tag, values):
        """
            Set the raw value of the tag named "tag"
        """
        # handle values that aren't lists
        if not isinstance(values, list):
            if not tag.startswith("__"): # internal tags dont have to be lists
                values = [values]

        # for lists, filter out empty values and convert to unicode
        if isinstance(values, list):
            values = [common.to_unicode(x, self.tags.get('__encoding'))
                for x in values if x not in (None, '')]

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
        event.log_event("track_tags_changed", self, tag)

    def get_tag_raw(self, tag, join=False):
        val = self.tags.get(tag)
        if join and val:
            return self.join_values(val)
        return val

    def get_tag_sort(self, tag, join=True):
        retval = None
        if tag == "artist":
            # The two magic values here are to ensure that compilations
            # and unknown values are always sorted below all normal
            # values.
            if self.tags.get('__compilation'):
                try:
                    retval = self.tags['albumartist']
                except KeyError: # No album artist, use Various Artist handling
                    retval = u"\ufffe\ufffe\ufffe\ufffe"
            else:
                try:
                    retval = self.tags['artist']
                except KeyError: # Unknown artist
                    retval = u"\uffff\uffff\uffff\uffff"
        elif tag in ('tracknumber', 'discnumber'):
            retval = self.split_numerical(self.tags.get(tag))[0]
        elif tag == '__length':
            retval = self.tags.get('__length', 0)
        elif tag == '__loc':
            return self.tags['__loc']
        else:
            retval = self.tags.get(tag)

        if not retval:
            retval = u"\uffff\uffff\uffff\uffff" # unknown

        if not tag.startswith("__") and \
                tag not in ('tracknumber', 'discnumber'):
            retval = self.strip_leading(retval)
            retval = self.the_cutter(retval)
            if join:
                retval = self.join_values(retval)
            # add the original string after the lowered val so that
            # we sort case-sensitively if the case-insensitive values
            # are identical. 
            retval = retval.lower() + retval

        return retval

    def get_tag_display(self, tag, join=True):
        if tag == '__loc':
            uri = gio.File(self.tags['__loc']).get_parse_name()
            return uri.decode('utf-8')

        retval = None
        if tag == "artist":
            if self.tags.get('__compilation'):
                try:
                    retval = self.tags['albumartist']
                except KeyError:
                    retval = _("Various Artists")
            else:
                try:
                    retval = self.tags['artist']
                except KeyError:
                    retval = _("Unknown")
        elif tag in ('tracknumber', 'discnumber'):
            retval = self.split_numerical(self.tags.get(tag))[0]
        elif tag == '__length':
            retval = self.tags.get('__length', 0)
        elif tag == '__bitrate':
            try:
                retval = int(self.tags['__bitrate']) / 1000
                retval = str(retval) + "k"
            except:
                retval = " "
        else:
            retval = self.tags.get(tag)

        if not retval:
            if tag in ('tracknumber', 'discnumber', '__rating',
                    '__playcount'):
                retval = "0"
            else:
                retval = _("Unknown")

        if isinstance(retval, list) and len(retval) == 1:
            retval = retval[0]

        if isinstance(retval, list):
            retval = [unicode(x) for x in retval]
        else:
            retval = unicode(retval)

        if join:
            retval = self.join_values(retval)

        return retval

    ### convenience funcs for rating ###
    # these dont fit in the normal set of tag access methods,
    # but are sufficiently useful to warrant inclusion here

    def get_rating(self):
        """
            Returns the current track rating.
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
            Sets the current track rating.
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

    @staticmethod
    def join_values(values):
        """
            Exaile's standard method to join tag values
        """
        if type(values) in (str, unicode):
            return values
        return u" / ".join(values)

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
    def strip_leading(values):
        """
            Strip special chars off the beginning of a field. If
            stripping the chars leaves nothing the original field is returned with
            only whitespace removed.
        """
        if isinstance(values, list):
            return [Track.strip_leading(v) for v in values]
        stripped = values.lstrip(" `~!@#$%^&*()_+-={}|[]\\\";'<>?,./")
        if stripped:
            return stripped
        else:
            return values.lstrip()

    @staticmethod
    def the_cutter(values):
        """
            Cut common words like 'the' from the beginning of a tag so that
            they sort properly.
        """
        if isinstance(values, list):
            return [Track.the_cutter(v) for v in values]
        lowered = values.lower()
        for word in settings.get_option('collection/strip_list', ''):
            if not word.endswith("'"):
                word += ' '
            if lowered.startswith(word):
                values = values[len(word):]
                break
        return values


