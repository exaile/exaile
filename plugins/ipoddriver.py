import gtk, plugins, gobject, re, time
from xl import tracks, db, media, common, xlmisc
import xl, os

PLUGIN_NAME = "iPod Device Driver"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.2'
PLUGIN_DESCRIPTION = r"""iPod Driver for the Devices Panel"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None

try:
    import gpod
    IPOD_AVAIL = True
except ImportError:
    IPOD_AVAIL = False

class iPodTrack(media.DeviceTrack):

    def __init__(self, *args):
        """
            Initializes the track
        """
        plugins.DriverTrack.__init__(self, *args)

        self.itrack = None
        self.type = 'ipod'

    def ipod_track(self):
        """
            Returns the ipod track
        """
        return self.itrack

    def write_tag(self, db=None):
        """
            Not implemented quite yet
        """
        if self.itrack:
            t = self.itrack
            t.artist = str(self.artist)
            t.album = str(self.album)
            t.genre = str(self.genre)
            t.title = str(self.title)

            try:
                t.year = int(self.year)
            except ValueError:
                pass

            try:
                t.track_nr = int(self.track)
            except ValueError:
                pass

        if db:
            plugins.DriverTrack.write_tag(self, db)


    def read_tag(self):
        """
            Reads the track
        """
        pass

    def get_rating(self): 
        """
            Gets the rating
        """
        # this is an approximate conversion from the iPod's rating system
        return "* " * int(self._rating / 14) 
    
    def set_rating(self, rating):
        """
            Sets the rating
        """
        self._rating = rating

    rating = property(get_rating, set_rating)

class iPodPlaylist(object):
    """
        Container for iPod playlist
    """
    def __init__(self, playlist, root=False):
        """
            requires an gpod playlist object
        """
        self.playlist = playlist
        self.name = playlist.name
        self.root = root

    def __str__(self):
        """
            Returns the playlist name
        """
        return self.playlist.name

class iPodDriver(plugins.DeviceDriver):
    name = 'ipod'
    def __init__(self):
        plugins.DeviceDriver.__init__(self)
        self.itdb = None
        self.db = None
        self.exaile = APP
        self.dp = APP.device_panel

        self.ipod_image = xlmisc.get_icon('gnome-dev-ipod')
        self.iplaylist_image = xlmisc.get_icon('gtk-justify-center')

    def get_initial_root(self, model):
        """
            Adds new nodes and returns the one tracks should be added to
        """
        if not self.lists: return None
        root_playlist = self.lists[0]
        other = self.lists[1:]

        self.iroot = model.append(None, [self.ipod_image, root_playlist])
        for playlist in other:
            item = model.append(self.iroot, [self.iplaylist_image, playlist])
        path = model.get_path(self.iroot)
        gobject.timeout_add(600, self.dp.tree.expand_row, path, False)
        return model.append(None, [self.ipod_image, "iPod Collection"])

    def put_item(self, item):
        """
            Transfers a track to the ipod
        """
        (song, target) = (item.track, item.target)
        print "Transferring %s %s" % (song, type(song))
        if self.find_dup(song): return
        if not isinstance(song, media.MP3Track): return
        track = self.get_ipod_track(song)
        cover = self.get_cover_location(song)
        track.itdb = self.itdb
        if cover:
            gpod.itdb_track_set_thumbnails(track, cover)

        loc = str(song.loc)

        gpod.itdb_cp_track_to_ipod(track, loc, None)
        gpod.itdb_track_add(self.itdb, track, -1)
        mpl = gpod.itdb_playlist_mpl(self.itdb)
        gpod.itdb_playlist_add_track(mpl, track, -1)

        if isinstance(target, iPodPlaylist):
            gpod.itdb_playlist_add_track(target.playlist, track, -1)

    def find_dup(self, song):
        """
            Finds if the song is already on the ipod
        """
        for s in self.all:
            if s.title != song.title:
                continue
            elif s.artist != song.artist:
                continue
            elif s.album != song.album:
                continue
            elif s.duration != song.duration:
                continue
            elif s.title != song.title:
                continue
            else:
                return True

        return False

    def get_ipod_track(self, song):
        """
            Returns an ipod compatable track
        """
        track = gpod.itdb_track_new()
        track.title = str(song.title)
        track.album = str(song.album)
        track.artist = str(song.artist)
        track.tracklen = song.duration * 1000

        try: track.bitrate = int(song._bitrate)
        except: pass
        try: track.track_nr = int(song.track)
        except: pass
        try: track.year = int(song.year)
        except: pass

        if song.type != 'podcast':
            info = os.stat(song.loc)
        else:
            info = os.stat(re.sub(r'^device_\w+://', '', song.download_path))
        track.size = info[6]

        track.time_added = int(time.time()) + 2082844800
        track.time_modified = track.time_added
        track.genre = str(song.genre)

        return track 

    def transfer_done(self):
        gpod.itdb_write(self.itdb, None)

    def get_cover_location(self, track):
        """
            Gets the location of the album art
        """
        db = APP.db
        
        rows = db.select("SELECT image FROM tracks,albums,paths WHERE paths.name=?"
            " AND paths.id=tracks.path AND albums.id=tracks.album",
            (track.loc,))
        if not rows: return None
        row = rows[0]
        if not row or row[0] == '': return None
        return "%s%scovers%s%s" % (APP.get_settings_dir(), os.sep,
            os.sep, str(row[0]))

    @common.threaded
    def connect(self, panel, done_func):
        """
            Connects to the ipod
        """
        self.mount = self.exaile.settings.get("%s_ipod_mount" % 
            plugins.name(__file__), "/media/ipod")

        self.mount = str(self.mount)
        self.itdb = gpod.itdb_parse(self.mount, None)
        self.db = db.DBManager(":memory:")
        self.db.add_function_create(('THE_CUTTER', 1, tracks.the_cutter))
        self.db.import_sql("sql/db.sql")
        self.db.check_version("sql")
        self.lists = []
        self.list_dict = dict()
        self.all = xl.tracks.TrackData()

        if not self.itdb: 
            self.connected = False
            self.all = tracks.TrackData()
            common.error(self.exaile.window, "Error connecting to "
                "iPod")
            return False

        for item in ('PATHS', 'ALBUMS', 'ARTISTS', 'PLAYLISTS'):
            setattr(tracks, 'IPOD_%s' % item, {})
        self.all = xl.tracks.TrackData()
        ## clear out ipod information from database
        self.db.execute("DELETE FROM tracks WHERE type=1")

        for playlist in gpod.sw_get_playlists(self.itdb):
            if playlist.type == 1:
                self.lists.insert(0, iPodPlaylist(playlist, True))
            else:
                self.lists.append(iPodPlaylist(playlist))
            self.list_dict[playlist.name] = playlist
            playlist_id = tracks.get_column_id(self.db, 'PLAYLISTS', 'name',
                playlist.name, 'IPOD_')
            for track in gpod.sw_get_playlist_tracks(playlist):
                loc = self.mount + track.ipod_path.replace(":", "/")
                path_id = tracks.get_column_id(self.db, 'paths', 'name', loc,
                    'IPOD_')
                self.db.execute("REPLACE INTO playlist_items(playlist, path) "
                    "VALUES( ?, ? )", (playlist_id, path_id))       

        left = []
        for i in range(10):
            left.append('?')
        left = ", ".join(left)
        for track in gpod.sw_get_tracks(self.itdb):
            loc = self.mount + track.ipod_path.replace(":", "/")
            try:
                loc = unicode(loc)

                path_id = tracks.get_column_id(self.db, 'paths', 'name', loc,
                    prep='IPOD_')
                artist_id = tracks.get_column_id(self.db, 'artists', 'name', 
                    track.artist, prep='IPOD_')
                album_id = tracks.get_album_id(self.db, artist_id, track.album, prep='IPOD_')

                self.db.execute("INSERT INTO tracks(path, " \
                    "title, artist, album, track, length," \
                    "bitrate, genre, year, user_rating ) " \
                    "VALUES( %s ) " % left, 

                    (path_id,
                    unicode(track.title),
                    unicode(artist_id),
                    unicode(album_id),
                    unicode(track.track_nr),
                    unicode(track.tracklen / 1000),
                    unicode(track.bitrate),
                    unicode(track.genre),
                    unicode(track.year),
                    unicode(track.rating)))

                itrack = track
                track = xl.tracks.read_track(self.db, None, loc, True, True, 
                    track_type=iPodTrack)
                   
                if not track: continue
                track.itrack = itrack
                
                self.all.append(track)

            except UnicodeDecodeError:
                traceback.print_exc()
                continue

        self.db.commit()
        self.connected = True
        gobject.idle_add(done_func, self)

    def search_tracks(self, keyword):
        return tracks.search_tracks(self.exaile.window, self.db, self.all,
            self.dp.keyword, None, self.dp.where)
    
    def disconnect(self):
        pass

def initialize():
    global PLUGIN

    if not IPOD_AVAIL:
        common.error(APP.window, "python-gpod could not be loaded. iPod"
            " device driver will not be available")
        return False
    PLUGIN = iPodDriver()
    APP.device_panel.add_driver(PLUGIN, PLUGIN_NAME)

    return True

def destroy():
    global PLUGIN

    if PLUGIN:
        APP.device_panel.remove_driver(PLUGIN)

    PLUGIN = None
