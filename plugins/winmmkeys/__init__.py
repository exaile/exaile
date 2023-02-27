# winmmkeys - Adds support for multimedia keys on Windows
# Copyright (C) 2007, 2010, 2016, 2022  Johannes Sasongko <sasongko@gmail.com>
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
        self.handler = HotkeyHandler_Pynput(self.exaile)

    def disable(self, exaile):
        if hasattr(self, 'handler'):
            self.handler.disable()
            del self.handler
        del self.exaile


plugin_class = WinmmkeysPlugin


class HotkeyHandler_Pynput:
    def __init__(self, exaile):
        from pynput import keyboard

        from xl.player import PLAYER, QUEUE

        # https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes
        key_map = {
            0xB0: QUEUE.next,
            0xB1: QUEUE.prev,
            0xB2: PLAYER.stop,
            0xB3: PLAYER.toggle_pause,
            0xB5: exaile.gui.main.window.present,
        }

        # NOTE: This runs on every key event in the system, so it should exit as
        # fast as possible when the key or event type doesn't match.
        def on_event(msg, data):
            # WM_KEYDOWN = 0x0100
            if data.vkCode in key_map and msg == 0x0100:
                key_map[data.vkCode]()
                listener.suppress_event()

        self.listener = listener = keyboard.Listener(win32_event_filter=on_event)
        listener.start()

    def __del__(self):
        self.disable()

    def disable(self):
        if hasattr(self, 'listener'):
            self.listener.stop()
            del self.listener
