
import _scrobbler as scrobbler
from xl import common, event
import logging, time, md5

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
            Connects evens to the player object
        """
        self.start_time = 0
        self.time_started = 0
        self.connected = False
        self.submission_queue = []
        self.get_options('','','plugin/lastfm/user')
        event.set_event_callback(self.get_options, 'option_set')


    def get_options(self, type, sm, option):
        if option not in ['plugin/lastfm/user', 'plugin/lastfm/password',
                'plugin/lastfm/submit' ]:
            return
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
        if self.connected:
            event.remove_callback(self.on_play, 'playback_start')
            event.remove_callback(self.on_stop, 'playback_end')
            self.connected = False

    @common.threaded
    def initialize(self, username, password):
        try:
            logger.info("LastFM: attempting to connect to audioscrobbler")
            password = md5.new(password).hexdigest()
            scrobbler.login(username, password)
        except:
            common.log_exception()
            return
       
        logger.info("LastFM: Connected to audioscrobbler")

        event.set_event_callback(self.on_play, 'playback_start')
        event.set_event_callback(self.on_stop, 'playback_end')
        self.connected = True
        

    @common.threaded
    def now_playing(self, track):
        logger.info("Attempting to submit now playing information...")
        scrobbler.now_playing(track['artist'], track['title'], track['album'],
            track.get_duration(), track.get_track())

    def on_play(self, type, player, track):
        self.time_started = track['playcount']
        if self.time_started == "":
            self.time_started = 0
        self.start_time = time.time()
        self.now_playing(track)

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


    @common.threaded
    def submit_to_scrobbler(self, track, time_started, time_played, queue=True):
        if scrobbler.SESSION_ID:
            try:
                scrobbler.submit(track['artist'], track['title'],
                    int(time_started), 'P', '', track.get_duration(), 
                    track['album'], track.get_track(), autoflush=True)
                if queue:
                    for item in self.submission_queue:
                        self.submit_to_scrobbler(item[0], item[1], item[2], False)
            except:
                common.log_exception()
                logger.warning("LastFM: Failed to submit track")
                self.submission_queue.append((track, time_started, time_played))
                return

