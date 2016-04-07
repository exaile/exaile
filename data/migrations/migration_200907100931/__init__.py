import os
from xl import xdg, trax, collection
from xl import settings, common
from xl.playlist import PlaylistManager, Playlist
from six.moves.configparser import SafeConfigParser
import oldexailelib, olddb
import logging
import time
import collections

logger = logging.getLogger(__name__)

_SETTINGS_MAP = (
    (int,   'ui',       'mainw_x',          'gui/mainw_x', None),
    (int,   'ui',       'mainw_y',          'gui/mainw_y', None),
    (int,   'ui',       'mainw_width',      'gui/mainw_width',  None),
    (int,   'ui',       'mainw_height',     'gui/mainw_height',  None),
    (list,  'ui',       'track_columns',    'gui/columns', '_set_track_columns'),
    (bool,  'ui',       'use_tray',         'gui/use_tray', None),
    (int,   'ui',       'mainw_sash_pos',   'gui/mainw_sash_pos', None),
    (bool,  'DEFAULT',  'shuffle',          'playback/shuffle', None),
    (bool,  'DEFAULT',  'repeat',           'playback/repeat', None),
    (bool,  'DEFAULT',  'dynamic',          'playback/dynamic', None),
    (str,   'lastfm',   'user',             'plugin/ascrobbler/user', None),
    (str,   'lastfm',   'pass',             'plugin/ascrobbler/password', '_set_lastfm_password'),
    (bool,  'lastfm',   'submit',           'plugin/ascrobbler/submit', None),
    (float, 'osd',      'opacity',          'osd/opacity', None),
    (int,   'osd',      'w',                'osd/w', None),
    (int,   'osd',      'h',                'osd/h', None),
    (int,   'osd',      'x',                'osd/x', None),
    (int,   'osd',      'y',                'osd/y', None),
    (str,   'osd',      'text_font',        'osd/text_font', None),
    (bool,  'osd',      'enabled',          'osd/enabled', None),
    (str,   'osd',      'text_color',       'osd/text_color', None),
    (str,   'osd',      'bgcolor',          'osd/bg_color', None),
    (str,   'ui',       'tab_placement',    'gui/tab_placement', '_set_tab_placement'),
)

class MigrationException(Exception): pass

def migration_needed():
    # check for the presence of old exaile settings
    for file in ('~/.exaile/music.db', '~/.exaile/settings.ini'):
        if not os.path.exists(os.path.expanduser(file)): 
            logger.debug("%s did not exist, old exaile version not detected" % file)
            return False

    # check for Exaile 0.3.x+ settings and music database
    if os.path.exists(os.path.join(xdg.get_data_dirs()[0], 'music.db')):
        logger.debug("Found a newer version of the database, no migration needed")
        return False

    if os.path.exists(os.path.join(xdg.get_config_dir(), 'settings.ini')):
        logger.debug("Found a newer version of the settings " \
            "file, no migration needed")
        return False

    if not olddb.SQLITE_AVAIL:
        raise MigrationException("Sqlite not available.  "
            "Cannot migrate 0.2.14 settings")

    # if we've gotten this far, check for sqlite, but if it's not available,
    # throw a migration exception

    # open up the old database, and make sure it's at least the version used
    # in 0.2.14
    db = olddb.DBManager(os.path.expanduser('~/.exaile/music.db'), False) 
    cur = db.cursor()
    row = db.read_one('db_version', 'version', '1=1', tuple())
    db.close()

    if row[0] != 4:
        logger.debug("Cannot migrate from db_version %d" % row[0])
        return False

    return True

