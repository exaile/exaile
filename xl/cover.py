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

import logging, os
import gio
from copy import deepcopy
from xl import common, providers, event, metadata, settings
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

try:
    import cPickle as pickle
except ImportError:
    import pickle

class CoverData(object):
    def __init__(self, data):
        self.data = data

def get_cover_data(info):
    if isinstance(info, CoverData):
        return info.data
    
    handle = gio.File(info).read()
    data = handle.read()

    return data

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

    def remove_cover(self, artist, album):
        """
            Removes a cover for an album

            @param artist: the artist
            @param album: the album
        """
        try:
            del self.artists[artist][album]
        except KeyError:
            pass

    def get_cover(self, artist, album):
        """
            Gets the cover filename for an album 

            @param artist: the artist
            @param album: the album
            @return: the location of the cover, or None if no cover exists
        """
        if artist and artist in self.artists:
            if album and album in self.artists[artist]:
                return self.artists[artist][album]
        return None
        
    def set_cover(self, artist, album, cover):
        """
            Sets the cover filename for an album
            
            @param artist: the artist
            @param album: the album
        """
        if not type(cover) == str and not type(cover) == unicode:
            return
        if not os.path.isfile(cover): return
        logger.info("CoverDB: set cover %(cover)s for '%(album)s - %(artist)s'" %
            {'cover' : cover, 'album' : album, 'artist' : artist})
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
            raise AttributeError(_("You did not specify a location to save the db"))

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
            raise AttributeError(_("You did not specify a location to save the db"))

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

