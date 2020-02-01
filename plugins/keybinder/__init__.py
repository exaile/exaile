# Keybinder-based multimedia keys support
# Copyright (C) 2015  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging

import gi

from xlgui import guiutil
from xl.nls import gettext as _

gi.require_version('Keybinder', '3.0')

from gi.repository import Keybinder


LOGGER = logging.getLogger(__name__)

KEYS = [
    'XF86AudioPlay',
    'XF86AudioStop',
    'XF86AudioPrev',
    'XF86AudioNext',
    'XF86AudioPause',
    'XF86AudioMedia',
    'XF86AudioRewind',
]


class KeybinderPlugin:
    def __init__(self):
        self.__exaile = None

    def enable(self, exaile):
        broken = False
        if hasattr(Keybinder, 'supported'):
            # introduced in Keybinder-3.0 0.3.2, see
            # https://github.com/kupferlauncher/keybinder/blob/master/NEWS
            if not Keybinder.supported():
                broken = True
        elif not guiutil.platform_is_x11():
            broken = True
        if broken:
            raise Exception(
                _(
                    'Keybinder is not supported on this platform! '
                    'It is only supported on X servers.'
                )
            )
        self.__exaile = exaile

    def on_exaile_loaded(self):
        if not self.__exaile:
            return  # Plugin has been disabled in the meantime
        Keybinder.init()
        for k in KEYS:
            if not Keybinder.bind(k, on_media_key, self.__exaile):
                LOGGER.warning("Failed to set key binding using Keybinder.")
                self.__exaile.plugins.disable_plugin(__name__)
                return

    def teardown(self, exaile):
        for k in KEYS:
            Keybinder.unbind(k)

    def disable(self, exaile):
        self.teardown(exaile)
        self.__exaile = None


plugin_class = KeybinderPlugin


def start_stop_playback(PLAYER, QUEUE):
    '''Toggles pause if playing/paused, starts playback if stopped'''
    if PLAYER.is_paused() or PLAYER.is_playing():
        PLAYER.toggle_pause()
    else:
        QUEUE.play(track=QUEUE.get_current())


def on_media_key(key, exaile):
    from xl.player import PLAYER, QUEUE

    {
        'XF86AudioPlay': lambda: start_stop_playback(PLAYER, QUEUE),
        'XF86AudioStop': PLAYER.stop,
        'XF86AudioPrev': QUEUE.prev,
        'XF86AudioNext': QUEUE.next,
        'XF86AudioPause': PLAYER.toggle_pause,
        'XF86AudioMedia': exaile.gui.main.window.present,
        'XF86AudioRewind': lambda: PLAYER.seek(0),
    }[key]()
