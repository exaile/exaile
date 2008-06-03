# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xl import trackdb, media, track

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
        #pickle_attrs += ['libraries']
        trackdb.TrackDB.__init__(self, location=location, 
                pickle_attrs=pickle_attrs)

    def add_library(self, library):
        """
            Add this library to the collection

            library: the library to add [Library]
        """
        loc = library.get_location()
        if loc not in self.libraries.keys():
            self.libraries[loc] = library
        else:
            pass # TODO: raise an exception or something here

    def remove_library(self, library):
        """
            Remove a library from the collection

            library: the library to remove
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

class Library:
    """
        Scans and watches a folder for tracks, and adds them to
        a Collection.
    """
    def __init__(self, location, collection):
        """
            Sets up the Library

            location: the directory this library will scan [string]
            collection: the Collection to associate with [Collection]
        """
        self.location = location
        self.collection = collection

        self.collection.add_library(self)

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

    def rescan(self):
        """
            Rescan the associated folder and add the contained files
            to the Collection
        """
        formats = media.formats.keys()

        for folder in os.walk(self.location):
            basepath = folder[0]
            for filename in folder[2]:
                fullpath = os.path.join(basepath, filename)
                #(stuff, ext) = os.path.splitext(fullpath)
                tr = track.Track(fullpath)
                if tr._scan_valid == True:
                    self.collection.add(tr)

    def set_realtime(self, bool):
        pass

    def set_rescan_interval(self, interval):
        pass


