# winmmkeys - Adds support for multimedia keys in Win32.
# Copyright (C) 2007, 2010  Johannes Sasongko <sasongko@gmail.com>
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

key_map = None
hook_manager = None

def on_key_down(event):
    # NOTE: Because we capture every single key in the system, the following
    # test will fail almost 100% of the time. That's why we use a very simple
    # test that fails fast rather than a try-except block.
    if event.Key in key_map:
        key_map[event.Key]()
        return False  # Swallow key.
    else:
        return True

def enable(exaile):
    if exaile.loading:
        import xl.event
        xl.event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, eventdata):
    global key_map, hook_manager
    from xl.player import PLAYER, QUEUE

    key_map = {
        'Launch_Media_Select': exaile.gui.main.window.present,
        'Media_Prev_Track': QUEUE.prev,
        'Media_Play_Pause': PLAYER.toggle_pause,
        'Media_Stop': PLAYER.stop,
        'Media_Next_Track': QUEUE.__next__,
    }

    import pyHook
    hook_manager = pyHook.HookManager()
    hook_manager.KeyDown = on_key_down
    hook_manager.HookKeyboard()

def disable(exaile):
    global key_map, hook_manager
    if hook_manager:
        hook_manager.UnhookKeyboard()
    key_map = hook_manager = None

# vi: et sts=4 sw=4 tw=80
