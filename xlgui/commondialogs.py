from gettext import gettext as _
import pygtk
pygtk.require('2.0')
import gtk, gtk.glade
from xl import xdg


#Taken from 0.2 branch, not quite sure if this is the right way to do it
class TextEntryDialog(gtk.Dialog):
    """
        Shows a dialog with a single line of text
    """
    def __init__(self, message, title):
        """
            Initializes the dialog
        """
        gtk.Dialog.__init__(self, title, None)

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
        main.pack_start(self.entry, False, False)

        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OK, gtk.RESPONSE_OK)

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

def error(parent, message): 
    """
        Shows an error dialog
    """
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_OK)
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