def _migrate_old_tracks(oldsettings, db, ntdb):
    libraries = eval(oldsettings.get('DEFAULT', 'search_paths'))

    oldtracks = oldexailelib.load_tracks(db)
    rating_steps = 5 # old dbs are hardcoded to 5 steps

    for library in libraries:
        ntdb.add_library(collection.Library(library))

    newtracks = []
    for oldtrack in oldtracks:
        # we shouldn't be checking os.path.isfile() here, since if it is a radio link, it will not be migrated
        newtrack = trax.Track(uri=oldtrack.loc, scan=False)

        if oldtrack._rating: # filter '' and 0
            oldtrack._rating = max(0, oldtrack._rating)
            oldtrack._rating = min(oldtrack._rating, rating_steps)
            newtrack.set_tag_raw('__rating', float((100.0*oldtrack._rating)/rating_steps))

        db_map = {'artist': 'artist',
                'album': 'album',
                'track': 'tracknumber',
                'genre': 'genre',
                'date': 'date',
                'title': 'title',
                'playcount': '__playcount'}

        newtrack.set_tag_raw('__length', int(getattr(oldtrack, 'duration')))

        # Apparently, there is a bug in exaile 0.2.xx that dumps the time as hh:mm:YYYY, rather than hh:mm:ss. This is a workaround, that takes the seconds == 0, since this information is lost b/c of the bug
        temp_time = oldtrack.time_added;

        try:
            newtrack.set_tag_raw('__date_added', time.mktime(time.strptime(temp_time[0:len(temp_time)-5],'%Y-%m-%d %H:%M')))
        except ValueError:
             try:
                 newtrack.set_tag_raw('__date_added', time.mktime(time.strptime(temp_time[0:len(temp_time)-3],'%Y-%m-%d %H:%M')))
             except ValueError:
                     pass

        for item in db_map.keys():
            newtrack.set_tag_raw(db_map[item], getattr(oldtrack, item))

        newtrack._dirty = True
        newtracks.append(newtrack)

    ntdb.add_tracks(newtracks)
    ntdb.save_to_location()

def _set_tab_placement(section, oldsetting, oldsettings):
    val = int(oldsettings.get(section, oldsetting))
    
    if val == 0: return 'top'
    elif val == 1: return 'left'
    elif val == 2: return 'right'
    elif val == 3: return 'bottom'

def _set_track_columns(section, oldsetting, oldsettings):
    items = eval(oldsettings.get(section, oldsetting)) 
    
    newitems = []
    for item in items:
        if item == 'track':
            newitems.append('tracknumber')
        else:
            newitems.append(item)

    return newitems

def _crypt(string, key):
    """
        Encrypt/Decrypt a string'
    """

    kidx = 0
    cryptstr = ""

    for x in range(len(string)):
        cryptstr = cryptstr + \
            chr(ord(string[x]) ^ ord(key[kidx]))

        kidx = (kidx + 1) % len(key)

    return cryptstr

XOR_KEY = "You're not drunk if you can lie on the floor without hanging on"
def _set_lastfm_password(section, oldsetting, oldsettings):
    string = oldsettings.get(section, oldsetting)

    new = ''
    vals = string.split()
    for val in vals:
        try:
            new += chr(int(val, 16))
        except ValueError:
            continue

    return _crypt(new, XOR_KEY)

def _migrate_old_settings(oldsettings):
    for (t, section, oldsetting, newspot, func) in _SETTINGS_MAP:
        value = None
        try:
            if func in globals():
                func = globals()[func]
                if isinstance(func, collections.Callable):
                    value = func(section, oldsetting, oldsettings)

            if not value: value = oldsettings.get(section, oldsetting)
            value = t(value)
            settings.set_option(newspot, value)
        except:
            common.log_exception(log=logger)

def _migrate_playlists(db, newdb, playlists):
    p_rows = db.select('SELECT name, id, type FROM playlists ORDER BY name') 

    for p_row in p_rows:
        if p_row[2]: continue

        pl = Playlist(p_row[0])
   
        rows = db.select('SELECT paths.name FROM playlist_items,paths WHERE '
            'playlist_items.path=paths.id AND playlist=?', (p_row[1],))

        locs = ['file://' + row[0] for row in rows]
        tracks = newdb.get_tracks_by_locs(locs)

        if tracks:
            pl.add_tracks(tracks, add_duplicates=False)
            playlists.save_playlist(pl)

    playlists.save_order()

def migrate(force=False):
    if not force and not migration_needed():
        logger.debug("Will not migrate and overwrite data.")
        return
    logger.info("Migrating data from 0.2.14....")

    # allow force to overwrite the new db
    newdbpath = os.path.join(xdg.get_data_dirs()[0], 'music.db')
    if os.path.exists(newdbpath):
        os.remove(newdbpath)

    oldsettings = SafeConfigParser()
    oldsettings.read(os.path.expanduser('~/.exaile/settings.ini'))

    if not olddb.SQLITE_AVAIL:
        raise MigrationException("Sqlite is not available. "
            "Unable to migrate 0.2.14 settings")

    # old database
    db = olddb.DBManager(os.path.expanduser('~/.exaile/music.db'), False) 

    # new database
    newdb = collection.Collection('tdb', os.path.join(xdg.get_data_dirs()[0],
        'music.db'))

    _migrate_old_tracks(oldsettings, db, newdb)
    _migrate_old_settings(oldsettings)
    settings.MANAGER.save()

    playlists = PlaylistManager()

    _migrate_playlists(db, newdb, playlists)

    logger.info("Migration complete!")

if __name__ == '__main__':
    migrate()
