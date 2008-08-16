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


# Classes representing collections and libraries
#
# A collection is a database of tracks. It is based on TrackDB but
# has the ability to be linked with libraries.
#
# A library finds tracks in a specified directory and adds them to an
# associated collection.

from xl import trackdb, track, common, xdg, event, metadata
from xl.settings import SettingsManager
settings = SettingsManager.settings

import os, time, os.path, logging
import gobject

logger = logging.getLogger(__name__)

COLLECTIONS = set()

def get_collection_by_loc(loc):
    """
        returns the collection containing a track having the
        given loc. returns None if no such collection exists.
    """
    for c in COLLECTIONS:
        if c.loc_is_member(loc):
            return c
    return None

class Collection(trackdb.TrackDB):
    """
        Manages a persistent track database.

        Simple usage:

        >>> from xl.collection import *
        >>> c = Collection("Test Collection")
        >>> c.add_library(Library("./tests/data"))
        >>> c.rescan_libraries()
        >>> tracks = list(c.search('artist="TestArtist"'))
        >>> print len(tracks)
        5
        >>> 
    """
    def __init__(self, name, location=None, pickle_attrs=[]):
        """
            Set up the collection

            args: see TrackDB
        """
        self.libraries = dict()
        self._scanning = False
        self._scan_stopped = False
        trackdb.TrackDB.__init__(self, name, location=location,
                pickle_attrs=pickle_attrs)

        COLLECTIONS.add(self)
        self.setup_libraries()

    def setup_libraries(self):
        lib_paths = settings.get_option("collection/libraries", [])
        for (loc, realtime, interval) in lib_paths:
            if len(loc.strip()) > 0:
                self.add_library(Library(loc, realtime, interval))

    def add_library(self, library):
        """
            Add this library to the collection

            library: the library to add [Library]
        """
        loc = library.get_location()
        if loc not in self.libraries.keys():
            self.libraries[loc] = library
            library.set_collection(self)
        else:
            pass # TODO: raise an exception or something here

    def remove_library(self, library):
        """
            Remove a library from the collection

            library: the library to remove [Library]
        """
        for k, v in self.libraries.iteritems():
            if v == library:
                del self.libraries[k]
                return

    def stop_scan(self):
        """
            Stops the library scan
        """
        self._scan_stopped = True
    
    def get_libraries(self):
        """
            Gets a list of all the Libraries associated with this 
            Collection

            returns: [list of Library]
        """
        return self.libraries.values()

    def rescan_libraries(self):
        """
            Rescans all libraries associated with this Collection
        """
        if self._scanning:
            raise Exception("Collection is already being scanned")
        if len(self.libraries) == 0:
            return # no libraries, no need to scan :)

        self._scanning = True
        self._scan_stopped = False

        self.file_count = 0
        for library in self.libraries.values():
            if self._scan_stopped: 
                self._scanning = False
                return
            self.file_count += library._count_files()

        logger.info("File count: %d" % self.file_count)

        scan_interval = self.file_count / len(self.libraries.values()) / 100
        if not scan_interval: scan_interval = 1

        for library in self.libraries.values():
            event.add_callback(self._progress_update, 'tracks_scanned',
                library)
            library.rescan(notify_interval=scan_interval)
            event.remove_callback(self._progress_update, 'tracks_scanned',
                library)
            if self._scan_stopped: 
                self._scanning = False
                return
        try:
            self.save_to_location()
        except AttributeError:
            pass

        event.log_event('scan_progress_update', self, 100)

        self._scanning = False

    def _progress_update(self, type, library, count):
        """
            Called when a progress update should be emitted while scanning
            tracks
        """
        event.log_event('scan_progress_update', self,
            int((float(count) / float(self.file_count)) * 100))

    def save_libraries(self):
        """
            Save information about libraries into settings
        """
        libraries = []
        for k, v in self.libraries.iteritems():
            libraries.append((v.location, v.realtime, v.scan_interval))
        settings.set_option("collection/libraries", libraries)

    def close(self):
        """
            close the collection. does any work like saving to disk,
            closing network connections, etc.
        """
        #TODO: make close() part of trackdb
        collections.remove(self)


