
GNOME_MMKEYS = None
EXAILE = None

from xl import common, event
import dbus, logging, traceback
logger = logging.getLogger(__name__)

def callback(key):
    global EXAILE
    if key in ('Play', 'PlayPause', 'Pause'):
        if EXAILE.player.is_playing() or EXAILE.player.is_paused(): 
            EXAILE.player.toggle_pause()
        elif key != "Pause":
            EXAILE.queue.play()
        else:
            pass
    elif key == 'Stop':
        EXAILE.player.stop()
    elif key == 'Previous':
        EXAILE.queue.prev()
    elif key == 'Next':
        EXAILE.queue.next()

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, "player_loaded")
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    global GNOME_MMKEYS, EXAILE
    EXAILE = exaile
    def on_gnome_mmkey(app, key):
        if app == "Exaile":
            callback(key)
    try:
        bus = dbus.SessionBus()
        try:
            # new method (for gnome 2.22.x)
            obj = bus.get_object('org.gnome.SettingsDaemon',
                '/org/gnome/SettingsDaemon/MediaKeys')
            GNOME_MMKEYS = gnome = dbus.Interface(obj,
                'org.gnome.SettingsDaemon.MediaKeys')
            gnome.GrabMediaPlayerKeys("Exaile", 0)
            gnome.connect_to_signal('MediaPlayerKeyPressed', on_gnome_mmkey)
            return True
        except:
            traceback.print_exc()
            # old method
            obj = bus.get_object('org.gnome.SettingsDaemon',
                '/org/gnome/SettingsDaemon')
            GNOME_MMKEYS = gnome = dbus.Interface(obj,
                'org.gnome.SettingsDaemon')
            gnome.GrabMediaPlayerKeys("Exaile", 0)
            gnome.connect_to_signal('MediaPlayerKeyPressed', on_gnome_mmkey)
            return True
    except:
        disable(exaile) #disconnect if we failed to load completely
        GNOME_MMKEYS = None
        common.log_exception(logger)
        return False

def disable(exaile):
    global GNOME_MMKEYS
    if GNOME_MMKEYS:
        try:
            GNOME_MMKEYS.ReleaseMediaPlayerKeys("Exaile")
        except:
            common.log_exception()
            GNOME_MMKEYS = None
            return False
    GNOME_MMKEYS = None
    return True
