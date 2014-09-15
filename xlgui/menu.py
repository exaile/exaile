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

import gtk

from xl.nls import gettext as _
from xl import settings, providers

from xlgui.accelerators import Accelerator
from xlgui.widgets import menu, menuitems, dialogs

def get_main():
    from xlgui import main
    return main.mainwindow()

def get_selected_playlist():
    from xlgui import main
    return main.get_selected_playlist()

_smi = menu.simple_menu_item
_sep = menu.simple_separator

def __create_file_menu():
    items = []
    accelerators = []

    def new_playlist_cb(*args):
        get_main().playlist_container.create_new_playlist()
    items.append(_smi('new-playlist', [], _("_New Playlist"), 'tab-new',
        new_playlist_cb, accelerator='<Control>t'))
    accelerators.append(Accelerator('<Control>t', new_playlist_cb))
    items.append(_sep('new-sep', [items[-1].name]))

    def open_cb(*args):
        dialog = dialogs.MediaOpenDialog(get_main().window)
        dialog.connect('uris-selected', lambda d, uris, ud:
            get_main().controller.open_uris(uris))
        dialog.show()
    items.append(_smi('open', [items[-1].name], icon_name=gtk.STOCK_OPEN,
        callback=open_cb, accelerator='<Control>o'))
    accelerators.append(Accelerator('<Control>o', open_cb))

    def open_uri_cb(*args):
        dialog = dialogs.URIOpenDialog(get_main().window)
        dialog.connect('uri-selected', lambda d, uri, ud:
            get_main().controller.open_uri(uri))
        dialog.show()
    items.append(_smi('open-uri', [items[-1].name], _("Open _URL"),
        'applications-internet', open_uri_cb, accelerator='<Control><Shift>o'))
    accelerators.append(Accelerator('<Control><Shift>o', open_uri_cb))

    def open_dirs_cb(*args):
        dialog = dialogs.DirectoryOpenDialog(get_main().window)
        dialog.props.create_folders = False
        dialog.connect('uris-selected', lambda d, uris, ud:
            get_main().controller.open_uris(uris))
        dialog.show()
    items.append(_smi('open-dirs', [items[-1].name], _("Open Directories"),
        None, open_dirs_cb))

    items.append(_sep('open-sep', [items[-1].name]))

    items.append(_smi('import-playlist', [items[-1].name],
        _("Import Playlist"), gtk.STOCK_OPEN, 
        lambda *e: get_main().controller.get_panel('playlists').import_playlist()
    ))
    
    def export_playlist_cb(*args):
        main = get_main()
        page = get_selected_playlist()
        if not page:
            return
        def on_message(dialog, message_type, message):
            """
                Show messages in the main window message area
            """
            if message_type == gtk.MESSAGE_INFO:
                main.message.show_info(markup=message)
            elif message_type == gtk.MESSAGE_ERROR:
                main.message.show_error(_('Playlist export failed!'), message)
            return True
        dialog = dialogs.PlaylistExportDialog(page.playlist, main.window)
        dialog.connect('message', on_message)
        dialog.show()
    items.append(_smi('export-playlist', [items[-1].name],
        _("_Export Current Playlist"), gtk.STOCK_SAVE_AS, export_playlist_cb))
    items.append(_sep('export-sep', [items[-1].name]))

    def close_tab_cb(*args):
        get_main().get_selected_page().tab.close()
    items.append(_smi('close-tab', [items[-1].name],
        _("Close Tab"), gtk.STOCK_CLOSE, callback=close_tab_cb,
        accelerator='<Control>w'))
    accelerators.append(Accelerator('<Control>w', close_tab_cb))


    if get_main().controller.exaile.options.Debug:
        def restart_cb(*args):
            from xl import main
            main.exaile().quit(True)
        items.append(_smi('restart-application', [items[-1].name], _("Restart"),
            callback=restart_cb, accelerator='<Control>r'))
        accelerators.append(Accelerator('<Control>r', restart_cb))

    def quit_cb(*args):
        from xl import main
        main.exaile().quit()
    items.append(_smi('quit-application', [items[-1].name],
        icon_name=gtk.STOCK_QUIT, callback=quit_cb, accelerator='<Control>q'))
    accelerators.append(Accelerator('<Control>q', quit_cb))

    for item in items:
        providers.register('menubar-file-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)

def __create_edit_menu():
    items = []
    accelerators = []

    def collection_manager_cb(*args):
        from xlgui import get_controller
        get_controller().collection_manager()
    items.append(_smi('collection-manager', [], _("_Collection"), None, collection_manager_cb))

    def queue_cb(*args):
        get_main().playlist_container.show_queue()
    items.append(_smi('queue', [items[-1].name], _("_Queue"),
        callback=queue_cb, accelerator='<Control>m'))
    accelerators.append(Accelerator('<Control>m', queue_cb))

    def cover_manager_cb(*args):
        from xlgui.cover import CoverManager
        dialog = CoverManager(get_main().window, get_main().collection)
    items.append(_smi('cover-manager', [items[-1].name], _("C_overs"), None, cover_manager_cb))

    def preferences_cb(*args):
        from xlgui.preferences import PreferencesDialog
        dialog = PreferencesDialog(get_main().window, get_main().controller)
        dialog.run()
    items.append(_smi('preferences', [items[-1].name],
        icon_name=gtk.STOCK_PREFERENCES, callback=preferences_cb))

    for item in items:
        providers.register('menubar-edit-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)

def __create_view_menu():
    items = []
    accelerators = []

    def show_playing_track_cb(*args):
        get_main().playlist_container.show_current_track()
    items.append(menuitems.ShowCurrentTrackMenuItem('show-playing-track', [],
        show_playing_track_cb, accelerator='<Control>j'))
    accelerators.append(Accelerator('<Control>j', show_playing_track_cb))

    items.append(_sep('show-playing-track-sep', [items[-1].name]))

    def playlist_utilities_cb(widget, name, parent, context):
        settings.set_option('gui/playlist_utilities_bar_visible',
            widget.get_active())
    def playlist_utilities_is_checked(name, parent, context):
        return settings.get_option('gui/playlist_utilities_bar_visible', True)
    items.append(menu.check_menu_item('playlist-utilities', [items[-1].name],
        _("_Playlist Utilities Bar"), playlist_utilities_is_checked, playlist_utilities_cb))

    items.append(_smi('columns', [items[-1].name], _('_Columns'),
        submenu=menu.ProviderMenu('playlist-columns-menu', get_main())))

    def clear_playlist_cb(*args):
        page = get_main().get_selected_page()
        if page:
            page.playlist.clear()
    items.append(_smi('clear-playlist', [items[-1].name], _('C_lear playlist'),
         gtk.STOCK_CLEAR, clear_playlist_cb, accelerator='<Control>l'))
    accelerators.append(Accelerator('<Control>l', clear_playlist_cb))

    for item in items:
        providers.register('menubar-view-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)

def __create_playlist_menu():
    items = []
    for item in items:
        providers.register('menubar-playlist-menu', item)

def __create_tools_menu():
    items = []
    items.append(_smi('device-manager', [], _('_Device Manager'),
        gtk.STOCK_HARDDISK, lambda *x: get_main().controller.show_devices()))
    
    items.append(_smi('scan-collection', [items[-1].name], _('Re_scan Collection'),
        gtk.STOCK_REFRESH, get_main().controller.on_rescan_collection))
    
    items.append(_smi('slow-scan-collection', [items[-1].name], _('Rescan Collection (slow)'),
        gtk.STOCK_REFRESH, get_main().controller.on_rescan_collection_forced))

    items.append(_smi('track-properties', [items[-1].name], _('Track _Properties'),
        gtk.STOCK_PROPERTIES, get_main().controller.on_track_properties))

    for item in items:
        providers.register('menubar-tools-menu', item)

def __create_help_menu():
    items = []
    accelerators = []
    def show_about_dialog(widget, name, parent, context):
        dialog = dialogs.AboutDialog(parent.window)
        dialog.show()
    items.append(_smi('about', [], icon_name=gtk.STOCK_ABOUT,
        callback=show_about_dialog))
    for item in items:
        providers.register('menubar-help-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)


def _create_menus():
    __create_file_menu()
    __create_edit_menu()
    __create_view_menu()
    __create_playlist_menu()
    __create_tools_menu()
    __create_help_menu()
