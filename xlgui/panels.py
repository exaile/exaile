# Copyright (C) 2014 Dustin Spicuzza
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

import logging

from xl.nls import gettext as _
from xl import providers, settings

from xlgui.widgets import menu, notebook
from xlgui.panel import lyrics


logger = logging.getLogger(__name__)


class PanelData:

    __slots__ = ['tab', 'menuitem', 'panel', 'position', 'shown']

    def __init__(self, tab, panel, position, menuitem):
        self.tab = tab  # Notebook tab
        self.menuitem = menuitem  # Menuitem
        self.panel = panel  # Panel provider
        self.position = position  # Position in notebook
        self.shown = True  # Whether the panel is shown

    @property
    def opts(self):
        return (self.shown, self.position)

    def __repr__(self):
        return '<PanelData tab: %s, panel: %s, position: %s, shown: %s>' % (
            self.tab,
            self.panel,
            self.position,
            self.shown,
        )


class PanelNotebook(notebook.SmartNotebook, providers.ProviderHandler):
    """
    This notebook holds the panels shown on the left side of the main
    UI. Do not directly add things to this panel, but instead register
    a provider.

    The provider object must have the following attributes:

        name: the name of the provider

    The provider object must have the following methods:

        get_panel: This must return a widget that is derived from
                   xlgui.widgets.notebook.NotebookPage
    """

    def __init__(self, exaile, gui):
        notebook.SmartNotebook.__init__(self, vertical=True)

        self.exaile = exaile
        self.panels = {}  # key: name, value: PanelData object

        self.set_add_tab_on_empty(False)

        self.loading_panels = True

        self.connect('page-removed', self.on_panel_removed)
        self.connect('page-reordered', self.on_panel_reordered)
        self.connect('switch-page', self.on_panel_switch)

        _register_builtin_panels(exaile, gui.main.window)

        self.view_menu = menu.ProviderMenu('panel-tab-context', None)

        # setup/register the view menu
        menu.simple_menu_item(
            'panel-menu', ['show-playing-track'], _('P_anels'), submenu=self.view_menu
        ).register('menubar-view-menu')

        providers.ProviderHandler.__init__(self, 'main-panel', simple_init=True)

        # Provide interface for adding buttons to the notebook
        self.actions = notebook.NotebookActionService(self, 'main-panel-actions')

        if not self.exaile.loading:
            self.on_gui_loaded()

    def focus_panel(self, tab_name):

        data = self.panels[tab_name]
        if data.shown:
            panel_nr = self.page_num(data.tab.page)
            self.set_current_page(panel_nr)
            data.tab.grab_focus()

    def get_active_panel(self):
        self.get_current_page()
        return None

    def toggle_panel(self, tab_name):

        data = self.panels[tab_name]

        if data.shown:
            self.remove_tab(data.tab)
        else:
            self.add_tab(data.tab, data.tab.page, data.position)
            data.shown = True

            self.save_panel_settings()

    def on_provider_added(self, provider):

        if provider.name is None:
            logger.warning(
                "Ignoring improperly initialized panel provider: %s", provider
            )
            return

        panel = provider.get_panel()
        panel.show()

        tab = notebook.NotebookTab(self, panel, vertical=True)
        tab.provider = provider

        item = menu.check_menu_item(
            provider.name,
            [],
            panel.get_page_name(),
            lambda *a: self.panels[provider.name].shown,
            lambda *a: self.toggle_panel(provider.name),
        )

        providers.register('panel-tab-context', item)

        self.add_tab(tab, panel)
        self.panels[provider.name] = PanelData(
            tab, provider, self.get_n_pages() - 1, item
        )

        self.save_panel_settings()

    def on_provider_removed(self, provider):

        data = self.panels[provider.name]

        for n in range(self.get_n_pages()):
            if data.tab.page == self.get_nth_page(n):
                self.remove_page(n)
                break

        providers.unregister('panel-tab-context', data.menuitem)
        del self.panels[provider.name]

    def on_panel_removed(self, notebook, page, pagenum):

        if self.loading_panels:
            return

        for name, data in self.panels.items():
            if data.tab.page == page:
                data.shown = False
                break

        self.save_panel_settings()

    def on_panel_reordered(self, notebook, page, pagenum):

        if self.loading_panels:
            return

        for name, data in self.panels.items():
            if data.shown:
                data.position = self.page_num(data.tab.page)

        self.save_panel_settings()

    def on_panel_switch(self, notebook, page, pagenum):
        """
        Saves the currently selected panel
        """
        if self.exaile.loading:
            return

        page = notebook.get_nth_page(pagenum)
        for name, data in self.panels.items():
            if data.tab.page == page:
                settings.set_option('gui/last_selected_panel', name)
                return

    def save_panel_settings(self):

        if self.loading_panels:
            return

        param = dict([(k, v.opts) for k, v in self.panels.items()])
        settings.set_option('gui/panels', param)

    def on_gui_loaded(self):

        last_selected_panel = settings.get_option(
            'gui/last_selected_panel', 'collection'
        )

        order = settings.get_option(
            'gui/panels',
            {
                'collection': (True, 0),
                'radio': (True, 1),
                'playlists': (True, 2),
                'files': (True, 3),
            },
        )

        selected_panel = None

        for name, (shown, pos) in order.items():

            panel_data = self.panels.get(name, None)
            if panel_data is None:
                continue

            tab = panel_data.tab
            panel_data.shown = shown
            panel_data.position = pos

            if shown:
                self.reorder_child(tab.page, pos)
            else:
                self.remove_tab(tab)

            if last_selected_panel == name:
                selected_panel = tab.page

        self.loading_panels = False

        # can't determine selected panel when reordering, find it now

        if selected_panel is not None:
            panel_num = self.page_num(selected_panel)
            self.set_current_page(panel_num)


def _register_builtin_panels(exaile, window):

    from xlgui.panel import collection, radio, playlists, files

    logger.info("Loading panels...")

    providers.register(
        'main-panel',
        collection.CollectionPanel(
            window, exaile.collection, 'collection', _show_collection_empty_message=True
        ),
    )

    providers.register(
        'main-panel',
        radio.RadioPanel(
            window, exaile.collection, exaile.radio, exaile.stations, 'radio'
        ),
    )

    providers.register(
        'main-panel',
        playlists.PlaylistsPanel(
            window,
            exaile.playlists,
            exaile.smart_playlists,
            exaile.collection,
            'playlists',
        ),
    )

    providers.register(
        'main-panel', files.FilesPanel(window, exaile.collection, 'files')
    )

    providers.register('main-panel', lyrics.LyricsPanel(window, 'lyrics'))
