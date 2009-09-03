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

"""
Classes representing collections and libraries

A collection is a database of tracks. It is based on :class:`TrackDB` but has
the ability to be linked with libraries.

A library finds tracks in a specified directory and adds them to an associated
collection.
"""

from xl.nls import gettext as _
from xl import trackdb, track, common, xdg, event, metadata, settings
from xl.settings import SettingsManager

import os, time, os.path, shutil, logging
import gobject, gio
import urllib
import traceback

logger = logging.getLogger(__name__)

COLLECTIONS = set()


def get_collection_by_loc(loc):
    """
        gets the collection by a location.
        
        :param loc: Location of the collection
        :return: collection at location or None
        :rtype: Collection
    """
    for c in COLLECTIONS:
        if c.loc_is_member(loc):
            return c
    return None

class Collection(trackdb.TrackDB):
    """
        Manages a persistent track database.

        :param args: see :class:`xl.trackdb.TrackDB`

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
        global COLLECTIONS
        self.libraries = dict()
        self._scanning = False
        self._scan_stopped = False
        self._running_count = 0
        self._running_total_count = 0
        self._frozen = False
        self._libraries_dirty = False
        pickle_attrs += ['_serial_libraries']
        trackdb.TrackDB.__init__(self, name, location=location,
                pickle_attrs=pickle_attrs)
        COLLECTIONS.add(self)

    def freeze_libraries(self):
        """
            Prevents "libraries_modified" events from being sent from individual
            add and remove library calls.

            Call this before making bulk changes to the libraries. Call
            thaw_libraries when you are done; this sends a single event if the
            libraries were modified.
        """
        self._frozen = True

    def thaw_libraries(self):
        """
            Re-allow "libraries_modified" events from being sent from individual
            add and remove library calls. Also sends a "libraries_modified"
            event if the libraries have ben modified since the last call to
            freeze_libraries.
        """
        # TODO: This method should probably be synchronized.
        self._frozen = False
        if self._libraries_dirty:
            self._libraries_dirty = False
            event.log_event('libraries_modified', self, None)

    def add_library(self, library):
        """
            Add this library to the collection

            :param library: the library to add
            :type library: :class:`Library`
        """
        loc = library.get_location()
        if loc not in self.libraries:
            self.libraries[loc] = library
            library.set_collection(self)
        else:
            traceback.print_exc()
        self.serialize_libraries()
        self._dirty = True

        if self._frozen:
            self._libraries_dirty = True
        else:
            event.log_event('libraries_modified', self, None)

    def remove_library(self, library):
        """
            Remove a library from the collection

            :param library: the library to remove
            :type library: :class:`Library`
        """
        for k, v in self.libraries.iteritems():
            if v == library:
                del self.libraries[k]
                break
 
        to_rem = []
        if not "://" in library.location:
            location = u"file://" + library.location
        else:
            location = library.location
        for tr in self.tracks:
            if tr.startswith(location):
                to_rem.append(self.tracks[tr]._track)
        self.remove_tracks(to_rem)       
       
        self.serialize_libraries()
        self._dirty = True

        if self._frozen:
            self._libraries_dirty = True
        else:
            event.log_event('libraries_modified', self, None)

    def stop_scan(self):
        """
            Stops the library scan
        """
        self._scan_stopped = True
    
    def get_libraries(self):
        """
            Gets a list of all the Libraries associated with this 
            Collection

            :rtype: list of :class:`Library`
        """
        return self.libraries.values()

    def rescan_libraries(self):
        """
            Rescans all libraries associated with this Collection
        """
        if self._scanning:
            raise Exception("Collection is already being scanned")
        if len(self.libraries) == 0:
            event.log_event('scan_progress_update', self, 100)
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
        if not scan_interval: 
            scan_interval = 1

        for library in self.libraries.values():
            event.add_callback(self._progress_update, 'tracks_scanned',
                library)
            library.rescan(notify_interval=scan_interval)
            event.remove_callback(self._progress_update, 'tracks_scanned',
                library)
            self._running_total_count += self._running_count
            if self._scan_stopped: 
                break
        else: # didnt break
            try:
                self.save_to_location()
            except AttributeError:
                traceback.print_exc()

        event.log_event('scan_progress_update', self, 100)

        self._running_total_count = 0
        self._running_count = 0
        self._scanning = False

    def _progress_update(self, type, library, count):
        """
            Called when a progress update should be emitted while scanning
            tracks
        """
        self._running_count = count
        count = count + self._running_total_count

        if self.file_count == 0:
            event.log_event('scan_progress_update', self, 100)

        try:
            event.log_event('scan_progress_update', self,
                int((float(count) / float(self.file_count)) * 100))
        except ZeroDivisionError:
            pass

    def serialize_libraries(self):
        """
            Save information about libraries

            Called whenever the library's settings are changed
        """
        _serial_libraries = []
        for k, v in self.libraries.iteritems():
            l = {}
            l['location'] = v.location
            l['realtime'] = v.realtime
            l['scan_interval'] = v.scan_interval
            _serial_libraries.append(l)
        return _serial_libraries

    def unserialize_libraries(self, _serial_libraries):
        """
            restores libraries from their serialized state.

            Should only be called once, from the constructor.
        """
        for l in _serial_libraries:
            self.add_library( Library( l['location'],
                        l['realtime'], l['scan_interval'] ))

    _serial_libraries = property(serialize_libraries, unserialize_libraries)

    def close(self):
        """
            close the collection. does any work like saving to disk,
            closing network connections, etc.
        """
        #TODO: make close() part of trackdb
        collections.remove(self)

    def delete_tracks(self, tracks):
        for tr in tracks:
            for prefix, lib in self.libraries.iteritems():
                if tr['__loc'].startswith('file://%s'%prefix):
                    lib.delete(tr['__loc'])


class Library(object):
    """
        Scans and watches a folder for tracks, and adds them to
        a Collection.

        :param location: the directory this library will scan
        :type location: string
        :param collection: the Collection to associate with
        :type collection: :class:`Collection`

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
        """
        self.location = location
        self.scan_interval = scan_interval
        self.scan_id = 0
        self.scanning = False
        self.realtime = False
        try:
            self.set_realtime(realtime)
        except PyInotifyNotSupportedException:
            logger.warning("PyInotify not installed or not supported. " +
                "Not watching library: %s" % location)
        except:
            common.log_exception()

        self.collection = None
        self.set_rescan_interval(scan_interval)

    def set_location(self, location):
        """
            Changes the location of this Library

            :param location: the new location to use
            :type location: string
        """
        self.location = location

    def get_location(self):
        """
            Gets the current location associated with this Library

            :return: the current location
            :rtype: string
        """
        return self.location

    def set_collection(self, collection):

        self.collection = collection

    def _scan_locations(self, locations):
        """
            Scans locations for tracks and adds them to the collection

            :param locations: a list of locations to check
        """
        db = self.collection
        for fullpath in locations:
            tr = db.get_track_by_loc(fullpath)
            if tr:
                # check to see if we need to scan this track
                mtime = os.path.getmtime(fullpath)
                if unicode(mtime) == tr['__modified']:
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

            :param locations: the paths to remove
        """
        for loc in locations:
            try:
                track = self.collection.tracks[loc]
            except KeyError:    
                traceback.print_exc()
                continue

            self.collection.remove(track)

    def _walk(self, location):
        """
            Compatibility wrapper for Python 2.5
        """
        try:
            return os.walk(self.location, followlinks=True)
        except TypeError:
            return os.walk(self.location)

    def _count_files(self):
        """
            Counts the number of files present in this directory
        """
        return 0

        count = 0
        for folder in self._walk(self.location):
            if self.collection:
                if self.collection._scan_stopped: 
                    return
            count += len(folder[2])

        return count

    def _check_compilation(self, ccheck, compilations, tr):
        """
            This is the hacky way to test to see if a particular track is a
            part of a compilation.

            Basically, if there is more than one track in a directory that has
            the same album but different artist, we assume that it's part of a
            compilation.

            :param ccheck: dictionary for internal use
            :param compilations: if a compilation is found, it'll be appended
                to this list
            :param tr: the track to check
        """
        # check for compilations
        if not settings.get_option('collection/file_based_compilations', True):
            return 
        try:
            basedir = metadata.j(tr['__basedir'])
            album = metadata.j(tr['album'])
            artist = metadata.j(tr['artist'])
        except UnicodeDecodeError: #TODO: figure out why this happens
            logger.warning("Encoding error, skipping compilation check")
            return
        if not basedir or not album or not artist: return
        album = album.lower()
        artist = artist.lower()
        try:
            if not basedir in ccheck:
                ccheck[basedir] = {}

            if not album in ccheck[basedir]:
                ccheck[basedir][album] = []
        except TypeError:
            traceback.print_exc()
            return

        if ccheck[basedir][album] and not \
            artist in ccheck[basedir][album]:
            if not (basedir, album) in compilations:
                compilations.append((basedir, album))
                logger.info("Compilation %(album)s detected in %(dir)s" % 
                        {'album':album, 'dir':basedir})

        ccheck[basedir][album].append(artist)

    def rescan(self, notify_interval=None):
        """
            Rescan the associated folder and add the contained files
            to the Collection
        """
        if self.collection is None:
            return True

        if self.scanning: 
            return 

        logger.info("Scanning library: %s" % self.location)
        self.scanning = True
        formats = metadata.formats.keys()
        db = self.collection

        totalcount = 0
        count = 0

        from collections import deque

        queue = deque()
        queue.append(self.location)

        while len(queue) > 0:
            dirloc = queue.pop()
            dir = gio.File(dirloc)

            dirtracks = deque()
            compilations = []
            ccheck = {}

            for fileinfo in dir.enumerate_children("standard::type," 
                    "standard::is-symlink,standard::name," 
                    "standard::symlink-target,time::modified"):
                type = fileinfo.get_file_type()
                fil = dir.get_child_for_display_name(fileinfo.get_name())
                uri = fil.get_uri()
                if fileinfo.get_is_symlink():
                    target = fileinfo.get_symlink_target()
                    if not "://" in target and not os.path.isabs(target):
                        logger.warning("Relative symlinks are not "
                                "supported, skipping %s."%uri)
                        continue
                    fil2 = gio.File(target)
                    # already in the collection, we'll get it anyway
                    if fil2.has_prefix(dir):
                        continue
                if type == gio.FILE_TYPE_DIRECTORY:
                    queue.append(uri)
                elif type == gio.FILE_TYPE_REGULAR:
                    path = fil.get_path()
                    if not path:
                        # not a locally-accessible file
                        continue
                    try:
                        trmtime = db.get_track_attr(path, '__modified')
                    except TypeError:
                        pass
                    except:
                        common.log_exception(log=logger)
                    else:
                        mtime = fileinfo.get_modification_time()
                        if mtime <= trmtime:
                            continue

                    tr = db.get_track_by_loc(path)
                    if tr:
                        tr.read_tags()
                    else:
                        tr = track.Track(path)
                        if tr._scan_valid == True:
                            tr['__date_added'] = time.time()
                            db.add(tr)
                    if dirtracks is not None:
                        dirtracks.append(tr)
                        # do this so that if we have, say, a 4000-song folder
                        # we dont get bogged down trying to keep track of them
                        # for compilation detection. Most albums have far fewer
                        # than 100 tracks anyway, so it is unlikely that this
                        # restriction will affect the heuristic's accuracy
                        if len(dirtracks) > 100:
                            logger.info("Too many files, skipping "
                                    "compilation detection heuristic.")
                            dirtracks = None

                    self._check_compilation(ccheck, compilations, tr)

            for (basedir, album) in compilations:
                base = basedir.replace('"', '\\"')
                alb = album.replace('"', '\\"')
                items = [ tr for tr in dirtracks if \
                        tr['__basedir'] == base and \
                        # FIXME: this is ugly
                        alb in u"".join(tr['album']) ]
                for item in items:
                    item['__compilation'] = (basedir, album)

        removals = deque()
        location = self.location
        if "://" not in location:
            location = u"file://" + location

        for k, tr in db.tracks.iteritems():
            tr = tr._track
            loc = tr.get_loc_for_io()
            if not loc: 
                continue
            try:
                if not loc.startswith(location):
                    continue
            except UnicodeDecodeError:
                common.log_exception(log=logger)
                continue

            if not os.path.exists(loc.replace('file://', '')):
                removals.append(tr)
       
        for tr in removals:
            logger.debug(u"Removing %s"%unicode(tr))
            db.remove(tr)

    def is_realtime(self):
        """
            :return: True if this is library is being watched
        """
        return self.realtime

    def set_realtime(self, realtime):
        """
            Set to True if you want this library to be monitored

            :raises PyInotifyNotSupportedException: The collection is not set
                to realtime or :mod:`pyinotify` is not available
        """
        pass # TODO: reimplement with gio.FileMonitor

    def get_rescan_interval(self):
        """
            :return: the scan interval in seconds
        """
        return self.scan_interval

    def set_rescan_interval(self, interval):
        """
            Sets the scan interval in seconds.  If the interval is 0 seconds,
            the scan interval is stopped

            :param interval: scan interval in seconds
            :type interval: int
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

    def add(self, loc, move=False):
        """
            Copies (or moves) a file into the library and adds it to the 
            collection
        """
        if not loc.startswith("file://"):
            return
        loc = loc[7:]
        print self.location

        newloc = os.path.join(self.location, os.path.basename(loc))
        if move:
            shutil.move(loc, newloc)
        else:
            shutil.copy(loc, newloc)
        tr = track.Track(newloc)
        if tr._scan_valid == True:
            self.collection.add(tr)

    def delete(self, loc):
        """
            Deletes a file from the disk

            .. warning::
               This permanently deletes the file from the hard disk.
        """
        tr = self.collection.get_track_by_loc(loc)
        if tr:
            self.collection.remove(tr)
            path = common.local_file_from_url(tr.get_loc_for_io())
            try:
                os.unlink(path)
            except OSError: # file not found?
                traceback.print_exc()
                pass
            except:
                common.log_exception(logger)

    # the below are not essential for 0.3.0, should be implemented only 
    # if time allows for it

    def set_layout(self, layout, default="Unknown"):
        pass

    def organize(self):
        pass

    def keep_organized(self, bool):
        pass

    def get_freespace(self):
        pass

    def get_totalspace(self):
        pass

    def get_usedspace(self):
        pass

    def get_usedspace_percent(self):
        pass


class TransferQueue(object):

    def __init__(self, library):
        self.library = library
        self.queue = []
        self.current_pos = -1
        self.transferring = False
        self._stop = False

    def enqueue(self, tracks):
        self.queue.extend(tracks)

    def dequeue(self, tracks):
        if self.transferring:
            # FIXME: use a proper exception, and make this only error on
            # tracks that have already been transferred
            raise Exception, "Cannot remove tracks while transferring"

        for t in tracks:
            try:
                self.queue.remove(t)
            except ValueError:
                pass

    def transfer(self):
        """
            Tranfer the queued tracks to the library.

            This is NOT asynchronous
        """
        self.transferring = True
        self.current_pos += 1
        try:
            while self.current_pos + 1 < len(self.queue) and not self._stop:
                track = self.queue[self.current_pos]
                loc = track.get_loc()
                self.library.add(loc)

                # TODO: make this be based on filesize not count
                progress = self.current_pos * 100 / len(self.queue)
                print progress
                event.log_event('track_transfer_progress', self, progress)

                self.current_pos += 1
        finally:
            self.transferring = False
            self.current_pos = -1
            self._stop = False
            event.log_event('track_transfer_progress', self, 100)

    def cancel(self):
        """
            Cancel the current transfer
        """
        # TODO: make this stop mid-file as well?
        self._stop = True


# vim: et sts=4 sw=4

