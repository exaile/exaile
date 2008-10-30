from guitest.gtktest import GtkTestCase
from guitest.utils import mainloop_handler
import pygtk, gtk, os
import xlgui
import tests.base
import logging
from xl import playlist, radio, player, cover, event, xdg

event._TESTING = True

class TestPlayer(player.BaseGSTPlayer):
    """
        Fake player.  Overrides most of the settings and playback info... the
        real GST player takes time to emit playback and stop signals.  This
        will always to it right away
    """
    def __init__(self):
        self.playing = False
        self.paused = False
        self.current = None

    def play(self, track):
        self.playing = True
        self.current = track
        event.log_event('playback_start', self, track)

    def get_volume(self):
        return 1

    def stop(self):
        self.playing = False
        self.paused = False
        current = self.current
        self.current = None
        event.log_event('playback_end', self, current)

    def pause(self):
        self.paused = True
        event.log_event('playback_pause', self, self.current)

    def unpause(self):
        self.paused = False
        event.log_event('playback_resume', self, self.current)

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
        self.covers = cover.CoverManager(self.settings, 
            '.testtemp/covers')
        self.player = TestPlayer()
        self.queue = player.PlayQueue(self.player)
        self.playlists = playlist.PlaylistManager()
        self.smart_playlists = playlist.PlaylistManager('smart_playlists')
        self.stations = playlist.PlaylistManager('radio_stations')
        self.radio = radio.RadioManager()
        self.gui = xlgui.Main(self)

    def setup_logging(self):
        console_format = "%(levelname)-8s: %(message)s"
        loglevel = logging.INFO
        logging.basicConfig(level=logging.INFO,
                format='%(asctime)s %(levelname)-8s: %(message)s (%(name)s)',
                datefmt="%m-%d %H:%M",
                filename=os.path.join(xdg.get_config_dir(), "exaile.log"),
                filemode="a")
        console = logging.StreamHandler()
        console.setLevel(loglevel)
        formatter = logging.Formatter(console_format)
        console.setFormatter(formatter)       