class ProcessEvent(object):
    """
        Stub ProcessEvent.  This is here so that the INotifyEventProcessor
        declaration doesn't fail if pyinotify doesn't import correctly
    """
    pass

# attempt to import pyinotify
try:
    import pyinotify
    from pyinotify import EventsCodes, ProcessEvent
except ImportError:
    pyinotify = None

class INotifyEventProcessor(ProcessEvent):
    """
        Processes events from inotify
    """
    def __init__(self):
        """
            Initializes the Event Processor
        """
        self.libraries = []
        self.mask = EventsCodes.IN_MOVED_TO|EventsCodes.IN_MOVED_FROM|\
            EventsCodes.IN_CREATE|EventsCodes.IN_DELETE|EventsCodes.IN_CLOSE_WRITE
            
        self.wm = pyinotify.WatchManager()
        self.notifier = pyinotify.ThreadedNotifier(self.wm, self)
        self.notifier.setDaemon(True)
        self.started = False

    def add_library(self, library):
        """
            Adds a library to be monitored by inotify.
            If the ThreadedNotifier hasn't been started already, it will be
            started

            library:  the Library to be watched
        """
        wdd = self.wm.add_watch(library.location,
            self.mask, rec=True, auto_add=True)

        self.libraries.append((library, wdd))
        logger.info("Watching directory: %s" % library.location)
        if not self.started:
            self.notifier.start()
            self.started = True

    def remove_library(self, library):
        """
            Stops a library from being watched.  If after removing the
            specified library there are no more libraries being watched, the
            notifier thread is stopped

            library: the Library to remove
        """
        if not self.libraries: return
        i = 0
        for (l, wdd) in self.libraries:
            if l == library:
                self.wm.rm_watch(wdd[l.location], rec=True)        
                break
            i += 1

        self.libraries.pop(i)
        if not self.libraries:
            self.notifier.stop()

    def process_IN_DELETE(self, event):
        """
            Called when a file is deleted
        """
        pathname = os.path.join(event.path, event.name)
        logger.info("Location deleted: %s" % pathname)
        for (library, wdd) in self.libraries:
            if pathname.find(library.location) > -1:
                library._remove_locations([pathname])         
                break

    def process_IN_CLOSE_WRITE(self, event):
        """
            Called when a file is changed
        """
        pathname = os.path.join(event.path, event.name)
        logger.info("Location modified: %s" % pathname)
        for (library, wdd) in self.libraries:
            if pathname.find(library.location) > -1:
                library._scan_locations([pathname])         
                break

    def process_IN_MOVED_FROM(self, event):
        """
            Called when a file is created as the result of moving
        """
        self.process_IN_DELETE(event)

    def process_IN_MOVED_TO(self, event):
        """
            Called when a file is removed as the result of moving
        """
        self.process_IN_CLOSE_WRITE(event)

if pyinotify:
    EVENT_PROCESSOR = INotifyEventProcessor()

class PyInotifyNotSupportedException(Exception):
    """
        Thrown when set_realtime is called with True and pyinotify is not
        installed or not supported
    """
    pass

