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

import os.path

import pygtk
pygtk.require('2.0')
import glib
import gtk
import pango

from xl import xdg
from xl.nls import gettext as _

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
        """
        label = gtk.Label(label + "     ")
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

class ListDialog(gtk.Dialog):
    """
        Shows a dialog with a list of specified items

        Items must define a __str__ method, or be a string
    """
    def __init__(self, title, parent=None, multiple=False):
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

def error(parent, message, _flags=gtk.DIALOG_MODAL):
    """
        Shows an error dialog
    """
    dialog = gtk.MessageDialog(parent, _flags, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_CLOSE)
    dialog.set_markup(message)
    dialog.run()
    dialog.destroy()

def info(parent, message):
    """
        Shows an info dialog
    """
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
        gtk.BUTTONS_OK)
    dialog.set_markup(message)
    dialog.run()
    dialog.destroy()

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

        self.expander = gtk.Expander(_('Select File Type (By Extension)'))

        #Create the list that will hold the file type/extensions pair
        self.liststore = gtk.ListStore(str, str)
        self.list = gtk.TreeView(self.liststore)

        #Create the columns
        filetype_cell = gtk.CellRendererText()
        filetype_col = gtk.TreeViewColumn(_('File Type'), filetype_cell, text=0)

        extension_cell = gtk.CellRendererText()
        extension_col = gtk.TreeViewColumn(_('Extension'), extension_cell, text=1)

        self.list.append_column(filetype_col)
        self.list.append_column(extension_col)

        self.list.show_all()

        #Setup the dialog
        self.expander.add(self.list)
        self.vbox.pack_start(self.expander, False, False, 0)
        self.expander.show()

        #Connect signals
        selection = self.list.get_selection()
        selection.connect('changed', self.on_selection_changed)

        self.set_do_overwrite_confirmation(True)

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

            :param parent: the parent container
            :type parent: :class:`gtk.Container`
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
        if parent is not None and not isinstance(parent, gtk.Container):
            raise TypeError('Parent needs to be of type gtk.Container')

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
        self.secondary_text.set_markup(markup)

        if markup is None:
            self.primary_text.set_attributes(
                self.primary_text_attributes)
        else:
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

    def show_info(self, text, secondary_text=None):
        """
            Convenience method which sets all
            required flags for a info message
            
            :param text: the message to display
            :param secondary_text: additional information
        """
        self.set_message_type(gtk.MESSAGE_INFO)
        self.set_text(text)
        self.set_secondary_text(secondary_text)
        self.show()
        glib.timeout_add_seconds(5, self.hide)

    def show_question(self, text, secondary_text=None):
        """
            Convenience method which sets all
            required flags for a question message
            
            :param text: the message to display
            :param secondary_text: additional information
        """
        self.set_message_type(gtk.MESSAGE_QUESTION)
        self.set_text(text)
        self.set_secondary_text(secondary_text)
        self.show()

    def show_warning(self, text, secondary_text=None):
        """
            Convenience method which sets all
            required flags for a warning message
            
            :param text: the message to display
            :param secondary_text: additional information
        """
        self.set_message_type(gtk.MESSAGE_WARNING)
        self.set_text(text)
        self.set_secondary_text(secondary_text)
        self.show()

    def show_error(self, text, secondary_text=None):
        """
            Convenience method which sets all
            required flags for a warning message
            
            :param text: the message to display
            :param secondary_text: additional information
        """
        self.set_message_type(gtk.MESSAGE_ERROR)
        self.set_text(text)
        self.set_secondary_text(secondary_text)
        self.show()

    def on_response(self, widget, response):
        """
            Handles the response for closing
        """
        if response == gtk.RESPONSE_CLOSE:
            self.hide()

