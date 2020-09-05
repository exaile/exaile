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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

from gi.repository import Gtk

from xl import common, providers

# Fake accel group so that menuitems can trick GTK into
# showing accelerators in the menus.
FAKEACCELGROUP = Gtk.AccelGroup()


def simple_separator(name, after):
    def factory(menu, parent, context):
        item = Gtk.SeparatorMenuItem()
        return item

    item = MenuItem(name, factory, after=after)
    item._pos = 'last'
    return item


def _get_accel(callback, display_name):
    # utility function to get menu information from an xlgui.Accelerator
    accelerator = None
    if hasattr(callback, 'key') and hasattr(callback, 'mods'):
        accelerator = callback
        if display_name is None:
            display_name = accelerator.helptext
        callback = accelerator.callback
    return accelerator, callback, display_name


def simple_menu_item(
    name,
    after,
    display_name=None,
    icon_name=None,
    callback=None,
    callback_args=[],
    submenu=None,
    condition_fn=None,
    sensitive_cb=None,
):
    """
    Factory function that should handle most cases for menus

    :param name: Internal name for the item. must be unique within the menu.
    :param after: List of ids which come before this item, this item will
            be placed after the lowest of these.
    :param display_name: Name as is to appear in the menu.
    :param icon_name: Name of the icon to display, or None for no icon.
    :param callback: The function to call when the menu item is activated OR
                     an xlgui accelerator object.
            signature: callback(widget, name, parent, context)
    :param submenu: The Gtk.Menu that is to be the submenu of this item
    :param condition_fn: A function to call when the menu is displayed. If
            the function returns False, the menu item is not shown
            signature: condition_fn(name, parent, context)
    :param sensitive_cb: A function that if it returns False, the menu item
                         will be disabled
    """
    accelerator, callback, display_name = _get_accel(callback, display_name)

    def factory(menu, parent, context):
        item = None

        if condition_fn is not None and not condition_fn(name, parent, context):
            return None

        if display_name is not None:
            if icon_name is not None:
                item = Gtk.ImageMenuItem.new_from_stock(display_name)
                image = Gtk.Image.new_from_icon_name(icon_name, size=Gtk.IconSize.MENU)
                item.set_image(image)
            else:
                item = Gtk.MenuItem.new_with_mnemonic(display_name)
        else:
            item = Gtk.ImageMenuItem.new_from_stock(icon_name)

        if submenu is not None:
            item.set_submenu(submenu)

        if accelerator is not None:
            item.add_accelerator(
                'activate',
                FAKEACCELGROUP,
                accelerator.key,
                accelerator.mods,
                Gtk.AccelFlags.VISIBLE,
            )

        if callback is not None:
            item.connect('activate', callback, name, parent, context, *callback_args)

        if sensitive_cb is not None and not sensitive_cb():
            item.set_sensitive(False)

        return item

    return MenuItem(name, factory, after=after)


def check_menu_item(name, after, display_name, checked_func, callback):
    accelerator, callback, display_name = _get_accel(callback, display_name)

    def factory(menu, parent, context):
        item = Gtk.CheckMenuItem.new_with_mnemonic(display_name)
        active = checked_func(name, parent, context)
        item.set_active(active)
        if accelerator is not None:
            item.add_accelerator(
                'activate',
                FAKEACCELGROUP,
                accelerator.key,
                accelerator.mods,
                Gtk.AccelFlags.VISIBLE,
            )
        item.connect('activate', callback, name, parent, context)
        return item

    return MenuItem(name, factory, after=after)


def radio_menu_item(name, after, display_name, groupname, selected_func, callback):
    def factory(menu, parent, context):
        for index, item in enumerate(menu._items):
            if hasattr(item, 'groupname') and item.groupname == groupname:
                break
        else:
            index = None

        if index is not None:
            try:
                group_parent = menu.get_children()[index]
                if not isinstance(group_parent, Gtk.RadioMenuItem):
                    group_parent = None
            except IndexError:
                group_parent = None

        if group_parent:
            group = group_parent.get_group()
        else:
            group = None

        item = Gtk.RadioMenuItem.new_with_mnemonic(group, display_name)
        active = selected_func(name, parent, context)
        item.set_active(active)

        item.connect('activate', callback, name, parent, context)
        return item

    return RadioMenuItem(name, factory, after=after, groupname=groupname)


class MenuItem:
    __slots__ = ['name', 'after', '_factory', '_pos', '_provider_data']

    def __init__(self, name, factory, after):
        self.name = name
        self.after = after
        self._factory = factory
        self._pos = 'normal'  # Don't change this unless you have a REALLY good
        # reason to. after= is the 'supported'
        # method of ordering, this property is not
        # considered public api and may change
        # without warning.

    def factory(self, menu, parent, context):
        """
        The factory function is called when the menu is shown, and
        should return a menu item. If it returns None, the item is
        not shown.
        """
        return self._factory(menu, parent, context)

    def register(self, servicename, target=None):
        """
        Shortcut for providers.register(), allows registration
        for use with a ProviderMenu
        """
        self._provider_data = (servicename, target)
        return providers.register(servicename, self, target=target)

    def unregister(self):
        """
        Shortcut for providers.unregister()
        """
        servicename, target = self._provider_data
        return providers.unregister(servicename, self, target)

    def __repr__(self):
        return '<xlgui.widgets.MenuItem: %s>' % self.name


