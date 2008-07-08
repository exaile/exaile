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

import os.path, os
import urllib, traceback
from xl import common
from xl.manager import SimpleManager
import logging
from copy import deepcopy
logger = logging.getLogger(__name__)

try:
    import cPickle as pickle
except ImportError:
    import pickle

class NoCoverFoundException(Exception):
    pass

class CoverDB(object):
    """
        Manages the stored cover database
    
        Allows you to set covers for a particular album
    """
    def __init__(self, location=None, pickle_attrs=[]):
        """
            Sets up the CoverDB
        """
        self.artists = common.idict()
        self.location = location
        self.pickle_attrs = pickle_attrs
        self.pickle_attrs += ['artists']
        self._dirty = False
        if location:
            self.load_from_location(location)


    def get_cover(self, artist, album):
        """
            Gets the cover filename for an album 

            @param artist: the artist
            @param album: the album
            @return: the location of the cover, or None if no cover exists
        """
        if artist in self.artists:
            if album in self.artists[artist]:
                return self.artists[artist][album]
        return None
        
    def set_cover(self, artist, album, cover):
        """
            Sets the cover filename for an album
            
            @param artist: the artist
            @param album: the album
        """
        if not artist in self.artists:
            self.artists[artist] = common.idict()

        self.artists[artist][album] = cover
        self._dirty = True

    def set_location(self, location):
        self.location = location

    def load_from_location(self, location=None):
        """
            Restores CoverDB state from the pickled representation
            stored at the specified location.

            @param location: the location to load the data from [string]
        """
        if not location:
            location = self.location
        if not location:
            raise AttributeError("You did not specify a location to save the db")

        pdata = None
        for loc in [location, location+".old", location+".new"]:
            try:
                f = open(loc, 'rb')
                pdata = pickle.load(f)
                f.close()
            except:
                pdata = None
            if pdata:
                break
        if not pdata:
            pdata = dict()

        for attr in self.pickle_attrs:
            try:
                setattr(self, attr, pdata[attr])
            except:
                pass

    def save_to_location(self, location=None):
        """
            Saves a pickled representation of this CoverDB to the 
            specified location.
            
            location: the location to save the data to [string]
        """
        if not self._dirty:
            return

        if not location:
            location = self.location
        if not location:
            raise AttributeError("You did not specify a location to save the db")

        try:
            f = file(location, 'rb')
            pdata = pickle.load(f)
            f.close()
        except:
            pdata = dict()
        for attr in self.pickle_attrs:
            pdata[attr] = deepcopy(getattr(self, attr))

        try:
            os.remove(location + ".old")
        except:
            pass
        try:
            os.remove(location + ".new")
        except:
            pass
        f = file(location + ".new", 'wb')
        pickle.dump(pdata, f, common.PICKLE_PROTOCOL)
        f.close()
        try:
            os.rename(location, location + ".old")
        except:
            pass # if it doesn'texist we don't care
        os.rename(location + ".new", location)
        try:
            os.remove(location + ".old")
        except:
            pass
        
        self._dirty = False

class CoverManager(SimpleManager):
    """
        Cover manager.

        Manages different pluggable album art interfaces
    """
    def __init__(self, cache_dir):
        """
            Initializes the cover manager

            @param cache_dir:  directory to save remotely downloaded art
        """
        SimpleManager.__init__(self)
        self.cache_dir = cache_dir
        if not os.path.isdir(cache_dir):
            os.mkdir(cache_dir, 0755)

        self.coverdb = CoverDB(location='%s/cover.db' % self.cache_dir)

    def get_cover_db(self):
        """
            Returns the cover database
        """
        return self.coverdb

    def save_cover_db(self):
        """
            Saves the cover database
        """
        self.coverdb.save_to_location()

    def add_defaults(self):
        """
            Adds default search methods
        """
        self.add_search_method(LocalCoverSearch())

    def set_cover(self, track, order=None):
        """ 
            Sets the ['album_image'] for a given track

            @param track:  The track to set the art for
            @param order:  an optional [list] for preferred search order
        """
        if type(order) in (list, tuple):
            self.preferred_order = order

        try:
            covers = self.find_covers(track)
            track['album_image'] = covers[0]
            return True
        except NoCoverFoundException:
            return False

    def get_cover(self, track, update_track=False):
        """
            Finds one cover for a specified track.

            This function first checks the cover database.  If the album art
            is not there, it searches the available methods

            @param track: the track to search for covers
            @param update_track: if True, update the coverdb to reflect the
                new art
        """
        cover = self.coverdb.get_cover(track['artist'], track['album'])
        if not cover:
            covers = self.find_covers(track, limit=1)
            if not covers:
                raise NoCoverFoundException()
            else:
                cover = covers[0]

        if update_track:
            self.coverdb.set_cover(track['artist'], track['album'], cover)

        return cover

    def find_covers(self, track, limit=-1):
        """
            Finds a cover for a track.  

            Searches the preferred order first, and then the rest of the
            available methods.  The first cover that is found is returned.
        """
        logger.info("Attempting to find covers for %s" % track)
        for method in self.get_methods():
            try:
                c = method.find_covers(track, limit)
                logger.info("Found covers from %s" % method.name)
                return c
            except NoCoverFoundException:
                pass

        # no covers were found, raise an exception
        raise NoCoverFoundException()

    def find_all_covers(self, track):
        """
            finds all available covers for a track
        """
        raise NotImplementedError # this isnt really needed til GUI

class CoverSearchMethod(object):
    """
        Base search method
    """
    name = "basesearchmethod"
    def find_covers(self, track, limit):
        """
            Searches for an album cover

            @param track:  the track to use to find the cover
        """
        return None

    def _set_manager(self, manager):
        """
            Sets the cover manager.  

            Called when this method is added to the cover manager via
            add_search_method()

            @param manager: the cover manager
        """
        self.manager = manager

class LocalCoverSearch(CoverSearchMethod):
    """
        Searches the local path for an album cover
    """
    name = 'local'
    def __init__(self):
        """
            Sets up the cover search method
        """
        CoverSearchMethod.__init__(self)
        self.preferred_names = ['album.jpg', 'cover.jpg']
        self.exts = ['.jpg', '.jpeg', '.png', '.gif']

    def find_covers(self, track, limit=-1):
        covers = []
        search_dir = os.path.dirname(track.get_loc())
        if not os.path.isdir(search_dir):
            raise NoCoverFoundException()
        for file in os.listdir(search_dir):
            if not os.path.isfile(os.path.join(search_dir, file)):
                continue

            # check preferred names
            if file.lower() in self.preferred_names:
                covers.append(os.path.join(search_dir, file))
                if limit != -1 and len(covers) == limit:
                    return covers

            # check for other names
            (pathinfo, ext) = os.path.splitext(file)
            if ext.lower() in self.exts:
                covers.append(os.path.join(search_dir, file))
                if limit != -1 and len(covers) == limit:
                    return covers

        if covers:
            return covers
        else:
            raise NoCoverFoundException()
