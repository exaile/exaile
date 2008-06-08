# Classes to assist in the creation of *Manager classes.
#
# SimpleManager - a very simple manager, basically a list with events on 
# add/remove

import event

class SimpleManager(object):
    """
        A simple class to easily manage a list of items, with add and 
        remove events.
    """
    def __init__(self, name):
        """
            name: the name of this manager
        """
        self.name = name

        self.items = []

        self.active = 0

    def add(self, item, pos=-1):
        """
            add an item. if the position is not specified it defaults 
            to appending

            item: the item to add [object]
            pos: the index to insert at [int]
        """
        if item not in self.items:
            if pos == -1:
                self.items.append(item)
            else:
                self.items.insert(pos, item)
                if pos <= self.active:
                    self.active += 1
            event.log_event("item_added", self, item)
        else:
            raise KeyError("Item already in Manager")

    def remove(self, item):
        """
            removes an item

            item: the item to remove [object]
        """
        i = self.items.index(item)
        self.remove(item)
        if i < self.active:
            self.active -= 1
        event.log_event("item_removed", self, item)

    def all(self):
        """
            returns a list of all items
        """
        return self.items[:]

    def get_active(self):
        """
            get the currently active item
        """
        return self.items[self.active]

    def set_active(self, pos):
        """
            set the currently active item

            pos: the index to make active [int]
        """
        if pos < len(self.items):
            self.active = pos
# vim: et sts=4 sw=4

