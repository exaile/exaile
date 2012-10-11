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

import gio
import glib
import gobject
import gtk
import logging
import pango
import os.path

from xl import (
    metadata, 
    providers,
    xdg
)
from xl.common import clamp
from xl.playlist import (
    is_valid_playlist,
    import_playlist,
    export_playlist,
    InvalidPlaylistTypeError,
    PlaylistExportOptions
)
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

def force_unicode(obj):
    if obj is None:
        return None

    try:
        # Try this first because errors='replace' fails if the object is unicode
        # or some other non-str object.
        return unicode(obj)
    except UnicodeDecodeError:
        return unicode(obj, errors='replace')

def error(parent, message=None, markup=None, _flags=gtk.DIALOG_MODAL):
    """
        Shows an error dialog
    """
    if message is markup is None:
        raise ValueError("message or markup must be specified")
    dialog = gtk.MessageDialog(parent, _flags, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_CLOSE)
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
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
        gtk.BUTTONS_OK)
    if markup is None:
        dialog.props.text = message
    else:
        dialog.set_markup(markup)
    dialog.run()
    dialog.destroy()

class AboutDialog(object):
    """
        A dialog showing program info and more
    """
    def __init__(self, parent=None):
        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path('ui', 'about_dialog.ui'))

        self.dialog = builder.get_object('AboutDialog')
        self.dialog.set_transient_for(parent)
        logo = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images', 'exailelogo.png'))
        self.dialog.set_logo(logo)
        from xl.main import __version__
        self.dialog.set_version('\n%s' % __version__)
        self.dialog.connect('response', lambda dialog, response: dialog.destroy())

    def show(self):
        """
            Shows the dialog
        """
        self.dialog.show()

class MultiTextEntryDialog(gtk.Dialog):
    """
        Exactly like a TextEntryDialog, except it can contain multiple
        labels/fields.

        Instead of using GetValue, use GetValues.  It will return a list with
        the contents of the fields. Each field must be filled out or the dialog
        will not close.
    """
    def __init__(self, parent, title):
        gtk.Dialog.__init__(self, title, parent)


        self.hbox = gtk.HBox()
        self.vbox.pack_start(self.hbox, True, True)
        self.vbox.set_border_width(5)
        self.hbox.set_border_width(5)
        self.left = gtk.VBox()
        self.right = gtk.VBox()

        self.hbox.pack_start(self.left, True, True)
        self.hbox.pack_start(self.right, True, True)

        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OK, gtk.RESPONSE_OK)

        self.fields = []

    def add_field(self, label):
        """
            Adds a field and corresponding label

            :param label: the label to display
            :returns: the newly created entry
            :rtype: :class:`gtk.Entry`
        """
        label = gtk.Label(label)
        label.set_alignment(0, 0)
        label.set_padding(0, 5)
        self.left.pack_start(label, False, False)

        entry = gtk.Entry()
        entry.set_width_chars(30)
        entry.set_icon_activatable(gtk.ENTRY_ICON_SECONDARY, False)
        entry.connect('activate', lambda *e: self.response(gtk.RESPONSE_OK))
        self.right.pack_start(entry, True, True)
        label.show()
        entry.show()

        self.fields.append(entry)

        return entry

    def get_values(self):
        """
            Returns a list of the values from the added fields
        """
        return [unicode(a.get_text(), 'utf-8') for a in self.fields]

    def run(self):
        """
            Shows the dialog, runs, hides, and returns
        """
        self.show_all()

        while True:
            response = gtk.Dialog.run(self)

            if response in (gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT):
                break

            if response == gtk.RESPONSE_OK:
                # Leave loop if all fields where filled
                if len(min([f.get_text() for f in self.fields])) > 0:
                    break

                # At least one field was not filled
                for field in self.fields:
                    if len(field.get_text()) > 0:
                        # Unset possible previous marks
                        field.set_icon_from_stock(
                            gtk.ENTRY_ICON_SECONDARY,
                            None
                        )
                    else:
                        # Mark via warning
                        field.set_icon_from_stock(
                            gtk.ENTRY_ICON_SECONDARY,
                            gtk.STOCK_DIALOG_WARNING
                        )
        self.hide()

        return response

