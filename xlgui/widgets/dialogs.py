# Copyright (C) 2008-2010 Adam Olsen
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

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
import logging
from gi.repository import Pango
import os.path

from xl import metadata, providers, settings, xdg
from xl.common import clamp
from xl.playlist import (
    is_valid_playlist,
    import_playlist,
    export_playlist,
    InvalidPlaylistTypeError,
    PlaylistExportOptions,
)
from xl.nls import gettext as _

from xlgui.guiutil import GtkTemplate
from threading import Thread

logger = logging.getLogger(__name__)


def error(parent, message=None, markup=None):
    """
    Shows an error dialog
    """
    if message is markup is None:
        raise ValueError("message or markup must be specified")
    dialog = Gtk.MessageDialog(
        buttons=Gtk.ButtonsType.CLOSE,
        message_type=Gtk.MessageType.ERROR,
        modal=True,
        transient_for=parent,
    )
    if markup is None:
        dialog.props.text = message
    else:
        dialog.set_markup(markup)
    dialog.run()
    dialog.destroy()


def info(parent, message=None, markup=None):
    """
    Shows an info dialog
    """
    if message is markup is None:
        raise ValueError("message or markup must be specified")
    dialog = Gtk.MessageDialog(
        buttons=Gtk.ButtonsType.OK,
        message_type=Gtk.MessageType.INFO,
        modal=True,
        transient_for=parent,
    )
    if markup is None:
        dialog.props.text = message
    else:
        dialog.set_markup(markup)
    dialog.run()
    dialog.destroy()


def yesno(parent, message):
    '''Gets a Yes/No response from a user'''
    dlg = Gtk.MessageDialog(
        buttons=Gtk.ButtonsType.YES_NO,
        message_type=Gtk.MessageType.QUESTION,
        text=message,
        transient_for=parent,
    )
    response = dlg.run()
    dlg.destroy()
    return response


@GtkTemplate('ui', 'about_dialog.ui')
class AboutDialog(Gtk.AboutDialog):
    """
    A dialog showing program info and more
    """

    __gtype_name__ = 'AboutDialog'

    def __init__(self, parent=None):
        Gtk.AboutDialog.__init__(self)
        self.init_template()

        self.set_transient_for(parent)
        logo = GdkPixbuf.Pixbuf.new_from_file(
            xdg.get_data_path('images', 'exailelogo.png')
        )
        self.set_logo(logo)

        import xl.version

        self.set_version(xl.version.__version__)

        # The user may have changed the theme since startup.
        theme = Gtk.Settings.get_default().props.gtk_theme_name
        xl.version.__external_versions__["GTK+ theme"] = theme

        comments = []
        for name, version in sorted(xl.version.__external_versions__.items()):
            comments.append('%s: %s' % (name, version))

        self.set_comments('\n'.join(comments))

    def on_response(self, *_):
        self.destroy()


@GtkTemplate('ui', 'shortcuts_dialog.ui')
class ShortcutsDialog(Gtk.Dialog):
    """
    Shows information about registered shortcuts

    TODO: someday upgrade to Gtk.ShortcutsWindow when we require 3.20 as
          a minimum GTK version. This would also enable automatically
          localized (translated) accelerator names.
    """

    # doesn't work if we don't set the treeview here too..
    shortcuts_treeview, shortcuts_model = GtkTemplate.Child.widgets(2)

    __gtype_name__ = 'ShortcutsDialog'

    def __init__(self, parent=None):
        Gtk.Dialog.__init__(self)
        self.init_template()

        self.set_transient_for(parent)

        for a in sorted(
            providers.get('mainwindow-accelerators'),
            key=lambda a: ('%04d' % (a.key)) + a.name,
        ):
            self.shortcuts_model.append(
                (Gtk.accelerator_get_label(a.key, a.mods), a.helptext.replace('_', ''))
            )

    @GtkTemplate.Callback
    def on_close_clicked(self, widget):
        self.destroy()


class MultiTextEntryDialog(Gtk.Dialog):
    """
    Exactly like a TextEntryDialog, except it can contain multiple
    labels/fields.

    Instead of using GetValue, use GetValues.  It will return a list with
    the contents of the fields. Each field must be filled out or the dialog
    will not close.
    """

    def __init__(self, parent, title):
        Gtk.Dialog.__init__(self, title=title, transient_for=parent)

        self.__entry_area = Gtk.Grid()
        self.__entry_area.set_row_spacing(3)
        self.__entry_area.set_column_spacing(3)
        self.__entry_area.set_border_width(3)
        self.vbox.pack_start(self.__entry_area, True, True, 0)

        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.fields = []

    def add_field(self, label):
        """
        Adds a field and corresponding label

        :param label: the label to display
        :returns: the newly created entry
        :rtype: :class:`Gtk.Entry`
        """
        line_number = len(self.fields)

        label = Gtk.Label(label=label)
        label.set_xalign(0)
        self.__entry_area.attach(label, 0, line_number, 1, 1)

        entry = Gtk.Entry()
        entry.set_width_chars(30)
        entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, False)
        entry.connect('activate', lambda *e: self.response(Gtk.ResponseType.OK))
        self.__entry_area.attach(entry, 1, line_number, 1, 1)
        label.show()
        entry.show()

        self.fields.append(entry)

        return entry

    def get_values(self):
        """
        Returns a list of the values from the added fields
        """
        return [a.get_text() for a in self.fields]

    def run(self):
        """
        Shows the dialog, runs, hides, and returns
        """
        self.show_all()

        while True:
            response = Gtk.Dialog.run(self)

            if response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
                break

            if response == Gtk.ResponseType.OK:
                # Leave loop if all fields where filled
                if len(min([f.get_text() for f in self.fields])) > 0:
                    break

                # At least one field was not filled
                for field in self.fields:
                    if len(field.get_text()) > 0:
                        # Unset possible previous marks
                        field.set_icon_from_icon_name(
                            Gtk.EntryIconPosition.SECONDARY, None
                        )
                    else:
                        # Mark via warning
                        field.set_icon_from_icon_name(
                            Gtk.EntryIconPosition.SECONDARY, 'dialog-warning'
                        )
        self.hide()

        return response


