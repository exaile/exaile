# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from time import sleep

import xl
import xlgui

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk

from xl.common import threaded
from xl.nls import gettext as _
from xlgui.widgets import menu, dialogs

from _base import get_name, Logger
from _database import execute_delete
from _utils import get_icon

#: Logger: Logger to file
_LOGGER = Logger(__name__)

#: str
_CONTEXT_MENU_NAME = get_name('tree-view-menu')


@xl.common.threaded
def read_tags(tracks):
    """
        Threaded read tags notifying changes
        :param tracks: list
        :return:  None
    """
    for i in tracks:
        i.read_tags()
        sleep(0.055)


def append_to_playlist(tracks, replace=False):
    """
        Helper function to append to playlist
        :param tracks: list
        :param replace: bool
        :return: None
    """
    page = xlgui.main.get_selected_playlist()
    if not page:
        return

    pl = page.playlist

    if replace:
        pl.clear()

    offset = len(pl)

    pl.extend(tracks)

    if (xl.settings.get_option('playlist/append_menu_starts_playback', False) and
        not xl.player.PLAYER.current): page.view.play_track_at(offset, tracks[0]);

    read_tags(tracks)


def append(_widget, parent):
    """
        Append tracks menu item callback
        :param _widget: MenuItem
        :param parent: _panel.MainPanel
        :return: None
    """
    append_to_playlist(parent.tree.get_selected_tracks(), False)


def enqueue(_widget, parent):
    tracks = parent.tree.get_selected_tracks()
    xl.player.QUEUE.extend(tracks)
    read_tags(tracks)


def replace(_widget, parent):
    """
        Replace current menu item callback
        :param _widget: MenuItem
        :param parent: _panel.MainPanel
        :return: None
    """
    append_to_playlist(parent.tree.get_selected_tracks(), True)


def properties(_widget, parent):
    """
        Properties menu item callback
        :param _widget: MenuItem
        :param parent: _panel.MainPanel
        :return: None
    """
    tracks = parent.tree.get_selected_tracks(True)
    if tracks:
        xlgui.properties.TrackPropertiesDialog(None, tracks)
        read_tags(tracks)


def open_directory(_widget, parent):
    """
        Open directory menu item callback
        :param _widget: MenuItem
        :param parent: _panel.MainPanel
        :return: None
    """
    for i in parent.tree.yield_selected_tracks_uri():
        xl.common.open_file_directory(i)
        return


def trash_tracks(_widget, parent):
    """
        Trash tracks menu item callback
        :param _widget: MenuItem
        :param parent: _panel.MainPanel
        :return: None
    """
    tracks_path = set(parent.tree.yield_selected_tracks_uri())
    tracks_file = [Gio.File.new_for_path(i) for i in tracks_path]

    def delete_tracks_msg(message_type, text, secondary_text, delete_func, fallback):
        """

            :param message_type: Gtk.MessageType
            :param text: str
            :param secondary_text: str
            :param delete_func: func to be called on delete - receives gio_file as param
            :param fallback: a fallback function
            :return: None
        """
        if tracks_path:
            message = dialogs.MessageBar(
                parent=parent.tree_box,
                type=message_type,
                buttons=Gtk.ButtonsType.YES_NO,
                text=text % len(tracks_path)
            )

            if secondary_text:
                message.set_secondary_text(secondary_text)

            def on_response(widget, response):
                """
                    Treats user response for message bar
                    :param widget: MessageBar
                    :param response: Gtk.ResponseType
                    :return: None
                """
                if response == Gtk.ResponseType.YES:
                    for path, file in zip(tracks_path, tracks_file):
                        try:
                            connection = execute_delete(path)
                        except:
                            pass
                        else:
                            if connection:
                                try:
                                    delete_result = delete_func(file)
                                except GLib.GError:
                                    delete_result = False

                                if delete_result:
                                    connection.commit()

                                    tracks_path.remove(path)
                                    tracks_file.remove(file)
                                else:
                                    connection.rollback()

                                connection.close()

                    if tracks_path:
                        fallback()
                    else:
                        parent.tree.load()

                widget.destroy()

            message.connect('response', on_response)
            message.show()

    def error_msg():
        """
            Shows error message

            When cannot remove
            :return: None
        """
        if tracks_path:
            for i in tracks_path:
                _LOGGER.error('cannot remove file: %s', i)

            message = dialogs.MessageBar(
                parent=parent.tree_box,
                type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=_('%d tracks cannot be removed.') % len(tracks_path)
            )

            message.connect('response', lambda widget, _response: widget.destroy())
            message.show()

    delete_tracks_msg(
        Gtk.MessageType.QUESTION,
        _("Deleting %d tracks from library."),
        _('Proceed?'),
        lambda gio_file: gio_file.trash(),
        lambda:
            delete_tracks_msg(
                Gtk.MessageType.WARNING,
                _('%d tracks cannot be moved to Trash.'),
                _('Delete permanently from disk?'),
                lambda gio_file: gio_file.delete(),
                error_msg
            )
    )


class Menu(menu.Menu):
    """
        Context menu to tree view
    """
    def __init__(self, container):
        """
            Constructor
            :param container: _panel.MainPanel
        """
        menu.Menu.__init__(self, container)

        after = ['top-sep']

        def add_menu_item(func, text, icon):
            """
                Adds a menu item
                :param func: callback on activate fnc
                :param text: str
                :param icon: str or None - icon name
                :return: None
            """
            name = func.__name__

            def create(_menu, parent, _context):
                """

                    :param _menu: Menu
                    :param parent: _panel.MainPanel
                    :param _context: {}
                    :return: MenuItem
                """
                if icon:
                    menu_item = Gtk.ImageMenuItem.new_with_mnemonic(text)
                    menu_item.set_image(
                        Gtk.Image.new_from_pixbuf(
                            get_icon(icon, Gtk.IconSize.MENU)
                        )
                    )
                    menu_item.props.always_show_image = True
                else:
                    menu_item = Gtk.MenuItem.new_with_mnemonic(text)

                menu_item.connect('activate', func, parent)
                return menu_item

            self.add_item(menu.MenuItem(name, create, after=list(after)))
            after[0] = name

        separator = [0]

        def add_separator():
            """
                Adds a separator menu item
                :return: None
            """
            name = 'sep-' + str(separator[0])
            self.add_item(menu.simple_separator(name, list(after)))
            separator[0] += 1
            after[0] = name

        add_menu_item(enqueue, _("En_queue"), 'list-add')
        add_menu_item(append, _("_Append to Current"), 'list-add')
        add_menu_item(replace, _("_Replace Current"), None)
        add_separator()
        add_menu_item(properties, _("_Track Properties"), 'document-properties')
        add_separator()
        add_menu_item(open_directory, _("_Open Directory"), 'folder-open')
        add_menu_item(trash_tracks, _('_Move to Trash'), 'user-trash')
