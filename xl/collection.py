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

from xl import trackdb, media

import os

class Collection(trackdb.TrackDB):
    """
        Manages a persistent track database.
    """
    def __init__(self, location=None, pickle_attrs=[]):
        self.libraries = dict()
        pickle_attrs += ['libraries']
        trackdb.TrackDB.__init__(self, location=location, 
                pickle_attrs=pickle_attrs)

    def add_library(self, library):
        loc = library.get_location()
        if loc not in self.libraries.keys():
            self.libraries[loc] = library
        else:
            pass # TODO: raise an exception or something here

    def remove_library(self, library):
        for k, v in self.libraries.iteritems():
            if v == library:
                del self.libraries[k]
                return
    
    def get_libraries(self):
        return self.libraries.values()

    def rescan_libraries(self):
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
        self.location = location
        self.collection = collection

        self.collection.add_library(self)

    def set_location(self, location):
        self.location = location

    def get_location(self):
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
                (stuff, ext) = os.path.splitext(fullpath)
                track = media.read_from_path(fullpath)
                if track is not None:
                    self.collection.add(track)

    def set_realtime(self, bool):
        pass

    def set_rescan_interval(self, interval):
        pass


