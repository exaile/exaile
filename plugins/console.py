#!/usr/bin/env python

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

import sys
import traceback
from cStringIO import StringIO
from gettext import gettext as _
import gtk

PLUGIN_NAME = "Python Console"
PLUGIN_VERSION = 0.1
PLUGIN_AUTHORS = ["Johannes Sasongko <sasongko@gmail.com>"]
PLUGIN_DESCRIPTION = r"""Provides a Python console that can be used to
manipulate Exaile."""

PLUGIN_ICON = None
PLUGIN_ENABLED = False

class PyConsole(gtk.Window):
    def __init__(self, dict):
        gtk.Window.__init__(self)
        self.dict = dict

        self.buffer = StringIO()

        self.set_title(_("Python Console - Exaile"))
        self.set_border_width(12)
        self.set_default_size(450, 250)

        vbox = gtk.VBox(False, 12)
        self.add(vbox)

        sw = gtk.ScrolledWindow()
        vbox.pack_start(sw)
        sw.set_shadow_type(gtk.SHADOW_IN)
        self.text_view = tv = gtk.TextView()
        sw.add(tv)
        tv.set_editable(False)
        tv.set_wrap_mode = gtk.WRAP_CHAR
        self.text_buffer = buff = tv.get_buffer()
        self.end_mark = buff.create_mark(None, buff.get_end_iter(), False)

        hbox = gtk.HBox(False, 6)
        vbox.pack_start(hbox, False)
        label = gtk.Label('>>>')
        hbox.pack_start(label, False)
        self.entry = entry = gtk.Entry()
        hbox.pack_start(entry)
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
        try:
            pycode = compile(code, '<console>', 'single')
            stdout = sys.stdout
            sys.stdout = self.buffer
            exec pycode in self.dict
            sys.stdout = stdout
            result = self.buffer.getvalue()
            # Can't simply close and recreate later because help() stores and
            # reuses stdout.
            self.buffer.truncate(0) 
        except:
            exc = traceback.format_exception(*sys.exc_info())
            del exc[1] # Remove our function.
            result = ''.join(exc)
        result = '>>> %s\n%s' % (code, result)
        self.text_buffer.insert(self.text_buffer.get_end_iter(), result)
        # Can't use iter, won't scroll correctly.
        self.text_view.scroll_to_mark(self.end_mark, 0)

PLUGIN = None
MENU_ITEM = None

def initialize():
    global MENU_ITEM
    MENU_ITEM = gtk.MenuItem('Show Python Console')
    MENU_ITEM.connect('activate', show_console)
    APP.xml.get_widget('tools_menu').get_submenu().append(MENU_ITEM)
    MENU_ITEM.show()
    return True

def destroy():
    global PLUGIN, MENU_ITEM
    if PLUGIN:
        PLUGIN.destroy()
        PLUGIN = None
    if MENU_ITEM:
        MENU_ITEM.hide()
        MENU_ITEM.destroy()
        MENU_ITEM = None

def show_console(*args):
    global PLUGIN
    if not PLUGIN:
        PLUGIN = PyConsole({'exaile': APP})
        PLUGIN.connect('destroy', console_destroyed)
    PLUGIN.present()

def console_destroyed(*args):
    global PLUGIN
    PLUGIN = None


if __name__ == '__main__':
    console = PyConsole({})
    console.connect('destroy', gtk.main_quit)
    console.show()
    gtk.main()

# vi: et ts=4 sts=4 sw=4
