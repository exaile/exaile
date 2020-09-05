# Copyright (C) 2014 Dustin Spicuzza <dustin@virtualroadside.com>
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

#
# Contains definitions for all of the context menus for panels
#
# Each panel pulls in menu items from different providers, so that
# plugins can easily hook all of the panels for track operations
# without a lot of work.
#
# To hook into a panel, just call 'register' on the menu item with
# the appropriate provider key.
#
# Each panel context has the following keys available:
#
#    - selection-empty
#       Use this for conditions to determine whether to show the menu
#       item or not.
#
#    - selected-tracks
#       Will return all selected tracks, even if a playlist is selected
#
# Other context keys are available for specific panels
#

from xl.nls import gettext as _
from xl import common
from xlgui.widgets import menu, menuitems

### Generic track selection menus


def __create_track_panel_menus():

    items = []

    items.append(menuitems.EnqueueMenuItem('enqueue', after=['top-sep']))

    items.append(menuitems.AppendMenuItem('append', after=[items[-1].name]))
    items.append(menuitems.ReplaceCurrentMenuItem('replace', after=[items[-1].name]))
    items.append(menuitems.RatingMenuItem('rating', after=[items[-1].name]))

    items.append(menu.simple_separator('tp-sep', after=[items[-1].name]))

    items.append(menuitems.PropertiesMenuItem('properties', after=[items[-1].name]))

    for item in items:
        item.register('track-panel-menu')


__create_track_panel_menus()


class TrackPanelMenu(menu.ProviderMenu):
    """
    Context menu when a track is clicked on a panel

    Provider key: track-panel-menu
    """

    def __init__(self, parent):
        menu.ProviderMenu.__init__(self, 'track-panel-menu', parent)

    def get_context(self):
        context = common.LazyDict(self._parent)
        context[
            'selected-tracks'
        ] = lambda name, parent: parent.tree.get_selected_tracks()
        context[
            'selection-empty'
        ] = lambda name, parent: parent.tree.get_selection_empty()
        return context


### Collection panel menus


def __create_collection_panel_context_menu():
    def collection_delete_tracks_func(panel, context, tracks):
        panel.collection.delete_tracks(tracks)

    items = []
    items.append(menu.simple_separator('cp-sep', after=['properties']))
    items.append(
        menuitems.OpenDirectoryMenuItem('open-directory', after=[items[-1].name])
    )
    items.append(
        menuitems.TrashMenuItem(
            'trash-tracks',
            after=[items[-1].name],
            delete_tracks_func=collection_delete_tracks_func,
        )
    )

    for item in items:
        item.register('collection-panel-context-menu')


__create_collection_panel_context_menu()


class CollectionContextMenu(menu.MultiProviderMenu):
    """
    Context menu when a collection track is clicked

    Provider keys: track-panel-menu, collection-panel-context-menu
    """

    def __init__(self, panel):
        menu.MultiProviderMenu.__init__(
            self, ['track-panel-menu', 'collection-panel-context-menu'], panel
        )

    def get_context(self):
        context = common.LazyDict(self._parent)
        context[
            'selected-tracks'
        ] = lambda name, parent: parent.tree.get_selected_tracks()
        context[
            'selection-empty'
        ] = lambda name, parent: parent.tree.get_selection_empty()
        return context


### Files panel menu


def __create_files_panel_context_menu():
    def trash_tracks_func(parent, context, tracks):
        menuitems.generic_trash_tracks_func(parent, context, tracks)
        parent.refresh(None)

    items = []
    items.append(menu.simple_separator('fp-sep', after=['properties']))
    items.append(
        menuitems.OpenDirectoryMenuItem('open-directory', after=[items[-1].name])
    )
    items.append(
        menuitems.TrashMenuItem(
            'trash-tracks', after=[items[-1].name], trash_tracks_func=trash_tracks_func
        )
    )

    for item in items:
        item.register('files-panel-context-menu')


__create_files_panel_context_menu()


class FilesContextMenu(menu.MultiProviderMenu):
    """
    Context menu when a files panel track is clicked

    Provider keys: track-panel-menu, files-panel-context-menu
    """

    def __init__(self, panel):
        menu.MultiProviderMenu.__init__(
            self, ['track-panel-menu', 'files-panel-context-menu'], panel
        )

    def get_context(self):
        context = common.LazyDict(self._parent)
        context[
            'needs-computing'
        ] = lambda name, parent: parent.tree.get_selection_is_computed()
        context[
            'selected-tracks'
        ] = lambda name, parent: parent.tree.get_selected_tracks()
        context[
            'selection-empty'
        ] = lambda name, parent: parent.tree.get_selection_empty()

        return context


