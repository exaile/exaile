# Copyright (C) 2006 Adam Olsen
#
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

import os, re, os.path, copy, traceback
import common, media, db, config, trackslist
import sys, md5, xlmisc, gobject
import thread, threading, urllib

try:    
    import DiscID, CDDB
    CDDB_AVAIL = True
except:
    CDDB_AVAIL = False

from pysqlite2 import dbapi2 as sqlite
from pysqlite2.dbapi2 import OperationalError
from media import *

class TrackData(list):
    """
        Represents a list of tracks
    """
    def __init__(self, tracks=None):
        """
            Inizializes the list
        """
        self.paths = dict()
        if tracks:
            for track in tracks:
                self.append(track)

    def append(self, track):
        """
            Adds a track to the list
        """
        if not track: return
        self.paths[track.loc] = track
        list.append(self, track)

    def for_path(self, path):
        """
            Returns the track associated with the path
        """
        if self.paths.has_key(path):
            track = self.paths[path]
            if track in self:
                return self.paths[path]

        return None

def search(exaile, all, keyword=None, custom=True):
    """
        Searches tracks for a specified pattern
    """
    if not keyword: return all

    if (keyword.lower().startswith("where ") or \
        keyword.lower().startswith("q: ")) and custom:
        return search_tracks(exaile.window, exaile.db, 
            TrackData(all), keyword, None, None)
        
    new = TrackData()

    for track in all:
        atts = ('title', 'album', 'artist')

        for attribute in atts:
            v = getattr(track, attribute)
            if v.lower().find(keyword.lower()) > -1:
                if not track in new: new.append(track)

    return new

def search_tracks(parent, db, all, keyword=None, playlist=None, w=None):
    """
        Searches the database for a specific pattern and returns the tracks
        represented by this pattern
    """
    items = []
    where = ""
    if keyword != None and w:
        w = w.replace(" WHERE ", " AND ")
        where = ' WHERE (title LIKE "%%' + keyword + \
            '%%" OR artist LIKE "%%' + keyword + \
            '%%" OR album LIKE "%%' + keyword + '%%") '

    if w == None:
        if keyword != None or playlist != None:
            if keyword != None:
                if keyword.startswith("q:") or keyword.lower().startswith("where"):
                    xlmisc.log("SQL query started")
                    where = re.sub("^(q:|where) ", "WHERE ", keyword.lower())

            if playlist != None:
                rows = db.select("SELECT path FROM playlist_items WHERE playlist=?",
                    (playlist,))

                for row in rows:
                    items.append(row[0])

                if all:
                    tracks = TrackData()
                    for item in items:
                        tracks.append(all.for_path(item))
                    return tracks
                    
        else:
            new = []
            for track in all:
                new.append(track)
            return new

    tracks = TrackData() 

    rows = []
    query = "SELECT path FROM tracks %s ORDER BY " % (where) + \
        "artist, album, track, title"
    if w != None:
        query = w
        query = re.sub("FROM (\w+) ", r"FROM \1 " + where, query)

    try:
        cur = db.db.cursor()
        cur.execute(query)
    except Exception, e:
        common.error(parent, "Query Error: " + e.args[0])
        raise e

    for row in cur:

        track = all.for_path(row[0])
        if track == None:
            pass
        else:
            if playlist != None:
                if track.loc in items:
                    tracks.append(track)
            else:
                tracks.append(track)

    cur.close() 
    return tracks

def already_added(t, added):
    """
        Checks to see if an md5 hash of the title, artist, album has already
        been added to the list of tracks
    """
    size = os.stat(t.loc).st_size
    if not t.title: t.title = ""
    if not t.album: t.album = ""
    if not t.artist: t.artist = ""
    h = "%s - %s - %s - %s" % (size, t.title, t.album, t.artist)

    if added.has_key(h): return True
    added[h] = 1
    return False

def load_tracks(db, current=None):
    """
        Loads all tracks currently stored in the database
    """
    added = dict()

    tracks = TrackData()
    count = 0
    for row in db.select("SELECT path FROM tracks WHERE blacklisted=0 ORDER"
        " BY artist, album, track, title"):
        if not os.path.isfile(row[0]): 
            continue

        t = read_track(db, current, row[0], True)

        if already_added(t, added): continue

        tracks.append(t)
        if count >= 10:
            xlmisc.finish()
            count = 0

        count += 1

    
    return tracks

