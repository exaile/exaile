# Copyright (C) 2010 Adam Olsen
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
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from xl.nls import gettext as _
from xl import providers
from xlgui import guiutil
from xlgui.widgets import menu

# Custom tab style; fixes some Adwaita ugliness
TAB_CSS = Gtk.CssProvider()
TAB_CSS.load_from_data(
    # For GTK+ <3.20 (TODO: remove eventually)

    '.notebook { ' +
        # Remove gap before first tab
        '-GtkNotebook-initial-gap: 0; ' +
        # Remove gap between tabs
        '-GtkNotebook-tab-overlap: 1; ' +
    '} ' +
    '.notebook tab { ' +
        # Make tabs smaller (or bigger on some other themes, unfortunately)
        'padding: 6px; ' +
    '} ' +

    # For GTK+ >=3.20

    # Work around weird Close button position on panel.
    # Need to find out why the button is not centered.
    'notebook.vertical tab { ' +
        'padding-left: 6px; ' +
        'padding-right: 3px; ' +
    '} ' +

    # Remove gap between tabs
    'header.top tab, header.bottom tab { ' +
        'margin-left: -1px; ' +
        'margin-right: -1px; ' +
    '} ' +
    'header.left tab, header.right tab { ' +
        'margin-top: -1px; ' +
        'margin-bottom: -1px; ' +
    '}')

