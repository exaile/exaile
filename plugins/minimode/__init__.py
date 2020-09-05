# Copyright (C) 2009-2010 Mathias Brodala
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from gi.repository import Gtk

from xl import event, providers, settings
from xl.nls import gettext as _
from xlgui.accelerators import Accelerator
from xlgui.widgets import menu

from . import controls
from . import minimode_preferences

MINIMODE = None


def __migrate_fixed_controls():
    """
    Makes sure fixed controls are selected,
    mostly for migration from older versions
    """
    option_name = 'plugin/minimode/selected_controls'

    if settings.MANAGER.has_option(option_name):
        selected_controls = settings.get_option(option_name)

        if 'restore' not in selected_controls:
            selected_controls += ['restore']
            settings.set_option(option_name, selected_controls)


def enable(exaile):
    """
    Enables the mini mode plugin
    """
    __migrate_fixed_controls()

    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)


def _enable(event, exaile, nothing):
    """
    Handles the deferred enable call
    """
    global MINIMODE
    MINIMODE = MiniMode(exaile)


def disable(exaile):
    """
    Disables the mini mode plugin
    """
    global MINIMODE
    MINIMODE.destroy()
    MINIMODE = None


def get_preferences_pane():
    return minimode_preferences


class MiniMode(Gtk.Window):
    """
    Mini Mode main window
    """

    __gsignals__ = {'show': 'override'}

    def __init__(self, exaile):
        """
        Sets up the mini mode main window and
        options to access it
        """
        Gtk.Window.__init__(self)
        self.set_title('Exaile Mini Mode')
        self.set_resizable(False)

        self.exaile_window = exaile.gui.main.window

        controls.register()

        self.box = controls.ControlBox()
        self.box.set_spacing(3)
        self.border_frame = Gtk.Frame()
        self.border_frame.add(self.box)
        self.add(self.border_frame)

        self.accelerator = Accelerator(
            '<Primary><Alt>M', _('Mini Mode'), self.on_menuitem_activate
        )

        self.menuitem = menu.simple_menu_item(
            'minimode',
            ['clear-playlist'],
            icon_name='exaile-minimode',
            callback=self.accelerator,
        )

        providers.register('menubar-view-menu', self.menuitem)
        providers.register('mainwindow-accelerators', self.accelerator)

        self.mainbutton = Gtk.Button(label=_('Mini Mode'))
        self.mainbutton.set_image(
            Gtk.Image.new_from_icon_name('exaile-minimode', Gtk.IconSize.BUTTON)
        )
        self.mainbutton.connect('clicked', self.on_mainbutton_clicked)
        action_area = exaile.gui.main.info_area.get_action_area()
        action_area.pack_end(self.mainbutton, False, False, 6)

        self.__active = False
        self.__dirty = True
        # XXX: Until defaults are implemented in xl.settings
        self.__defaults = {
            'plugin/minimode/always_on_top': True,
            'plugin/minimode/show_in_panel': False,
            'plugin/minimode/on_all_desktops': True,
            'plugin/minimode/display_window_decorations': True,
            'plugin/minimode/window_decoration_type': 'full',
            'plugin/minimode/use_alpha': False,
            'plugin/minimode/transparency': 0.3,
            'plugin/minimode/horizontal_position': 10,
            'plugin/minimode/vertical_position': 10,
        }

        exaile.gui.main.connect('main-visible-toggle', self.on_main_visible_toggle)
        event.add_ui_callback(self.on_option_set, 'plugin_minimode_option_set')
        self.on_option_set(
            'plugin_minimode_option_set',
            settings,
            'plugin/minimode/button_in_mainwindow',
        )

    def destroy(self):
        """
        Cleanups
        """
        providers.unregister('mainwindow-accelerators', self.accelerator)
        providers.unregister('menubar-view-menu', self.menuitem)
        controls.unregister()

        self.mainbutton.destroy()

        self.set_active(False)
        self.box.destroy()
        Gtk.Window.destroy(self)

    def set_active(self, active):
        """
        Enables or disables the Mini Mode window
        """
        if active == self.__active:
            return

        if active and not self.props.visible:
            self.exaile_window.hide()
            self.show_all()
        elif not active and self.props.visible:
            self.hide()
            self.exaile_window.show()

        self.__active = active

    def do_show(self):
        """
        Updates the appearance if
        settings have been changed
        """
        h = None
        v = None

        if self.__dirty:
            for option, default in self.__defaults.items():
                value = settings.get_option(option, default)

                if option == 'plugin/minimode/always_on_top':
                    self.set_keep_above(value)
                elif option == 'plugin/minimode/show_in_panel':
                    self.props.skip_taskbar_hint = not value
                elif option == 'plugin/minimode/on_all_desktops':
                    if value:
                        self.stick()
                    else:
                        self.unstick()
                elif option == 'plugin/minimode/display_window_decorations':
                    if value:
                        option = 'plugin/minimode/window_decoration_type'
                        value = settings.get_option(option, self.__defaults[option])

                        if value == 'full':
                            self.set_decorated(True)
                            self.border_frame.set_shadow_type(Gtk.ShadowType.NONE)
                        elif value == 'simple':
                            self.set_decorated(False)
                            self.border_frame.set_shadow_type(Gtk.ShadowType.OUT)
                    else:
                        self.set_decorated(False)
                        self.border_frame.set_shadow_type(Gtk.ShadowType.NONE)
                elif option == 'plugin/minimode/use_alpha':
                    if value:
                        option = 'plugin/minimode/transparency'
                        opacity = 1 - settings.get_option(
                            option, self.__defaults[option]
                        )
                        self.set_opacity(opacity)
                elif option == 'plugin/minimode/horizontal_position':
                    h = value
                elif option == 'plugin/minimode/vertical_position':
                    v = value

            self.__dirty = False

        min_width, natural_width = self.get_preferred_width()
        min_height, natural_height = self.get_preferred_height()
        self.resize(natural_width, natural_height)
        self.queue_draw()
        Gtk.Window.do_show(self)

        # GTK (or perhaps the theme?) likes to move the window to some
        # random default position while showing it... so do these at the
        # same time after show, otherwise it'll move on us
        x, y = self.get_position()
        if h is not None:
            x = h
        if v is not None:
            y = v

        self.move(x, y)

    def do_configure_event(self, event):
        """
        Stores the window position upon window movement
        """
        settings.set_option('plugin/minimode/horizontal_position', event.x)
        settings.set_option('plugin/minimode/vertical_position', event.y)

    def do_delete_event(self, event):
        """
        Takes care of restoring Exaile's main window
        """
        self.set_active(False)

        return True

    def on_menuitem_activate(self, menuitem, name, parent, context):
        """
        Shows the Mini Mode window
        """
        self.set_active(True)

    def on_mainbutton_clicked(self, button):
        """
        Shows the Mini Mode window
        """
        self.set_active(True)

    def on_main_visible_toggle(self, main):
        """
        Handles visiblity toggles in
        Exaile's main window stead
        """
        if self.__active:
            if self.props.visible:
                self.hide()
            else:
                self.show_all()

            return True

        return False

    def on_option_set(self, event, settings, option):
        """
        Queues updates upon setting change
        """
        self.__dirty = True

        if option == 'plugin/minimode/button_in_mainwindow':
            button_in_mainwindow = settings.get_option(option, False)

            if button_in_mainwindow:
                self.mainbutton.set_no_show_all(False)
                self.mainbutton.show_all()
            else:
                self.mainbutton.hide()
                self.mainbutton.set_no_show_all(True)


# vim: et sts=4 sw=4
