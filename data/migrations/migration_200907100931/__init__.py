import os
import traceback
from xl import xdg, track, collection
from xl import settings
from ConfigParser import SafeConfigParser
import urlparse
import olddb, oldexailelib

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

def migration_needed():
    # check for the presence of old exaile settings
    for file in ('~/.exaile/music.db', '~/.exaile/settings.ini'):
        if not os.path.exists(os.path.expanduser(file)): 
            print "%s did not exist, old exaile version not detected" % file
            return False

    # check for Exaile 0.3.x+ settings and music database
    if os.path.exists(os.path.join(xdg.get_data_dirs()[0], 'music.db')):
        print "Found a newer version of the database, no migration needed"
        return False

    if os.path.exists(os.path.join(xdg.get_config_dir(), 'settings.ini')):
        print "Found a newer version of the settings " \
            "file, no migration needed"
        return False

    # open up the old database, and make sure it's at least the version used
    # in 0.2.14
    db = olddb.DBManager(os.path.expanduser('~/.exaile/music.db'), False) 
    cur = db.cursor()
    row = db.read_one('db_version', 'version', '1=1', tuple())
    db.close()

    if row[0] != 4:
        print "Cannot migrate from db_version %d" % row[0]
        return False

    return True

def _migrate_old_tracks(oldsettings, db, ntdb):
    libraries = eval(oldsettings.get('DEFAULT', 'search_paths'))

    oldtracks = oldexailelib.load_tracks(db)
    rating_steps = settings.get_option('miscellaneous/rating_steps', 5)

    for library in libraries:
        ntdb.add_library(collection.Library(library))

    newtracks = []
    for oldtrack in oldtracks:
        newtrack = track.Track()

        if int(oldtrack._rating) > 0: 
            newtrack['rating'] = float((100.0*oldtrack._rating)/rating_steps) 

        newtrack.set_loc(oldtrack.loc)

        for item in ('bitrate', 'artist', 'album', 'track', 'genre', 'date',
            'track', 'title', 'duration'):
            if item == 'duration':
                newtrack['length'] = oldtrack._len
            elif item == 'track':
                newtrack['tracknumber'] = oldtrack.track
            else:
                newtrack[item] = getattr(oldtrack, item)

        newtrack._scan_valid = True
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
            if globals().has_key(func):
                func = globals()[func]
                if callable(func):
                    value = func(section, oldsetting, oldsettings)

            if not value: value = oldsettings.get(section, oldsetting)
            value = t(value)
            settings.set_option(newspot, value)
        except:
            traceback.print_exc()

def migrate():
    if not migration_needed():
        print "Will not migrate and overwrite data."
        return

    oldsettings = SafeConfigParser()
    oldsettings.read(os.path.expanduser('~/.exaile/settings.ini'))

    # old database
    db = olddb.DBManager(os.path.expanduser('~/.exaile/music.db'), False) 

    # new database
    newdb = collection.Collection('tdb', os.path.join(xdg.get_data_dirs()[0],
        'music.db'))

    _migrate_old_tracks(oldsettings, db, newdb)
    _migrate_old_settings(oldsettings)
    settings._SETTINGSMANAGER.save()

if __name__ == '__main__':
    migrate()
