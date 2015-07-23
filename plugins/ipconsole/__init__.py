# This plugin is adapted from the Python Console plugin and the IPython
# cookbook at:
#   http://ipython.scipy.org/moin/Cookbook/EmbeddingInGTK
# Copyright (C) 2009-2010 Brian Parma
# Updated       2012 Brian Parma
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
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
import ipconsoleprefs
from xl import settings, providers
from xlgui.widgets import menu

try:    # xl doesn't exist outside of exaile
    from xl.nls import gettext as _
    from xl import event
except:
    from gettext import gettext as _
    print 'Running outside of Exaile...'


import ipython_view as ip
from gi.repository import Pango
import __builtin__, site

FONT = "Luxi Mono 10"

PLUGIN                  = None

def get_preferences_pane():
    return ipconsoleprefs

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


class IPView(ip.IPythonView):
    '''Extend IPythonView to support closing with Ctrl+D'''
    def onKeyPressExtend(self, event):
        if ip.IPythonView.onKeyPressExtend(self, event):
            return True
            
        
        if event.string == '\x04':
            # ctrl+d
            self.destroy()


class IPyConsole(Gtk.Window):
    """
        A gtk Window with an embedded IPython Console.
    """
    def __init__(self, namespace):
        Gtk.Window.__init__(self)

        self.set_title(_("IPython Console - Exaile"))
        self.set_size_request(750,550)
        self.set_resizable(True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        ipv = IPView()

        ipv.connect('destroy', lambda *x: self.destroy())

        # so it's exposed in the shell
        self.ipv = ipv

        # change display to emulate dark gnome-terminal
        console_font = settings.get_option('plugin/ipconsole/font', FONT)
        
        text_color = settings.get_option('plugin/ipconsole/text_color', 
                                            'lavender')
                                            
        bg_color = settings.get_option('plugin/ipconsole/background_color', 
                                        'black')
                                
        iptheme = settings.get_option('plugin/ipconsole/iptheme', 'Linux')

        ipv.modify_font(Pango.FontDescription(console_font))
        ipv.set_wrap_mode(Gtk.WrapMode.CHAR)
        ipv.modify_base(Gtk.StateType.NORMAL, Gdk.color_parse(bg_color))
        ipv.modify_text(Gtk.StateType.NORMAL, Gdk.color_parse(text_color))
        
        if hasattr(ipv.IP, 'magic_colors'):
            ipv.IP.magic_colors(iptheme) # IPython color scheme

        opacity = settings.get_option('plugin/ipconsole/opacity', 80.0)

        # add a little transparency :)
        if opacity < 100: self.set_opacity(float(opacity) / 100.0)   
        ipv.updateNamespace(namespace)      # expose exaile (passed in)
        ipv.updateNamespace({'self':self})  # Expose self to IPython

        # prevent exit and quit - freezes window? does bad things
        ipv.updateNamespace({'exit':None,
                             'quit':None})

        # This is so when exaile calls exit(), IP doesn't prompt and prevent
        # it from closing
        try:
            __builtin__.exit = Quitter(ipv.IP.magic_Exit, 'exit')
            __builtin__.quit = Quitter(ipv.IP.magic_Exit, 'quit')
        except AttributeError: # newer versions of IP don't need this
            pass

        ipv.show()

        # make it scrollable
        sw.add(ipv)
        sw.show()

        self.add(sw)
        self.show()

        # don't destroy the window on delete, hide it
        self.connect('delete_event',lambda x,y:False)

def _enable(exaile):
    """
        Enable plugin.
            Create menu item.
    """
    # add menuitem to tools menu
    item = menu.simple_menu_item('ipconsole', ['plugin-sep'], _('Show _IPython Console'),
        callback=lambda *x: show_console(exaile)) 
    providers.register('menubar-tools-menu', item)
    
    if settings.get_option('plugin/ipconsole/autostart', False):
        show_console(exaile)


def on_option_set(event, settings, option):
    if option == 'plugin/ipconsole/opacity' and PLUGIN:
        value = settings.get_option(option, 80.0)
        value = float(value) / 100.0
        PLUGIN.set_opacity(value)

    if option == 'plugin/ipconsole/font' and PLUGIN:
        value = settings.get_option(option, FONT)
        PLUGIN.ipv.modify_font(Pango.FontDescription(value))

    if option == 'plugin/ipconsole/text_color' and PLUGIN:
        value = settings.get_option(option, 'lavender')
        PLUGIN.ipv.modify_text(Gtk.StateType.NORMAL, Gdk.color_parse(value))
        
    if option == 'plugin/ipconsole/background_color' and PLUGIN:
        value = settings.get_option(option, 'black')
        PLUGIN.ipv.modify_base(Gtk.StateType.NORMAL, Gdk.color_parse(value))

    if option == 'plugin/ipconsole/iptheme' and PLUGIN:
        value = settings.get_option(option, 'Linux')
        PLUGIN.ipv.IP.magic_colors(value)


def __enb(evt, exaile, nothing):
    GLib.idle_add(_enable, exaile)
    event.add_callback(on_option_set, 'plugin_ipconsole_option_set')

def enable(exaile):
    """
        Called when plugin is enabled, or when exaile is loaded with the plugin
        on by default.
            Wait for exaile to fully load, then call _enable with idle priority.
    """
    if exaile.loading:
        event.add_callback(__enb, "gui_loaded")
    else:
        __enb(None, exaile, None)

def disable(exaile):
    """
        Called when the plugin is disabled
    """
    for item in providers.get('menubar-tools-menu'):
        if item.name == 'ipconsole':
            providers.unregister('menubar-tools-menu', item)
            break
            
    # if window is open, kill it
    if PLUGIN is not None:
        PLUGIN.destroy()        

def show_console(exaile):
    """
        Display window when the menu item is clicked.
    """
    global PLUGIN
    if PLUGIN is None:
        import xl, xlgui
        PLUGIN = IPyConsole({'exaile': exaile,
                             'xl': xl,
                             'xlgui': xlgui})
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
    con.connect('destroy', Gtk.main_quit)
    con.show()
    Gtk.main()