class TextEntryDialog(gtk.Dialog):
    """
        Shows a dialog with a single line of text
    """
    def __init__(self, message, title, default_text=None, parent=None,
        cancelbutton=None, okbutton=None):
        """
            Initializes the dialog
        """
        if not cancelbutton:
            cancelbutton = gtk.STOCK_CANCEL
        if not okbutton:
            okbutton = gtk.STOCK_OK
        gtk.Dialog.__init__(self, title, parent, gtk.DIALOG_DESTROY_WITH_PARENT,
            (cancelbutton, gtk.RESPONSE_CANCEL,
            okbutton, gtk.RESPONSE_OK))

        label = gtk.Label(message)
        label.set_alignment(0.0, 0.0)
        self.vbox.set_border_width(5)

        main = gtk.VBox()
        main.set_spacing(3)
        main.set_border_width(5)
        self.vbox.pack_start(main, True, True)

        main.pack_start(label, False, False)

        self.entry = gtk.Entry()
        self.entry.set_width_chars(35)
        if default_text:
            self.entry.set_text(default_text)
        main.pack_start(self.entry, False, False)

        self.entry.connect('activate',
            lambda e: self.response(gtk.RESPONSE_OK))

    def get_value(self):
        """
            Returns the text value
        """
        return unicode(self.entry.get_text(), 'utf-8')

    def set_value(self, value):
        """
            Sets the value of the text
        """
        self.entry.set_text(value)

    def run(self):
        self.show_all()
        response = gtk.Dialog.run(self)
        self.hide()
        return response

class URIOpenDialog(TextEntryDialog):
    """
        A dialog specialized for opening an URI
    """
    __gsignals__ = {
        'uri-selected': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gobject.TYPE_PYOBJECT,),
            gobject.signal_accumulator_true_handled
        )
    }
    def __init__(self, parent=None):
        """
            :param parent: a parent window for modal operation or None
            :type parent: :class:`gtk.Window`
        """
        TextEntryDialog.__init__(self,
            message=_('Enter the URL to open'),
            title=_('Open URL'),
            parent=parent)

        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

        self.connect('response', self.on_response)

    def run(self):
        """
            Override to take care of the response
        """
        clipboard = gtk.clipboard_get()
        text = clipboard.wait_for_text()

        if text is not None:
            location = gio.File(uri=text)

            if location.get_uri_scheme() is not None:
                self.set_value(text)

        self.show_all()
        response = TextEntryDialog.run(self)
        self.emit('response', response)

    def show(self):
        """
            Override to capture clipboard content
        """
        clipboard = gtk.clipboard_get()
        text = clipboard.wait_for_text()

        if text is not None:
            location = gio.File(uri=text)

            if location.get_uri_scheme() is not None:
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

        if response == gtk.RESPONSE_OK:
            self.emit('uri-selected', self.get_value())

        #self.destroy()
    '''
        dialog = dialogs.TextEntryDialog(_('Enter the URL to open'),
        _('Open URL'))
        dialog.set_transient_for(self.main.window)
        dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

        clipboard = gtk.clipboard_get()
        text = clipboard.wait_for_text()

        if text is not None:
            location = gio.File(uri=text)

            if location.get_uri_scheme() is not None:
                dialog.set_value(text)

        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_OK:
            url = dialog.get_value()
            self.open_uri(url, play=False)
    '''

class ListDialog(gtk.Dialog):
    """
        Shows a dialog with a list of specified items

        Items must define a __str__ method, or be a string
    """
    def __init__(self, title, parent=None, multiple=False, write_only=False):
        """
            Initializes the dialog
        """
        gtk.Dialog.__init__(self, title, parent)

        self.vbox.set_border_width(5)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.model = gtk.ListStore(object)
        self.list = gtk.TreeView(self.model)
        self.list.set_headers_visible(False)
        self.list.connect('row-activated',
            lambda *e: self.response(gtk.RESPONSE_OK))
        scroll.add(self.list)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.vbox.pack_start(scroll, True, True)

        if write_only:
            self.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK)
        else:
            self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK)

        self.selection = self.list.get_selection()

        if multiple:
            self.selection.set_mode(gtk.SELECTION_MULTIPLE)
        else:
            self.selection.set_mode(gtk.SELECTION_SINGLE)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Item")
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
        if not check: return None
        (model, paths) = check

        for path in paths:
            iter = self.model.get_iter(path)
            item = self.model.get_value(iter, 0)
            items.append(item)

        return items

    def run(self):
        self.show_all()
        result = gtk.Dialog.run(self)
        self.hide()
        return result

    def set_items(self, items):
        """
            Sets the items
        """
        for item in items:
            self.model.append([item])

    def cell_data_func(self, column, cell, model, iter):
        """
            Called when the tree needs a value for column 1
        """
        object = model.get_value(iter, 0)
        cell.set_property('text', str(object))

