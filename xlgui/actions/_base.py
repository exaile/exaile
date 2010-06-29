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


class BaseAction(gobject.GObject):
    def __init__(self, name):
        gobject.GObject.__init__(self)
        self.name = name
        self._props = {}

    def create_menu_item(self, after):
        raise NotImplementedError

    def create_button(self):
        raise NotImplementedError

class Action(BaseAction):
    __gsignals__ = {
        'activate': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            tuple()
        )
    }

    def __init__(self, name, display_name, icon_name):
        BaseAction.__init__(self, name)
        self.display_name = display_name
        self.icon_name = icon_name

    def create_menu_item(self, after):
        return menu.simple_menu_item(self.name, after, self.display_name, self.icon_name, self.on_menu_activate)

    def on_menu_activate(self, widget, name, parent_obj, parent_context):
        self.activate()

    def create_button(self):
        b = gtk.Button(label=self.display_name, stock=self.icon_name)
        b.connect('activate', self.on_button_activate)
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
    active = gobject.property(type=gobject.TYPE_BOOLEAN, default=False)

    def __init__(self, name, display_name, icon_name, active=False):
        Action.__init__(self, name, display_name, icon_name)
        self.set_property('active', active)

    def create_menu_item(self, after):
        return menu.check_menu_item(self.name, after, self.display_name, self.menu_checked_func, self.on_menu_activate)

    def menu_checked_func(self, name, parent_obj, parent_context):
        return self.props.active

    def on_menu_activate(self, widget, name, parent_obj, parent_context):
        self.toggle()

    def create_button(self):
        b = gtk.ToggleButton(label=self.display_name, stock=self.icon_name)
        b.connect('toggled', lambda *args: self.toggled())
        return b

    def set_active(self, active):
        if self.props.active != active:
            self.toggle()

    def toggle(self):
        self.props.active = not self.props.active
        self.emit('toggled')
        if self.props.active:
            self.activate()


class ChoiceAction(BaseAction):
    __gsignals__ = {
        'changed': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (int,)
        )
    }

    active_choice = gobject.property(type=gobject.TYPE_INT)

    # choice name of "----" means separator
    # choices MUST be unique (except for separators)

    def __init__(self, name, display_name, icon_name, choices, choice_displays, active_choice=0):
        BaseAction.__init__(self, name)
        self.display_name = display_name
        self.icon_name = icon_name
        self.choices = choices[:]
        self.choice_displays = choice_displays[:]
        self.set_active_choice(active_choice)

    def set_active_choice(self, index):
        if not index < len(self.choices):
            raise IndexError, "Choice index out of range."
        if self.choices[index] == "----":
            raise ValueError, "Cannot choose a separator."
        oldval = self.get_property('active-choice')
        if oldval != index: # only emit if changed, helps avoid event loops
            self.set_property('active-choice', index)
            self.emit('changed', index)

    def create_submenu(self):
        m = menu.Menu(self)
        previous = None
        sep_count = 0
        for choice, display in zip(self.choices, self.choice_displays):
            after = [previous] if previous else []
            if choice == "----":
                # force sep names to be unique
                choice = choice + str(sep_count)
                sep_count += 1
                item = menu.simple_separator(choice, after)
            else:
                item = menu.radio_menu_item(choice, after, display, self.name, self.choice_selected_func, self.on_choice_activated)
            m.add_item(item)
            previous = choice
        return m

    def choice_selected_func(self, name, parent_obj, parent_context):
        return name == self.choices[self.props.active_choice]

    def on_choice_activated(self, widget, name, parent_obj, parent_context):
        self.set_active_choice(self.choices.index(name))

    def create_menu_item(self, after):
        return menu.simple_menu_item(self.name, after, self.display_name, self.icon_name, lambda *args: None, submenu=self.create_submenu())

    def create_button(self):
        pass


