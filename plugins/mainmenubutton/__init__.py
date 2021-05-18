# Copyright (C) 2012  Mathias Brodala <info@noctus.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from gi import require_version

require_version('Atk', '1.0')

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import Gdk

from xl.nls import gettext as _
from xl import event, providers
from xlgui import main
from xlgui.widgets import notebook


EXAILE = None


def enable(exaile):
    """
    Enables the plugin
    """
    global EXAILE
    EXAILE = exaile
    if exaile.loading:
        event.add_callback(on_gui_loaded, 'gui_loaded')
    else:
        on_gui_loaded()


def disable(exaile):
    """
    Disables the plugin
    """
    global EXAILE
    EXAILE = None
    providers.unregister('main-panel-actions', MainMenuButton)


def on_gui_loaded(*args):
    """
    Creates the main menu button
    which takes care of the rest
    """
    if EXAILE.gui.panel_notebook.get_n_pages() == 0:
        raise Exception(_("This plugin needs at least one visible panel"))

    providers.register('main-panel-actions', MainMenuButton)


class MainMenuButton(Gtk.ToggleButton, notebook.NotebookAction):
    __gsignals__ = {}

    name = 'main-menu'
    position = Gtk.PackType.START

    def __init__(self, panel_notebook):
        """
        Adds the button to the main window
        and moves the main menu items
        """
        Gtk.ToggleButton.__init__(self)
        notebook.NotebookAction.__init__(self, panel_notebook)

        self.set_image(Gtk.Image.new_from_icon_name('exaile', Gtk.IconSize.BUTTON))
        self.set_tooltip_text(_('Main Menu'))
        self.set_focus_on_click(True)
        self.set_relief(Gtk.ReliefStyle.NONE)

        accessible = self.get_accessible()
        accessible.set_role(Atk.Role.MENU)
        accessible.set_name(_('Main Menu'))

        builder = main.mainwindow().builder

        # Move menu items of the main menu to the internal menu
        self.mainmenu = mainmenu = builder.get_object('mainmenu')
        self.menu = menu = Gtk.Menu()
        menu.attach_to_widget(self, None)
        menu.connect('deactivate', self.on_menu_deactivate)

        for menuitem in mainmenu:
            mainmenu.remove(menuitem)
            menu.add(menuitem)

        menu.show_all()
        self.show_all()

        self.connect('toggled', self.on_toggled)

        self.notebook_page_removed_connection = panel_notebook.connect(
            'page-removed', self.on_notebook_page_removed
        )

    def destroy(self):
        """
        Moves the main menu items back and
        removes the button from the main window
        """
        self.notebook.disconnect(self.notebook_page_removed_connection)

        menu = self.menu
        mainmenu = self.mainmenu
        for menuitem in menu:
            menu.remove(menuitem)
            mainmenu.add(menuitem)

        self.unparent()
        Gtk.Button.destroy(self)

    def get_menu_position(self, *_):
        """
        Positions the menu at the right of the button
        """
        # Origin includes window position and decorations
        _, x, y = self.props.window.get_origin()

        allocation = self.get_allocation()

        return (x + allocation.x + allocation.width, y + allocation.y, False)

    def do_button_press_event(self, e):
        """
        Pops out the menu upon click
        """
        if e.button == Gdk.BUTTON_PRIMARY:
            self.set_active(not self.get_active())

        return True

    def do_popup_menu(self):
        """
        Pops out the menu upon pressing
        the Menu or Shift+F10 keys
        """
        self.set_active(True)

        return True

    def on_toggled(self, button):
        """
        Pops out the menu upon button toggle
        """
        self.menu.popup(
            None, None, self.get_menu_position, None, 0, Gtk.get_current_event_time()
        )

    def on_menu_deactivate(self, menu):
        """
        Removes button activation upon menu popdown
        """
        self.set_active(False)

    def on_notebook_page_removed(self, notebook, *_):
        if notebook.get_n_pages() == 0:
            EXAILE.plugins.disable_plugin(__name__)