class RadioMenuItem(MenuItem):
    __slots__ = ['groupname']

    def __init__(self, name, factory, after, groupname):
        MenuItem.__init__(self, name, factory, after)
        self.groupname = groupname


class Menu(Gtk.Menu):
    """
    Generic flexible menu with reliable
    menu item order and context handling
    """

    def __init__(self, parent, context_func=None, inherit_context=False):
        """
        :param parent: the parent for this menu
        :param context_func: a function for context
            retrieval
        :param inherit_context: If a submenu, inherit context function from
                                parent menu
        """
        Gtk.Menu.__init__(self)
        self._parent = parent
        self._items = []
        self.context_func = context_func
        self.connect('show', lambda *e: self.regenerate_menu())
        self.connect('hide', lambda *e: self.clear_menu())
        # Placeholder exists to make sure unity doesn't get confused (legacy?)
        self.placeholder = Gtk.MenuItem.new_with_mnemonic('')
        self._inherit_context = inherit_context

    def get_context(self):
        """
        Retrieves the menu context which
        can contain various data

        :returns: {'key1': 'value1', ...}
        :rtype: dictionary
        """
        if self._inherit_context:
            return self.get_parent_shell().get_context()
        elif self.context_func is None:
            return {}
        else:
            return self.context_func(self._parent)

    def add_item(self, item):
        """
        Adds a menu item and triggers reordering

        :param item: the menu item
        :type item: :class:`MenuItem`
        """
        self._items.append(item)
        self.reorder_items()

    def add_simple(self, label, callback, icon_name=None):
        """
        Provide a simple mechanism to add menu items without a lot of hassle

        :param label: Label to display
        :param callback: Callback that will be called on click
        :param icon_name: GTK mostly ignores this, and it will go away

        .. note:: If you use this API, you should generally only use this
                  API to add items to that menu
        """
        self.add_item(
            simple_menu_item(
                '_i%s' % len(self._items),
                [],
                label,
                icon_name=icon_name,
                callback=callback,
            )
        )

    def remove_item(self, item):
        """
        Removes a menu item

        :param item: the menu item
        :type item: :class:`MenuItem`
        """
        self._items.remove(item)

    def clear_menu(self):
        """
        Removes all menu items and submenus to prevent
        references sticking around due to saved contexts
        """
        self.append(self.placeholder)
        children = self.get_children()
        for c in children:
            if c == self.placeholder:
                continue
            c.set_submenu(None)
            self.remove(c)

    def reorder_items(self):
        """
        Reorders all menu items
        """
        pmap = {'first': 0, 'normal': 1, 'last': 2}
        items = [
            common.PosetItem(i.name, i.after, pmap[i._pos], value=i)
            for i in self._items
        ]
        items = common.order_poset(items)
        self._items = [i.value for i in items]

    def regenerate_menu(self):
        """
        Regenerates the menu by retrieving
        the context and calling the factory
        method of all menu items
        """
        context = self.get_context()
        if self.placeholder in self.get_children():
            self.remove(self.placeholder)
        for item in self._items:
            subitem = item.factory(self, self._parent, context)
            if subitem is not None:
                self.append(subitem)
        self.show_all()

    def popup(self, *args):
        """
        Pops out the menu (Only if
        there are items to show)
        """
        if len(self._items) > 0:
            if len(args) == 1:
                event = args[0]
                Gtk.Menu.popup(self, None, None, None, None, event.button, event.time)
            else:
                Gtk.Menu.popup(self, *args)


class ProviderMenu(providers.ProviderHandler, Menu):
    """
    A menu that can be added to by registering a menu item with
    the providers system. If desired, a menu item can be targeted
    towards a specific parent widget.
    """

    def __init__(self, name, parent):
        providers.ProviderHandler.__init__(self, name, parent)
        Menu.__init__(self, parent)
        for p in self.get_providers():
            self.on_provider_added(p)

    def on_provider_added(self, provider):
        self.add_item(provider)

    def on_provider_removed(self, provider):
        self.remove_item(provider)


class MultiProviderMenu(providers.MultiProviderHandler, Menu):
    """
    A menu that can be added to by registering a menu item with
    the providers system. If desired, a menu item can be targeted
    towards a specific parent widget.

    Supports retrieving menu items from multiple providers
    """

    def __init__(self, names, parent):
        providers.MultiProviderHandler.__init__(self, names, parent)
        Menu.__init__(self, parent)
        for p in self.get_providers():
            self.on_provider_added(p)

    def on_provider_added(self, provider):
        self.add_item(provider)

    def on_provider_removed(self, provider):
        self.remove_item(provider)