# TODO: combine this and list dialog
class ListBox(object):
    """
        Represents a list box
    """
    def __init__(self, widget, rows=None):
        """
            Initializes the widget
        """
        self.list = widget
        self.store = gtk.ListStore(str)
        widget.set_headers_visible(False)
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('', cell, text=0)
        self.list.append_column(col)
        self.rows = rows
        if not rows: self.rows = []

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
        self.store = gtk.ListStore(str)
        for row in rows:
            self.store.append([row])

        self.list.set_model(self.store)

    def get_selection(self):
        """
            Returns the selection
        """
        selection = self.list.get_selection()
        (model, iter) = selection.get_selected()
        if not iter: return None
        return model.get_value(iter, 0)

class FileOperationDialog(gtk.FileChooserDialog):
    """
        An extension of the gtk.FileChooserDialog that
        adds a collapsable panel to the bottom listing
        valid file extensions that the file can be
        saved in. (similar to the one in GIMP)
    """
    def __init__(self, title=None, parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN,
                 buttons=None, backend=None):
        """
            Standard __init__ of the gtk.FileChooserDialog.
            Also sets up the expander and list for extensions
        """
        gtk.FileChooserDialog.__init__(self, title, parent, action, buttons, backend)

        self.set_do_overwrite_confirmation(True)

        # Container for additional option widgets
        self.extras_box = gtk.VBox(spacing=3)
        self.set_extra_widget(self.extras_box)
        self.extras_box.show()

        # Create the list that will hold the file type/extensions pair
        self.liststore = gtk.ListStore(str, str)
        self.list = gtk.TreeView(self.liststore)
        self.list.set_headers_visible(False)

        # Create the columns
        filetype_cell = gtk.CellRendererText()
        extension_cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn()
        column.pack_start(filetype_cell)
        column.pack_start(extension_cell, expand=False)
        column.set_attributes(filetype_cell, text=0)
        column.set_attributes(extension_cell, text=1)

        self.list.append_column(column)
        self.list.show_all()

        self.expander = gtk.Expander(_('Select File Type (by Extension)'))
        self.expander.add(self.list)
        self.extras_box.pack_start(self.expander, False, False)
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
        extension, = model.get(iter, 1)
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
        keys = extensions.keys()
        for key in keys:
            self.liststore.append([extensions[key], key])

