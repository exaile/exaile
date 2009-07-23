import _scrobbler as scrobbler
import asprefs
from xl import common, event, xdg, metadata, settings
from xl.nls import gettext as _
import gobject, logging, time, pickle, os, gtk

logger = logging.getLogger(__name__)

SCROBBLER = None

def enable(exaile):
    """
        Enables the audioscrobbler plugin
    """
    global SCROBBLER

    SCROBBLER = ExaileScrobbler(exaile)
    
    if exaile.loading:
        event.add_callback(__enb, 'exaile_loaded')
    else:
        __enb(None, exaile, None)

def __enb(eventname, exaile, nothing):
    gobject.idle_add(_enable, exaile)

def _enable(exaile):
    SCROBBLER.exaile_menu = exaile.gui.xml.get_widget('tools_menu')
    SCROBBLER.get_options('','','plugin/ascrobbler/menu_check')
    
def disable(exaile):
    """
        Disables the audioscrobbler plugin
    """
    global SCROBBLER
    
    if SCROBBLER:
        SCROBBLER.stop()
        SCROBBLER = None

def get_prefs_pane():
    return asprefs

class ExaileScrobbler(object):
    def __init__(self, exaile):
        """
            Connects events to the player object, loads settings and cache
        """
        self.connected = False
        self.connecting = False
        self.use_menu = False
        self.exaile_menu = None
        self.menu_entry = None
        self.exaile = exaile
        self.menu_conn = 0
        self.cachefile = os.path.join(xdg.get_data_dirs()[0], 
                "audioscrobbler.cache")
        self.get_options('','','plugin/ascrobbler/cache_size')
        self.get_options('','','plugin/ascrobbler/user')
        self.load_cache()
        event.add_callback(self.get_options, 'option_set')
        event.add_callback(self._save_cache_cb, 'quit_application')

    def get_options(self, type, sm, option):
        if option == 'plugin/ascrobbler/cache_size':
            self.set_cache_size(
                    settings.get_option('plugin/ascrobbler/cache_size', 100), False)
            return

        if option in ['plugin/ascrobbler/user', 'plugin/ascrobbler/password',
                'plugin/ascrobbler/submit']:
            username = settings.get_option('plugin/ascrobbler/user', '')
            password = settings.get_option('plugin/ascrobbler/password', '')
            server = settings.get_option('plugin/ascrobbler/url',
                'http://post.audioscrobbler.com/')
            self.submit = settings.get_option('plugin/ascrobbler/submit', True)
            
            if self.use_menu and self.menu_entry:
                self.menu_entry.set_active(self.submit)
                
            if (not self.connecting and not self.connected) and self.submit:
                if username and password:
                    self.connecting = True
                    self.initialize(username, password, server)
            
        if option == 'plugin/ascrobbler/menu_check':
            self.use_menu = settings.get_option('plugin/ascrobbler/menu_check', False)
            if self.use_menu and not self.menu_entry:
                self.setup_menu()
            elif self.menu_entry and not self.use_menu:
                self.remove_menu()
    
    def setup_menu(self):
        self.menu_agr = self.exaile.gui.main.accel_group
        
        self.menu_sep = gtk.SeparatorMenuItem()
        
        self.menu_entry = gtk.CheckMenuItem(_('Enable audioscrobbling'), self.menu_agr)
        self.menu_entry.set_active(self.submit)
        
        self.exaile_menu.append(self.menu_sep)
        self.exaile_menu.append(self.menu_entry)
        
        self.menu_conn = self.menu_entry.connect('toggled', self._menu_entry_toggled)
        key, mod = gtk.accelerator_parse("<Control>L")
        self.menu_entry.add_accelerator("activate", self.menu_agr, key, 
            mod, gtk.ACCEL_VISIBLE)
        
        self.menu_entry.show_all()
        self.menu_sep.show_all()
    
    def remove_menu(self):
        self.menu_entry.disconnect(self.menu_conn)
        
        self.menu_entry.hide()
        self.menu_entry.destroy()
        self.menu_entry = None
        
        self.menu_sep.hide()
        self.menu_sep.destroy()
        self.menu_sep = None
        
    def _menu_entry_toggled(self, data):
        settings.set_option('plugin/ascrobbler/submit', self.menu_entry.get_active())
    
    def stop(self):
        """
            Stops submitting
        """
        logger.info("AS: Stopping submissions")
        if self.use_menu:
            self.remove_menu()
        if self.connected:
            event.remove_callback(self.on_play, 'playback_track_start')
            event.remove_callback(self.on_stop, 'playback_track_end')
            self.connected = False
            self.save_cache()

    @common.threaded
    def initialize(self, username, password, server):
        try:
            logger.info("AS: attempting to connect to audioscrobbler")
            scrobbler.login(username, password, hashpw=False, post_url=server)
        except:
            try:
                scrobbler.login(username, password, hashpw=True, post_url=server)
            except:
                self.connecting = False
                common.log_exception()
                return
           
        logger.info("AS: Connected to audioscrobbler")

        event.add_callback(self.on_play, 'playback_track_start')
        event.add_callback(self.on_stop, 'playback_track_end')
        self.connected = True
        self.connecting = False

    @common.threaded
    def now_playing(self, player, track):
        # wait 5 seconds before now playing to allow for skipping
        time.sleep(5)
        if player.current != track: 
            return

        logger.info("Attempting to submit now playing information...")
        scrobbler.now_playing(
            metadata.j(track['artist']), metadata.j(track['title']), 
            metadata.j(track['album']), 
            track.get_duration(), track.get_track())

    def on_play(self, type, player, track):
        track['__audioscrobbler_playtime'] = track['playtime']
        track['__audioscrobbler_starttime'] = time.time()

        if track.is_local():
            self.now_playing(player, track)

    def on_stop(self, type, player, track):
        if not track or not track.is_local() \
           or track['playtime'] is None: 
            return
        playtime = (track['playtime'] or 0) - \
                (track['__audioscrobbler_playtime'] or 0)
        if playtime > 240 or playtime > float(track['__length']) / 2.0:
            if self.submit and track['__length'] > 30:
                self.submit_to_scrobbler(track, 
                    track['__audioscrobbler_starttime'], playtime)

        track['__audioscrobbler_starttime'] = None
        track['__audioscrobbler_playtime'] = None

    def set_cache_size(self, size, save=True):
        scrobbler.MAX_CACHE = size
        if save:
            settings.set_option("plugin/ascrobbler/cache_size", size)

    def _save_cache_cb(self, a, b, c):
        self.save_cache()

    def save_cache(self):
        cache = scrobbler.SUBMIT_CACHE
        f = open(self.cachefile,'w')
        pickle.dump(cache, f)
        f.close()

    def load_cache(self):
        try:
            f = open(self.cachefile,'r')
            cache = pickle.load(f)
            f.close()
            scrobbler.SUBMIT_CACHE = cache
        except:
            pass

    @common.threaded
    def submit_to_scrobbler(self, track, time_started, time_played):
        if scrobbler.SESSION_ID and track and time_started and time_played:
            try:
                scrobbler.submit(
                    metadata.j(track['artist']), 
                    metadata.j(track['title']),
                    int(time_started), 'P', '', track.get_duration(), 
                    metadata.j(track['album']), track.get_track(), autoflush=True)
            except:
                common.log_exception()
                logger.warning("AS: Failed to submit track")
