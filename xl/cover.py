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
logger = logging.getLogger(__name__)

class NoCoverFoundException(Exception):
    pass

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
