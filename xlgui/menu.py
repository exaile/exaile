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

_smi = menu.simple_menu_item
_sep = menu.simple_separator

def __create_file_menu():
    items = []
    accelerators = []
    def new_playlist_cb(*args):
        get_main().playlist_notebook.create_new_playlist()
    items.append(_smi('new-playlist', [], _("New Playlist"), 'tab-new', new_playlist_cb, accelerator='<Control>t'))
    accelerators.append(Accelerator('<Control>t', new_playlist_cb))
    for item in items:
        providers.register('menubar-file-menu', item)
    for accelerator in accelerators:
        providers.register('mainwindow-accelerators', accelerator)
__create_file_menu()

def __create_edit_menu():
    items = []
    for item in items:
        providers.register('menubar-edit-menu', item)
__create_edit_menu()

def __create_view_menu():
    items = []
    for item in items:
        providers.register('menubar-view-menu', item)
__create_view_menu()

def __create_playlist_menu():
    items = []
    for item in items:
        providers.register('menubar-playlist-menu', item)
__create_playlist_menu()

def __create_tools_menu():
    items = []
    for item in items:
        providers.register('menubar-tools-menu', item)
__create_tools_menu()

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
__create_help_menu()