### Playlist panel menus


def __create_playlist_panel_menus():

    # w, n, o, c: window, name, parent, context

    menu.simple_menu_item(
        'new-playlist',
        [],
        _('_New Playlist'),
        'tab-new',
        lambda w, n, o, c: o.add_new_playlist(),
    ).register('playlist-panel-menu')

    menu.simple_menu_item(
        'new-smart-playlist',
        ['new-playlist'],
        _('New _Smart Playlist'),
        'tab-new',
        lambda w, n, o, c: o.add_smart_playlist(),
    ).register('playlist-panel-menu')

    menu.simple_menu_item(
        'import-playlist',
        ['new-smart-playlist'],
        _('_Import Playlist'),
        'document-open',
        lambda w, n, o, c: o.import_playlist(),
    ).register('playlist-panel-menu')

    menu.simple_separator('top-sep', after=['import-playlist']).register(
        'playlist-panel-menu'
    )


__create_playlist_panel_menus()


class PlaylistPanelMenu(menu.ProviderMenu):
    """
    Menu for xlgui.panel.playlists.PlaylistsPanel, for when the
    user does not click on a playlist/track.  The default menu.

    Provider key: playlist-panel-menu
    """

    def __init__(self, parent):
        menu.ProviderMenu.__init__(self, 'playlist-panel-menu', parent)


def __create_playlist_panel_playlist_menus():

    items = []

    items.append(menu.simple_separator('pp-top-sep', ['properties']))

    items.append(
        menuitems.RenamePlaylistMenuItem('rename-playlist', after=[items[-1].name])
    )
    items.append(
        menuitems.EditPlaylistMenuItem('edit-playlist', after=[items[-1].name])
    )
    items.append(
        menuitems.ExportPlaylistMenuItem('export-playlist', after=[items[-1].name])
    )
    items.append(
        menuitems.ExportPlaylistFilesMenuItem('export-files', after=[items[-1].name])
    )

    items.append(menu.simple_separator('pp-sep', after=[items[-1].name]))

    items.append(
        menuitems.DeletePlaylistMenuItem('delete-playlist', after=[items[-1].name])
    )

    for item in items:
        item.register('playlist-panel-context-menu')


__create_playlist_panel_playlist_menus()


class PlaylistsPanelPlaylistMenu(menu.MultiProviderMenu):
    """
    Context menu when a playlist is clicked

    Provider keys: playlist-panel-menu, track-panel-menu, playlist-panel-context-menu
    """

    def __init__(self, parent):
        menu.MultiProviderMenu.__init__(
            self,
            ['playlist-panel-menu', 'track-panel-menu', 'playlist-panel-context-menu'],
            parent,
        )

    def get_context(self):
        context = common.LazyDict(self._parent)
        context[
            'needs-computing'
        ] = lambda name, parent: parent.tree.get_selection_is_computed()
        context[
            'selected-playlist'
        ] = lambda name, parent: parent.tree.get_selected_page(raw=True)
        context[
            'selected-tracks'
        ] = lambda name, parent: parent.tree.get_selected_tracks()
        context[
            'selection-empty'
        ] = lambda name, parent: parent.tree.get_selection_empty()
        return context


### Radio panel menu


def __create_radio_panel_menus():

    # w, n, o, c: window, name, parent, context

    menu.simple_menu_item(
        'new-station',
        [],
        _('_New Station'),
        'list-add',
        lambda w, n, o, c: o._on_add_button_clicked(),
    ).register('radio-panel-menu')


__create_radio_panel_menus()


class RadioPanelPlaylistMenu(menu.MultiProviderMenu):
    """
    Context menu when a playlist is clicked
    """

    def __init__(self, parent):
        menu.MultiProviderMenu.__init__(
            self,
            ['radio-panel-menu', 'track-panel-menu', 'playlist-panel-context-menu'],
            parent,
        )

    def get_context(self):
        context = common.LazyDict(self._parent)
        context[
            'selected-playlist'
        ] = lambda name, parent: parent.tree.get_selected_page(raw=True)
        context[
            'selected-tracks'
        ] = lambda name, parent: parent.tree.get_selected_tracks()
        context[
            'selection-empty'
        ] = lambda name, parent: parent.tree.get_selection_empty()
        return context