class CoverManager(providers.ProviderHandler):
    """
        Cover manager.

        Manages different pluggable cover interfaces
    """
    def __init__(self, cache_dir):
        """
            Initializes the cover manager

            @param cache_dir:  directory to save remotely downloaded art
        """
        providers.ProviderHandler.__init__(self, "covers")
        self.methods = {}
        self.preferred_order = settings.get_option(
                'covers/preferred_order', [])
        self.add_defaults()
        self.cache_dir = cache_dir
        if not os.path.isdir(cache_dir):
            os.mkdir(cache_dir, 0755)

        self.coverdb = CoverDB(location='%s/cover.db' % self.cache_dir)

    def add_search_method(self, method):
        """
            Adds a search method to the provider list.
            
            @param method: the search method instance
        """
        providers.register(self.servicename, method)
        
    def remove_search_method(self, method):
        """
            Removes the given search method from the provider list.
            
            @param method: the search method instance
        """
        providers.unregister(self.servicename, method)
        
    def remove_search_method_by_name(self, name):
        """
            Removes a search method from the provider list.
            
            @param name: the search method name
        """
        try:
            providers.unregister(self.servicename, self.methods[name])
        except KeyError:
            return

    def set_preferred_order(self, order):
        """
            Sets the preferred search order

            @param order: a list containing the order you'd like to search
                first
        """
        if not type(order) in (list, tuple):
            raise AttributeError(_("order must be a list or tuple"))
        self.preferred_order = order
        settings.set_option('covers/preferred_order', list(order))

    def on_new_provider(self, provider):
        """
            Adds the new provider to the methods dict and passes a
            reference of the manager instance to the provider.
            
            @param provider: the provider instance being added.
        """
        if not provider.name in self.methods:
            self.methods[provider.name] = provider
            provider._set_manager(self)
            event.log_event('cover_search_method_added', self, provider) 

    def on_del_provider(self, provider):
        """
            Remove the provider from the methods dict, and the
            preferred_order dict if needed.
            
            @param provider: the provider instance being removed.
        """
        try:
            del self.methods[provider.name]
            event.log_event('cover_search_method_removed', self, provider) 
        except KeyError:
            pass
        try:
            self.preferred_order.remove(provider.name)
        except (ValueError, AttributeError):
            pass     

    def get_methods(self):
        """
            Returns a list of Methods, sorted by preference
        """
        methods = []
        
        for name in self.preferred_order:
            if name in self.methods:
                methods.append(self.methods[name])
        for k, method in self.methods.iteritems():
            if method not in methods:
                methods.append(method)
        return methods

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

    def remove_cover(self, track):
        """
            Removes the cover for a track
        """
        self.coverdb.remove_cover(*track.get_album_tuple())

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

            This function first checks the cover database.  If the cover
            is not there, it searches the available methods

            @param track: the track to search for covers
            @param update_track: if True, update the coverdb to reflect the
                new art
        """
        if not track: raise NoCoverFoundException()

        cover = None
        try:
            item = track.get_album_tuple()
            if not item[0] or not item[1]: 
                raise NoCoverFoundException()
            cover = self.coverdb.get_cover(item[0], item[1]) 
        except TypeError: # one of the fields is missing
            raise NoCoverFoundException()
        except AttributeError:
            pass

        if cover:
            return cover

        covers = self.find_covers(track, limit=1)

        if covers:
            cover = covers[0]
        else:
            raise NoCoverFoundException()

        if update_track:
            self.coverdb.set_cover(item[0], item[1], cover)

        event.log_event('cover_found', self, (track, cover))

        return cover

    def search_covers(self, search_string, limit=-1):
        """
            Finds a cover for a search string

            @param search_string: the search string
            @param limit: Set to -1 to return all covers, or to the max number
            of covers you want returned
        """
        return self.find_covers(search_string, limit=-1, search=True)

    def find_covers(self, track, limit=-1, search=False):
        """
            Finds a cover for a track.  

            Searches the preferred order first, and then the rest of the
            available methods.  The first cover that is found is returned.

            @param track: the track 
            @para limit: Set to -1 to return all covers, or the max number of
                covers you want returned
        """
        covers = []
        logger.info("Attempting to find covers for %s" % track)
        for method in self.get_methods():
            try:
                if not search:
                    c = method.find_covers(track, limit)
                else:
                    if not hasattr(method, 'search_covers'):
                        logger.info("%s method doesn't "
                            "support searching, skipping" % method.name)
                        continue
                    c = method.search_covers(track, limit)

                logger.info("Found covers from %s" % method.name)
                covers.extend(c)
                if limit != -1:
                    event.log_event('cover_found', self, (covers, method.type))
                    break
            except NoCoverFoundException:
                pass
        
        if not covers:
            # no covers were found, raise an exception
            raise NoCoverFoundException()

        event.log_event('covers_found', self, covers) 
        return covers

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
    type = 'local'
    def __init__(self):
        """
            Sets up the cover search method
        """
        CoverSearchMethod.__init__(self)
        self.preferred_names = ['album.jpg', 'cover.jpg']
        self.exts = ['.jpg', '.jpeg', '.png', '.gif']

    def find_covers(self, track, limit=-1):
        covers = []
        try:
            search_dir = gio.File(track.get_loc_for_io()).get_parent()
        except AttributeError:
            raise NoCoverFoundException()

        if not search_dir.query_file_type(flags=gio.FILE_QUERY_INFO_NONE,
                cancellable=gio.Cancellable()) == gio.FILE_TYPE_DIRECTORY:
            raise NoCoverFoundException()
        for fileinfo in search_dir.enumerate_children("standard::type"
                ",standard::name"):
            gloc = search_dir.get_child_for_display_name(fileinfo.get_name())
            if not fileinfo.get_file_type() == gio.FILE_TYPE_REGULAR:
                continue

            filename = gloc.get_basename()

            # check preferred names
            if filename.lower() in self.preferred_names:
                covers.append(gloc.get_uri())
                if limit != -1 and len(covers) == limit:
                    return covers

            # check for other names
            (pathinfo, ext) = os.path.splitext(filename)
            if ext.lower() in self.exts:
                covers.append(gloc.get_uri())
                if limit != -1 and len(covers) == limit:
                    return covers

        if covers:
            return covers
        else:
            raise NoCoverFoundException()