class Library(object):
    """
        Scans and watches a folder for tracks, and adds them to
        a Collection.

        Simple usage:

        >>> from xl.collection import *
        >>> c = Collection("TestCollection")
        >>> l = Library("./tests/data")
        >>> c.add_library(l)
        >>> l.rescan()
        True
        >>> print c.get_libraries()[0].location
        ./tests/data
        >>> print len(list(c.search('artist="TestArtist"')))
        5
        >>> 
    """
    def __init__(self, location, realtime=False, scan_interval=0):
        """
            Sets up the Library

            location: the directory this library will scan [string]
            collection: the Collection to associate with [Collection]
        """
        self.location = location
        self.scan_interval = scan_interval
        self.scan_id = 0
        self.scanning = False
        try:
            self.set_realtime(realtime)
        except PyInotifyNotSupportedException:
            logger.warning("PyInotify not installed or not supported.  "
                "Not watching library: %s" % location)
        except:
            common.log_exception()

        self.collection = None
        self.set_rescan_interval(scan_interval)

    def set_location(self, location):
        """
            Changes the location of this Library

            location: the new location to use [string]
        """
        self.location = location

    def get_location(self):
        """
            Gets the current location associated with this Library

            returns: the current location [string]
        """
        return self.location

    def set_collection(self, collection):

        self.collection = collection

    def _scan_locations(self, locations):
        """
            Scans locations for tracks and adds them to the collection

            locations: a list of locations to check
        """
        db = self.collection
        for fullpath in locations:
            tr = db.get_track_by_loc(fullpath)
            if tr:
                # check to see if we need to scan this track
                mtime = os.path.getmtime(fullpath)
                if unicode(mtime) == tr['modified']:
                    continue
                else:
                    tr.read_tags()
                    continue

            tr = track.Track(fullpath)
            if tr._scan_valid == True:
                db.add(tr)

    def _remove_locations(self, locations):
        """
            Removes tracks at the specified locations from the collection

            locations: the paths to remove
        """
        for loc in locations:
            try:
                track = self.collection.tracks[loc]
            except KeyError:    
                continue

            self.collection.remove(track)

    def _count_files(self):
        """
            Counts the number of files present in this directory
        """
        count = 0
        for folder in os.walk(self.location):
            if self.collection:
                if self.collection._scan_stopped: 
                    return
            count += len(folder[2])

        return count

    def rescan(self, notify_interval=None):
        """
            Rescan the associated folder and add the contained files
            to the Collection
        """
        if self.collection is None:
            return True

        if self.scanning: return

        logger.info("Scanning library: %s" % self.location)
        self.scanning = True
        formats = metadata.formats.keys()
        db = self.collection

        count = 0
        for folder in os.walk(self.location):
            basepath = folder[0]
            for filename in folder[2]:
                if self.collection:
                    if self.collection._scan_stopped: 
                        self.scanning = False
                        return False
                count += 1
                fullpath = os.path.join(basepath, filename)

                try:
                    trmtime = db.get_track_attr(fullpath, "modified")
                    mtime = os.path.getmtime(fullpath)
                    if mtime == trmtime:
                        continue
                except:
                    pass

                tr = db.get_track_by_loc(fullpath)
                if tr:
                    tr.read_tags()
                else:
                    tr = track.Track(fullpath)
                    if tr._scan_valid == True:
                        db.add(tr)

                # notify scanned tracks
                if notify_interval is not None:
                    if count % notify_interval == 0:
                        event.log_event('tracks_scanned', self, count)

        if notify_interval is not None:
            event.log_event('tracks_scanned', self, count)

        self.scanning = False
        return True

    def is_realtime(self):
        """
            Returns True if this is library is being watched
        """
        return self.realtime

    def set_realtime(self, realtime):
        """
            Sets to True if you want this library to be monitored
        """
        if realtime and not pyinotify:
            raise PyInotifyNotSupportedException()           

        self.realtime = realtime
        if realtime and pyinotify:
            EVENT_PROCESSOR.add_library(self)
        
        if not realtime and pyinotify:
            EVENT_PROCESSOR.remove_library(self)

    def get_rescan_interval(self):
        """
            Returns the scan interval in seconds
        """
        return self.scan_interval

    def set_rescan_interval(self, interval):
        """
            Sets the scan interval in seconds.  If the interval is 0 seconds,
            the scan interval is stopped

            interval: scan interval (int) in seconds
        """
        if not interval:
            if self.scan_id:
                gobject.source_remove(self.scan_id)
                self.scan_id = 0
        else:
            if self.scan_id:
                gobject.source_remove(self.scan_id)

            self.scan_id = gobject.timeout_add(interval * 1000, 
                self.rescan)

        self.scan_interval = interval

# vim: et sts=4 sw=4

