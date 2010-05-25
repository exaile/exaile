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

from xl import providers, settings
from xlgui import icons, rating
from xl.nls import gettext as _

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

def simple_separator(name, after):
    def factory(menu, parent_obj, parent_context):
        item = gtk.SeparatorMenuItem()
        return item
    item = MenuItem(name, factory, after=after)
    item.pos = 'last'
    return item

def simple_menu_item(name, after, display_name, icon_name, callback):
    """
        Factory function that should handle most cases for menus

        :param name: Internal name for the item. must be unique within the menu.
        :param after: List of ids which come before this item, this item will
                be placed after the lowest of these.
        :param display_name: Name as ito.close is to appear in the menu.
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
    return MenuItem(name, factory, after=after)



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

class RatingMenuItem(MenuItem):
    def __init__(self, name, after, tracks_func):
        # tracks_func(parent, context) -> list of tracks
        MenuItem.__init__(self, name, self._factory, after)
        self.tracks_func = tracks_func

    def _factory(self, menu, parent_obj, parent_context):
        item = gtk.MenuItem()
        tracks = self.tracks_func(parent_obj, parent_context)
        ratingnum = self._get_tracks_rating(tracks)

        hbox = gtk.HBox(spacing=3)
        hbox.pack_start(gtk.Label(_("Rating:")), False, False)
        image = gtk.image_new_from_pixbuf(self._get_pixbuf(ratingnum))
        hbox.pack_start(image)
        item.add(hbox)

        item.connect('button-release-event',
                self._update_rating, image, tracks)
        item.connect('motion-notify-event', self._motion_notify, image)
        item.connect('leave-notify-event',
                self._leave_notify, image, ratingnum)
        return item

    @staticmethod
    def _get_tracks_rating(tracks):
        ratingnum = tracks[0].get_rating()
        for tr in tracks:
            if tr.get_rating() != ratingnum:
                return 0
        return ratingnum

    @staticmethod
    def _get_pixbuf(num):
        return rating.rating_images[num]

    @staticmethod
    def _event_to_r(widget, event, image):
        steps = settings.get_option('miscellaneous/rating_steps', 5)
        (x, y) = event.get_coords()
        try:
            (u, v) =  widget.translate_coordinates(image, int(x), int(y))
        except ValueError:
            return

        if -12 <= u < 0:
            r = 0
        elif 0 <= u < (steps+1)*12:
            r = (u / 12)
        else:
            r = -1
        return r

    @classmethod
    def _update_rating(cls, widget, event, image, tracks):
        r = cls._event_to_r(widget, event, image)
        if r >= 0:
            for tr in tracks:
                tr.set_rating(r)

    @classmethod
    def _motion_notify(cls, widget, event, image):
        r = cls._event_to_r(widget, event, image)
        if r >= 0:
            image.set_from_pixbuf(cls._get_pixbuf(r))
            widget.queue_draw()

    @classmethod
    def _leave_notify(cls, widget, event, image, ratingnum):
        image.set_from_pixbuf(cls._get_pixbuf(ratingnum))
        widget.queue_draw()

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
        items = [(pmap[i._pos], i) for i in self._items]
        items.sort()
        newitems = []
        for item in items:
            item = item[1]
            if not item.after:
                newitems.append(item)
                continue
            id = item.name
            put_after = None
            for idx, i in enumerate(newitems):
                if i.name in item.after:
                    put_after = idx
            if put_after is None:
                newitems.append(item)
            else:
                newitems.insert(put_after+1, item)
        self._items = newitems

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


testmenu = ProviderMenu("test", None)
providers.register("test", simple_menu_item("test", [], "Test Providers", None,
    lambda *args: False))


