# Copyright (C) 2006 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import gtk, pango
from gettext import gettext as _
import common

class ConfigurationItem(object):
    """
        Represents a single configuration item
    """
    def __init__(self, ace, name, setting_type, value, description,
        change_func = None):
        """
            Sets up the configuration item
        """
        self.ace = ace
        self.name = name
        self.type = setting_type
        self._value = value
        self.description = description
        self.change_func = change_func

    def set_value(self, value):
        if self.type == 'float':
            try:
                self._value = float(value)
            except ValueError:
                self._value = 0.0
        elif self.type == 'int':
            try:
                self._value = int(value)
            except ValueError:
                self._value = 0
        elif self.type == 'list':
            try:
                self._value = eval(value)
            except:
                self._value = []
        elif self.type == 'boolean':
            if value and value.lower() == 'true':
                self._value = True
            else:
                self._value = False
        else:
            self._value = value

        if self.change_func:
            self.change_func(self, self._value)
        
        m = getattr(self.ace.settings, 'set_%s' % self.type.lower())
        m(self.name, self._value)
        print "setting %s to %s" % (self.name, self._value)
        if self.ace.eventhandler and hasattr(self.ace.eventhandler,
            'setting_changed'):
            self.ace.eventhandler.setting_changed()

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

class AdvancedConfigEditor(gtk.Window):
    """
        Show an advanced configuration dialog
    """
    def __init__(self, app, parent, eventhandler, settings, metafile):
        gtk.Window.__init__(self)
        self.set_title(_('Advanced Configuration Editor'))
        self.set_transient_for(parent)
        self.app = app
        self.eventhandler = eventhandler
        self.settings = settings
        self.metafile = metafile
        self.items = []

        h = open(metafile)
        lines = h.readlines()
        h.close()

        for line in lines:
            (name, type, default, description, changefunc) = line.strip().split('\t')
            m = getattr(settings, 'get_%s' % type.lower())
            current = m(name, default)

            handler = None
            if changefunc and changefunc != 'none' and hasattr(eventhandler, 'advanced_%s' % 
                changefunc):
                handler = getattr(eventhandler, 'advanced_%s' % changefunc)

            self.items.append(ConfigurationItem(self, name, type, current,
                description, handler))

        main = gtk.VBox()
        main.set_border_width(3)
        main.set_spacing(3)
        self.add(main)

        top_box = gtk.HBox()
        top_box.pack_start(gtk.Label(_('Filter:') + '  '), False, False)
        self.filter = gtk.Entry()
        self.filter.connect('activate', lambda *e: self.populate_model())
        top_box.pack_start(self.filter, True, True)

        main.pack_start(top_box, False, False)

        self.model = gtk.ListStore(object, str, str, str)
        self.populate_model()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.tree = gtk.TreeView(self.model)
        self.tree.connect('row-activated', self.row_activated)
        self.tree.get_selection().connect('changed',
            self.on_selection_changed)

        # set up the treeview
        text = gtk.CellRendererText()
        # TRANSLATORS: Name of a setting in the Advanced Configuration Editor
        col = gtk.TreeViewColumn(_('Setting Name'))
        col.pack_start(text, False)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)

        col.set_attributes(text, text=1)
        self.tree.append_column(col)

        self.value_text = gtk.CellRendererText()
        self.value_text.set_property('editable', True)
        self.value_text.connect('edited', self.edited_cb)
        col = gtk.TreeViewColumn(_('Value'))
        col.set_expand(True)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_fixed_width(1)
        self.value_text.set_property('ellipsize', pango.ELLIPSIZE_END)
        col.pack_start(self.value_text, True)
        col.set_attributes(self.value_text, text=2)
        col.set_cell_data_func(self.value_text, self.value_data_func)
        self.tree.append_column(col)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Type'))
        col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        col.pack_start(text, True)
        col.set_attributes(text, text=3)
        self.tree.append_column(col)

        scroll.add(self.tree)

        main.pack_start(scroll, True, True)
        label = gtk.Label()
        label.set_markup('<b>' + _('Description:') + '</b>')
        label.set_alignment(0, 0)
        main.pack_start(label, False)

        self.desc_label = gtk.Label()
        self.desc_label.set_alignment(0, 0)
        main.pack_start(self.desc_label, False)

        buttons = gtk.HBox()
        close = gtk.Button(_('Close'), gtk.STOCK_CLOSE)
        close.connect('clicked', lambda *e: self.destroy())
        buttons.pack_end(close, False, False)

        main.pack_start(buttons, False, False)

        self.resize(635, 500)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.show_all()

    def on_selection_changed(self, selection):
        """
            Called when an item in the list is selected (so that we can
            populate the description label
        """
        if selection.get_selected():
            (model, iter) = selection.get_selected()
            if not iter:
                self.desc_label.set_label('')
                return
            item = model.get_value(iter, 0)
            self.desc_label.set_label(item.description)
        else:
            self.desc_label.set_label('')

    def value_data_func(self, column, cell, model, iter):
        """
            Value data func
        """
        type = model.get_value(iter, 3)
        if type == 'Boolean':
            cell.set_property('editable', False)
        else:
            cell.set_property('editable', True)
        cell.set_property('text', model.get_value(iter, 2))

    def row_activated(self, tree, path, col):
        """
            Called when the user clicks on the TreeView
        """
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 0)

        if item.type.lower() == 'boolean':
            item.value = not item.value
            self.model.set_value(iter, 2, item.value)
        else: return True

    def validate(self, type, value):
        """
            Validates a value for a given type
        """
        if type == 'Int':
            value = int(value)
        elif type == 'Float':
            value = float(value)
        elif type == 'List':
            value = eval(value)

    def edited_cb(self, cell, path, new_text, data=None):
        """
            Called when one of the cells is edited
        """
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 0)

        try:
            self.validate(item.type, new_text)
        except:
            common.error(self.parent, _('Invalid setting for %s' %
                item.name))
            return

        item.value = new_text
        self.model.set_value(iter, 2, new_text)

    def populate_model(self):
        """
            Populates the model with the settings items
        """
        self.model.clear()
        filter = unicode(self.filter.get_text(), 'utf-8')
        for item in self.items:
            if filter:
                if item.name.lower().find(filter.lower()) == -1: continue
            self.model.append([item, item.name, item.value, item.type])
