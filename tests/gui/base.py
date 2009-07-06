from guitest.gtktest import GtkTestCase
from guitest.utils import mainloop_handler
import pygtk, gtk, os
import xlgui
import tests.base
import logging
from xl import playlist, radio, player, cover, event, xdg
from xl.player import engine_unified, queue

event._TESTING = True

class TestStream():
    def __init__(self, track):
        self.track = track

    def get_current(self):
        return self.track

class TestPlayer(engine_unified.UnifiedPlayer):
    """
        Fake player.  Overrides most of the settings and playback info... the
        real GST player takes time to emit playback and stop signals.  This
        will always to it right away
    """
    def __init__(self):
        self.playing = False
        self.paused = False
        self.streams=[None, None]
        self._current_stream = 0

    def play(self, track):
        self.playing = True
        self.streams[0] = TestStream(track)
        event.log_event('playback_player_start', self, track)
        event.log_event('playback_track_start', self, track)

    def get_volume(self):
        return 1

    def stop(self):
        self.playing = False
        self.paused = False
        current = self.current
        self.streams[0] = None
        event.log_event('playback_player_end', self, current)
        event.log_event('playback_track_end', self, current)

    def pause(self):
        self.paused = True
        event.log_event('playback_player_pause', self, self.current)

    def unpause(self):
        self.paused = False
        event.log_event('playback_player_resume', self, self.current)

    def toggle_pause(self):
        if self.is_paused():
            self.unpause()
        else:
            self.pause()

        event.log_event('playback_toggle_pause', self, self.current)

    def is_paused(self):
        return self.paused

    def is_playing(self):
        if self.paused: return False
        if not self.playing: return False
        return True

class FakeRadio(object):
    stations = {}

class BaseTestCase(GtkTestCase, 
    tests.base.BaseTestCase):
    
    def setUp(self):
        GtkTestCase.setUp(self)
        self.setup_logging()
        self.radio = FakeRadio()
        tests.base.BaseTestCase.setUp(self)
        self.covers = cover.CoverManager('.testtemp/covers')
        self.player = TestPlayer()
        self.queue = queue.PlayQueue(self.player)
        self.playlists = playlist.PlaylistManager()
        self.smart_playlists = playlist.PlaylistManager('smart_playlists')
        self.stations = playlist.PlaylistManager('radio_stations')
        self.radio = radio.RadioManager()
        self.gui = xlgui.Main(self)

    def setup_logging(self):
        console_format = "%(levelname)-8s: %(message)s"
#        loglevel = logging.DEBUG
#        loglevel = logging.INFO
        loglevel = logging.ERROR
        logging.basicConfig(level=loglevel, format=console_format)
#        event.EVENT_MANAGER.use_logger = True