class MediaOpenDialog(gtk.FileChooserDialog):
    """
        A dialog for opening general media
    """
    __gsignals__ = {
        'uris-selected': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gobject.TYPE_PYOBJECT,),
            gobject.signal_accumulator_true_handled
        )
    }
    _last_location = None

    def __init__(self, parent=None):
        """
            :param parent: a parent window for modal operation or None
            :type parent: :class:`gtk.Window`
        """
        gtk.FileChooserDialog.__init__(self,
            title=_('Choose Media to Open'),
            parent=parent,
            buttons=(
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.set_local_only(False)
        self.set_select_multiple(True)

        supported_filter = gtk.FileFilter()
        supported_filter.set_name(_('Supported Files'))
        audio_filter = gtk.FileFilter()
        audio_filter.set_name(_('Music Files'))
        playlist_filter = gtk.FileFilter()
        playlist_filter.set_name(_('Playlist Files'))
        all_filter = gtk.FileFilter()
        all_filter.set_name(_('All Files'))
        all_filter.add_pattern('*')

        for extension in metadata.formats.iterkeys():
            pattern = '*.%s' % extension
            supported_filter.add_pattern(pattern)
            audio_filter.add_pattern(pattern)

        playlist_file_extensions = sum([p.file_extensions \
            for p in providers.get('playlist-format-converter')], [])

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

        response = gtk.FileChooserDialog.run(self)
        self.emit('response', response)

    def show(self):
        """
            Override to restore last location
        """
        if MediaOpenDialog._last_location is not None:
            self.set_current_folder_uri(MediaOpenDialog._last_location)

        gtk.FileChooserDialog.show(self)

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

        if response == gtk.RESPONSE_OK:
            MediaOpenDialog._last_location = self.get_current_folder_uri()
            self.emit('uris-selected', self.get_uris())

        #self.destroy()

class DirectoryOpenDialog(gtk.FileChooserDialog):
    """
        A dialog specialized for opening directories
    """
    __gsignals__ = {
        'uris-selected': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gobject.TYPE_PYOBJECT,),
            gobject.signal_accumulator_true_handled
        )
    }
    _last_location = None

    def __init__(self, parent=None, title=_('Choose Directory to Open')):
        gtk.FileChooserDialog.__init__(self,
            title,
            parent=parent,
            buttons=(
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        self.set_local_only(False)
        self.set_select_multiple(True)

        self.connect('response', self.on_response)

    def run(self):
        """
            Override to take care of the response
        """
        if DirectoryOpenDialog._last_location is not None:
            self.set_current_folder_uri(DirectoryOpenDialog._last_location)

        response = gtk.FileChooserDialog.run(self)

    def show(self):
        """
            Override to restore last location
        """
        if DirectoryOpenDialog._last_location is not None:
            self.set_current_folder_uri(DirectoryOpenDialog._last_location)

        gtk.FileChooserDialog.show(self)

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

        if response == gtk.RESPONSE_OK:
            DirectoryOpenDialog._last_location = self.get_current_folder_uri()
            self.emit('uris-selected', self.get_uris())

        #self.destroy()
        
class PlaylistImportDialog(gtk.FileChooserDialog):
    """
        A dialog for importing a playlist
    """
    __gsignals__ = {
        'playlist-selected': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gobject.TYPE_PYOBJECT,),
            gobject.signal_accumulator_true_handled
        )
    }
    _last_location = None

    def __init__(self, parent=None):
        """
            :param parent: a parent window for modal operation or None
            :type parent: :class:`gtk.Window`
        """
        gtk.FileChooserDialog.__init__(self,
            title=_('Import Playlist'),
            parent=parent,
            buttons=(
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.set_local_only(False)
        self.set_select_multiple(False)

        playlist_filter = gtk.FileFilter()
        playlist_filter.set_name(_('Playlist Files'))
        all_filter = gtk.FileFilter()
        all_filter.set_name(_('All Files'))
        all_filter.add_pattern('*')

        playlist_file_extensions = sum([p.file_extensions \
            for p in providers.get('playlist-format-converter')], [])

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

        response = gtk.FileChooserDialog.run(self)
        self.emit('response', response)

    def show(self):
        """
            Override to restore last location
        """
        if PlaylistImportDialog._last_location is not None:
            self.set_current_folder_uri(PlaylistImportDialog._last_location)

        gtk.FileChooserDialog.show(self)

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

        if response == gtk.RESPONSE_OK:
            PlaylistImportDialog._last_location = self.get_current_folder_uri()
            
            try:
                playlist = import_playlist(self.get_uri())
            except InvalidPlaylistTypeError, e:
                error(None, 'Invalid playlist: %s' % e)
                self.destroy()
            else:
                self.emit('playlist-selected', playlist)

        #self.destroy()

class PlaylistExportDialog(FileOperationDialog):
    """
        A dialog specialized for playlist export
    """
    __gsignals__ = {
        'message': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gtk.MessageType, gobject.TYPE_STRING),
            gobject.signal_accumulator_true_handled
        )
    }

    def __init__(self, playlist, parent=None):
        """
            :param playlist: the playlist to export
            :type playlist: :class:`xl.playlist.Playlist`
            :param parent: a parent window for modal operation or None
            :type parent: :class:`gtk.Window`
        """
        FileOperationDialog.__init__(self,
            title=_('Export Current Playlist'),
            parent=parent,
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_SAVE, gtk.RESPONSE_OK
            )
        )

        self.set_local_only(False)

        self.relative_checkbox = gtk.CheckButton(_('Use relative paths to tracks'))
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
        if message_type == gtk.MESSAGE_INFO:
            info(None, markup=message)
        elif message_type == gtk.MESSAGE_ERROR:
            error(None, markup=message)

    def on_response(self, dialog, response):
        """
            Exports the playlist if requested
        """
        self.hide()

        if response == gtk.RESPONSE_OK:
            path = unicode(self.get_uri(), 'utf-8')
            
            if not is_valid_playlist(path):
                path = '%s.m3u' % path

            options = PlaylistExportOptions(
                relative=self.relative_checkbox.get_active()
            )
            
            try:
                export_playlist(self.playlist, path, options)
            except InvalidPlaylistTypeError, e:
                self.emit('message', gtk.MESSAGE_ERROR, str(e))
            else:
                self.emit('message', gtk.MESSAGE_INFO,
                    _('Playlist saved as <b>%s</b>.') % path)

        #self.destroy()