class SmartNotebook(Gtk.Notebook):
    def __init__(self, vertical=False):
        Gtk.Notebook.__init__(self)
        self.set_scrollable(True)
        self.connect('button-press-event', self.on_button_press)
        self.connect('popup-menu', self.on_popup_menu)
        self._add_tab_on_empty = True

        sc = self.get_style_context()
        sc.add_provider(TAB_CSS, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if vertical:
            sc.add_class('vertical')
            self.set_tab_pos(Gtk.PositionType.LEFT)

    def get_current_tab(self):
        current_page = self.get_current_page()
        if current_page == -1:
            return None
        return self.get_nth_page(current_page)

    def add_tab(self, tab, page, position=-1, switch=True):
        """
            Add a tab to the notebook. It will be given focus.

            :param tab: The tab to use
            :type tab: NotebookTab
            :param page: The page to use
            :type page: NotebookPage
            :param position: index to insert page at, or -1 for append
            :type position: int
        """
        self.insert_page(page, tab, position=position)
        tab.notebook = self
        self.set_tab_reorderable(page, page.reorderable)
        self.child_set_property(page, 'tab-expand', True)
        if switch:
            self.set_current_page(self.page_num(page))

    def add_default_tab(self):
        """
            Action taken when a generic "new tab" option is triggered.
            Subclasses need to override this if they want new tab
            functionality to work automatically.

            :return: The NotebookTab created, or None
        """
        pass

    def remove_page(self, page_num):
        '''
            Overrides Gtk.Notebook.remove_page
        '''
        if page_num == -1:
            page_num = self.get_n_pages()-1
        tab = self.get_tab_label(self.get_nth_page(page_num))
        
        Gtk.Notebook.remove_page(self, page_num)
        tab.notebook = None
        
        if self._add_tab_on_empty and self.get_n_pages() == 0:
            self.add_default_tab()
            
    def remove_tab(self, tab):
        '''
            Remove a specific NotebookTab from the notebook
        '''
        page_num = self.page_num(tab.page)
        if page_num >= 0:
            self.remove_page(page_num)
            
    def set_add_tab_on_empty(self, add_tab_on_empty):
        '''
            If set True, the SmartNotebook will always maintain at
            least one tab in the notebook
        '''
        self._add_tab_on_empty = add_tab_on_empty

    def on_button_press(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 2:
            self.add_default_tab()
            
    def on_popup_menu(self, widget):
        page = self.get_current_tab()
        tab_label = self.get_tab_label(self.get_current_tab())
        page.tab_menu.popup(None, None, guiutil.position_menu, tab_label,
                            0, 0)
        return True        
        

class NotebookTab(Gtk.EventBox):
    """
        Class to represent a generic tab in a Gtk.Notebook.
    """
    menu_provider_name = 'notebooktab' # Change this in subclasses!
    reorderable = True
    def __init__(self, notebook, page, vertical=False):
        """
            :param notebook: The notebook this tab will belong to
            :type notebook: SmartNotebook
            :param page: The page this tab will be associated with
            :type page: NotebookPage
            :param vertical: Whether the tab contents are to be laid out vertically
            :type vertical: bool
        """
        Gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.closable = True

        self.notebook = notebook
        self.page = page

        self.menu = menu.ProviderMenu(self.menu_provider_name, self)

        self.connect('button-press-event', self.on_button_press)

        if vertical:
            box = Gtk.Box(False, 2, orientation=Gtk.Orientation.VERTICAL)
        else:
            box = Gtk.Box(False, 2)
        self.add(box)

        self.icon = Gtk.Image()
        self.icon.set_no_show_all(True)

        self.label = Gtk.Label(label=self.page.get_page_name())

        if vertical:
            self.label.set_angle(90)
            self.label.props.valign = Gtk.Align.CENTER
            # Don't ellipsize but give a sane maximum length.
            self.label.set_max_width_chars(20)
        else:
            self.label.props.halign = Gtk.Align.CENTER
            self.label.set_ellipsize(Pango.EllipsizeMode.END)
            self.label.set_width_chars(4)  # Minimum, including ellipsis

        self.label.set_tooltip_text(self.page.get_page_name())
        
        if self.can_rename():
            self.entry = Gtk.Entry()
            self.entry.set_width_chars(self.label.get_max_width_chars())
            self.entry.set_text(self.label.get_text())
            border = Gtk.Border.new()
            border.left = 1
            border.right = 1
            self.entry.set_inner_border(border)
            self.entry.connect('activate', self.on_entry_activate)
            self.entry.connect('focus-out-event', self.on_entry_focus_out_event)
            self.entry.connect('key-press-event', self.on_entry_key_press_event)
            self.entry.set_no_show_all(True)
        

        self.button = button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_halign(Gtk.Align.CENTER)
        button.set_valign(Gtk.Align.CENTER)
        button.set_focus_on_click(False)
        button.set_tooltip_text(_("Close Tab"))
        button.add(Gtk.Image.new_from_icon_name('window-close-symbolic', Gtk.IconSize.MENU))
        button.connect('clicked', self.close)
        button.connect('button-press-event', self.on_button_press)
        
        # pack the widgets in
        if vertical:
            box.pack_start(button, False, False, 0)
            box.pack_end(self.icon, False, False, 0)
            box.pack_end(self.label, True, True, 0)
            if self.can_rename():
                box.pack_end(self.entry, True, True, 0)
            
        else:
            box.pack_start(self.icon, False, False, 0)
            box.pack_start(self.label, True, True, 0)
            if self.can_rename():
                box.pack_start(self.entry, True, True, 0)
            box.pack_end(button, False, False, 0)

        page.set_tab(self)
        page.connect('name-changed', self.on_name_changed)
        self.show_all()

    def set_icon(self, pixbuf):
        """
            Set the primary icon for the tab.

            :param pixbuf: The icon to use, or None to hide
            :type pixbuf: :class:`GdkPixbuf.Pixbuf`
        """
        if pixbuf is None:
            self.icon.set_property("visible", False)
        else:
            self.icon.set_from_pixbuf(pixbuf)
            self.icon.set_property("visible", True)

    def set_closable(self, closable):
        self.closable = closable
        self.button.set_sensitive(closable)

    def on_button_press(self, widget, event):
        """
            Handles mouse button events on the tab.

            Typically triggers renaming, closing and menu.
        """
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.start_rename()
        elif event.button == 2:
            self.close()
        elif event.button == 3:
            self.page.tab_menu.popup( None, None, None, None,
                    event.button, event.time)
            return True

    def on_entry_activate(self, entry):
        """
            Handles end of editing and triggers the actual rename.
        """
        self.entry.props.editing_canceled = False
        self.end_rename()

    def on_entry_focus_out_event(self, widget, event):
        """
            Make defocusing the rename box equivalent to activating it.
        """
        if not self.entry.props.editing_canceled:
            widget.activate()

    def on_entry_key_press_event(self, widget, event):
        """
            Cancel rename if Escape is pressed
        """
        if event.keyval == Gdk.KEY_Escape:
            self.entry.props.editing_canceled = True
            self.end_rename()
            return True

    def on_name_changed(self, *args):
        self.label.set_text(self.page.get_page_name())

    def start_rename(self):
        """
            Initiates the renaming of a tab, if the page supports this.
        """
        if not self.can_rename():
            return
        self.entry.set_text(self.page.get_page_name())
        self.label.hide()
        self.button.hide()
        self.entry.show()
        self.entry.select_region(0, -1)
        self.entry.grab_focus()

    def end_rename(self, cancel=False):
        """
            Finishes or cancels the renaming
        """
        name = self.entry.get_text()

        if name.strip() != "" and not self.entry.props.editing_canceled:
            self.page.set_page_name(name)
            self.label.set_text(name)
            self.label.set_tooltip_text(name)

        self.entry.hide()
        self.label.show()
        self.button.show()

        self.entry.props.editing_canceled = False

    def can_rename(self):
        return hasattr(self.page, 'set_page_name')

    def close(self, *args):
        if self.closable and not self.page.emit('closing'):
            self.notebook.remove_page(self.notebook.page_num(self.page))


class NotebookPage(Gtk.Box):
    """
        Base class representing a page. Should never be used directly.
    """
    menu_provider_name = 'tab-context' #override this in subclasses
    reorderable = True
    __gsignals__ = {
        'name-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            ()
        ),
        'closing': (
            GObject.SignalFlags.RUN_LAST,
            GObject.TYPE_BOOLEAN,
            ()
        )
    }
    def __init__(self, child=None, page_name=None):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.tab = None
        self.tab_menu = menu.ProviderMenu(self.menu_provider_name, self)
        
        if child is not None:
            self.pack_start(child, True, True, 0)
            
        if page_name is not None:
            self.page_name = page_name
        

    def focus(self):
        '''
            Grabs focus for this page. Should be overriden in subclasses.
        '''
        self.grab_focus()
        
    def get_page_name(self):
        """
            Returns the name of this tab. Should be overriden in subclasses.

            Subclasses can also implement set_page_name(self, name) to allow
            renaming, but this is not mandatory.
        """
        if hasattr(self, 'page_name'):
            return self.page_name
        return "UNNAMED PAGE"

    def set_tab(self, tab):
        """
            Set the tab that holds this page.  This will be called directly
            from the tab itself when it is created, and should not be used
            outside of that.
        """
        self.tab = tab

    def is_current_page(self):
        """
            Returns True if this page is the currently-visible page in
            the Notebook.
        """
        return self.tab.get_nth_page(self.tab.get_current_page()) == self

    def name_changed(self):
        self.emit('name-changed')


class NotebookAction(object):
    """
        A custom action to be placed to the left or right of tabs in a notebook
    """
    name = None
    position = Gtk.PackType.END

    def __init__(self, notebook):
        self.notebook = notebook


class NotebookActionService(providers.ProviderHandler):
    '''
        Provides interface for action widgets to be dynamically attached
        detached from notebooks.
        
        Actions are widgets placed to the left or right of tabs on a notebook. 
    '''
    
    
    def __init__(self, notebook, servicename):
        '''
            :param notebook:     Notebook to attach to
            :param servicename:  Provider service name to use
        '''
        
        providers.ProviderHandler.__init__(self, servicename, notebook)

        self.notebook = notebook

        # Try to set up action widgets
        notebook.set_action_widget(Gtk.Box(spacing=3), Gtk.PackType.START)
        notebook.set_action_widget(Gtk.Box(spacing=3), Gtk.PackType.END)
    
        self.__actions = {}
        for provider in self.get_providers():
            self.on_provider_added(provider)
            
    def on_provider_added(self, provider):
        """
            Adds actions on provider addition
        """
        try:
            actions_box = self.notebook.get_action_widget(provider.position)
        except AttributeError:
            pass
        else:
            self.__actions[provider.name] = provider(self.notebook)
            actions_box.pack_start(self.__actions[provider.name], False, False, 0)
            actions_box.show_all()

    def on_provider_removed(self, provider):
        """
            Removes actions on provider removal
        """
        try:
            actions_box = self.notebook.get_action_widget(provider.position)
        except AttributeError:
            pass
        else:
            action = self.__actions[provider.name]
            actions_box.remove(action)
            action.destroy()
            
            del self.__actions[provider.name]