def scan_dir(directory, matches, files):
    for file in os.listdir(directory):
        if os.path.isdir("%s%s%s" % (directory, os.sep, file)):
            scan_dir("%s%s%s" % (directory, os.sep, file))
        else:
            (stuff, ext) = os.path.splitext(file)
            if ext in matches:
                files.append("%s%s%s" % (directory, os.sep, file))

def count_files(directories):
    """
        Recursively counts the number of supported files in the specified
        directories
    """
    paths = []
    for dir in directories:
        dir = str(dir)
        xlmisc.log(dir)
        try:
            for root, dirs, files in os.walk(dir):
                for f in files:
                    (stuff, ext) = os.path.splitext(f)
                    if ext in media.SUPPORTED_MEDIA:
                        paths.append(os.path.join(root, f).decode("utf-8",
                            'replace'))
        except:
            pass

    return paths

def get_cddb_info(thread):
    """
        Fetches cddb info about an audio cd
    """
    (status, info) = CDDB.query(thread.disc_id)
    if status in (210, 211):
        info = info[0]
        status = 200
    if status != 200: return

    (status, info) = CDDB.read(info['category'], info['disc_id'])
    title = info['DTITLE'].split(" / ")
    for i in range(thread.disc_id[1]):
        thread.songs[i].title = info['TTITLE' + `i`].decode('iso-8859-15',
            'replace')
        thread.songs[i].album = title[1].decode('iso-8859-15', 'replace')
        thread.songs[i].artist = title[0].decode('iso-8859-15', 'replace')
        thread.songs[i].year = info['EXTD'].replace("YEAR: ", "")
        thread.songs[i].genre = info['DGENRE']

    songs = thread.exaile.tracks.songs

    gobject.idle_add(thread.exaile.tracks.set_songs, songs)

def read_audio_disc(exaile):
    """
        Reads track information from an audio CD
    """
    disc = DiscID.open()
    try:
        info = DiscID.disc_id(disc)
    except:
        common.error(exaile.window, _("Could not open audio disc"))
        return None
    minus = 0; total = 0
    thread = xlmisc.ThreadRunner(get_cddb_info)
    thread.disc_id = info
    thread.exaile = exaile

    songs = TrackData()
    for i in range(info[1]):
        length = ( info[i + 3] / 75 ) - minus
        if i + 1 == info[1]:
            length = info[i + 3] - total

        minus = info[i + 3] / 75
        song = media.CDTrack(str(i + 1), length=length)
        total += length
        song.track = i + 1
        songs.append(song)

    thread.songs = songs
    thread.start()

    return songs

def read_track(db, current, path, skipmod=False, ipod=False, adddb=True):
    """
        Reads a track, either from the database, or from it's metadata
    """
    if not os.path.isfile(path): return None
    (f, ext) = os.path.splitext(path)

    mod = os.stat(os.path.join(path)).st_mtime
    row = None
    if db:
        row = db.read_one("tracks", "path, title, artist, album, " 
            "genre, track, length, bitrate, year, modified, user_rating, "  
            "blacklisted, the_track", "path=?", (path,))

    if skipmod and not row: return None

    if (not row or row[9] != mod) and not skipmod:
        try:
            if media.FORMAT.has_key(ext.lower()):
                ttype = media.FORMAT[ext.lower()]
                tr = ttype(path)
            else:
                return None

            tr.read_tag()
            tr.user_rating = 2

            tr.read_from_db = False
            the_track = ""
            if tr.artist.lower()[:4] == "the ":
                # it's a "the" track.  strip "the " and mark it
                the_track = tr.artist[:4]
                tr.artist = tr.artist[4:]
                tr.the_track = the_track

            if db and adddb:
                db.update("tracks",
                    {
                        "path": tr.loc,
                        "title": tr.title,
                        "artist": tr._artist,
                        "album": tr.album,
                        "genre": tr.genre,
                        "track": tr.track,
                        "length": tr.duration,
                        "the_track": the_track,
                        "bitrate": tr.bitrate,
                        "blacklisted": tr.blacklisted,
                        "year": tr.year,
                        "modified": mod
                    }, "path=?", (path,), row == None)

        except:
            xlmisc.log_exception()
    elif current != None and current.for_path(path):
        return current.for_path(path)
    else:
        if ipod:
            tr = iPodTrack(row[0])
        elif media.FORMAT.has_key(ext.lower()):
            ttype = media.FORMAT[ext.lower()]
            tr = ttype(row[0])
        else:
            return None

        tr.set_info(*row)


        tr.read_from_db = True

    if not tr.title: tr.title = ""
    if not tr.album: tr.album = ""
    if not tr.artist: tr.artist = ""

    return tr