class ConfirmCloseDialog(gtk.MessageDialog):
    """
        Shows the dialog to confirm closing of the playlist
    """
    def __init__(self, document_name):
        """
            Initializes the dialog
        """
        gtk.MessageDialog.__init__(self, type = gtk.MESSAGE_WARNING)

        self.set_title(_('Close %s' % document_name))
        self.set_markup(_('<b>Save changes to %s before closing?</b>') % document_name)
        self.format_secondary_text(_('Your changes will be lost if you don\'t save them'))

        self.add_buttons(_('Close Without Saving'), 100, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                        gtk.STOCK_SAVE, 110)

    def run(self):
        self.show_all()
        response = gtk.Dialog.run(self)
        self.hide()
        return response

class MessageBar(gtk.InfoBar):
    type_map = {
        gtk.MESSAGE_INFO: gtk.STOCK_DIALOG_INFO,
        gtk.MESSAGE_QUESTION: gtk.STOCK_DIALOG_QUESTION,
        gtk.MESSAGE_WARNING: gtk.STOCK_DIALOG_WARNING,
        gtk.MESSAGE_ERROR: gtk.STOCK_DIALOG_ERROR,
    }
    buttons_map = {
        gtk.BUTTONS_OK: [
            (gtk.STOCK_OK, gtk.RESPONSE_OK)
        ],
        gtk.BUTTONS_CLOSE: [
            (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        ],
        gtk.BUTTONS_CANCEL: [
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        ],
        gtk.BUTTONS_YES_NO: [
            (gtk.STOCK_NO, gtk.RESPONSE_NO),
            (gtk.STOCK_YES, gtk.RESPONSE_YES)
        ],
        gtk.BUTTONS_OK_CANCEL: [
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
            (gtk.STOCK_OK, gtk.RESPONSE_OK)
        ]
    }
    def __init__(self, parent=None, type=gtk.MESSAGE_INFO,
                 buttons=gtk.BUTTONS_NONE, text=None):
        """
            Report important messages to the user

            :param parent: the parent container box
            :type parent: :class:`gtk.Box`
            :param type: the type of message: gtk.MESSAGE_INFO,
                gtk.MESSAGE_WARNING, gtk.MESSAGE_QUESTION or
                gtk.MESSAGE_ERROR.
            :param buttons: the predefined set of buttons to
                use: gtk.BUTTONS_NONE, gtk.BUTTONS_OK,
                gtk.BUTTONS_CLOSE, gtk.BUTTONS_CANCEL,
                gtk.BUTTONS_YES_NO, gtk.BUTTONS_OK_CANCEL
            :param text: a string containing the message
                text or None
        """
        if parent is not None and not isinstance(parent, gtk.Box):
            raise TypeError('Parent needs to be of type gtk.Box')

        gtk.InfoBar.__init__(self)
        self.set_no_show_all(True)

        if parent is not None:
            parent.add(self)
            parent.reorder_child(self, 0)
            parent.child_set_property(self, 'expand', False)

        self.image = gtk.Image()
        self.image.set_property('yalign', 0)
        self.set_message_type(type)

        self.primary_text = gtk.Label(text)
        self.primary_text.set_property('xalign', 0)
        self.primary_text.set_line_wrap(True)
        self.secondary_text = gtk.Label()
        self.secondary_text.set_property('xalign', 0)
        self.secondary_text.set_line_wrap(True)
        self.secondary_text.set_no_show_all(True)
        self.secondary_text.set_selectable(True)

        self.message_area = gtk.VBox(spacing=12)
        self.message_area.pack_start(self.primary_text, False, False)
        self.message_area.pack_start(self.secondary_text, False, False)

        box = gtk.HBox(spacing=6)
        box.pack_start(self.image, False)
        box.pack_start(self.message_area)

        content_area = self.get_content_area()
        content_area.add(box)
        content_area.show_all()

        self.action_area = self.get_action_area()
        self.action_area.set_property('layout-style',
            gtk.BUTTONBOX_START)

        if buttons != gtk.BUTTONS_NONE:
            for text, response in self.buttons_map[buttons]:
                self.add_button(text, response)

        self.primary_text_attributes = pango.AttrList()
        self.primary_text_attributes.insert(
            pango.AttrWeight(pango.WEIGHT_NORMAL, 0, -1))
        self.primary_text_attributes.insert(
            pango.AttrScale(pango.SCALE_MEDIUM, 0, -1))

        self.primary_text_emphasized_attributes = pango.AttrList()
        self.primary_text_emphasized_attributes.insert(
            pango.AttrWeight(pango.WEIGHT_BOLD, 0, -1))
        self.primary_text_emphasized_attributes.insert(
            pango.AttrScale(pango.SCALE_LARGE, 0, -1))

        self.connect('response', self.on_response)

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
            self.primary_text.set_attributes(
                self.primary_text_attributes)
        else:
            self.secondary_text.set_text(text)
            self.secondary_text.show()
            self.primary_text.set_attributes(
                self.primary_text_emphasized_attributes)

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
            self.primary_text.set_attributes(
                self.primary_text_attributes)
        else:
            self.secondary_text.set_markup(markup)
            self.secondary_text.show()
            self.primary_text.set_attributes(
                self.primary_text_emphasized_attributes)

    def set_image(self, image):
        """
            Sets the contained image to the :class:`gtk.Widget`
            specified by image.

            :param image: the image widget
            :type image: :class:`gtk.Widget`
        """
        box = self.image.get_parent()
        box.remove(self.image)
        self.image = image
        box.pack_start(self.image, False)
        box.reorder_child(self.image, 0)
        self.image.show()

    def get_image(self):
        """
            Gets the contained image
        """
        return self.image

    def add_button(self, button_text, response_id):
        """
            Overrides :class:`gtk.InfoBar` to prepend
            instead of append to the action area

            :param button_text: text of button, or stock ID
            :type button_text: string
            :param response_id: response ID for the button
            :type response_id: int
        """
        button = gtk.InfoBar.add_button(self, button_text, response_id)
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

            :param type: the type of message: gtk.MESSAGE_INFO,
                gtk.MESSAGE_WARNING, gtk.MESSAGE_QUESTION or
                gtk.MESSAGE_ERROR.
        """
        if type != gtk.MESSAGE_OTHER:
            self.image.set_from_stock(self.type_map[type],
                gtk.ICON_SIZE_DIALOG)

        gtk.InfoBar.set_message_type(self, type)

    def get_message_area(self):
        """
            Retrieves the message area
        """
        return self.message_area

    def _show_message(self, message_type, text, secondary_text,
            markup, secondary_markup, timeout):
        """
            Helper for the various `show_*` methods. See `show_info` for
            documentation on the parameters.
        """
        if text is markup is None:
            raise ValueError("text or markup must be specified")

        self.set_message_type(message_type)
        if markup is None:
            self.set_text(force_unicode(text))
        else:
            self.set_markup(force_unicode(markup))
        if secondary_markup is None:
            self.set_secondary_text(force_unicode(secondary_text))
        else:
            self.set_secondary_markup(force_unicode(secondary_markup))
        self.show()

        if timeout > 0:
            glib.timeout_add_seconds(timeout, self.hide)

    def show_info(self, text=None, secondary_text=None,
            markup=None, secondary_markup=None, timeout=5):
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
        self._show_message(gtk.MESSAGE_INFO, text, secondary_text,
            markup, secondary_markup, timeout)

    def show_question(self, text=None, secondary_text=None,
            markup=None, secondary_markup=None):
        """
            Convenience method which sets all
            required flags for a question message
            
            :param text: the message to display
            :param secondary_text: additional information
            :param markup: the message to display, in Pango markup format
            :param secondary_markup: additional information, in Pango markup format
        """
        self._show_message(gtk.MESSAGE_QUESTION, text, secondary_text,
            markup, secondary_markup, 0)

    def show_warning(self, text=None, secondary_text=None,
            markup=None, secondary_markup=None):
        """
            Convenience method which sets all
            required flags for a warning message
            
            :param text: the message to display
            :param secondary_text: additional information
            :param markup: the message to display, in Pango markup format
            :param secondary_markup: additional information, in Pango markup format
        """
        self._show_message(gtk.MESSAGE_WARNING, text, secondary_text,
            markup, secondary_markup, 0)

    def show_error(self, text=None, secondary_text=None,
            markup=None, secondary_markup=None):
        """
            Convenience method which sets all
            required flags for a warning message
            
            :param text: the message to display
            :param secondary_text: additional information
            :param markup: the message to display, in Pango markup format
            :param secondary_markup: additional information, in Pango markup format
        """
        self._show_message(gtk.MESSAGE_ERROR, text, secondary_text,
            markup, secondary_markup, 0)

    def on_response(self, widget, response):
        """
            Handles the response for closing
        """
        if response == gtk.RESPONSE_CLOSE:
            self.hide()

#
# Message ID's used by the XMessageDialog
#

XRESPONSE_YES = gtk.RESPONSE_YES    
XRESPONSE_YES_ALL = 8000    
XRESPONSE_NO = gtk.RESPONSE_NO
XRESPONSE_NO_ALL = 8001   
XRESPONSE_CANCEL = gtk.RESPONSE_CANCEL
            
class XMessageDialog(gtk.Dialog):
    '''Used to show a custom message dialog with custom buttons'''

    def __init__(self, title, text, parent=None,
                       show_yes=True, show_yes_all=True, 
                       show_no=True, show_no_all=True,
                       show_cancel=True,
                       ):
        
        gtk.Dialog.__init__(self, None, parent)
        
        #
        # TODO: Make these buttons a bit prettier
        #
        
        if show_yes:
            self.add_button( gtk.STOCK_YES, XRESPONSE_YES )
            self.set_default_response( XRESPONSE_YES )
            
        if show_yes_all:
            self.add_button( _('Yes to all'), XRESPONSE_YES_ALL )
            self.set_default_response( XRESPONSE_YES_ALL )
            
        if show_no:
            self.add_button( gtk.STOCK_NO, XRESPONSE_NO )
            self.set_default_response( XRESPONSE_NO )
            
        if show_no_all:
            self.add_button( _('No to all'), XRESPONSE_NO_ALL )
            self.set_default_response( XRESPONSE_NO_ALL )
            
        if show_cancel:
            self.add_button( gtk.STOCK_CANCEL, XRESPONSE_CANCEL )
            self.set_default_response( XRESPONSE_CANCEL )
            
        vbox = self.get_content_area()
        self._label = gtk.Label()
        self._label.set_use_markup(True)
        self._label.set_markup(text)
        vbox.pack_start(self._label)


class FileCopyDialog(gtk.Dialog):
    '''
        Used to copy a list of files to a single destination directory
        
        Usage:
            dialog = FileCopyDialog( [file_uri,..], destination_uri, text, parent)
            dialog.do_copy()
            
        Do not use run() on this dialog!
    '''

    def __init__(self, file_uris, destination_uri, title, text=_("Saved %(count)s of %(total)s."), parent=None):
        
        self.file_uris = file_uris
        self.destination_uri = destination_uri
        self.cancel = gio.Cancellable()
        self.is_copying = False
        
        gtk.Dialog.__init__(self, title, parent)
        
        self.count = 0
        self.total = len(file_uris)
        self.text = text
        self.overwrite_response = None

        #self.set_modal(True)
        #self.set_decorated(False)
        self.set_resizable(False)
        #self.set_focus_on_map(False)
        
        vbox = self.get_content_area()
        
        vbox.set_spacing(12)
        vbox.set_border_width(12)
        
        self._label = gtk.Label()
        self._label.set_use_markup(True)
        self._label.set_markup(self.text % {'count': 0, 'total': self.total})
        vbox.pack_start(self._label)
        
        self._progress = gtk.ProgressBar()
        self._progress.set_size_request(300, -1)
        vbox.pack_start(self._progress)
        
        self.show_all()

        # TODO: Make dialog cancelable
        #self.cancel_button.connect('activate', lambda *e: self.cancel.cancel() )
        
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
            
    def do_copy(self):
        logger.info( "Copy started." )
        self._start_next_copy()
        self.show_all()
        self.connect('response',self._on_response)
        
    def run(self):
        raise NotImplementedError( "Don't use this" )
        
    def _on_response(self, widget, response):
        logger.info( "Copy complete." )
        self.destroy()

    
    def _step(self):
        '''Steps the progress bar'''
        self.count += 1
        self._progress.set_fraction(
                clamp(self.count / float(self.total), 0, 1))
        self._label.set_markup(self.text % {
            'count': self.count,
            'total': self.total
        })
        
    def _start_next_copy(self, overwrite=False):
        
        if self.count == len(self.file_uris):
            self.response( gtk.RESPONSE_OK )
            return
        
        flags = gio.FILE_COPY_NONE
        
        src_uri = self.file_uris[self.count] 
        dst_uri = self.destination_uri + '/' + src_uri.split('/')[-1]
        
        self.source = gio.File( uri=src_uri)
        self.destination = gio.File( uri=dst_uri )
        
        
        if not overwrite:
            if self.destination.query_exists():
                if self.overwrite_response == XRESPONSE_YES_ALL:
                    overwrite = True
                    
                elif self.overwrite_response == XRESPONSE_NO_ALL or self.overwrite_response == XRESPONSE_NO:
                
                    # only deny the overwrite once.. 
                    if self.overwrite_response == XRESPONSE_NO:
                        self.overwrite_response = None
                        
                    logging.info( "NoOverwrite: %s" % self.destination.get_uri() )
                    self._step()
                    glib.idle_add( self._start_next_copy ) # don't recurse
                    return
                else:
                    self._query_overwrite()
                    return
                
        if overwrite:
            flags = gio.FILE_COPY_OVERWRITE
            try:
                # gio.FILE_COPY_OVERWRITE doesn't actually work
                logging.info( "DeleteDest : %s" % self.destination.get_uri() )
                self.destination.delete()
            except gio.Error:
                pass
        
        logging.info( "CopySource : %s" % self.source.get_uri() )
        logging.info( "CopyDest   : %s" % self.destination.get_uri() )
        
        self.source.copy_async( self.destination, self._finish_single_copy, flags=flags, cancellable=self.cancel ) 
    
    
    def _finish_single_copy(self, source, async_result):
        
        try:
            if source.copy_finish(async_result):
                self._step()
                self._start_next_copy()
        except gio.Error,e:
            self._on_error( _("Error occurred while copying %s: %s") % (
                glib.markup_escape_text( self.source.get_uri() ),
                glib.markup_escape_text( str(e) ) ) )
            
        
    def _query_overwrite(self):
    
        self.hide_all()
    
        text = _('File exists, overwrite %s ?') % glib.markup_escape_text(self.destination.get_uri())
        dialog=XMessageDialog(self.parent, text )
        dialog.connect( 'response', self._on_query_overwrite_response, dialog )
        dialog.show_all()
        dialog.grab_focus()
        self.query_dialog = dialog
        
    def _on_query_overwrite_response(self, widget, response, dialog):
        dialog.destroy()
        self.overwrite_response = response
        
        if response == gtk.RESPONSE_CANCEL:
            self.response( response )
        else:
            if response == XRESPONSE_NO or response == XRESPONSE_NO_ALL:
                overwrite = False
            else:
                overwrite = True
        
            self.show_all()
            self._start_next_copy( overwrite )
        
            
    def _on_error(self, message):
        
        self.hide()
    
        dialog = gtk.MessageDialog(self.parent, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE)
        dialog.set_markup( message )
        dialog.connect( 'response', self._on_error_response, dialog )
        dialog.show()
        dialog.grab_focus()
        self.error_dialog = dialog
    
    def _on_error_response(self, widget, response, dialog):
        self.response( gtk.RESPONSE_CANCEL )
        dialog.destroy()

        
def ask_for_playlist_name(playlist_manager, name=None):
    """
        Returns a user-selected name that is not already used
            in the specified playlist manager
            
        :param name: A default name to show to the user
        Returns None if the user hits cancel
    """
    
    while True:
            
        dialog = TextEntryDialog(
            _('Playlist name:'),
            _('Add new playlist...'), name, okbutton=gtk.STOCK_ADD)
            
        result = dialog.run()
        if result != gtk.RESPONSE_OK:
            return None
            
        name = dialog.get_value()
        
        if name == '':
            error(None, _("You did not enter a name for your playlist"))
        elif playlist_manager.has_playlist_name(name):
            # name is already in use
            error(None, _("The playlist name you entered is already in use."))
        else:
            return name

