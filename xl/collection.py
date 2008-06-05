# Classes representing collections and libraries
#
# A collection is a database of tracks. It is based on TrackDB but
# has the ability to be linked with libraries.
#
# A library finds tracks in a specified directory and adds them to an
# associated collection.

from xl import trackdb, media, track
from settings import SettingsManager

import os

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
        lib_paths = self.settings.get_option("collection/library_paths", "")
        for l in lib_paths.split(":"):
            if len(l.strip()) > 0:
                self.add_library( Library(l) )

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
        lib_paths = ""
        for k, v in self.libraries.iteritems():
            lib_paths += k + ":"
        lib_paths = lib_paths[:-1]
        self.settings.set_option("collection/library_paths", lib_paths)


class Library:
    """
        Scans and watches a folder for tracks, and adds them to
        a Collection.
    """
    def __init__(self, location):
        """
            Sets up the Library

            location: the directory this library will scan [string]
            collection: the Collection to associate with [Collection]
        """
        self.location = location

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

    def rescan(self):
        """
            Rescan the associated folder and add the contained files
            to the Collection
        """
        if not self.collection:
            return

        formats = media.formats.keys()

        for folder in os.walk(self.location):
            basepath = folder[0]
            for filename in folder[2]:
                fullpath = os.path.join(basepath, filename)
                #(stuff, ext) = os.path.splitext(fullpath)
                tr = track.Track(fullpath)
                if tr._scan_valid == True:
                    self.collection.add(tr)

    def is_realtime(self):
        return False

    def set_realtime(self, bool):
        pass

    def get_rescan_interval(self):
        return 0

    def set_rescan_interval(self, interval):
        pass


