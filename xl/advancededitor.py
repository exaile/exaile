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

import gtk
from gettext import gettext as _

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
        elif self.type == 'bool':
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
                handler = getattr(eventhandler, changefunc)

            self.items.append(ConfigurationItem(self, name, type, current,
                description, handler))

        main = gtk.VBox()
        main.set_border_width(3)
        main.set_spacing(3)
        self.add(main)

        top_box = gtk.HBox()
        top_box.pack_start(gtk.Label(_('Filter:') + '  '), False, False)
        self.filter = gtk.Entry()
        top_box.pack_start(self.filter, True, True)

        main.pack_start(top_box, False, False)

        self.model = gtk.ListStore(object, str, str, str)
        self.populate_model()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.tree = gtk.TreeView(self.model)

        # set up the treeview
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Setting Name'))
        col.pack_start(text, True)
        col.set_attributes(text, text=1)
        self.tree.append_column(col)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Value'))
        col.pack_start(text, True)
        col.set_attributes(text, text=2)
        self.tree.append_column(col)

        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Type'))
        col.pack_start(text, False)
        col.set_attributes(text, text=3)
        self.tree.append_column(col)

        scroll.add(self.tree)

        main.pack_start(scroll, True, True)

        buttons = gtk.HBox()
        close = gtk.Button(_('Close'), gtk.STOCK_CLOSE)
        close.connect('clicked', lambda *e: self.destroy())
        buttons.pack_end(close, False, False)

        main.pack_start(buttons, False, False)

        self.resize(635, 500)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.show_all()

    def populate_model(self):
        """
            Populates the model with the settings items
        """
        for item in self.items:
            self.model.append([item, item.name, item.value, item.type])
