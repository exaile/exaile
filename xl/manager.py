# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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


class SimpleManager(object):
    """
        Simple Manager
        
        other managers will extend this
    """
    def __init__(self):
        """
            Initializes the simple manager
        """
        self.methods = {}
        self.preferred_order = []

        # Should call child class method
        self.add_defaults()

    def add_search_method(self, method):
        """
            Adds a search method

            @param method: search method
        """
        self.methods[method.name] = method
        method._set_manager(self)

    def remove_search_method(self, method):
        """
            Removes a search method
            
            @param method: the method to remove
        """
        if method.name in self.methods:
            del self.methods[method.name]

    def remove_search_method_by_name(self, name):
        """
            Removes a search method
            
            @param name: the name of the method to remove
        """
        if name in self.methods:
            del self.methods[name]

    def set_preferred_order(self, order):
        """
            Sets the preferred search order

            @param order: a list containing the order you'd like to search
                first
        """
        if not type(order) in (list, tuple):
            raise AttributeError("order must be a list or tuple")
        self.preferred_order = order

    def add_defaults(self):
        """
            Adds default search methods
        """
        pass # Not all managers will need to add defaults

    def get_methods(self):
        """
            returns a list of Methods, sorted by preference
        """
        methods = []
        for name in self.preferred_order:
            if name in self.methods:
                methods.append(self.methods[name])
        for k, method in self.methods.iteritems():
            if k not in self.preferred_order:
                methods.append(method)
        return methods

