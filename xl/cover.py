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

import logging
import os
import hashlib
try:
    import cPickle as pickle
except ImportError:
    import pickle

import gio

from xl import common, providers, event, settings, xdg
from xl.nls import gettext as _

logger = logging.getLogger(__name__)


# TODO: maybe this could go into common.py instead? could be
# useful in other areas.
class Cacher(object):
    """
        Simple on-disk cache.  Note that as entries are stored as
        individual files, the data being stored should be of significant
        size (several KB) or a lot of disk space will likely be wasted.
    """
    def __init__(self, cache_dir):
        """
            :param cache_dir: directory to use for the cache
        """
        try:
            os.makedirs(cache_dir)
        except:
            pass
        self.cache_dir = cache_dir

    def add(self, data):
        """
            Adds an entry to the cache.  Returns a key that can be used
            to retrieve the data from the cache.

            :param data: The data to store, as a bytestring.
        """
        # FIXME: this doesnt handle hash collisions at all. with
        # 2^256 possible keys its unlikely that we'll have a collision,
        # but we should handle it anyway.
        h = hashlib.sha256()
        h.update(data)
        key = h.hexdigest()
        path = os.path.join(self.cache_dir, key)
        open(path, "wb").write(data)
        return key

    def remove(self, key):
        """
            Remove an entry from the cache.

            :param key: The key to retrieve data for.
        """
        path = os.path.join(self.cache_dir, key)
        try:
            os.remove(path)
        except: # FIXME
            pass

    def get(self, key):
        """
            Retrieve an entry from the cache.  Returns None if the given
            key does not exist.
        """
        path = os.path.join(self.cache_dir, key)
        if os.path.exists(path):
            return open(path, "rb").read()
        return None


class CoverManager(providers.ProviderHandler):
    def __init__(self, location=None):
        providers.ProviderHandler.__init__(self, "covers")
        self.__cache = Cacher(os.path.join(location, 'cache'))
        self.location = location
        self.methods = {}
        self.order = settings.get_option(
                'covers/preferred_order', ['tags', 'localfile'])
        self.db = {}
        self.load()
        for method in self.get_providers():
            self.on_new_provider(method)

        providers.register('covers', TagCoverFetcher())
        providers.register('covers', LocalFileCoverFetcher())

    def _get_methods(self):
        """
            Returns a list of Methods, sorted by preference
        """
        methods = []
        for name in self.order:
            if name in self.methods:
                methods.append(self.methods[name])
        for k, method in self.methods.iteritems():
            if method not in methods:
                methods.append(method)
        return methods

    def _get_track_key(self, track):
        """
            Get the db mapping key for a track
        """
        album = track.get_tag_raw("album", join=True)
        compilation = track.get_tag_raw("__compilation")

        if compilation:
            value = self.__tags.get('albumartist')
            if value:
                tag = 'albumartist'
            else:
                tag = 'compilation'
                value = compilation
        elif album:
            tag = 'album'
            value = album
        else:
            # no album info, cant store it
            return None
        return (tag, value)

    def find_covers(self, track, limit=-1, local_only=False):
        covers = []
        for method in self._get_methods():
            if local_only and method.use_cache:
                continue
            new = method.find_covers(track, limit=limit)
            new = ["%s:%s"%(method.name, x) for x in new]
            covers.extend(new)
            if limit != -1 and len(covers) >= limit:
                break
        return covers

    def set_cover(self, track, db_string, data=None):
        """
            Sets the cover for a track. This will overwrite any existing
            entry.

            db_string must be in "method:key" format

            cache will be used if data is not None and the method has
            use_cache=True. otherwise, the method's
            get_cover_data will be called with db_string
            when the cover is requested.
        """
        name, info = db_string.split(":", 1)
        method = self.methods.get(name)
        if method and method.use_cache and data:
            db_string = "cache:%s"%self.__cache.add(data)
        key = self._get_track_key(track)
        self.db[key] = db_string

    def remove_cover(self, track):
        """
            Remove the saved cover entry for a track, if it exists.
        """
        key = self._get_track_key(track)
        db_string = self.db.get(key)
        if db_string:
            del self.db[key]
            self.__cache.remove(db_string)

    def get_cover(self, track, save_cover=True, local_only=False):
        """
            get the cover for a given track.
            if the track has no set cover, backends are
            searched until a cover is found or we run out of backends.
            if a cover is found and save_cover is True, a set_cover
            call will be made to store the cover for later use.
        """
        key = self._get_track_key(track)
        db_string = self.db.get(key)
        if db_string:
            return self.get_cover_data(db_string)

        covers = self.find_covers(track, limit=1, local_only=local_only)
        if covers:
            cover = covers[0]
            data = self.get_cover_data(cover)
            if save_cover:
                self.set_cover(track, cover, data)
            return data

        return None

    def get_cover_data(self, db_string):
        source, data = db_string.split(":", 1)
        if source == "cache":
            return self.__cache.get(data)
        else:
            method = self.methods.get(source)
            if method:
                return method.get_cover_data(data)
            return None

    def get_default_cover(self):
        path = xdg.get_data_path("images", "nocover.png")
        return open(path, "rb").read()

    def load(self):
        path = os.path.join(self.location, 'covers.db')
        data = None
        for loc in [path, path+".old", path+".new"]:
            try:
                f = open(loc, 'rb')
                data = pickle.load(f)
                f.close()
            except: #FIXME
                pass
            if data:
                break
        if data:
            self.db = data

    def save(self):
        path = os.path.join(self.location, 'covers.db')
        try:
            f = open(path + ".new", 'wb')
            pickle.dump(self.db, f, common.PICKLE_PROTOCOL)
            f.close()
        except:
            return
        try:
            os.rename(path, path + ".old")
        except:
            pass # if it doesn'texist we don't care
        os.rename(path + ".new", path)
        try:
            os.remove(path + ".old")
        except:
            pass

    def on_new_provider(self, provider):
        self.methods[provider.name] = provider
        if provider.name not in self.order:
            self.order.append(provider.name)

    def on_del_provider(self, provider):
        del self.methods[provider.name]
        if provider.name in self.order:
            self.order.remove(provider.name)

    def set_preferred_order(self, order):
        """
            Sets the preferred search order

            :param order: a list containing the order you'd like to search
                first
        """
        if not type(order) in (list, tuple):
            raise TypeError("order must be a list or tuple")
        self.order = order
        settings.set_option('covers/preferred_order', list(order))


