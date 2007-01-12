from xl import media, tracks, xlmisc, db, common
import os, xl, plugins, gobject

PLUGIN_NAME = "Mass Storage Driver"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r"""Mass Storage Driver for the Devices Panel"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None

class MassStorageTrack(media.DeviceTrack):
    """
        Representation of a track on a mass storage device
    """
    def __init__(self, *args):
        """
            Initializes the track
        """
        media.DeviceTrack.__init__(self, *args)

    def write_tag(self, db=None):
        pass

    def read_tag(self):
        """ 
            Reads the track
        """
        pass

class MassStorageDriver(plugins.DeviceDriver):
    name = "massstorage"

    def __init__(self):
        plugins.DeviceDriver.__init__(self)
        self.db = None
        self.exaile = APP
        self.dp = APP.device_panel

    def connect(self, panel, done_func):
        self.db = db.DBManager(":memory:")
        self.db.add_function_create(("THE_CUTTER", 1, tracks.the_cutter))
        self.db.import_sql('sql/db.sql')
        self.db.check_version('sql')
        self.db.db.commit()

        self._connect(panel, done_func)

    @common.threaded
    def _connect(self, panel, done_func):
        """
            Connects and scans the device
        """

        self.mount = self.exaile.settings.get("%s_mount" %
            plugins.name(__file__), "/home/synic/fruity")

        for item in ('PATHS', 'ALBUMS', 'ARTISTS', 'PLAYLISTS'):
            setattr(tracks, 'MASS_STORAGE_%s' % item, {})
        self.all = xl.tracks.TrackData()

        files = tracks.scan_dir(str(self.mount), exts=media.SUPPORTED_MEDIA)
        for i, loc in enumerate(files):
            tr = tracks.read_track(self.db, self.all, loc, prep='MASS_STORAGE_')
            if tr: 
                temp = MassStorageTrack(tr.loc)
                for field in ('title', 'track', '_artist',
                    'album', 'genre', 'year'):
                    setattr(temp, field, getattr(tr, field))
                self.all.append(temp)

            if float(i) % 500 == 0:
                self.db.commit()

        self.db.commit()
        print 'we have connected, and scanned %d files!' % len(files)
        gobject.idle_add(done_func, self)

    def search_tracks(self, keyword):
        songs = tracks.search_tracks(self.exaile.window, self.db, self.all,
            self.dp.keyword, None, self.dp.where)
        xlmisc.log("There were %d tracks found" % len(songs))

        print type(songs[0])
        return songs

    def disconnect(self):
        pass

def initialize():
    global PLUGIN

    PLUGIN = MassStorageDriver()
    APP.device_panel.add_driver(PLUGIN, PLUGIN_NAME)

    return True

def destroy():
    global PLUGIN

    if PLUGIN:
        APP.device_panel.remove_driver(PLUGIN)

    PLUGIN = None
