# Provides a signals-like system for sending and listening for 'events'
#
#
# Events are kind of like signals, except they may be listened for on a 
# global scale, rather than connected on a per-object basis like signals 
# are. This means that ANY object can emit ANY event, and these events may 
# be listened for by ANY object. Events may be emitted either syncronously 
# or asyncronously, the default is asyncronous.
#
# The events module also provides an idle_add() function similar to that of
# gobject's. However this should not be used for long-running tasks as they
# may block other events queued via idle_add().
#
# Events should be emitted AFTER the given event has taken place. Often the
# most appropriate spot is immediately before a return statement.

import _scrobbler as scrobbler
from xl import common, event
import gobject, logging, time, md5

logger = logging.getLogger(__name__)
exaile = None
PLUGIN = None

def enable(ex):
    """
        Enables the audioscrobbler plugin
    """
    global exaile, PLUGIN
    exaile = ex

    user = exaile.settings.get_option('plugin/lastfm/user', '')
    passwd = exaile.settings.get_option('plugin/lastfm/password', '')
    submit = exaile.settings.get_option('plugin/lastfm/submit', True)

    PLUGIN = ExaileScrobbler(exaile.player, user, passwd, submit)

def disable(exaile):
    """
        Disables the audioscrobbler plugin
    """
    global PLUGIN

    if PLUGIN:
        PLUGIN.stop()
        PLUGIN = None


def set_user(user):
    exaile.settings['plugin/lastfm/user'] = user

def get_user():
    return exaile.settings.get_option('plugin/lastfm/user', '')

def set_password(password):
    exaile.settings['plugin/lastfm/password'] = md5.new(password).hexdigest()

# no get_password function (on purpose)

def set_submit(value):
    exaile.settings['plugin/lastfm/submit'] = value

def get_submit():
    return exaile.settings.get_option('plugin/lastfm/submit', True)

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
        self.connected = False

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
            scrobbler.login(username, password)
        except:
            common.log_exception()
            return
       
        logger.info("LastFM: Connected to audioscrobbler")

        event.set_event_callback(self.on_play, 'playback_start')
        event.set_event_callback(self.on_stop, 'playback_end')
        self.connected = True
        
    def on_play(self, type, player, track):
        self.timer_id = gobject.timeout_add(1000, self.timer_update) 
        self.time_started = time.time()
        self.now_playing(track)

    @common.threaded
    def now_playing(self, track):
        logger.info("Attempting to submit now playing information...")
        scrobbler.now_playing(track['artist'], track['title'], track['album'],
            track.get_duration(), track.get_track())

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
                    int(time_started), 'P', '', track.get_duration(), track['album'],
                    track.get_track(), autoflush=True)
            except:
                common.log_exception()
                logger.warning("LastFM: Failed to submit track")
