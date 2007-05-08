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

import os, re, os.path, copy, traceback, gc
import common, media, db, config, trackslist
import sys, md5, xlmisc, gobject, random
import thread, threading, urllib, audioscrobbler
import dbusinterface, xl.db, time
from db import DBOperationalError
from gettext import gettext as _

try:    
    import DiscID, CDDB
    CDDB_AVAIL = True
except:
    CDDB_AVAIL = False

import media

def the_cutter(field):
    """
        Cuts "THE " off of the beginning of any field for better sorting
    """
    field = field.lower()
    if field.find("the ") == 0:
        return field.replace("the ", "", 1)
    else:
        return field

def get_suggested_songs(exaile, db, song, s, count, done_func):
    """
        Finds and returns 10 suggested songs from last.fm
    """
    new = s[:]
    random.shuffle(new)
    new.insert(0, song)
    new = new[:5]
    all = []

    for song in new:
        if not song.artist: continue
        if song.type == 'stream': continue
        xlmisc.log("Fetching suggested tracks for %s" % song.artist)
        try:
            lastfm = audioscrobbler.AudioScrobblerQuery(artist=song.artist)
            artists = []
            for artist in lastfm.similar():
                artists.append(artist.name)

            random.shuffle(artists)
            all.extend(artists)
           
        except audioscrobbler.AudioScrobblerError:
            pass
        except:
            xlmisc.log_exception()
        if len(all) >= 100: break

    gobject.idle_add(done_func, all, count)    

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
    args = []
    where = ""
    if keyword != None and w:
        regex = re.compile("\s+WHERE\s", re.DOTALL)
        w = regex.sub(" AND ", w)
        tokens = keyword.lower().split(' ')

        anditems = []
        check_fields = ('title', 'artists.name', 'albums.name')
        for token in tokens:
            if not token: continue
            oritems = []
            for field in check_fields:
                oritems.append("%s LIKE \"%%%s%%\"" % (field, token))
            anditems.append('(' + ' OR '.join(oritems) + ')')

        anditems = ' AND '.join(anditems)

        where = 'WHERE (%s) AND ' \
            '(paths.id=tracks.path AND artists.id=tracks.artist AND ' \
            'albums.id=tracks.album)' % anditems

    if w == None:
        if keyword != None or playlist != None:

            if playlist != None:
                rows = db.select("""
                    SELECT 
                        paths.name 
                    FROM playlist_items,paths,playlists
                    WHERE 
                        playlists.name=? AND 
                        playlist_items.playlist=playlists.id AND 
                    paths.id=playlist_items.path
                """, (playlist,))

                for row in rows:
                    items.append(row[0])

                if all:
                    tracks = TrackData()
                    for item in items:
                        tracks.append(all.for_path(item))
                    return tracks
                    
        else:
            new = TrackData() 
            for track in all:
                new.append(track)
            return new

    tracks = TrackData() 

    rows = []
    query = """
        SELECT 
            paths.name 
        FROM tracks,paths,artists,albums %s 
        ORDER BY 
            LOWER(artists.name), 
            LOWER(albums.name), 
            disc_id,
            track, 
            title
        """ % where

    if w != None:
        query = w
        if keyword:
            regex = re.compile("FROM\s+(.*?)\s+AND", re.DOTALL)
            query = regex.sub(r"FROM \1 %s AND" % where, query)


    try:
        cur = db.realcursor()
        cur.execute(query)
    except Exception, e:
        xlmisc.log(query)
        common.error(parent, _("Query Error: %s") % str(e))
        raise e

    for row in cur.fetchall():
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
        Checks to see if an md5 hash of the title, artist, album and path 
        has already been added to the list of tracks
    """

    if dbusinterface.options.testing: return False
    if not t.title: t.title = ""
    if not t.album: t.album = ""
    if not t.artist: t.artist = ""
    h = "%s - %s - %s - %s" % (t.title, t.album, t.artist, t.loc)

    if added.has_key(h): return True
    added[h] = 1
    return False

def load_tracks(db, current=None):
    """
        Loads all tracks currently stored in the database
    """
    global ALBUMS

    items = ('PATHS', 'ARTISTS', 'RADIO', 'PLAYLISTS')
    for item in items:
        globals()[item] = dict()
    ALBUMS = {}
    added = dict()

    tracks = TrackData()
    for row in db.select("""
        SELECT 
            paths.name, 
            title, 
            artists.name, 
            albums.name, 
            disc_id,
            tracks.genre, 
            track, 
            length, 
            bitrate, 
            year, 
            modified, 
            user_rating, 
            blacklisted, 
            time_added
        FROM tracks, paths, artists, albums 
        WHERE 
            (
                paths.id=tracks.path AND 
                artists.id = tracks.artist AND 
                albums.id = tracks.album
            ) AND 
            blacklisted=0 
        ORDER BY 
            THE_CUTTER(artists.name), 
            LOWER(albums.name), 
            disc_id,
            track, 
            title
        """):

        t = media.Track(*row)
        path, ext = os.path.splitext(row[0].lower().encode('utf-8'))
        t.type = ext.replace('.', '')

        if already_added(t, added): continue

        tracks.append(t)
    cur = db.cursor(new=True)

    for item in items:
        cur.execute("SELECT id, name FROM %s" % item.lower())
        while True:
            try:
                row = cur.fetchone()
                if not row: break
                globals()[item][row[1]] = row[0]
            except: 
                xlmisc.log_file_and_line()
                xlmisc.log_exception()

    cur.execute("SELECT artist, name, id FROM albums")
    while True:
        try:
            row = cur.fetchone()
            if not row: break
            ALBUMS["%d - %s" % (row[0], row[1])] = row[2]
        except:
            xlmisc.log_exception()

    cur.close()
    db._close_thread()
    return tracks

def scan_dir(dir, files=None, exts=()):
    """
        Scans a directory recursively
    """
    if files is None: 
        files = []

    try:
        to_scan = os.listdir(dir)
    except OSError:
        return files

    for file in to_scan:
        try:
            file = os.path.join(dir, file)
        except UnicodeDecodeError:
            xlmisc.log("Error decoding filename %s" % file)
            continue
        except:
            xlmisc.log_exception()
            continue

        try:
            if os.path.isdir(file) and not \
                os.path.islink(file):
                    scan_dir(file, files, exts)
        except:
            xlmisc.log("Error scanning %s" % file)
            traceback.print_exc()
       
        try:
            (stuff, ext) = os.path.splitext(file)
            if ext.lower() in exts and not file in files:
                files.append(file)
        except:
            traceback.print_exc()
            continue

    return files     

def count_files(directories):
    """
        Recursively counts the number of supported files in the specified
        directories
    """
    paths = []
    for dir in directories:
        paths.extend(scan_dir(dir, exts=media.SUPPORTED_MEDIA))

    return paths

@common.threaded
def get_cddb_info(songs, disc_info, exaile):
    """
        Fetches cddb info about an audio cd
    """
    (status, info) = CDDB.query(disc_info)
    if status in (210, 211):
        info = info[0]
        status = 200
    if status != 200: return

    (status, info) = CDDB.read(info['category'], info['disc_id'])
    title = info['DTITLE'].split(" / ")
    for i in range(disc_info[1]):
        songs[i].title = info['TTITLE' + `i`].decode('iso-8859-15',
            'replace')
        songs[i].album = title[1].decode('iso-8859-15', 'replace')
        songs[i].artist = title[0].decode('iso-8859-15', 'replace')
        songs[i].year = info['EXTD'].replace("YEAR: ", "")
        songs[i].genre = info['DGENRE']

    songs = exaile.tracks.songs

    gobject.idle_add(exaile.tracks.set_songs, songs)

def read_audio_disc(exaile):
    """
        Reads track information from an audio CD
    """
    device = exaile.settings.get_str('cd_device', '/dev/cdrom')
    disc = DiscID.open(device)
    try:
        info = DiscID.disc_id(disc)
    except:
        common.error(exaile.window, _("Could not open audio disc"))
        return None
    minus = 0; total = 0

    songs = TrackData()
    for i in range(info[1]):
        length = ( info[i + 3] / 75 ) - minus
        if i + 1 == info[1]:
            length = info[i + 3] - total

        minus = info[i + 3] / 75
        tracknum = i + 1
        song = media.Track("cdda://%d" % tracknum, _("Track %d") % tracknum,
            track=tracknum, length=length)
        song.type = 'cd'
        total += length
        songs.append(song)

    get_cddb_info(songs, info, exaile)

    return songs

@common.synchronized
def get_column_id(db, table, col, value, prep=''):
    """
        Gets a column id for inserting the specific col into the specific
        table
    """
    if not value: value = ''
    cols = globals()['%s%s' % (prep, table.upper())]
    if cols.has_key(value):
        return cols[value]

    vals = cols.values()
    vals.sort()
    if not vals:
        index = 1
    else:
        index = vals[len(vals) - 1]
        index += 1
    cols[value] = index

    db.execute("INSERT INTO %s( id, %s ) VALUES( ?, ? )" % (table, col), 
        (index, value,))
    return index

@common.synchronized
def get_album_id(db, artist_id, album, prep=''):
    cols = globals()['%sALBUMS' % prep]
    if cols.has_key("%d - %s" % (artist_id, album)):
        return cols["%d - %s" % (artist_id, album)]

    vals = cols.values()
    vals.sort()
    if not vals:
        index = 1
    else:
        index = vals[len(vals) - 1]
        index += 1

    cols["%d - %s" % (artist_id, album)] = index
    if not album: album = ''
    db.execute("INSERT INTO albums( id, artist, name ) VALUES( ?, ?, ?)",
        (index, artist_id, album))
    return index

def read_track(db, all, path):
    if not os.path.isfile(path): return None
    if all:
        tr = all.for_path(path)
    else: tr = None
   
    # if the track is not already read, try the database
    if not tr and db:
        tr = read_track_from_db(db, path)

    # if it's not in the database, read it from the filesystem
    if not tr:
        tr = media.read_from_path(path)

    return tr

def read_track_from_db(db, path):
    """
        Reads a track from the database
    """
    rows = db.select("""
        SELECT 
            paths.name, 
            title, 
            artists.name, 
            albums.name, 
            disc_id,
            tracks.genre,
            track, 
            length, 
            bitrate, 
            year, 
            modified, 
            user_rating, 
            blacklisted, 
            time_added,
            encoding
        FROM tracks,paths,artists,albums 
        WHERE 
            (
                paths.id=tracks.path AND 
                artists.id=tracks.artist AND 
                albums.id=tracks.album
            ) 
            AND paths.name=? 
        LIMIT 1
        """, (path,))

    if rows:
        tr = media.Track(*rows[0])
    else: 
        tr = None

    if tr:
        (path, ext) = os.path.splitext(tr.loc.lower())
        tr.type = ext.replace('.', '')
    
    return tr

def save_track_to_db(db, tr, new=False, prep=''):
    if new:
        tr.time_added = time.strftime("%Y-%m-%d %H:%M:%Y", 
            time.localtime())

    path_id = get_column_id(db, 'paths', 'name', tr.loc,
        prep=prep)
    artist_id = get_column_id(db, 'artists', 'name', tr.artist, prep=prep)
    album_id = get_album_id(db, artist_id, tr.album,
        prep=prep)

    db.update("tracks",
        {
            "path": path_id,
            "title": tr.title,
            "artist": artist_id,
            "album": album_id,
            "disc_id": tr.disc_id,
            "genre": tr.genre,
            "track": tr.track,
            "length": tr.duration,
            "bitrate": tr._bitrate,
            "blacklisted": tr.blacklisted,
            "year": tr.year,
            "modified": tr.modified,
            "time_added": tr.time_added,
            "encoding": tr.encoding
        }, "path=?", (path_id,), new)

class PopulateThread(threading.Thread):
    """
        Reads all the tracks in the library and adds them to the database
    """
    running = False
    stopped = False

    def __init__(self, exaile, db, directories, update_func, 
        delete=True, load_tree=False, done_func=None):
        """
            Expects an exaile instance, the location of the database file,
            the directories to search, the function to call as reading
            progresses, and whether or not this is a quick scan.
        """
        threading.Thread.__init__(self)
        self.db = db
        self.setDaemon(True)
        self.exaile = exaile
        self.directories = directories
        self.update_func = update_func
        self.done = False
        self.delete = delete
        self.load_tree = load_tree
        self.done_func = done_func

    def run(self):
        """
            Called when the thread is started
        """
        xlmisc.log("Running is %s" % PopulateThread.running)
        if PopulateThread.running: return
        PopulateThread.running = True
        PopulateThread.stopped = False

        directories = self.directories
        db = self.db
        cur = self.db.cursor()

        update_func = self.update_func
        gobject.idle_add(update_func, 0.001)

        paths = count_files(directories)
        total = len(paths)
        xlmisc.log("File count: %d" % total)

        db.execute("UPDATE tracks SET included=0")
        count = 0
        update_queue = dict()
        added = dict()

        # found_tracks will hold /all/ tracks found in this import, regardless
        # of if they have already been previously imported or not.  They will
        # be handed to the "done_func"
        self.found_tracks = []

        for loc in paths:
            if PopulateThread.stopped:
                self.stop()
                return
            try:
                tr = self.exaile.all_songs.for_path(loc)
               
                if not tr:
                    tr = read_track_from_db(db, unicode(loc, xlmisc.get_default_encoding()))

                modified = os.stat(loc).st_mtime
                if not tr or tr.modified != modified:
                    if not tr: new = True
                    else: new = False
                    tr = media.read_from_path(loc)
                    if not tr: continue
                    save_track_to_db(db, tr, new)

                if tr:
                    path_id = get_column_id(db, 'paths', 'name', unicode(loc, xlmisc.get_default_encoding()))
                    db.execute("UPDATE tracks SET included=1 WHERE path=?",
                        (path_id,))
                if not tr or tr.blacklisted: continue
                
                if not self.exaile.all_songs.for_path(loc):
                    if not already_added(tr, added): self.exaile.all_songs.append(tr)
                self.found_tracks.append(tr)
                already_added(tr, added)

            except DBOperationalError:
                xlmisc.log_exception()
                continue
            except OSError:
                xlmisc.log_exception()
                continue
            except Exception, ex:
                xlmisc.log_exception()

            count = count + (1 * 1.0)

            if total != 0 and (count % 3) == 0.0:
                percent = float(count / total)
                gobject.idle_add(update_func, percent)

            # periodical commit
            if count % 1500 == 0:
                xlmisc.log("Committing 1500 scanned tracks...")
                db.commit()

        if PopulateThread.stopped:
            self.stop()
            return
        self.stop()
        xlmisc.log("Count is now: %d" % count)
        if self.done: return

        if self.delete:
            db.execute("DELETE FROM tracks WHERE included=0")
        db.commit()

    def stop(self):
        """
            Stops the thread
        """
        self.db._close_thread()
        self.db.commit()

        num = -2
        if not self.load_tree: num = -1
        tracks = self.found_tracks
        if PopulateThread.stopped:
            tracks = None
        gobject.idle_add(self.update_func, num, tracks, 
            self.done_func) 
        PopulateThread.stopped = False
        PopulateThread.running = False

def populate(exaile, db, directories, update_func, delete=True,
    load_tree=False, done_func=None):
    """
        Runs the populate thread
    """
    thread = PopulateThread(exaile, db, directories, update_func, 
        delete, load_tree, done_func)
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
