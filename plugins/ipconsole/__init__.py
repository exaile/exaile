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


import logging
import sys
import site

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib

from xl.nls import gettext as _
from xl import event
from xl import settings as xl_settings
from xl import providers
from xlgui.widgets import menu
from xlgui import guiutil

from . import ipconsoleprefs
from . import ipython_view as ip

FONT = "Luxi Mono 10"
SETTINGS_STRING = 'plugin_ipconsole_option_set'
LOGGER = logging.getLogger(__name__)


class Quitter:
    """Simple class to handle exit, similar to Python 2.5's.

    This Quitter is used to circumvent IPython's circumvention
    of the builtin Quitter, since it prevents exaile form closing."""

    def __init__(self, exit_function, name):
        self.exit_function = exit_function
        self.name = name

    def __repr__(self):
        return 'Type %s() to exit.' % self.name

    def __call__(self):
        self.exit_function()  # Passed in exit function
        site.setquit()  # Restore default builtins
        exit()  # Call builtin


class IPView(ip.IPythonView):
    '''Extend IPythonView to support closing with Ctrl+D'''

    __text_color = None
    __background_color = None
    __font = None

    __css_provider = None

    __text_color_str = None
    __background_color_str = None
    __font_str = None

    __iptheme = None

    def __init__(self, namespace):
        ip.IPythonView.__init__(self)
        event.add_ui_callback(self.__on_option_set, SETTINGS_STRING)
        self.set_wrap_mode(Gtk.WrapMode.CHAR)

        self.updateNamespace(namespace)  # expose exaile (passed in)

        # prevent exit and quit - freezes window? does bad things
        self.updateNamespace({'exit': None, 'quit': None})

        style_context = self.get_style_context()
        self.__css_provider = Gtk.CssProvider()
        style_context.add_provider(
            self.__css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        # Trigger setup through options
        for option in ('text_color', 'background_color', 'font'):
            self.__on_option_set(
                None, xl_settings, 'plugin/ipconsole/{option}'.format(option=option)
            )

    def __on_option_set(self, _event, settings, option):
        if option == 'plugin/ipconsole/font':
            pango_font_str = settings.get_option(option, FONT)
            self.__font_str = guiutil.css_from_pango_font_description(pango_font_str)
            GLib.idle_add(self.__update_css)
        if option == 'plugin/ipconsole/text_color':
            rgba_str = settings.get_option(option, 'lavender')
            rgba = Gdk.RGBA()
            rgba.parse(rgba_str)
            self.__text_color_str = "color: " + guiutil.css_from_rgba_without_alpha(
                rgba
            )
            GLib.idle_add(self.__update_css)
        if option == 'plugin/ipconsole/background_color':
            rgba_str = settings.get_option(option, 'black')
            rgba = Gdk.RGBA()
            rgba.parse(rgba_str)
            self.__background_color_str = (
                "background-color: " + guiutil.css_from_rgba_without_alpha(rgba)
            )
            GLib.idle_add(self.__update_css)

    def __update_css(self):
        if (
            self.__text_color_str is None
            or self.__background_color_str is None
            or self.__font_str is None
        ):
            # early initialization state: not all properties have been initialized yet
            return False

        data_str = "text {%s; %s;} textview {%s;}" % (
            self.__background_color_str,
            self.__text_color_str,
            self.__font_str,
        )
        self.__css_provider.load_from_data(data_str.encode('utf-8'))
        return False

    def onKeyPressExtend(self, key_event):
        if ip.IPythonView.onKeyPressExtend(self, key_event):
            return True
        if key_event.string == '\x04':  # ctrl+d
            self.destroy()


class IPythonConsoleWindow(Gtk.Window):
    """
    A Gtk Window with an embedded IPython Console.
    """

    __ipv = None

    def __init__(self, namespace):
        Gtk.Window.__init__(self)
        self.set_title(_("IPython Console - Exaile"))
        self.set_size_request(750, 550)
        self.set_resizable(True)

        self.__ipv = IPView(namespace)
        self.__ipv.connect('destroy', lambda *_widget: self.destroy())
        self.__ipv.updateNamespace({'self': self})  # Expose self to IPython

        # make it scrollable
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.__ipv)
        scrolled_window.show_all()
        self.add(scrolled_window)

        event.add_ui_callback(self.on_option_set, SETTINGS_STRING)

    def on_option_set(self, _event, settings, option):
        if option == 'plugin/ipconsole/opacity':
            if sys.platform.startswith("win32"):
                # Setting opacity on Windows crashes with segfault,
                # see https://bugzilla.gnome.org/show_bug.cgi?id=674449
                # Ignore this option.
                return
            value = settings.get_option(option, 80.0)
            value = value / 100
            if value > 1:
                value = 1
            self.set_opacity(value)


class IPConsolePlugin:
    """
    This class holds the IPConsole plugin itself
    """

    __console_window = None
    __exaile = None

    def enable(self, exaile):
        """
        Called when plugin is enabled, or when exaile is loaded with the plugin
        on by default.
        """
        self.__exaile = exaile

    def on_gui_loaded(self):
        """
        Called when Exaile finished loading its GUI
        """
        # Trigger initial setup through options:
        if xl_settings.get_option('plugin/ipconsole/autostart', False):
            self.__show_console()

        # add menuitem to tools menu
        item = menu.simple_menu_item(
            'ipconsole',
            ['plugin-sep'],
            _('Show _IPython Console'),
            callback=lambda *_args: self.__show_console(),
        )
        providers.register('menubar-tools-menu', item)

    def teardown(self, _exaile):
        """
        Called when Exaile is shutting down
        """
        # if window is open, kill it
        if self.__console_window is not None:
            self.__console_window.destroy()

    def disable(self, exaile):
        """
        Called when the plugin is disabled
        """
        for item in providers.get('menubar-tools-menu'):
            if item.name == 'ipconsole':
                providers.unregister('menubar-tools-menu', item)
                break
        self.teardown(exaile)

    def __show_console(self):
        """
        Display window when the menu item is clicked.
        """
        if self.__console_window is None:
            import xl
            import xlgui

            self.__console_window = IPythonConsoleWindow(
                {'exaile': self.__exaile, 'xl': xl, 'xlgui': xlgui}
            )
            self.__console_window.connect('destroy', self.__console_destroyed)

        self.__console_window.present()
        self.__console_window.on_option_set(
            None, xl_settings, 'plugin/ipconsole/opacity'
        )

    def __console_destroyed(self, *_args):
        """
        Called when the window is closed.
        """
        self.__console_window = None

    def get_preferences_pane(self):
        """
        Called by Exaile when ipconsole preferences pane should be shown
        """
        return ipconsoleprefs


plugin_class = IPConsolePlugin
