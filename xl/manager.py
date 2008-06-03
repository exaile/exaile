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

import event

class SimpleManager:
    """
        A simple class to easily manage a list of items, with add and remove events.
    """
    def __init__(self, name):
        self.name = name

        self.items = []

        self.active = 0

    def add(self, item, pos=-1):
        """
            add an item. if the position is not specified it defaults to appending
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
        """
        if pos < len(self.items):
            self.active = pos

