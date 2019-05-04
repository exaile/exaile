# winmmkeys - Adds support for multimedia keys in Win32.
# Copyright (C) 2007, 2010, 2016  Johannes Sasongko <sasongko@gmail.com>
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


class WinmmkeysPlugin:
    def enable(self, exaile):
        self.exaile = exaile

    def on_gui_loaded(self):
        try:
            self.handler = HotkeyHandler_PyHook(self.exaile)
        except ImportError:
            self.handler = HotkeyHandler_Keyboard(self.exaile)

    def disable(self, exaile):
        if hasattr(self, 'handler'):
            self.handler.disable()
            del self.handler
        del self.exaile


plugin_class = WinmmkeysPlugin


class HotkeyHandler_PyHook:
    def __init__(self, exaile):
        import pyHook
        from xl.player import PLAYER, QUEUE

        key_map = {
            'Launch_Media_Select': exaile.gui.main.window.present,
            'Media_Stop': PLAYER.stop,
            'Media_Play_Pause': PLAYER.toggle_pause,
            'Media_Next_Track': QUEUE.next,
            'Media_Prev_Track': QUEUE.prev,
        }

        def on_key_down(event):
            # NOTE: Because we capture every single key in the system, the
            # following test will fail almost 100% of the time. That's why we
            # use a very simple test that fails fast rather than a try-except
            # block.
            if event.Key in key_map:
                key_map[event.Key]()
                return False  # Indicate that we've handled the key.
            return True

        self.hook_manager = man = pyHook.HookManager()
        man.KeyDown = on_key_down
        man.HookKeyboard()

    def __del__(self):
        self.disable()

    def disable(self):
        if hasattr(self, 'hook_manager'):
            self.hook_manager.UnhookKeyboard()
            del self.hook_manager


class HotkeyHandler_Keyboard:
    def __init__(self, exaile):
        import keyboard
        from xl.player import PLAYER, QUEUE

        self.handlers = [
            # use lambda here because gi function isn't hashable
            keyboard.add_hotkey(
                'select media', lambda: exaile.gui.main.window.present()
            ),
            keyboard.add_hotkey('stop media', PLAYER.stop),
            keyboard.add_hotkey('play/pause media', PLAYER.toggle_pause),
            keyboard.add_hotkey('next track', QUEUE.next),
            keyboard.add_hotkey('previous track', QUEUE.prev),
        ]

    def __del__(self):
        self.disable()

    def disable(self):
        if hasattr(self, 'handlers'):
            import keyboard

            for handler in self.handlers:
                keyboard.remove_hotkey(handler)
            del self.handlers


# vi: et sts=4 sw=4 tw=80