class PopulateThread(threading.Thread):
    """
        Reads all the tracks in the library and adds them to the database
    """
    running = False

    def __init__(self, exaile, db, directories, update_func, quick=False,
        delete=True, load_tree=False):
        """
            Expects an exaile instance, the location of the database file,
            the directories to search, the function to call as reading
            progresses, and whether or not this is a quick scan.
        """
        threading.Thread.__init__(self)
        self.db = db
        self.exaile = exaile
        self.directories = directories
        self.update_func = update_func
        self.done = False
        self.quick = quick
        self.delete = delete
        self.load_tree = load_tree

    def run(self):
        """
            Called when the thread is started
        """
        xlmisc.log("Running is %s" % PopulateThread.running)
        if PopulateThread.running: return
        PopulateThread.running = True

        directories = self.directories
        directories = [x.decode('utf-8', 'replace') for x in directories]
        for path in directories:
            try:
                mod = os.path.getmtime(path)
            except OSError:
                continue
            self.db.execute("REPLACE INTO directories( path, modified ) "
                "VALUES( ?, ? )", (path, mod))

        update_func = self.update_func
        gobject.idle_add(update_func, 0.001)

        paths = count_files(directories)
        total = len(paths)
        xlmisc.log("File count: %d" % total)

        db = self.db
        count = 0; commit_count = 0
        update_queue = dict()
        included = []
        added = dict()

        for loc in paths:
            try:
                modified = os.stat(loc).st_mtime
                size = os.stat(loc).st_size

                temp = self.exaile.all_songs.for_path(loc)
                
                tr = read_track(db, self.exaile.all_songs, loc)
                if not tr or tr.blacklisted: continue
                
                if not temp:
                    if not already_added(tr, added): self.exaile.all_songs.append(tr)
                elif not isinstance(temp, media.StreamTrack):
                    for field in ('title', 'track', '_artist',
                        'album', 'genre', 'year'):
                        setattr(temp, field, getattr(tr, field))
                already_added(tr, added)
                included.append(tr)

            except OperationalError:
                continue
            except OSError:
                continue
            except Exception, ex:
                xlmisc.log_exception()

            count = count + (1 * 1.0)
            commit_count += 1
            if commit_count >= 50:
                db.commit()
                commit_count = 0

            if total != 0 and (count % 3) == 0.0:
                percent = float(count / total)
                gobject.idle_add(update_func, percent)

        xlmisc.log("Count is now: %d" % count)
        if self.done: return
        db.commit()

        num = -1
        if self.quick or not self.load_tree: num = -2
        gobject.idle_add(update_func, -2) 

        if included and self.delete:
            xlmisc.log("Keeping %d track paths in the database" %
                len(included))
            where = " AND path!=".join(["\"%s\"" % track.loc for 
                track in included])
            db.execute("DELETE FROM tracks WHERE path!=%s" % where)

        PopulateThread.running = False

def populate(exaile, db, directories, update_func, quick=False, delete=True,
    load_tree=False):
    """
        Runs the populate thread
    """
    thread = PopulateThread(exaile, db, directories, update_func, quick,
        delete, load_tree)
    exaile.thread_pool.append(thread)
    thread.start()

def find_and_delete_dups(path):
    """
        Searches a path and finds duplicate files based on their md5sum
    """
    hashes = dict()
    for root, dirs, files in os.walk(path):
        for f in files:
            (stuff, ext) = os.path.splitext(f)
            if ext in media.SUPPORTED_MEDIA:
                handle = open(os.path.join(root, f), "r")
                h = md5.new(handle.read()).hexdigest()
                handle.close()
                if h in hashes:
                    xlmisc.log("\nDuplicate of '%s' found!\n" % hashes[h])

                    os.remove(os.path.join(root, f))
                print ".",
                sys.stdout.flush()
                hashes[h] = os.path.join(root, f)
