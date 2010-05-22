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

import gobject
import gtk

from xl import providers
from xlgui import icons

"""
    what we need to describe a menu item:
        - internal name
        - display name
        - callback


    menus itself supplies all items with a certain list of parameters
        - the parent object (playlist, collection, etc.)
        - the selected object(s) (tracks, tab, etc.)

    duties of the factory func:
        create the menu item
        set up any needed callbacks

    if a factory func fails to complete (raises error, returns something
        other than a valid gtk.MenuItem), that entry will be omitted from
        the resulting menu


    factory(menu, parent_obj, parent_context={prop:val, prop:val...})


"""

def simple_menu_item(id, after, display_name, icon_name, callback):
    """
        Factory function that should handle most cases for menus

        :param id: Internal name for the item. must be unique within the menu.
        :param after: List of ids which come before this item, this item will
                be placed after the lowest of these.
        :param display_name: Name as it is to appear in the menu.
        :param icon_name: Name of the icon to display, or None for no icon.
        :param callback: The function to call when the menu item is activated.
                signature: callback(widget, parent_obj, parent_context)
    """
    def factory(menu, parent_obj, parent_context):
        item = None
        if icon_name is not None:
            item = gtk.ImageMenuItem(display_name)
            image = gtk.image_new_from_icon_name(icon_name,
                    size=gtk.ICON_SIZE_MENU)
            item.set_image(image)
        else:
            item = gtk.MenuItem(display_name)
        item.connect('activate', callback, parent_obj, parent_context)
        return item
    return MenuItem(id, factory, after=after or [])



class MenuItem(object):
    def __init__(self, id, factory, after=[]):
        self.id = id
        self.after = after
        self.factory = factory

class Menu(gtk.Menu):
    def __init__(self, parent):
        gtk.Menu.__init__(self)
        self._parent = parent
        self._items = []

        self.connect('map', self.regenerate_menu)
        self.connect('unmap', self.clear_menu)

    def get_parent_context(self):
        return {}

    def add_item(self, item):
        if not item.after:
            self._items.append(item)
            return
        id = item.id
        if id in [i.id for i in self._items]:
            raise ValueError, "Menu already has an element with id %s."%id
        put_after = None
        for idx, i in enumerate(items):
            if i.id in item.after:
                put_after = idx
        if put_after is None:
            self._items.append(item)
        else:
            self._items.insert(idx+1, item)

    def remove_item(self, item):
        self._items.remove(item)

    def clear_menu(self, *args):
        # clear menu on unmap to prevent any references sticking around
        # due to saved parent_contexts.
        children = self.get_children()
        for c in children:
            self.remove(c)

    def regenerate_menu(self, *args):
        context = self.get_parent_context()
        for item in self._items:
            print item
            self.append(item.factory(self, self.parent, context))
        self.show_all()



class ProviderMenu(providers.ProviderHandler, Menu):
    pass



if __name__ == '__main__':
    menu = Menu()
    item = simple_menu_item('test', [], "Test", 'new', lambda *args: False)
    gobject.idle_add(menu.popup, None, None, None, 1, 1)
