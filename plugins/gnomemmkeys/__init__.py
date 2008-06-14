
GNOME_MMKEYS = None
EXAILE = None

from xl import common
import dbus, logging
logger = logging.getLogger(__name__)

def callback(key):
    global EXAILE
    if key in ('Play', 'PlayPause', 'Pause'):
        if EXAILE.player.is_playing(): 
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
            logger.info("Activated gnome mmkeys for gnome 2.22.x")
            return True
        except:
            # old method
            obj = bus.get_object('org.gnome.SettingsDaemon',
                '/org/gnome/SettingsDaemon')
            GNOME_MMKEYS = gnome = dbus.Interface(obj,
                'org.gnome.SettingsDaemon')
            gnome.GrabMediaPlayerKeys(self.application, 0)
            gnome.connect_to_signal('MediaPlayerKeyPressed', on_gnome_mmkey)
            logger.info("Activated gnome mmkeys for gnome 2.20.x")
            return True
    except:
        disable(exaile) #disconnect if we failed to load completely
        GNOME_MMKEYS = None
        common.log_exception(__name__)
        return False

def disable(exaile):
    global GNOME_MMKEYS
    if GNOME_MMKEYS:
        try:
            GNOME_MMKEYS.ReleaseMediaPlayerKeys("Exaile")
        except:
            common.log_exception()
            return False
    return True
