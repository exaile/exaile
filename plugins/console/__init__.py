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

from gi.repository import GLib
from gi.repository import Gtk

import sys, traceback
from cStringIO import StringIO
from xl.nls import gettext as _

class PyConsole(Gtk.Window):
    def __init__(self, dict):
        Gtk.Window.__init__(self)
        self.dict = dict

        self.buffer = StringIO()

        self.set_border_width(12)
        self.set_default_size(450, 250)

        vbox = Gtk.VBox(False, 12)
        self.add(vbox)

        sw = Gtk.ScrolledWindow()
        vbox.pack_start(sw, True, True, 0)
        sw.set_shadow_type(Gtk.ShadowType.IN)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS) 
        self.text_view = tv = Gtk.TextView()
        sw.add(tv)
        tv.set_editable(False)
        self.text_buffer = buff = tv.get_buffer()
        self.end_mark = buff.create_mark(None, buff.get_end_iter(), False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD)

        hbox = Gtk.HBox(False, 6)
        vbox.pack_start(hbox, False)
        label = Gtk.Label(label='>>>')
        hbox.pack_start(label, False)
        self.entry = entry = Gtk.Entry()
        hbox.pack_start(entry, True, True, 0)
        entry.connect('activate', self.entry_activated)

        entry.grab_focus()
        vbox.show_all()

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
        stdout = sys.stdout
        try:
            pycode = compile(code, '<console>', 'single')
            sys.stdout = self.buffer
            exec pycode in self.dict
        except:
            sys.stdout = stdout
            exc = traceback.format_exception(*sys.exc_info())
            del exc[1]  # Remove our function.
            result = ''.join(exc)
        else:
            sys.stdout = stdout
            result = self.buffer.getvalue()
            # Can't simply close and recreate later because help() stores and
            # reuses stdout.
            self.buffer.truncate(0) 
        result = '>>> %s\n%s' % (code, result)
        self.text_buffer.insert(self.text_buffer.get_end_iter(), result)
        # Can't use iter; won't scroll correctly.
        self.text_view.scroll_to_mark(self.end_mark, 0)
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
    PLUGIN = PyConsole({'exaile': exaile})
    PLUGIN.set_title(_("Console"))
    PLUGIN.set_transient_for(exaile.gui.main.window)
    PLUGIN.connect('destroy', console_destroyed, exaile)
    PLUGIN.present()

def console_destroyed(window, exaile):
    """Disable plugin on window destroy"""
    global PLUGIN
    if PLUGIN:
        exaile.plugins.disable_plugin(__name__)

def disable(exaile):
    global PLUGIN
    if PLUGIN:
        plugin = PLUGIN
        PLUGIN = None
        plugin.destroy()

# vi: et sts=4 sw=4 ts=4
