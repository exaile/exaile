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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
from xl import providers

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
        get_main().playlist_notebook.create_new_playlist()
    items.append(_smi('new-playlist', [], _("_New Playlist"), 'tab-new',
        new_playlist_cb, accelerator='<Control>t'))
    accelerators.append(Accelerator('<Control>t', new_playlist_cb))
    items.append(_sep('new-sep', [items[-1].name]))

    def open_cb(*args):
        dialog = dialogs.MediaOpenDialog(get_main().window)
        dialog.connect('uris-selected', lambda d, uris:
            get_main().controller.open_uris(uris))
        dialog.show()
    items.append(_smi('open', [items[-1].name], icon_name=gtk.STOCK_OPEN,
        callback=open_cb, accelerator='<Control>o'))
    accelerators.append(Accelerator('<Control>o', open_cb))

    def open_uri_cb(*args):
        dialog = dialogs.URIOpenDialog(get_main().window)
        dialog.connect('uri-selected', lambda d, uri:
            get_main().controller.open_uri(uri))
        dialog.show()
    items.append(_smi('open-uri', [items[-1].name], _("Open _URL"),
        'applications-internet', open_uri_cb, accelerator='<Control><Shift>o'))
    accelerators.append(Accelerator('<Control><Shift>o', open_uri_cb))

    def open_dirs_cb(*args):
        dialog = dialogs.DirectoryOpenDialog(get_main().window)
        dialog.props.create_folders = False
        dialog.connect('uris-selected', lambda d, uris:
            get_main().controller.open_uris(uris))
        dialog.show()
    items.append(_smi('open-dirs', [items[-1].name], _("Open Directories"),
        None, open_dirs_cb))

    items.append(_sep('open-sep', [items[-1].name]))

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
                main.message.show_info(message)
            elif message_type == gtk.MESSAGE_ERROR:
                main.message.show_error(_('Playlist export failed!'), message)
            return True
        dialog = dialogs.PlaylistExportDialog(page.playlist, main.window)
        dialog.connect('message', on_message)
        dialog.show()
    items.append(_smi('export-playlist', [items[-1].name],
        _("_Export Current Playlist"), 'gtk-save-as', export_playlist_cb))
    items.append(_sep('export-sep', [items[-1].name]))

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
    items.append(menu.simple_menu_item('quit-application', [items[-1].name],
        icon_name=gtk.STOCK_QUIT, callback=quit_cb, accelerator='<Control>q'))
    accelerators.append(Accelerator('<Control>q', quit_cb))

    for item in items:
        providers.register('menubar-file-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)

def __create_edit_menu():
    items = []
    for item in items:
        providers.register('menubar-edit-menu', item)

def __create_view_menu():
    items = []
    for item in items:
        providers.register('menubar-view-menu', item)

def __create_playlist_menu():
    items = []
    for item in items:
        providers.register('menubar-playlist-menu', item)

def __create_tools_menu():
    items = []
    for item in items:
        providers.register('menubar-tools-menu', item)

def __create_help_menu():
    items = []
    accelerators = []
    def show_about_dialog(widget, name, parent, context):
        dialog = dialogs.AboutDialog(parent.window)
        dialog.show()
    items.append(_smi('about', [], _("_About"), 'gtk-about', show_about_dialog))
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
