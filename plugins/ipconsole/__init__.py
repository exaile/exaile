#!/usr/bin/env python

# This plugin is adapted from the Python Console plugin and the IPython cookbook at:
#   http://ipython.scipy.org/moin/Cookbook/EmbeddingInGTK
# Copyright (C) 2009 Brian Parma
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
import gtk
import gobject

try:    # xl doesn't exist outside of exaile
    from xl.nls import gettext as _
    from xl import event
except:
    from gettext import gettext as _
    print 'Running outside of Exaile...'
    

import ipython_view as ip
import pango
import __builtin__, site

FONT = "Luxi Mono 10"

# From the 0.2.4 version... now in separate text file (Icon?)
#PLUGIN_NAME             = _("IPython Console")
#PLUGIN_VERSION          = '0.1.1'
#PLUGIN_AUTHORS          = ["Brian Parma"]
#PLUGIN_DESCRIPTION      = _(r"""Provides an IPython console that can be used to manipulate Exaile.""")
#PLUGIN_ICON             = None
#PLUGIN_ENABLED          = False

PLUGIN                  = None
MENU_ITEM               = None

class Quitter(object):
    """Simple class to handle exit, similar to Python 2.5's.

       This Quitter is used to circumvent IPython's circumvention 
       of the builtin Quitter, since it prevents exaile form closing."""
    
    def __init__(self,exit,name):
        self.exit = exit
        self.name = name
      
    def __repr__(self):
        return 'Type %s() to exit.' % self.name
        __str__ = __repr__

    def __call__(self):
        self.exit()         # Passed in exit function
        site.setquit()      # Restore default builtins
        exit()              # Call builtin


class IPyConsole(gtk.Window):
    """
        A gtk Window with an embedded IPython Console.
    """
    def __init__(self, namespace):
        gtk.Window.__init__(self)
        
        self.set_title(_("IPython Console - Exaile"))
        self.set_size_request(750,550)
        self.set_resizable(True)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        ipv = ip.IPythonView()

        # so it's exposed in the shell
        self.ipv = ipv

        # change display to emulate dark gnome-terminal
        ipv.modify_font(pango.FontDescription(FONT))
        ipv.set_wrap_mode(gtk.WRAP_CHAR)
        ipv.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        ipv.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('lavender'))
        ipv.IP.magic_colors('Linux') # IPython color scheme

#           or white background?
#        ipv.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('white'))
#        ipv.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
#        ipv.IP.magic_colors('LightBG') # IPython color scheme

        self.set_opacity(0.8)   # add a little transparency :)
        ipv.updateNamespace(namespace)      # expose exaile (passed in)
        ipv.updateNamespace({'self':self})  # Expose self to IPython

        # prevent exit and quit - freezes window? does bad things
        ipv.updateNamespace({'exit':None,
                             'quit':None})
                             
        # This is so when exaile calls exit(), IP doesn't prompt and preven it from closing
        __builtin__.exit = Quitter(ipv.IP.magic_Exit, 'exit')
        __builtin__.quit = Quitter(ipv.IP.magic_Exit, 'quit')
        
        ipv.show()
        
        sw.add(ipv)
        sw.show()
        
        self.add(sw)
        self.show()
        
        self.connect('delete_event',lambda x,y:False)

def _enable(exaile):
    """
        Enable plugin.
            Create menu item.
    """
    global MENU_ITEM
    MENU_ITEM = gtk.MenuItem(_('Show IPython Console'))
    MENU_ITEM.connect('activate', show_console,exaile)

    # tools menu, not renamed yet :b
    exaile.gui.xml.get_widget('menuitem5').get_submenu().append(MENU_ITEM)
    MENU_ITEM.show()
#    return True    # bad! crashes compiz

def enable(exaile):
    """
        Called when plugin is enabled, or when exaile is loaded with the plugin
        on by default.
            Wait for exaile to fully load, then call _enable with idle priority.
    """
    def enb(eventname, exaile, nothing):
        gobject.idle_add(_enable, exaile)

    if exaile.loading:
        event.add_callback(enb, "exaile_loaded")
    else:
        enb(None, exaile, None)

def disable(exaile):
    """
        Called when the plugin is disabled
    """
    global PLUGIN, MENU_ITEM
    if PLUGIN:
        PLUGIN.destroy()
        PLUGIN = None
    if MENU_ITEM:
        MENU_ITEM.hide()
        MENU_ITEM.destroy()
        MENU_ITEM = None

def show_console(widget, exaile):
    """
        Display window when the menu item is clicked.
    """
    global PLUGIN
    if PLUGIN is None:
        PLUGIN = IPyConsole({'exaile': exaile})
        PLUGIN.connect('destroy', console_destroyed)
    PLUGIN.present()

def console_destroyed(*args):
    """
        Called when the window is closed.
    """
    global PLUGIN
    PLUGIN = None


if __name__ == '__main__':
    """
        If run outside of exaile.
    """
    con = IPyConsole({})
    con.connect('destroy', gtk.main_quit)
    con.show()
    gtk.main()

