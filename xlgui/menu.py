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

from gi.repository import Gtk

import os.path
import webbrowser

from xl.nls import gettext as _
from xl import common, settings, providers, xdg

from xlgui.accelerators import Accelerator
from xlgui.widgets import menu, dialogs


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

    accelerators.append(Accelerator('<Primary>t', _("_New Playlist"), new_playlist_cb))
    items.append(
        _smi('new-playlist', [], icon_name='tab-new', callback=accelerators[-1])
    )
    items.append(_sep('new-sep', [items[-1].name]))

    def open_cb(*args):
        dialog = dialogs.MediaOpenDialog(get_main().window)
        dialog.connect(
            'uris-selected', lambda d, uris: get_main().controller.open_uris(uris)
        )
        dialog.show()

    accelerators.append(Accelerator('<Primary>o', _("_Open"), open_cb))
    items.append(
        _smi(
            'open',
            [items[-1].name],
            icon_name='document-open',
            callback=accelerators[-1],
        )
    )

    def open_uri_cb(*args):
        dialog = dialogs.URIOpenDialog(get_main().window)
        dialog.connect(
            'uri-selected', lambda d, uri: get_main().controller.open_uri(uri)
        )
        dialog.show()

    accelerators.append(Accelerator('<Primary><Shift>o', _("Open _URL"), open_uri_cb))
    items.append(
        _smi(
            'open-uri',
            [items[-1].name],
            icon_name='emblem-web',
            callback=accelerators[-1],
        )
    )

    def open_dirs_cb(*args):
        dialog = dialogs.DirectoryOpenDialog(get_main().window)
        dialog.props.create_folders = False
        dialog.connect(
            'uris-selected', lambda d, uris: get_main().controller.open_uris(uris)
        )
        dialog.show()

    items.append(
        _smi(
            'open-dirs',
            [items[-1].name],
            _("Open _Directories"),
            'folder-open',
            open_dirs_cb,
        )
    )

    items.append(_sep('open-sep', [items[-1].name]))

    items.append(
        _smi(
            'import-playlist',
            [items[-1].name],
            _("_Import Playlist"),
            'document-open',
            lambda *e: get_main().controller.get_panel('playlists').import_playlist(),
        )
    )

    def export_playlist_cb(*args):
        main = get_main()
        page = get_selected_playlist()
        if not page:
            return

        def on_message(dialog, message_type, message):
            """
            Show messages in the main window message area
            """
            if message_type == Gtk.MessageType.INFO:
                main.message.show_info(markup=message)
            elif message_type == Gtk.MessageType.ERROR:
                main.message.show_error(_('Playlist export failed!'), message)
            return True

        dialog = dialogs.PlaylistExportDialog(page.playlist, main.window)
        dialog.connect('message', on_message)
        dialog.show()

    items.append(
        _smi(
            'export-playlist',
            [items[-1].name],
            _("E_xport Current Playlist"),
            'document-save-as',
            export_playlist_cb,
        )
    )
    items.append(_sep('export-sep', [items[-1].name]))

    def close_tab_cb(*args):
        get_main().get_selected_page().tab.close()

    accelerators.append(Accelerator('<Primary>w', _("Close _Tab"), close_tab_cb))
    items.append(
        _smi(
            'close-tab',
            [items[-1].name],
            icon_name='window-close',
            callback=accelerators[-1],
        )
    )

    if get_main().controller.exaile.options.Debug:

        def restart_cb(*args):
            from xl import main

            main.exaile().quit(True)

        accelerators.append(Accelerator('<Primary>r', _("_Restart"), restart_cb))
        items.append(
            _smi('restart-application', [items[-1].name], callback=accelerators[-1])
        )

    def quit_cb(*args):
        from xl import main

        main.exaile().quit()

    accelerators.append(Accelerator('<Primary>q', _("_Quit Exaile"), quit_cb))
    items.append(
        _smi(
            'quit-application',
            [items[-1].name],
            icon_name='application-exit',
            callback=accelerators[-1],
        )
    )

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

    items.append(
        _smi('collection-manager', [], _("_Collection"), None, collection_manager_cb)
    )

    def queue_cb(*args):
        get_main().playlist_container.show_queue()

    accelerators.append(Accelerator('<Primary>m', _("_Queue"), queue_cb))
    items.append(_smi('queue', [items[-1].name], callback=accelerators[-1]))

    def cover_manager_cb(*args):
        from xlgui.cover import CoverManager

        CoverManager(get_main().window, get_main().collection)

    items.append(
        _smi(
            'cover-manager',
            [items[-1].name],
            _("C_overs"),
            'image-x-generic',
            cover_manager_cb,
        )
    )

    def preferences_cb(*args):
        from xlgui.preferences import PreferencesDialog

        dialog = PreferencesDialog(get_main().window, get_main().controller)
        dialog.run()

    items.append(
        _smi(
            'preferences',
            [items[-1].name],
            _("_Preferences"),
            'preferences-system',
            preferences_cb,
        )
    )

    for item in items:
        providers.register('menubar-edit-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)


def __create_view_menu():
    items = []
    accelerators = []

    def show_playing_track_cb(*args):
        get_main().playlist_container.show_current_track()

    def show_playing_track_sensitive():
        from xl import player

        return player.PLAYER.get_state() != 'stopped'

    accelerators.append(
        Accelerator('<Primary>j', _("_Show Playing Track"), show_playing_track_cb)
    )
    items.append(
        _smi(
            'show-playing-track',
            [],
            icon_name='go-jump',
            callback=accelerators[-1],
            sensitive_cb=show_playing_track_sensitive,
        )
    )

    items.append(_sep('show-playing-track-sep', [items[-1].name]))

    def playlist_utilities_cb(widget, name, parent, context):
        settings.set_option('gui/playlist_utilities_bar_visible', widget.get_active())

    def playlist_utilities_is_checked(name, parent, context):
        return settings.get_option('gui/playlist_utilities_bar_visible', True)

    items.append(
        menu.check_menu_item(
            'playlist-utilities',
            [items[-1].name],
            _("_Playlist Utilities Bar"),
            playlist_utilities_is_checked,
            playlist_utilities_cb,
        )
    )

    items.append(
        _smi(
            'columns',
            [items[-1].name],
            _('C_olumns'),
            submenu=menu.ProviderMenu('playlist-columns-menu', get_main()),
        )
    )

    def clear_playlist_cb(*args):
        page = get_main().get_selected_page()
        if page:
            page.playlist.clear()

    accelerators.append(
        Accelerator('<Primary>l', _('_Clear playlist'), clear_playlist_cb)
    )
    items.append(
        _smi(
            'clear-playlist',
            [items[-1].name],
            icon_name='edit-clear-all',
            callback=accelerators[-1],
        )
    )

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
    items.append(
        _smi(
            'device-manager',
            [],
            _('_Device Manager'),
            'multimedia-player',
            lambda *x: get_main().controller.show_devices(),
        )
    )

    items.append(
        _smi(
            'scan-collection',
            [items[-1].name],
            _('_Rescan Collection'),
            'view-refresh',
            get_main().controller.on_rescan_collection,
        )
    )

    items.append(
        _smi(
            'slow-scan-collection',
            [items[-1].name],
            _('Rescan Collection (_slow)'),
            'view-refresh',
            get_main().controller.on_rescan_collection_forced,
        )
    )

    for item in items:
        providers.register('menubar-tools-menu', item)


def __create_help_menu():
    items = []
    accelerators = []

    def show_logs_directory(*args):
        common.open_file_directory(os.path.join(xdg.get_logs_dir(), 'exaile.log'))

    def show_report_issue(*args):
        webbrowser.open('https://github.com/exaile/exaile/issues')

    def show_shortcuts(widget, name, parent, context):
        dialog = dialogs.ShortcutsDialog(parent.window)
        dialog.show()

    def show_user_guide(*args):
        # TODO: Other languages
        webbrowser.open('https://exaile.readthedocs.io/en/latest/user/index.html')

    def show_about_dialog(widget, name, parent, context):
        dialog = dialogs.AboutDialog(parent.window)
        dialog.show()

    items.append(
        _smi('guide', [], _("User's Guide (website)"), 'help-contents', show_user_guide)
    )
    items.append(
        _smi('shortcuts', [items[-1].name], _("Shortcuts"), None, show_shortcuts)
    )
    items.append(_sep('about-sep1', [items[-1].name]))
    items.append(
        _smi(
            'report',
            [items[-1].name],
            _("Report an issue (GitHub)"),
            None,
            show_report_issue,
        )
    )
    items.append(
        _smi('logs', [items[-1].name], _("Open error logs"), None, show_logs_directory)
    )
    items.append(_sep('about-sep2', [items[-1].name]))
    items.append(
        _smi('about', [items[-1].name], _("_About"), 'help-about', show_about_dialog)
    )
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
