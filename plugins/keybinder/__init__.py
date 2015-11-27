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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Keybinder

KEYS = [
    'XF86AudioPlay',
    'XF86AudioStop',
    'XF86AudioPrev',
    'XF86AudioNext',
    'XF86AudioPause',
    'XF86AudioMedia',
    'XF86AudioRewind',
]

initialized = False


def enable(exaile):
    if exaile.loading:
        import xl.event
        xl.event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def _enable(eventname, exaile, eventdata):
    global initialized
    if not initialized:
        Keybinder.init()
        initialized = True
    for k in KEYS:
        Keybinder.bind(k, on_media_key, exaile)


def disable(exaile):
    for k in KEYS:
        Keybinder.unbind(k)


def on_media_key(key, exaile):
    from xl.player import PLAYER, QUEUE
    {
        'XF86AudioPlay': PLAYER.toggle_pause,
        'XF86AudioStop': PLAYER.stop,
        'XF86AudioPrev': QUEUE.prev,
        'XF86AudioNext': QUEUE.next,
        'XF86AudioPause': PLAYER.toggle_pause,
        'XF86AudioMedia': exaile.gui.main.window.present,
        'XF86AudioRewind': lambda: PLAYER.seek(0),
    }[key]()
