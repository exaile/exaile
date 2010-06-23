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


import gobject, gtk

from xlgui.widgets import menu


class Action(gobject.GObject):
    __gsignals__ = {
        'activate': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            tuple()
        )
    }

    def __init__(self, name, display_name, icon_name):
        gobject.GObject.__init__(self)
        self.name = name
        self.display_name = display_name
        self.icon_name = icon_name

    def create_menu_item(self, after):
        return menu.simple_menu_item(self.name, after, self.display_name, self.icon_name, self.on_menu_activate)

    def on_menu_activate(self, widget, name, parent_obj, parent_context):
        self.activate()

    def create_button(self):
        b = gtk.Button(label=self.display_name, stock=self.icon_name)
        b.connect('activate', lambda *args: self.activate())
        return b

    def on_button_activate(self, button):
        self.activate()

    def activate(self):
        self.emit('activate')



class ToggleAction(Action):
    __gsignals__ = {
        'toggled': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            tuple()
        )
    }
    __gproperties__ = {
        'active': (
            gobject.TYPE_BOOLEAN,
            'active',
            'Whether the Action is active',
            False,
            gobject.PARAM_READWRITE
        )
    }

    def __init__(self, name, display_name, active=False):
        Action.__init__(self, name, display_name, None)
        self.set_property('active', active)

    def create_menu_item(self, after):
        return menu.check_menu_item(self.name, after, self.display_name, self.menu_checked_func, self.on_menu_activate)

    def menu_checked_func(self, name, parent_obj, parent_context):
        return self.props.active

    def on_menu_activate(self, widget, name, parent_obj, parent_context):
        self.toggle()

    def create_button(self):
        b = gtk.ToggleButton(label=self.display_name)
        b.connect('toggled', lambda *args: self.toggled())
        return b

    def toggle(self):
        self.props.active = not self.props.active
        self.emit('toggled')
        if self.props.active:
            self.activate()

class ChoiceAction(Action):
    pass
