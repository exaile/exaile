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

import os.path, os
from lib import ecs
import md5, urllib, traceback, re
from xl import common

class CoverNotFoundException(Exception):
    pass

class CoverManager(object):
    """
        Cover manager.

        Manages different pluggable album art interfaces
    """
    def __init__(self, cache_dir):
        """
            Initializes the cover manager

            @param cache_dir:  directory to save remotely downloaded art
        """
        self.cache_dir = cache_dir
        if not os.path.isdir(cache_dir):
            os.mkdir(cache_dir, 0755)

        self.methods = {}
        self.preferred_order = []

    def add_search_method(self, method):
        """
            Adds a search method

            @param method: search method
        """
        self.methods[method.name] = method
        method._set_manager(self)

    def remove_search_method(self, method):
        """
            Removes a search method
            
            @param method: the method to remove
        """
        if method.name in self.methods:
            del self.methods[method.name]

    def set_preferred_order(self, order):
        """
            Sets the preferred search order

            @param order: a list containing the order you'd like to search
                first
        """
        self.preferred_order = order

    def add_defaults(self):
        """
            Adds default search methods
        """
        self.add_search_method(LocalCoverSearch())
        self.add_search_method(
            AmazonCoverSearch('15VDQG80MCS2K1W2VRR2') # Adam Olsen's key
        )
        self.add_search_method(LastFMCoverSearch())

    def find_covers(self, track, limit=-1):
        """
            Finds a cover for a track.  

            Searches the preferred order first, and then the rest of the
            available methods.  The first cover that is found is returned.
        """
        for name in self.preferred_order:
            if name in self.methods:
                try:
                    c = self.methods[name].find_covers(track, limit)
                    return c
                except CoverNotFoundException:  
                    pass

        for k, method in self.methods.iteritems():
            if k not in self.preferred_order:
                try:
                    c = method.find_covers(track, limit)
                    return c
                except CoverNotFoundException:
                    pass

        # no covers were found, raise an exception
        raise CoverNotFoundException()

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
            raise CoverNotFoundException()


class AmazonCoverSearch(CoverSearchMethod):
    """
        Searches amazon for an album cover
    """
    name = 'amazon'
    def __init__(self, amazon_key):
        ecs.setLicenseKey(amazon_key)

    def find_covers(self, track, limit=-1):
        """
            Searches amazon for album covers
        """
        cache_dir = self.manager.cache_dir
        try:
            albums = ecs.ItemSearch(Keywords="%s - %s" %
                (track['artist'], track['album']), SearchIndex="Music",
                ResponseGroup="ItemAttributes,Images")
        except ecs.NoExactMatches:
            raise CoverNotFoundException()

        covers = []
        for album in albums:
            try:
                h = urllib.urlopen(album.LargeImage.URL)
                data = h.read()
                h.close()

                covername = os.path.join(cache_dir,
                    md5.new(album.LargeImage.URL).hexdigest())
                covername += ".jpg"
                h = open(covername, 'w')
                h.write(data)
                h.close()

                covers.append(covername)
                if limit != -1 and len(covers) == limit:
                    return covers
            except AttributeError: continue
            except:
                traceback.print_exc()
                common.log_exception()

        if not covers:
            raise CoverNotFoundException()

        return covers


class LastFMCoverSearch(CoverSearchMethod):
    """
        Searches Last.FM for album art
    """
    name = 'lastfm'
    regex = re.compile(r'<coverart>.*?medium>([^<]*)</medium>.*?</coverart>', 
        re.IGNORECASE|re.DOTALL)
    url = "http://ws.audioscrobbler.com/1.0/album/%(artist)s/%(album)s/info.xml"

    def find_covers(self, track, limit=-1):
        """
            Searches last.fm for album covers
        """
        cache_dir = self.manager.cache_dir

        data = urllib.urlopen(self.url % 
        {
            'album': track['album'],
            'artist': track['artist']
        }).read()

        m = self.regex.search(data)
        if not m:
            raise CoverNotFoundException()

        h = urllib.urlopen(m.group(1))
        data = h.read()
        h.close()

        covername = os.path.join(cache_dir, md5.new(m.group(1)).hexdigest())
        covername += ".jpg"
        h = open(covername, 'w')
        h.write(data)
        h.close()

        return [covername]
