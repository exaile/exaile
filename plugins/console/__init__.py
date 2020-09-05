# Python console plugin for Exaile media player
# Copyright (C) 2007 Johannes Sasongko
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Simple console plugin

For better development experience, please use the IPython console plugin. This
plugin is meant as a basic alternative without the extra dependencies.
"""

from gi.repository import Gtk

from contextlib import redirect_stdout
from io import StringIO
import os
import sys
import traceback


class PyConsole:
    def __init__(self, dict, exaile):
        self.dict = dict
        self.buffer = StringIO()

        ui = Gtk.Builder()
        ui.add_from_file(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'console_window.ui'
            )
        )

        self.window = ui.get_object('simple_console_window')
        self.close_handler = self.window.connect(
            'delete-event', console_destroyed, exaile
        )

        self.text_view = tv = ui.get_object('console_output')

        self.text_buffer = buff = tv.get_buffer()
        self.end_mark = buff.create_mark(None, buff.get_end_iter(), False)

        self.entry = entry = ui.get_object('console_input')
        entry.connect('activate', self.entry_activated)
        entry.grab_focus()

    def entry_activated(self, entry, user_data=None):
        """
        Called when the user presses Return on the GtkEntry.
        """
        self.execute(entry.get_text())
        entry.select_region(0, -1)

    def execute(self, code):
        """
        Executes some Python code.
        """
        buffer = self.buffer
        try:
            pycode = compile(code, '<console>', 'single')
            with redirect_stdout(buffer):
                exec(pycode, self.dict)
        except Exception:
            exc = traceback.format_exception(*sys.exc_info())
            del exc[1]  # Remove our function.
            result = ''.join(exc)
        else:
            result = buffer.getvalue()
            # Can't simply close and recreate later because help() stores and
            # reuses stdout.
            buffer.seek(0)
            buffer.truncate(0)
        result = '>>> %s\n%s' % (code, result)
        self.text_buffer.insert(self.text_buffer.get_end_iter(), result)
        # Can't use iter; won't scroll correctly.
        self.text_view.scroll_to_mark(self.end_mark, 0, False, 0.5, 0.5)
        self.entry.grab_focus()


PLUGIN = None


def enable(exaile):
    if exaile.loading:
        from xl import event

        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)


def _enable(eventname, exaile, eventdata):
    global PLUGIN
    PLUGIN = PyConsole({'exaile': exaile}, exaile)
    PLUGIN.window.set_transient_for(exaile.gui.main.window)
    PLUGIN.window.present()


def console_destroyed(window, event, exaile):
    """Disable plugin on window destroy"""
    global PLUGIN
    if PLUGIN:
        exaile.plugins.disable_plugin(__name__)


def disable(exaile):
    global PLUGIN
    if PLUGIN:
        PLUGIN.window.disconnect(PLUGIN.close_handler)
        PLUGIN.window.destroy()
        PLUGIN = None


# vi: et sts=4 sw=4 ts=4
