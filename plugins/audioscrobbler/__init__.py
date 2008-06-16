
import _scrobbler as scrobbler
from xl import common, event,xdg
import gobject, logging, time, md5, pickle, os

from xl.settings import SettingsManager
settings = SettingsManager.settings

logger = logging.getLogger(__name__)

SCROBBLER = None

def enable(exaile):
    """
        Enables the audioscrobbler plugin
    """
    global SCROBBLER

    SCROBBLER = ExaileScrobbler()

def disable(exaile):
    """
        Disables the audioscrobbler plugin
    """
    global SCROBBLER

    if SCROBBLER:
        SCROBBLER.stop()
        SCROBBLER = None


class ExaileScrobbler(object):
    def __init__(self):
        """
            Connects events to the player object, loads settings and cache
        """
        self.start_time = 0
        self.time_started = 0
        self.connected = False
        self.cachefile = os.path.join(xdg.get_data_dirs()[0], 
                "audioscrobbler.cache")
        self.get_options('','','plugin/lastfm/cache_size')
        self.get_options('','','plugin/lastfm/user')
        self.load_cache()
        event.add_callback(self.get_options, 'option_set')
        event.add_callback(self._save_cache_cb, 'quit_application')

    def get_options(self, type, sm, option):
        if option == 'plugin/lastfm/cache_size':
            self.set_cache_size(
                    settings.get_option('plugin/lastfm/cache_size', 100), False)
            return
        
        if option in ['plugin/lastfm/user', 'plugin/lastfm/password',
                'plugin/lastfm/submit' ]:
            username = settings.get_option('plugin/lastfm/user', '')
            password = settings.get_option('plugin/lastfm/password', '')
            self.submit = settings.get_option('plugin/lastfm/submit', True)

            if not self.connected:
                if username and password:
                    self.initialize(username, password)

    def stop(self):
        """
            Stops submitting
        """
        logger.info("LastFM: Stopping submissions")
        if self.connected:
            event.remove_callback(self.on_play, 'playback_start')
            event.remove_callback(self.on_stop, 'playback_end')
            self.connected = False
            self.save_cache()

    @common.threaded
    def initialize(self, username, password):
        try:
            logger.info("LastFM: attempting to connect to audioscrobbler")
            scrobbler.login(username, password, hashpw=True)
        except:
            common.log_exception()
            return
       
        logger.info("LastFM: Connected to audioscrobbler")

        event.add_callback(self.on_play, 'playback_start')
        event.add_callback(self.on_stop, 'playback_end')
        self.connected = True
        

    @common.threaded
    def now_playing(self, player, track):
        # wait 5 seconds before now playing to allow for skipping
        time.sleep(5)
        if player.current != track: return

        logger.info("Attempting to submit now playing information...")
        scrobbler.now_playing(track['artist'], track['title'], track['album'],
            track.get_duration(), track.get_track())

    def on_play(self, type, player, track):

        self.time_started = track['playcount']
        if self.time_started == "":
            self.time_started = 0
        self.start_time = time.time()

        self.now_playing(player, track)

    def on_stop(self, type, player, track):
        if not track: 
            return
        playtime = track['playtime'] - self.time_started
        logger.info("Stop called: %s" % playtime)
        if playtime > 240 or playtime > float(track['length']) / 2.0:
            if self.submit and track['length'] > 30:
                self.submit_to_scrobbler(track, self.start_time, playtime)

        self.time_started = 0
        self.start_time = 0

    def set_cache_size(self, size, save=True):
        scrobbler.MAX_CACHE = size
        if save:
            settings.set_option("plugin/lastfm/cache_size", size)

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
        if scrobbler.SESSION_ID:
            try:
                scrobbler.submit(track['artist'], track['title'],
                    int(time_started), 'P', '', track.get_duration(), 
                    track['album'], track.get_track(), autoflush=True)
            except:
                common.log_exception()
                logger.warning("LastFM: Failed to submit track")
