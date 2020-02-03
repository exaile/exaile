# mpris2 - Support MPRIS 2 in Exaile
# Copyright (C) 2015-2016  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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


from gi.repository import GLib

Variant = GLib.Variant


class DBusHelper:
    """Helper to make D-Bus handling more Pythonic.

    The `object` argument of the constructor should be a Python object in the
    following form:

        class Object:
            def MyMethod(self, arg1, arg2):
                return GLib.Variant('s', 'out1'), GLib.Variant('s', 'out2')
            @property
            def MyProperty(self):
                return GLib.Variant('i', 0)
            @MyProperty.setter
            def MyProperty(self, value):
                pass

    You can then set the `method_call`, `get_property`, and `set_property`
    methods as the callbacks for the D-Bus object (i.e. the last three
    arguments in `DBusConnection.register_object`).

    Methods receive their arguments as plain Python objects, whereas property
    setters receive theirs as `GLib.Variant`s.
    Both methods and property setters must return their values as
    `GLib.Variant`s (technically, the return type is `Union[None, GLib.Variant,
    Tuple[GLib.Variant]]`).

    A Python method or property is exported if the name starts with an
    uppercase character and does not end with `_`.
    Attributes which are neither methods nor properties are not exported.
    """

    def __init__(self, obj):
        self.object = obj

    def method_call(
        self, connection, sender, path, interface, method, args, invocation
    ):
        self._check_method(method)
        result = getattr(self.object, method)(*args)
        # If the method returns nothing, return empty tuple. If the method
        # returns multiple values, return those. If the method returns a single
        # value, wrap in a tuple and return.
        if result is None:
            result = Variant.new_tuple()
        elif isinstance(result, tuple):
            assert all(isinstance(v, Variant) for v in result)
            result = Variant.new_tuple(*result)
        else:
            assert isinstance(result, Variant)
            result = Variant.new_tuple(result)
        invocation.return_value(result)

    def get_property(self, connection, sender, path, interface, prop):
        self._check_property(prop)
        return getattr(self.object, prop)

    def set_property(self, connection, sender, path, interface, prop, value):
        self._check_property(prop)
        setattr(self.object, prop, value)
        return True

    def _check_method(self, meth):
        """Check that `meth` is a valid property of `self.object`"""
        import types

        if meth and meth[0].isupper() and not meth.endswith('_'):
            classprop = getattr(self.object.__class__, meth, None)
            if isinstance(classprop, types.FunctionType):
                return
        raise AttributeError("Invalid method: " + meth)

    def _check_property(self, prop):
        """Check that `prop` is a valid property of `self.object`"""
        if prop and prop[0].isupper() and not prop.endswith('_'):
            classprop = getattr(self.object.__class__, prop, None)
            if isinstance(classprop, property):
                return
        raise AttributeError("Invalid property: " + prop)
