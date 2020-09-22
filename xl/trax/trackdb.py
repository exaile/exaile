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
from time import time
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from xl import common, event
from xl.nls import gettext as _
from xl.trax.track import Track

logger = logging.getLogger(__name__)


class TrackHolder:
    def __init__(self, track, key, **kwargs):
        self._track = track
        self._key = key
        self._attrs = kwargs

    def __getattr__(self, attr):
        return getattr(self._track, attr)


class TrackDBIterator:
    def __init__(self, track_iterator: Iterator[Tuple[str, TrackHolder]]):
        self.iter = track_iterator

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.iter)[1]._track


class TrackDB:
    """
    Manages a track database.

    Allows you to add, remove, retrieve, search, save and load
    Track objects.

    :param name:   The name of this :class:`TrackDB`.
    :param location:   Path to a file where this :class:`TrackDB`
            should be stored.
    :param pickle_attrs:   A list of attributes to store in the
            pickled representation of this object. All
            attributes listed must be built-in types, with
            one exception: If the object contains the phrase
            'tracks' in its name it may be a list or dict
            of :class:`Track` objects.
    :param load_first: Set to True if this collection should be
            loaded before any tracks are created.
    """

    def __init__(
        self,
        name: str = "",
        location: str = "",
        pickle_attrs: List[str] = [],
        loadfirst: bool = False,
    ):
        """
        Sets up the trackDB.
        """

        # ensure that the DB is always loaded before any tracks are,
        # otherwise internal values are not loaded and may be lost/corrupted
        if loadfirst and Track._get_track_count() != 0:
            raise RuntimeError(
                (
                    "Internal error! %d tracks already loaded, "
                    + "TrackDB must be loaded first!"
                )
                % Track._get_track_count()
            )

        self.name = name
        self.location = location
        self._dirty = False
        self.tracks: Dict[str, TrackHolder] = {}  # key is URI of the track
        self.pickle_attrs = pickle_attrs
        self.pickle_attrs += ['tracks', 'name', '_key']
        self._saving = False
        self._key = 0
        self._dbversion = 2.0
        self._dbminorversion = 0
        self._deleted_keys = []
        if location:
            self.load_from_location()
            self._timeout_save()

    def __iter__(self):
        """
        Provide the ability to iterate over a TrackDB.
        Just as with a dictionary, if tracks are added
        or removed during iteration, iteration will halt
        wuth a RuntimeError.
        """
        track_iterator = iter(self.tracks.items())
        iterator = TrackDBIterator(track_iterator)
        return iterator

    def __len__(self):
        """
        Obtain a count of how many items are in the TrackDB
        """
        return len(self.tracks)

    @common.glib_wait_seconds(300)
    def _timeout_save(self):
        """
        Callback for auto-saving.
        """
        self.save_to_location()
        return True

    def set_name(self, name):
        """
        Sets the name of this :class:`TrackDB`

        :param name:   The new name.
        :type name: string
        """
        self.name = name
        self._dirty = True

    def get_name(self):
        """
        Gets the name of this :class:`TrackDB`

        :return: The name.
        :rtype: string
        """
        return self.name

    def set_location(self, location):
        """
        Sets the location to save to

        :param location: the location to save to
        """
        self.location = location
        self._dirty = True

    @common.synchronized
    def load_from_location(self, location=None):
        """
        Restores :class:`TrackDB` state from the pickled representation
        stored at the specified location.

        :param location: the location to load the data from
        :type location: string
        """
        if not location:
            location = self.location
        if not location:
            raise AttributeError(
                _("You did not specify a location to load the db from")
            )

        logger.debug("Loading %s DB from %s.", self.name, location)

        pdata = common.open_shelf(location)

        if "_dbversion" in pdata:
            if int(pdata['_dbversion']) > int(self._dbversion):
                raise common.VersionError("DB was created on a newer Exaile version.")
            elif pdata['_dbversion'] < self._dbversion:
                logger.info("Upgrading DB format....")
                import shutil

                shutil.copyfile(location, location + "-%s.bak" % pdata['_dbversion'])
                import xl.migrations.database as dbmig

                dbmig.handle_migration(
                    self, pdata, pdata['_dbversion'], self._dbversion
                )

        for attr in self.pickle_attrs:
            try:
                if 'tracks' == attr:
                    data = {}
                    for k in (x for x in pdata.keys() if x.startswith("tracks-")):
                        p = pdata[k]
                        tr = Track(_unpickles=p[0])
                        loc = tr.get_loc_for_io()
                        if loc not in data:
                            data[loc] = TrackHolder(tr, p[1], **p[2])
                        else:
                            logger.warning("Duplicate track found: %s", loc)
                            # presumably the second track was written because of an error,
                            # so use the first track found.
                            del pdata[k]

                    setattr(self, attr, data)
                else:
                    setattr(self, attr, pdata.get(attr, getattr(self, attr)))
            except Exception:
                # FIXME: Do something about this
                logger.exception("Exception occurred while loading %s", location)

        pdata.close()

        self._dirty = False

    @common.synchronized
    def save_to_location(self, location=None):
        """
        Saves a pickled representation of this :class:`TrackDB` to the
        specified location.

        :param location: the location to save the data to
        :type location: string
        """
        if not self._dirty:
            for track in self.tracks.values():
                if track._track._dirty:
                    self._dirty = True
                    break

        if not self._dirty:
            return

        if not location:
            location = self.location
        if not location:
            raise AttributeError(_("You did not specify a location to save the db"))

        if self._saving:
            return
        self._saving = True

        logger.debug("Saving %s DB to %s.", self.name, location)

        try:
            pdata = common.open_shelf(location)
            if pdata.get('_dbversion', self._dbversion) > self._dbversion:
                raise common.VersionError("DB was created on a newer Exaile.")
        except Exception:
            logger.exception("Failed to open music DB for writing.")
            return

        for attr in self.pickle_attrs:
            # bad hack to allow saving of lists/dicts of Tracks
            if 'tracks' == attr:
                for k, track in self.tracks.items():
                    key = "tracks-%s" % track._key
                    if track._track._dirty or key not in pdata:
                        pdata[key] = (
                            track._track._pickles(),
                            track._key,
                            deepcopy(track._attrs),
                        )
            else:
                pdata[attr] = deepcopy(getattr(self, attr))

        pdata['_dbversion'] = self._dbversion

        for key in self._deleted_keys:
            key = "tracks-%s" % key
            if key in pdata:
                del pdata[key]

        pdata.sync()
        pdata.close()

        for track in self.tracks.values():
            track._track._dirty = False

        self._dirty = False
        self._saving = False

    def get_track_by_loc(self, loc: str, raw=False) -> Optional[Track]:
        """
        returns the track having the given loc. if no such track exists,
        returns None
        """
        try:
            return self.tracks[loc]._track
        except KeyError:
            return None

    def loc_is_member(self, loc: str) -> bool:
        """
        Returns True if loc is a track in this collection, False
        if it is not
        """
        return loc in self.tracks

    def get_count(self) -> int:
        """
        Returns the number of tracks stored in this database
        """
        return len(self.tracks)

    def add(self, track: Track) -> None:
        """
        Adds a track to the database of tracks

        :param track: The :class:`xl.trax.Track` to add
        """
        self.add_tracks([track])

    @common.synchronized
    def add_tracks(self, tracks: Iterable[Track]) -> None:
        """
        Like add(), but takes a list of :class:`xl.trax.Track`
        """
        locations = []
        now = time()
        for tr in tracks:
            if not tr.get_tag_raw('__date_added'):
                tr.set_tags(__date_added=now)
            location = tr.get_loc_for_io()
            # Don't add duplicates -- track URLs are unique
            if location in self.tracks:
                continue
            locations += [location]
            self.tracks[location] = TrackHolder(tr, self._key)
            self._key += 1

        if locations:
            event.log_event('tracks_added', self, locations)
            self._dirty = True

    def remove(self, track: Track) -> None:
        """
        Removes a track from the database

        :param track: the :class:`xl.trax.Track` to remove
        """
        self.remove_tracks([track])

    @common.synchronized
    def remove_tracks(self, tracks: Iterable[Track]) -> None:
        """
        Like remove(), but takes a list of :class:`xl.trax.Track`
        """
        locations = []

        for tr in tracks:
            location = tr.get_loc_for_io()
            locations += [location]
            self._deleted_keys.append(self.tracks[location]._key)
            del self.tracks[location]

        event.log_event('tracks_removed', self, locations)

        self._dirty = True

    def get_tracks(self) -> List[Track]:
        return list(self)
