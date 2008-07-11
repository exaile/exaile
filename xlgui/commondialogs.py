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