class CoverSearchMethod(object):
    """
        Base class for creating cover search methods.

        Search methods do not have to inherit from this class, it's
        intended more as a template to demonstrate the needed interface.

        class attributes:
            use_cache - If True, use the cover cache to store the result of
                    get_cover_data.
            name - The name of this backend. Must be globally unique.
    """
    use_cache = True
    name = "base"
    def find_covers(self, track, limit=-1):
        """
            Find the covers for a given track.

            :param track: The track to find covers for.
            :param limit: Maximal number of covers to return.
            :returns: A list of strings that can be passed to get_cover_data.
        """
        raise NotImplementedError

    def get_cover_data(self, db_string):
        """
            Get the image data for a cover

            :param db_string: A method-dependent string that identifies the
                    cover to get.
        """
        raise NotImplementedError


class TagCoverFetcher(CoverSearchMethod):
    use_cache = False
    name = "tags"
    def find_covers(self, track, limit=-1):
        # TODO: handle other art tags, like apev2 uses
        try:
            data = track.get_tag_disk("cover")
        except KeyError:
            return []
        if data:
            # path format: tagname:track_uri
            path = "cover:%s"%track.get_loc()
            return [path]
        return []

    def get_cover_data(self, db_string):
        tag, uri = db_string.split(":", 1)
        tr = trax.Track(uri, scan=False)
        data = tr.get_tag_disk(tag)
        return data

class LocalFileCoverFetcher(CoverSearchMethod):
    use_cache = False
    name = "localfile"
    uri_types = ['file', 'smb', 'sftp', 'nfs']
    extensions = ['.png', '.jpg', '.jpeg', '.gif']
    preferred_names = ['album', 'cover']
    def find_covers(self, track, limit=-1):
        # TODO: perhaps should instead check to see if its mounted in
        # gio, rather than basing this on uri type. file:// should
        # always be checked, obviously.
        if track.get_type() not in self.uri_types:
            return []
        basedir = gio.File(track.get_loc_for_io()).get_parent()
        if not basedir.query_info("standard::type").get_file_type() == \
                gio.FILE_TYPE_DIRECTORY:
            return []
        covers = []
        for fileinfo in basedir.enumerate_children("standard::type"
                ",standard::name"):
            gloc = basedir.get_child(fileinfo.get_name())
            if not fileinfo.get_file_type() == gio.FILE_TYPE_REGULAR:
                continue
            filename = gloc.get_basename()
            base, ext = os.path.splitext(filename)
            if ext.lower() not in self.extensions:
                continue
            if base in self.preferred_names:
                covers.insert(0, gloc.get_uri())
            else:
                covers.append(gloc.get_uri())
        if limit == -1:
            return covers
        else:
            return covers[:limit]

    def get_cover_data(self, db_string):
        handle = gio.File(db_string).read()
        return handle.read()

