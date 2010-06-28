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

from xl import (
    common,
    event,
    providers,
    settings,
    trax
)
from xl.nls import gettext as _
from xlgui import icons
from xlgui.widgets import rating


def simple_separator(name, after):
    def factory(menu, parent_obj, parent_context):
        item = gtk.SeparatorMenuItem()
        return item
    item = MenuItem(name, factory, after=after)
    item._pos = 'last'
    return item

def simple_menu_item(name, after, display_name, icon_name, callback, submenu=None):
    """
        Factory function that should handle most cases for menus

        :param name: Internal name for the item. must be unique within the menu.
        :param after: List of ids which come before this item, this item will
                be placed after the lowest of these.
        :param display_name: Name as is to appear in the menu.
        :param icon_name: Name of the icon to display, or None for no icon.
        :param callback: The function to call when the menu item is activated.
                signature: callback(widget, name, parent_obj, parent_context)
        :param submenu: The gtk.Menu that is to be the submenu of this item
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
        if submenu is not None:
            item.set_submenu(submenu)
        item.connect('activate', callback, name, parent_obj, parent_context)
        return item
    return MenuItem(name, factory, after=after)

def check_menu_item(name, after, display_name, checked_func, callback):
    def factory(menu, parent_obj, parent_context):
        item = gtk.CheckMenuItem(display_name)
        active = checked_func(name, parent_obj, parent_context)
        item.set_active(active)
        item.connect('activate', callback, name, parent_obj, parent_context)
        return item
    return MenuItem(name, factory, after=after)

def radio_menu_item(name, after, display_name, groupname, selected_func,
        callback):

    def factory(menu, parent_obj, parent_context):
        for index, item in enumerate(menu._items):
            if hasattr(item, 'groupname') and item.groupname == groupname:
                break
        else:
            index = None
        if index is not None:
            try:
                group_parent = menu.get_children()[index]
            except IndexError:
                group_parent = None

        item = gtk.RadioMenuItem(label=display_name)
        active = selected_func(name, parent_obj, parent_context)
        item.set_active(active)
        if group_parent:
            item.set_group(group_parent)
        item.connect('activate', callback, name, parent_obj, parent_context)
        return item
    return RadioMenuItem(name, factory, after=after, groupname=groupname)




class MenuItem(object):
    def __init__(self, name, factory, after):
        self.name = name
        self.after = after
        self.factory = factory
        self._pos = 'normal' # Don't change this unless you have a REALLY good
                             # reason to. after= is the 'supported'
                             # method of ordering, this property is not
                             # considered public api and may change
                             # without warning.

class RadioMenuItem(MenuItem):
    def __init__(self, name, factory, after, groupname):
        MenuItem.__init__(self, name, factory, after)
        self.groupname = groupname

class RatingMenuItem(MenuItem):
    """
        A menu item displaying rating images
        and allowing for selection of ratings
    """
    def __init__(self, name, after, get_tracks_func):
        MenuItem.__init__(self, name, self.factory, after)
        self.get_tracks_func = get_tracks_func

    def factory(self, menu, parent_obj, parent_context):
        item = rating.RatingMenuItem(auto_update=False)
        item.connect('show', self.on_show, menu, parent_obj, parent_context)
        self._rating_changed_id = item.connect('rating-changed',
            self.on_rating_changed, menu, parent_obj, parent_context)

        return item

    def on_show(self, widget, menu, parent_obj, context):
        """
            Updates the menu item on show
        """
        widget.disconnect(self._rating_changed_id)
        tracks = self.get_tracks_func(menu, parent_obj, context)
#        tracks = [row[1] for row in context['selected-tracks']]
        rating = trax.util.get_rating_from_tracks(tracks)
        widget.props.rating = rating
        self._rating_changed_id = widget.connect('rating-changed',
            self.on_rating_changed, menu, parent_obj, context)

    def on_rating_changed(self, widget, rating, menu, parent_obj, context):
        """
            Passes the 'rating-changed' signal
        """
        tracks = self.get_tracks_func(menu, parent_obj, context)
        #tracks = [row[1] for row in context['selected-tracks']]

        for track in tracks:
            track.set_rating(rating)

        maximum = settings.get_option('rating/maximum', 5)
        event.log_event('rating_changed', self, rating / maximum * 100)

class Menu(gtk.Menu):
    def __init__(self, parent):
        gtk.Menu.__init__(self)
        self._parent = parent
        self._items = []
        self.connect('show', self.regenerate_menu)
        self.connect('hide', self.clear_menu)

    def get_parent_context(self):
        return {}

    def add_item(self, item):
        self._items.append(item)
        self.reorder_items()

    def remove_item(self, item):
        self._items.remove(item)

    def clear_menu(self, *args):
        # clear menu on unmap to prevent any references sticking around
        # due to saved parent_contexts.
        children = self.get_children()
        for c in children:
            self.remove(c)

    def reorder_items(self):
        pmap = {'first': 0, 'normal': 1, 'last': 2}
        items = [common.PosetItem(i.name, i.after, pmap[i._pos], value=i) for i in self._items]
        items = common.order_poset(items)
        self._items = [i.value for i in items]

    def regenerate_menu(self, *args):
        context = self.get_parent_context()
        for item in self._items:
            self.append(item.factory(self, self._parent, context))
        self.show_all()


class ProviderMenu(providers.ProviderHandler, Menu):
    def __init__(self, name, parent):
        providers.ProviderHandler.__init__(self, name)
        Menu.__init__(self, parent)
        for p in self.get_providers():
            self.on_provider_added(p)

    def on_provider_added(self, provider):
        self.add_item(provider)

    def on_provider_removed(self, provider):
        self.remove_item(provider)