class TextEntryDialog(Gtk.Dialog):
    """
    Shows a dialog with a single line of text
    """

    def __init__(
        self,
        message,
        title,
        default_text=None,
        parent=None,
        cancelbutton=None,
        okbutton=None,
    ):
        """
        Initializes the dialog
        """
        if not cancelbutton:
            cancelbutton = Gtk.STOCK_CANCEL
        if not okbutton:
            okbutton = Gtk.STOCK_OK
        Gtk.Dialog.__init__(
            self, title=title, transient_for=parent, destroy_with_parent=True
        )

        self.add_buttons(
            cancelbutton, Gtk.ResponseType.CANCEL, okbutton, Gtk.ResponseType.OK
        )

        label = Gtk.Label(label=message)
        label.set_xalign(0)
        self.vbox.set_border_width(5)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main.set_spacing(3)
        main.set_border_width(5)
        self.vbox.pack_start(main, True, True, 0)

        main.pack_start(label, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_width_chars(35)
        if default_text:
            self.entry.set_text(default_text)
        main.pack_start(self.entry, False, False, 0)

        self.entry.connect('activate', lambda e: self.response(Gtk.ResponseType.OK))

    def get_value(self):
        """
        Returns the text value
        """
        return self.entry.get_text()

    def set_value(self, value):
        """
        Sets the value of the text
        """
        self.entry.set_text(value)

    def run(self):
        self.show_all()
        response = Gtk.Dialog.run(self)
        self.hide()
        return response


class URIOpenDialog(TextEntryDialog):
    """
    A dialog specialized for opening an URI
    """

    __gsignals__ = {
        'uri-selected': (
            GObject.SignalFlags.RUN_LAST,
            GObject.TYPE_BOOLEAN,
            (GObject.TYPE_PYOBJECT,),
            GObject.signal_accumulator_true_handled,
        )
    }

    def __init__(self, parent=None):
        """
        :param parent: a parent window for modal operation or None
        :type parent: :class:`Gtk.Window`
        """
        TextEntryDialog.__init__(
            self, message=_('Enter the URL to open'), title=_('Open URL'), parent=parent
        )

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        self.connect('response', self.on_response)

    def run(self):
        """
        Show the dialog and block until it's closed.

        The dialog will be automatically destroyed on user response.
        To obtain the entered URI, handle the "uri-selected" signal.
        """
        self.show()
        response = TextEntryDialog.run(self)
        self.emit('response', response)

    def show(self):
        """
        Show the dialog and return immediately.

        The dialog will be automatically destroyed on user response.
        To obtain the entered URI, handle the "uri-selected" signal.
        """
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()

        if text is not None:
            f = Gio.File.new_for_uri(text)
            if f.get_uri_scheme():
                self.set_value(text)

        TextEntryDialog.show_all(self)

    def do_uri_selected(self, uri):
        """
        Destroys the dialog
        """
        self.destroy()

    def on_response(self, dialog, response):
        """
        Notifies about the selected URI
        """
        self.hide()

        if response == Gtk.ResponseType.OK:
            self.emit('uri-selected', self.get_value())

        # self.destroy()

    '''
        dialog = dialogs.TextEntryDialog(_('Enter the URL to open'),
        _('Open URL'))
        dialog.set_transient_for(self.main.window)
        dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()

        if text is not None:
            location = Gio.File.new_for_uri(text)

            if location.get_uri_scheme() is not None:
                dialog.set_value(text)

        result = dialog.run()
        dialog.hide()
        if result == Gtk.ResponseType.OK:
            url = dialog.get_value()
            self.open_uri(url, play=False)
    '''


class ListDialog(Gtk.Dialog):
    """
    Shows a dialog with a list of specified items

    Items must define a __str__ method, or be a string
    """

    def __init__(self, title, parent=None, multiple=False, write_only=False):
        """
        Initializes the dialog
        """
        Gtk.Dialog.__init__(self, title=title, transient_for=parent)

        self.vbox.set_border_width(5)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.model = Gtk.ListStore(object)
        self.list = Gtk.TreeView(model=self.model)
        self.list.set_headers_visible(False)
        self.list.connect(
            'row-activated', lambda *e: self.response(Gtk.ResponseType.OK)
        )
        scroll.add(self.list)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.vbox.pack_start(scroll, True, True, 0)

        if write_only:
            self.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        else:
            self.add_buttons(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK,
                Gtk.ResponseType.OK,
            )

        self.selection = self.list.get_selection()

        if multiple:
            self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        else:
            self.selection.set_mode(Gtk.SelectionMode.SINGLE)

        text = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn()
        col.pack_start(text, True)

        col.set_cell_data_func(text, self.cell_data_func)
        self.list.append_column(col)
        self.list.set_model(self.model)
        self.resize(400, 240)

    def get_items(self):
        """
        Returns the selected items
        """
        items = []
        check = self.selection.get_selected_rows()
        if not check:
            return None
        (model, paths) = check

        for path in paths:
            iter = self.model.get_iter(path)
            item = self.model.get_value(iter, 0)
            items.append(item)

        return items

    def run(self):
        self.show_all()
        result = Gtk.Dialog.run(self)
        self.hide()
        return result

    def set_items(self, items):
        """
        Sets the items
        """
        for item in items:
            self.model.append([item])

    def cell_data_func(self, column, cell, model, iter, user_data):
        """
        Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 0)
        cell.set_property('text', str(object))


# TODO: combine this and list dialog


class ListBox:
    """
    Represents a list box
    """

    def __init__(self, widget, rows=None):
        """
        Initializes the widget
        """
        self.list = widget
        self.store = Gtk.ListStore(str)
        widget.set_headers_visible(False)
        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn('', cell, text=0)
        self.list.append_column(col)
        self.rows = rows
        if not rows:
            self.rows = []

        if rows:
            for row in rows:
                self.store.append([row])

        self.list.set_model(self.store)

    def connect(self, signal, func, data=None):
        """
        Connects a signal to the underlying treeview
        """
        self.list.connect(signal, func, data)

    def append(self, row):
        """
        Appends a row to the list
        """
        self.rows.append(row)
        self.set_rows(self.rows)

    def remove(self, row):
        """
        Removes a row
        """
        try:
            index = self.rows.index(row)
        except ValueError:
            return
        path = (index,)
        iter = self.store.get_iter(path)
        self.store.remove(iter)
        del self.rows[index]

    def set_rows(self, rows):
        """
        Sets the rows
        """
        self.rows = rows
        self.store = Gtk.ListStore(str)
        for row in rows:
            self.store.append([row])

        self.list.set_model(self.store)

    def get_selection(self):
        """
        Returns the selection
        """
        selection = self.list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return None
        return model.get_value(iter, 0)


class FileOperationDialog(Gtk.FileChooserDialog):
    """
    An extension of the Gtk.FileChooserDialog that
    adds a collapsable panel to the bottom listing
    valid file extensions that the file can be
    saved in. (similar to the one in GIMP)
    """

    def __init__(
        self,
        title=None,
        parent=None,
        action=Gtk.FileChooserAction.OPEN,
        buttons=None,
        backend=None,
    ):
        """
        Standard __init__ of the Gtk.FileChooserDialog.
        Also sets up the expander and list for extensions
        """
        Gtk.FileChooserDialog.__init__(self, title, parent, action, buttons, backend)

        self.set_do_overwrite_confirmation(True)

        # Container for additional option widgets
        self.extras_box = Gtk.Box(spacing=3, orientation=Gtk.Orientation.VERTICAL)
        self.set_extra_widget(self.extras_box)
        self.extras_box.show()

        # Create the list that will hold the file type/extensions pair
        self.liststore = Gtk.ListStore(str, str)
        self.list = Gtk.TreeView(self.liststore)
        self.list.set_headers_visible(False)

        # Create the columns
        filetype_cell = Gtk.CellRendererText()
        extension_cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn()
        column.pack_start(filetype_cell, True)
        column.pack_start(extension_cell, False)
        column.set_attributes(filetype_cell, text=0)
        column.set_attributes(extension_cell, text=1)

        self.list.append_column(column)
        self.list.show_all()

        self.expander = Gtk.Expander.new(_('Select File Type (by Extension)'))
        self.expander.add(self.list)
        self.extras_box.pack_start(self.expander, False, False, 0)
        self.expander.show()

        selection = self.list.get_selection()
        selection.connect('changed', self.on_selection_changed)

    def on_selection_changed(self, selection):
        """
        When the user selects an extension the filename
        that is entered will have its extension changed
        to the selected extension
        """
        model, iter = selection.get_selected()
        (extension,) = model.get(iter, 1)
        filename = ""
        if self.get_filename():
            filename = os.path.basename(self.get_filename())
            filename, old_extension = os.path.splitext(filename)
            filename += '.' + extension
        else:
            filename = '*.' + extension
        self.set_current_name(filename)

    def add_extensions(self, extensions):
        """
        Adds extensions to the list

        @param extensions: a dictionary of extension:file type pairs
        i.e. { 'm3u':'M3U Playlist' }
        """
        for key, value in extensions.items():
            self.liststore.append((value, key))


class MediaOpenDialog(Gtk.FileChooserDialog):
    """
    A dialog for opening general media
    """

    __gsignals__ = {
        'uris-selected': (
            GObject.SignalFlags.RUN_LAST,
            GObject.TYPE_BOOLEAN,
            (GObject.TYPE_PYOBJECT,),
            GObject.signal_accumulator_true_handled,
        )
    }
    _last_location = None

    def __init__(self, parent=None):
        """
        :param parent: a parent window for modal operation or None
        :type parent: :class:`Gtk.Window`
        """
        Gtk.FileChooserDialog.__init__(
            self,
            title=_('Choose Media to Open'),
            parent=parent,
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
            ),
        )

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_local_only(False)
        self.set_select_multiple(True)

        supported_filter = Gtk.FileFilter()
        supported_filter.set_name(_('Supported Files'))
        audio_filter = Gtk.FileFilter()
        audio_filter.set_name(_('Music Files'))
        playlist_filter = Gtk.FileFilter()
        playlist_filter.set_name(_('Playlist Files'))
        all_filter = Gtk.FileFilter()
        all_filter.set_name(_('All Files'))
        all_filter.add_pattern('*')

        for extension in metadata.formats.keys():
            pattern = '*.%s' % extension
            supported_filter.add_pattern(pattern)
            audio_filter.add_pattern(pattern)

        playlist_file_extensions = (
            ext
            for p in providers.get('playlist-format-converter')
            for ext in p.file_extensions
        )

        for extension in playlist_file_extensions:
            pattern = '*.%s' % extension
            supported_filter.add_pattern(pattern)
            playlist_filter.add_pattern(pattern)

        self.add_filter(supported_filter)
        self.add_filter(audio_filter)
        self.add_filter(playlist_filter)
        self.add_filter(all_filter)

        self.connect('response', self.on_response)

    def run(self):
        """
        Override to take care of the response
        """
        if MediaOpenDialog._last_location is not None:
            self.set_current_folder_uri(MediaOpenDialog._last_location)

        response = Gtk.FileChooserDialog.run(self)
        self.emit('response', response)

    def show(self):
        """
        Override to restore last location
        """
        if MediaOpenDialog._last_location is not None:
            self.set_current_folder_uri(MediaOpenDialog._last_location)

        Gtk.FileChooserDialog.show(self)

    def do_uris_selected(self, uris):
        """
        Destroys the dialog
        """
        self.destroy()

    def on_response(self, dialog, response):
        """
        Notifies about selected URIs
        """
        self.hide()

        if response == Gtk.ResponseType.OK:
            MediaOpenDialog._last_location = self.get_current_folder_uri()
            self.emit('uris-selected', self.get_uris())

        # self.destroy()


class DirectoryOpenDialog(Gtk.FileChooserDialog):
    """
    A dialog specialized for opening directories
    """

    __gsignals__ = {
        'uris-selected': (
            GObject.SignalFlags.RUN_LAST,
            GObject.TYPE_BOOLEAN,
            (GObject.TYPE_PYOBJECT,),
            GObject.signal_accumulator_true_handled,
        )
    }
    _last_location = None

    def __init__(
        self, parent=None, title=_('Choose Directory to Open'), select_multiple=True
    ):
        Gtk.FileChooserDialog.__init__(
            self,
            title,
            parent=parent,
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
            ),
        )

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
        self.set_local_only(False)
        self.set_select_multiple(select_multiple)

        self.connect('response', self.on_response)

    def run(self):
        """
        Override to take care of the response
        """
        if DirectoryOpenDialog._last_location is not None:
            self.set_current_folder_uri(DirectoryOpenDialog._last_location)

        Gtk.FileChooserDialog.run(self)

    def show(self):
        """
        Override to restore last location
        """
        if DirectoryOpenDialog._last_location is not None:
            self.set_current_folder_uri(DirectoryOpenDialog._last_location)

        Gtk.FileChooserDialog.show(self)

    def do_uris_selected(self, uris):
        """
        Destroys the dialog
        """
        self.destroy()

    def on_response(self, dialog, response):
        """
        Notifies about selected URIs
        """
        self.hide()

        if response == Gtk.ResponseType.OK:
            DirectoryOpenDialog._last_location = self.get_current_folder_uri()
            self.emit('uris-selected', self.get_uris())

        # self.destroy()


class PlaylistImportDialog(Gtk.FileChooserDialog):
    """
    A dialog for importing a playlist
    """

    __gsignals__ = {
        'playlists-selected': (
            GObject.SignalFlags.RUN_LAST,
            GObject.TYPE_BOOLEAN,
            (GObject.TYPE_PYOBJECT,),
            GObject.signal_accumulator_true_handled,
        )
    }
    _last_location = None

    def __init__(self, parent=None):
        """
        :param parent: a parent window for modal operation or None
        :type parent: :class:`Gtk.Window`
        """
        Gtk.FileChooserDialog.__init__(
            self,
            title=_('Import Playlist'),
            parent=parent,
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN,
                Gtk.ResponseType.OK,
            ),
        )

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_local_only(False)
        self.set_select_multiple(True)

        playlist_filter = Gtk.FileFilter()
        playlist_filter.set_name(_('Playlist Files'))
        all_filter = Gtk.FileFilter()
        all_filter.set_name(_('All Files'))
        all_filter.add_pattern('*')

        playlist_file_extensions = (
            ext
            for p in providers.get('playlist-format-converter')
            for ext in p.file_extensions
        )

        for extension in playlist_file_extensions:
            pattern = '*.%s' % extension
            playlist_filter.add_pattern(pattern)

        self.add_filter(playlist_filter)
        self.add_filter(all_filter)

        self.connect('response', self.on_response)

    def run(self):
        """
        Override to take care of the response
        """
        if PlaylistImportDialog._last_location is not None:
            self.set_current_folder_uri(PlaylistImportDialog._last_location)

        response = Gtk.FileChooserDialog.run(self)
        self.emit('response', response)

    def show(self):
        """
        Override to restore last location
        """
        if PlaylistImportDialog._last_location is not None:
            self.set_current_folder_uri(PlaylistImportDialog._last_location)

        Gtk.FileChooserDialog.show(self)

    def do_playlist_selected(self, uris):
        """
        Destroys the dialog
        """
        self.destroy()

    def on_response(self, dialog, response):
        """
        Notifies about selected URIs
        """
        self.hide()

        if response == Gtk.ResponseType.OK:
            PlaylistImportDialog._last_location = self.get_current_folder_uri()

            playlists = []
            for uri in self.get_uris():
                try:
                    playlists.append(import_playlist(uri))
                except InvalidPlaylistTypeError as e:
                    error(
                        self.get_transient_for(), 'Invalid playlist "%s": %s' % (uri, e)
                    )
                    self.destroy()
                    return
                except Exception as e:
                    error(
                        self.get_transient_for(),
                        'Invalid playlist "%s": (internal error): %s' % (uri, e),
                    )
                    self.destroy()
                    return

            self.emit('playlists-selected', playlists)

        # self.destroy()


class PlaylistExportDialog(FileOperationDialog):
    """
    A dialog specialized for playlist export
    """

    __gsignals__ = {
        'message': (
            GObject.SignalFlags.RUN_LAST,
            GObject.TYPE_BOOLEAN,
            (Gtk.MessageType, GObject.TYPE_STRING),
            GObject.signal_accumulator_true_handled,
        )
    }

    def __init__(self, playlist, parent=None):
        """
        :param playlist: the playlist to export
        :type playlist: :class:`xl.playlist.Playlist`
        :param parent: a parent window for modal operation or None
        :type parent: :class:`Gtk.Window`
        """
        FileOperationDialog.__init__(
            self,
            title=_('Export Current Playlist'),
            parent=parent,
            action=Gtk.FileChooserAction.SAVE,
            buttons=(
                Gtk.STOCK_CANCEL,
                Gtk.ResponseType.CANCEL,
                Gtk.STOCK_SAVE,
                Gtk.ResponseType.OK,
            ),
        )

        self.set_current_folder_uri(
            settings.get_option('gui/playlist_export_dir')
            or GLib.filename_to_uri(xdg.homedir, None)
        )

        self.set_local_only(False)

        self.relative_checkbox = Gtk.CheckButton(_('Use relative paths to tracks'))
        self.relative_checkbox.set_active(True)
        self.extras_box.pack_start(self.relative_checkbox, False, False, 3)
        self.relative_checkbox.show()

        self.playlist = playlist

        extensions = {}

        for provider in providers.get('playlist-format-converter'):
            extensions[provider.name] = provider.title

        self.add_extensions(extensions)
        self.set_current_name('%s.m3u' % playlist.name)

        self.connect('response', self.on_response)

    def run(self):
        """
        Override to take care of the response
        """
        response = FileOperationDialog.run(self)
        self.emit('response', response)

    def do_message(self, message_type, message):
        """
        Displays simple dialogs on messages
        """
        if message_type == Gtk.MessageType.INFO:
            info(self.get_transient_for(), markup=message)
        elif message_type == Gtk.MessageType.ERROR:
            error(self.get_transient_for(), markup=message)

    def on_response(self, dialog, response):
        """
        Exports the playlist if requested
        """
        self.hide()

        if response == Gtk.ResponseType.OK:
            gfile = self.get_file()
            settings.set_option('gui/playlist_export_dir', gfile.get_parent().get_uri())

            path = gfile.get_uri()
            if not is_valid_playlist(path):
                path = '%s.m3u' % path

            options = PlaylistExportOptions(
                relative=self.relative_checkbox.get_active()
            )

            try:
                export_playlist(self.playlist, path, options)
            except InvalidPlaylistTypeError as e:
                self.emit('message', Gtk.MessageType.ERROR, str(e))
            else:
                self.emit(
                    'message',
                    Gtk.MessageType.INFO,
                    _('Playlist saved as <b>%s</b>.') % path,
                )

        # self.destroy()


class ConfirmCloseDialog(Gtk.MessageDialog):
    """
    Shows the dialog to confirm closing of the playlist
    """

    def __init__(self, document_name):
        """
        Initializes the dialog
        """
        Gtk.MessageDialog.__init__(self, type=Gtk.MessageType.WARNING)

        self.set_title(_('Close %s' % document_name))
        self.set_markup(_('<b>Save changes to %s before closing?</b>') % document_name)
        self.format_secondary_text(
            _('Your changes will be lost if you don\'t save them')
        )

        self.add_buttons(
            _('Close Without Saving'),
            100,
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE,
            110,
        )

    def run(self):
        self.show_all()
        response = Gtk.Dialog.run(self)
        self.hide()
        return response


class MessageBar(Gtk.InfoBar):
    type_map = {
        Gtk.MessageType.INFO: 'dialog-information',
        Gtk.MessageType.QUESTION: 'dialog-question',
        Gtk.MessageType.WARNING: 'dialog-warning',
        Gtk.MessageType.ERROR: 'dialog-error',
    }
    buttons_map = {
        Gtk.ButtonsType.OK: [(Gtk.STOCK_OK, Gtk.ResponseType.OK)],
        Gtk.ButtonsType.CLOSE: [(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)],
        Gtk.ButtonsType.CANCEL: [(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)],
        Gtk.ButtonsType.YES_NO: [
            (Gtk.STOCK_NO, Gtk.ResponseType.NO),
            (Gtk.STOCK_YES, Gtk.ResponseType.YES),
        ],
        Gtk.ButtonsType.OK_CANCEL: [
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL),
            (Gtk.STOCK_OK, Gtk.ResponseType.OK),
        ],
    }

    def __init__(
        self,
        parent=None,
        type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.NONE,
        text=None,
    ):
        """
        Report important messages to the user

        :param parent: the parent container box
        :type parent: :class:`Gtk.Box`
        :param type: the type of message: Gtk.MessageType.INFO,
            Gtk.MessageType.WARNING, Gtk.MessageType.QUESTION or
            Gtk.MessageType.ERROR.
        :param buttons: the predefined set of buttons to
            use: Gtk.ButtonsType.NONE, Gtk.ButtonsType.OK,
            Gtk.ButtonsType.CLOSE, Gtk.ButtonsType.CANCEL,
            Gtk.ButtonsType.YES_NO, Gtk.ButtonsType.OK_CANCEL
        :param text: a string containing the message
            text or None
        """
        if parent is not None and not isinstance(parent, Gtk.Box):
            raise TypeError('Parent needs to be of type Gtk.Box')

        Gtk.InfoBar.__init__(self)
        self.set_no_show_all(True)

        if parent is not None:
            parent.add(self)
            parent.reorder_child(self, 0)
            parent.child_set_property(self, 'expand', False)

        self.image = Gtk.Image()
        self.set_message_type(type)

        self.primary_text = Gtk.Label(label=text)
        self.primary_text.set_property('xalign', 0)
        self.primary_text.set_line_wrap(True)
        self.secondary_text = Gtk.Label()
        self.secondary_text.set_property('xalign', 0)
        self.secondary_text.set_line_wrap(True)
        self.secondary_text.set_no_show_all(True)
        self.secondary_text.set_selectable(True)

        self.message_area = Gtk.Box(spacing=12, orientation=Gtk.Orientation.VERTICAL)
        self.message_area.pack_start(self.primary_text, False, False, 0)
        self.message_area.pack_start(self.secondary_text, False, False, 0)

        box = Gtk.Box(spacing=6)
        box.pack_start(self.image, False, True, 0)
        box.pack_start(self.message_area, True, True, 0)

        content_area = self.get_content_area()
        content_area.add(box)
        content_area.show_all()

        self.action_area = self.get_action_area()
        self.action_area.set_property('layout-style', Gtk.ButtonBoxStyle.START)

        if buttons != Gtk.ButtonsType.NONE:
            for text, response in self.buttons_map[buttons]:
                self.add_button(text, response)

        self.primary_text_attributes = Pango.AttrList()
        # TODO: GI: Pango attr
        # self.primary_text_attributes.insert(
        #    Pango.AttrWeight(Pango.Weight.NORMAL, 0, -1))
        # self.primary_text_attributes.insert(
        #    Pango.AttrScale(Pango.SCALE_MEDIUM, 0, -1))'''

        self.primary_text_emphasized_attributes = Pango.AttrList()
        # TODO: GI: Pango attr
        # self.primary_text_emphasized_attributes.insert(
        #    Pango.AttrWeight(Pango.Weight.BOLD, 0, -1))
        # self.primary_text_emphasized_attributes.insert(
        #    Pango.AttrScale(Pango.SCALE_LARGE, 0, -1))'''

        self.connect('response', self.on_response)

        # Workaround for https://bugzilla.gnome.org/show_bug.cgi?id=710888
        # -> From pitivi: https://phabricator.freedesktop.org/D1103#34aa2703
        def _make_sure_revealer_does_nothing(widget):
            if not isinstance(widget, Gtk.Revealer):
                return
            widget.set_transition_type(Gtk.RevealerTransitionType.NONE)

        self.forall(_make_sure_revealer_does_nothing)

    def set_text(self, text):
        """
        Sets the primary text of the message bar

        :param markup: a regular text string
        :type markup: string
        """
        self.primary_text.set_text(text)

    def set_markup(self, markup):
        """
        Sets the primary markup text of the message bar

        :param markup: a markup string
        :type markup: string
        """
        self.primary_text.set_markup(markup)

    def set_secondary_text(self, text):
        """
        Sets the secondary text to the text
        specified by message_format

        :param text: The text to be displayed
            as the secondary text or None.
        :type text: string
        """
        if text is None:
            self.secondary_text.hide()
            self.primary_text.set_attributes(self.primary_text_attributes)
        else:
            self.secondary_text.set_text(text)
            self.secondary_text.show()
            self.primary_text.set_attributes(self.primary_text_emphasized_attributes)

    def set_secondary_markup(self, markup):
        """
        Sets the secondary text to the markup text
        specified by text.

        :param text: A string containing the
            pango markup to use as secondary text.
        :type text: string
        """
        if markup is None:
            self.secondary_text.hide()
            self.primary_text.set_attributes(self.primary_text_attributes)
        else:
            self.secondary_text.set_markup(markup)
            self.secondary_text.show()
            self.primary_text.set_attributes(self.primary_text_emphasized_attributes)

    def set_image(self, image):
        """
        Sets the contained image to the :class:`Gtk.Widget`
        specified by image.

        :param image: the image widget
        :type image: :class:`Gtk.Widget`
        """
        box = self.image.get_parent()
        box.remove(self.image)
        self.image = image
        box.pack_start(self.image, False, True, 0)
        box.reorder_child(self.image, 0)
        self.image.show()

    def get_image(self):
        """
        Gets the contained image
        """
        return self.image

    def add_button(self, button_text, response_id):
        """
        Overrides :class:`Gtk.InfoBar` to prepend
        instead of append to the action area

        :param button_text: text of button, or stock ID
        :type button_text: string
        :param response_id: response ID for the button
        :type response_id: int
        """
        button = Gtk.InfoBar.add_button(self, button_text, response_id)
        self.action_area.reorder_child(button, 0)

        return button

    def clear_buttons(self):
        """
        Removes all buttons currently
        placed in the action area
        """
        for button in self.action_area:
            self.action_area.remove(button)

    def set_message_type(self, type):
        """
        Sets the message type of the message area.

        :param type: the type of message: Gtk.MessageType.INFO,
            Gtk.MessageType.WARNING, Gtk.MessageType.QUESTION or
            Gtk.MessageType.ERROR.
        """
        if type != Gtk.MessageType.OTHER:
            self.image.set_from_icon_name(self.type_map[type], Gtk.IconSize.DIALOG)

        Gtk.InfoBar.set_message_type(self, type)

    def get_message_area(self):
        """
        Retrieves the message area
        """
        return self.message_area

    def _show_message(
        self, message_type, text, secondary_text, markup, secondary_markup, timeout
    ):
        """
        Helper for the various `show_*` methods. See `show_info` for
        documentation on the parameters.
        """
        if text is markup is None:
            raise ValueError("text or markup must be specified")

        self.set_message_type(message_type)
        if markup is None:
            self.set_text(text)
        else:
            self.set_markup(markup)
        if secondary_markup is None:
            self.set_secondary_text(secondary_text)
        else:
            self.set_secondary_markup(secondary_markup)
        self.show()

        if timeout > 0:
            GLib.timeout_add_seconds(timeout, self.hide)

    def show_info(
        self,
        text=None,
        secondary_text=None,
        markup=None,
        secondary_markup=None,
        timeout=5,
    ):
        """
        Convenience method which sets all
        required flags for an info message

        :param text: the message to display
        :type text: string
        :param secondary_text: additional information
        :type secondary_text: string
        :param markup: the message to display, in Pango markup format
            (overrides `text`)
        :type markup: string
        :param secondary_markup: additional information, in Pango markup
            format (overrides `secondary_text`)
        :type secondary_markup: string
        :param timeout: after how many seconds the
            message should be hidden automatically,
            use 0 to disable this behavior
        :type timeout: int
        """
        self._show_message(
            Gtk.MessageType.INFO,
            text,
            secondary_text,
            markup,
            secondary_markup,
            timeout,
        )

    def show_question(
        self, text=None, secondary_text=None, markup=None, secondary_markup=None
    ):
        """
        Convenience method which sets all
        required flags for a question message

        :param text: the message to display
        :param secondary_text: additional information
        :param markup: the message to display, in Pango markup format
        :param secondary_markup: additional information, in Pango markup format
        """
        self._show_message(
            Gtk.MessageType.QUESTION, text, secondary_text, markup, secondary_markup, 0
        )

    def show_warning(
        self, text=None, secondary_text=None, markup=None, secondary_markup=None
    ):
        """
        Convenience method which sets all
        required flags for a warning message

        :param text: the message to display
        :param secondary_text: additional information
        :param markup: the message to display, in Pango markup format
        :param secondary_markup: additional information, in Pango markup format
        """
        self._show_message(
            Gtk.MessageType.WARNING, text, secondary_text, markup, secondary_markup, 0
        )

    def show_error(
        self, text=None, secondary_text=None, markup=None, secondary_markup=None
    ):
        """
        Convenience method which sets all
        required flags for a warning message

        :param text: the message to display
        :param secondary_text: additional information
        :param markup: the message to display, in Pango markup format
        :param secondary_markup: additional information, in Pango markup format
        """
        self._show_message(
            Gtk.MessageType.ERROR, text, secondary_text, markup, secondary_markup, 0
        )

    def on_response(self, widget, response):
        """
        Handles the response for closing
        """
        if response == Gtk.ResponseType.CLOSE:
            self.hide()


#
# Message ID's used by the XMessageDialog
#

XRESPONSE_YES = Gtk.ResponseType.YES
XRESPONSE_YES_ALL = 8000
XRESPONSE_NO = Gtk.ResponseType.NO
XRESPONSE_NO_ALL = 8001
XRESPONSE_CANCEL = Gtk.ResponseType.CANCEL


class XMessageDialog(Gtk.Dialog):
    '''Used to show a custom message dialog with custom buttons'''

    def __init__(
        self,
        title,
        text,
        parent=None,
        show_yes=True,
        show_yes_all=True,
        show_no=True,
        show_no_all=True,
        show_cancel=True,
    ):

        Gtk.Dialog.__init__(self, title=title, transient_for=parent)

        #
        # TODO: Make these buttons a bit prettier
        #

        if show_yes:
            self.add_button(Gtk.STOCK_YES, XRESPONSE_YES)
            self.set_default_response(XRESPONSE_YES)

        if show_yes_all:
            self.add_button(_('Yes to all'), XRESPONSE_YES_ALL)
            self.set_default_response(XRESPONSE_YES_ALL)

        if show_no:
            self.add_button(Gtk.STOCK_NO, XRESPONSE_NO)
            self.set_default_response(XRESPONSE_NO)

        if show_no_all:
            self.add_button(_('No to all'), XRESPONSE_NO_ALL)
            self.set_default_response(XRESPONSE_NO_ALL)

        if show_cancel:
            self.add_button(Gtk.STOCK_CANCEL, XRESPONSE_CANCEL)
            self.set_default_response(XRESPONSE_CANCEL)

        vbox = self.get_content_area()
        self._label = Gtk.Label()
        self._label.set_use_markup(True)
        self._label.set_markup(text)
        vbox.pack_start(self._label, True, True, 0)


class FileCopyDialog(Gtk.Dialog):
    """
    Used to copy a list of files to a single destination directory

    Usage:
        dialog = FileCopyDialog( [file_uri,..], destination_uri, text, parent)
        dialog.do_copy()

    Do not use run() on this dialog!
    """

    class CopyThread(Thread):
        def __init__(self, source, dest, callback_finish_single_copy, copy_flags):
            Thread.__init__(self, name='CopyThread')
            self.__source = source
            self.__dest = dest
            self.__cb_single_copy = callback_finish_single_copy
            self.__copy_flags = copy_flags
            self.__cancel = Gio.Cancellable()
            self.start()

        def run(self):
            try:
                result = self.__source.copy(
                    self.__dest, flags=self.__copy_flags, cancellable=self.__cancel
                )
                GLib.idle_add(self.__cb_single_copy, self.__source, result, None)
            except GLib.Error as err:
                GLib.idle_add(self.__cb_single_copy, self.__source, False, err)

        def cancel_copy(self):
            self.__cancel.cancel()

    def __init__(
        self,
        file_uris,
        destination_uri,
        title,
        text=_("Saved %(count)s of %(total)s."),
        parent=None,
    ):

        self.file_uris = file_uris
        self.destination_uri = destination_uri
        self.is_copying = False

        Gtk.Dialog.__init__(self, title=title, transient_for=parent)

        self.parent = parent
        self.count = 0
        self.total = len(file_uris)
        self.text = text
        self.overwrite_response = None

        # self.set_modal(True)
        # self.set_decorated(False)
        self.set_resizable(False)
        # self.set_focus_on_map(False)

        vbox = self.get_content_area()

        vbox.set_spacing(12)
        vbox.set_border_width(12)

        self._label = Gtk.Label()
        self._label.set_use_markup(True)
        self._label.set_markup(self.text % {'count': 0, 'total': self.total})
        vbox.pack_start(self._label, True, True, 0)

        self._progress = Gtk.ProgressBar()
        self._progress.set_size_request(300, -1)
        vbox.pack_start(self._progress, True, True, 0)

        self.show_all()

        # TODO: Make dialog cancelable
        # self.cancel_button.connect('activate', lambda *e: self.cancel.cancel() )

        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

    def do_copy(self):
        logger.info("Copy started.")
        self._start_next_copy()
        self.show_all()
        self.connect('response', self._on_response)

    def run(self):
        raise NotImplementedError("Don't use this")

    def _on_response(self, widget, response):
        logger.info("Copy complete.")
        self.destroy()

    def _step(self):
        '''Steps the progress bar'''
        self.count += 1
        self._progress.set_fraction(clamp(self.count / float(self.total), 0, 1))
        self._label.set_markup(self.text % {'count': self.count, 'total': self.total})

    def _start_next_copy(self, overwrite=False):

        if self.count == len(self.file_uris):
            self.response(Gtk.ResponseType.OK)
            return

        flags = Gio.FileCopyFlags.NONE

        src_uri = self.file_uris[self.count]
        dst_uri = self.destination_uri + '/' + src_uri.split('/')[-1]

        self.source = Gio.File.new_for_uri(src_uri)
        self.destination = Gio.File.new_for_uri(dst_uri)

        if not overwrite:
            if self.destination.query_exists(None):
                if self.overwrite_response == XRESPONSE_YES_ALL:
                    overwrite = True

                elif (
                    self.overwrite_response == XRESPONSE_NO_ALL
                    or self.overwrite_response == XRESPONSE_NO
                ):

                    # only deny the overwrite once..
                    if self.overwrite_response == XRESPONSE_NO:
                        self.overwrite_response = None

                    logging.info("NoOverwrite: %s" % self.destination.get_uri())
                    self._step()
                    GLib.idle_add(self._start_next_copy)  # don't recurse
                    return
                else:
                    self._query_overwrite()
                    return

        if overwrite:
            flags = Gio.FileCopyFlags.OVERWRITE
            try:
                # Gio.FileCopyFlags.OVERWRITE doesn't actually work
                logging.info("DeleteDest : %s" % self.destination.get_uri())
                self.destination.delete()
            except GLib.Error:
                pass

        logging.info("CopySource : %s" % self.source.get_uri())
        logging.info("CopyDest   : %s" % self.destination.get_uri())

        # TODO g_file_copy_async() isn't introspectable
        # see https://github.com/exaile/exaile/issues/198 for details
        # self.source.copy_async( self.destination, self._finish_single_copy_async, flags=flags, cancellable=self.cancel )

        self.cpthr = self.CopyThread(
            self.source, self.destination, self._finish_single_copy, flags
        )

    def _finish_single_copy(self, source, success, error):
        if error:
            self._on_error(
                _("Error occurred while copying %s: %s")
                % (
                    GLib.markup_escape_text(self.source.get_uri()),
                    GLib.markup_escape_text(str(error)),
                )
            )
        if success:
            self._step()
            self._start_next_copy()

    def _finish_single_copy_async(self, source, async_result):

        try:
            if source.copy_finish(async_result):
                self._step()
                self._start_next_copy()
        except GLib.Error as e:
            self._on_error(
                _("Error occurred while copying %s: %s")
                % (
                    GLib.markup_escape_text(self.source.get_uri()),
                    GLib.markup_escape_text(str(e)),
                )
            )

    def _query_overwrite(self):

        self.hide()

        text = _('File exists, overwrite %s ?') % GLib.markup_escape_text(
            self.destination.get_uri()
        )
        dialog = XMessageDialog(self.parent, text)
        dialog.connect('response', self._on_query_overwrite_response, dialog)
        dialog.show_all()
        dialog.grab_focus()
        self.query_dialog = dialog

    def _on_query_overwrite_response(self, widget, response, dialog):
        dialog.destroy()
        self.overwrite_response = response

        if response == Gtk.ResponseType.CANCEL:
            self.response(response)
        else:
            if response == XRESPONSE_NO or response == XRESPONSE_NO_ALL:
                overwrite = False
            else:
                overwrite = True

            self.show_all()
            self._start_next_copy(overwrite)

    def _on_error(self, message):

        self.hide()

        dialog = Gtk.MessageDialog(
            buttons=Gtk.ButtonsType.CLOSE,
            message_type=Gtk.MessageType.ERROR,
            modal=True,
            text=message,
            transient_for=self.parent,
        )
        dialog.set_markup(message)
        dialog.connect('response', self._on_error_response, dialog)
        dialog.show()
        dialog.grab_focus()
        self.error_dialog = dialog

    def _on_error_response(self, widget, response, dialog):
        self.response(Gtk.ResponseType.CANCEL)
        dialog.destroy()


def ask_for_playlist_name(parent, playlist_manager, name=None):
    """
    Returns a user-selected name that is not already used
        in the specified playlist manager

    :param name: A default name to show to the user
    Returns None if the user hits cancel
    """

    while True:

        dialog = TextEntryDialog(
            _('Playlist name:'),
            _('Add new playlist...'),
            name,
            parent=parent,
            okbutton=Gtk.STOCK_ADD,
        )

        result = dialog.run()
        if result != Gtk.ResponseType.OK:
            return None

        name = dialog.get_value()

        if name == '':
            error(parent, _("You did not enter a name for your playlist"))
        elif playlist_manager.has_playlist_name(name):
            # name is already in use
            error(parent, _("The playlist name you entered is already in use."))
        else:
            return name


def save(
    parent, output_fname, output_setting=None, extensions=None, title=_("Save As")
):
    """
    A 'save' dialog utility function, which can be used to easily
    remember the last location the user saved something.

    :param parent:          Parent window
    :param output_fname:    Output filename
    :param output_setting:  Setting to store the last 'output directory' saved at
    :param extensions:      Valid output extensions. Dict { '.m3u': 'Description', .. }
    :param title:           Title of dialog

    :returns: None if user cancels, chosen URI otherwise
    """

    uri = None

    dialog = FileOperationDialog(
        title,
        parent,
        Gtk.FileChooserAction.SAVE,
        (
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE,
            Gtk.ResponseType.ACCEPT,
        ),
    )

    if extensions is not None:
        dialog.add_extensions(extensions)

    dialog.set_current_name(output_fname)

    if output_setting:
        output_dir = settings.get_option(output_setting)
        if output_dir:
            dialog.set_current_folder_uri(output_dir)

    if dialog.run() == Gtk.ResponseType.ACCEPT:
        uri = dialog.get_uri()

        settings.set_option(output_setting, dialog.get_current_folder_uri())

    dialog.destroy()

    return uri


def export_playlist_dialog(playlist, parent=None):
    '''Exports the playlist to a user-specified path'''
    if playlist is not None:
        dialog = PlaylistExportDialog(playlist, parent)
        dialog.show()


def export_playlist_files(playlist, parent=None):
    '''Exports the playlist files to a user-specified URI'''

    if playlist is None:
        return

    def _on_uri(uri):
        if hasattr(playlist, 'get_playlist'):
            pl = playlist.get_playlist()
        else:
            pl = playlist
        pl_files = [track.get_loc_for_io() for track in pl]
        dialog = FileCopyDialog(
            pl_files, uri, _('Exporting %s') % playlist.name, parent=parent
        )
        dialog.do_copy()

    dialog = DirectoryOpenDialog(
        title=_('Choose directory to export files to'), parent=parent
    )
    dialog.set_select_multiple(False)
    dialog.connect('uris-selected', lambda widget, uris: _on_uri(uris[0]))
    dialog.run()
    dialog.destroy()
