################################33
#
#
#  This is a temporary plugin for simple scrobbling while we work on core
#  development of 0.3
#
#
################################33

from lib import scrobbler
from xl import common, event
import gobject, logging, time

logger = logging.getLogger(__name__)

class ExaileScrobbler(object):
    def __init__(self, player, username, password, submit=True):
        """
            Connects evens to the player object
        """

        self.time_started = 0
        self.time_played = 0
        self.player = player
        self.timer_id = None
        self.submit = submit

        if username and password:
            self.initialize(username, password)

    @common.threaded
    def initialize(self, username, password):
        try:
            logger.info("LastFM: attempting to connect to audioscrobbler")
            scrobbler.login(username, password, hashpw=True)
        except:
            common.log_exception()
            return
       
        logger.info("LastFM: Connected to audioscrobbler")

        event.set_event_callback(self.on_play, 'playback_start')
        event.set_event_callback(self.on_stop, 'playback_end')
        
    def on_play(self, type, player, track):
        self.timer_id = gobject.timeout_add(1000, self.timer_update) 
        self.time_started = time.time()
        self.now_playing(track)

    @common.threaded
    def now_playing(self, track):
        scrobbler.now_playing(track['artist'], track['title'], track['album'],
            int(track['length']), int(track['track']))

    def on_stop(self, type, player, track):
        if not track: return
        logger.info("Stop called: %s %s" % (self.time_played,
            self.time_started))
        if self.time_played > 240 or float(self.time_played) > \
            float(track['length']) / 2.0:
            
            if self.submit and track['length'] > 30:
                self.submit_to_scrobbler(track, self.time_started,
                self.time_played)

        gobject.source_remove(self.timer_id)
        self.time_started = 0
        self.time_played = 0

    def timer_update(self, *e):
        """
            Called every second
        """
        if not self.player.is_paused() and self.time_started:
            self.time_played += 1
        return True

    @common.threaded
    def submit_to_scrobbler(self, track, time_started, time_played):
        if scrobbler.SESSION_ID:
            try:
                scrobbler.submit(track['artist'], track['title'],
                int(time_started), 'P', '', int(track['length']), track['album'],
                int(track['track']), autoflush=True)
            except:
                common.log_exception()
                logger.warning("LastFM: Failed to submit track")
