# Classes representing collections and libraries
#
# A collection is a database of tracks. It is based on TrackDB but
# has the ability to be linked with libraries.
#
# A library finds tracks in a specified directory and adds them to an
# associated collection.

from xl import trackdb, media, track
from settings import SettingsManager

import os, time, os.path, logging

logger = logging.getLogger(__name__)

class Collection(trackdb.TrackDB):
    """
        Manages a persistent track database.
    """
    def __init__(self, name, location=None, pickle_attrs=[]):
        """
            Set up the collection

            args: see TrackDB
        """
        self.libraries = dict()
        self.settings = SettingsManager.settings
        trackdb.TrackDB.__init__(self, location=location, 
                pickle_attrs=pickle_attrs)
        lib_paths = self.settings.get_option("collection/libraries", [])
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
        for library in self.libraries.values():
            library.rescan()
        try:
            self.save_to_location()
        except AttributeError:
            pass

    def save_libraries(self):
        """
            Save information about libraries into settings
        """
        libraries = []
        for k, v in self.libraries.iteritems():
            libraries.append((v.location, v.realtime, v.scan_interval))
        self.settings.set_option("collection/libraries", libraries)


class ProcessEvent(object):
    pass

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
        self.libraries = []
        self.mask = EventsCodes.IN_MOVED_TO|EventsCodes.IN_MOVED_FROM|\
            EventsCodes.IN_CREATE|EventsCodes.IN_DELETE|EventsCodes.IN_CLOSE_WRITE
            
        self.wm = pyinotify.WatchManager()
        self.notifier = pyinotify.ThreadedNotifier(self.wm, self)
        self.notifier.setDaemon(True)
        self.started = False

    def add_library(self, library):
        wdd = self.wm.add_watch(library.location,
            self.mask, rec=True, auto_add=True)

        self.libraries.append((library, wdd))
        logger.info("Watching directory: %s" % library.location)
        if not self.started:
            self.notifier.start()
            self.started = True

    def process_IN_DELETE(self, event):
        pathname = os.path.join(event.path, event.name)
        logger.info("Location deleted: %s" % pathname)
        for (library, wdd) in self.libraries:
            if pathname.find(library.location) > -1:
                library._remove_locations([pathname])         

    def process_IN_CLOSE_WRITE(self, event):
        pathname = os.path.join(event.path, event.name)
        logger.info("Location modified: %s" % pathname)
        for (library, wdd) in self.libraries:
            if pathname.find(library.location) > -1:
                library._scan_locations([pathname])         

    def process_IN_MOVED_FROM(self, event):
        self.process_IN_DELETE(event)

    def process_IN_MOVED_TO(self, event):
        self.process_IN_CLOSE_WRITE(event)

if pyinotify:
    EVENT_PROCESSOR = INotifyEventProcessor()

class Library(object):
    """
        Scans and watches a folder for tracks, and adds them to
        a Collection.
    """
    def __init__(self, location, realtime=False, scan_interval=0):
        """
            Sets up the Library

            location: the directory this library will scan [string]
            collection: the Collection to associate with [Collection]
        """
        self.location = location
        self.realtime = realtime
        self.scan_interval = scan_interval
        self.set_realtime(realtime)

        self.collection = None

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
        for fullpath in locations:
            if fullpath in self.collection.tracks:
                # check to see if we need to scan this track
                mtime = os.path.getmtime(fullpath)
                if unicode(mtime) == self.collection.tracks[fullpath]['modified']:
                    continue
                else:
                    self.collection.tracks[fullpath].read_tags()
                    continue

            tr = track.Track(fullpath)
            if tr._scan_valid == True:
                self.collection.add(tr)

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

    def rescan(self):
        """
            Rescan the associated folder and add the contained files
            to the Collection
        """
        if not self.collection:
            return

        formats = track.formats.keys()

        for folder in os.walk(self.location):
            basepath = folder[0]
            for filename in folder[2]:
                fullpath = os.path.join(basepath, filename)

                if fullpath in self.collection.tracks:
                    # check to see if we need to scan this track
                    mtime = os.path.getmtime(fullpath)
                    if unicode(mtime) == self.collection.tracks[fullpath]['modified']:
                        continue
                    else:
                        self.collection.tracks[fullpath].read_tags()
                        continue

                tr = track.Track(fullpath)
                if tr._scan_valid == True:
                    self.collection.add(tr)

    def is_realtime(self):
        """
            Returns True if this is library is being watched by gamin
        """
        return self.realtime

    def set_realtime(self, realtime):
        """
            Sets to True if you want this library to be monitored
        """
        self.realtime = realtime
        if realtime and pyinotify:
            EVENT_PROCESSOR.add_library(self)

    def get_rescan_interval(self):
        return 0

    def set_rescan_interval(self, interval):
        pass


