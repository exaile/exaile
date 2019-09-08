# Copyright (C) 2009-2010 Aren Olson, 2014 Dustin Spicuzza
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

'''
    If you don't care about whether the UI/exaile have finished loading,
    you can create a plugin by implementing the following functions:

        def enable(exaile):
            print("Hello, world!")
            testlib.sucess()

        def disable(exaile):
            print("Goodbye. :(")

        def teardown(exaile):
            # optional function
            print("Unhello, World!")

    Exaile 3.4 introduced a new way to write plugins which will eliminate
    a lot of unnecessary boilerplate for plugin authors.

    New-style plugins must have a variable in the module that is
    called 'plugin_class', which is a Python object with the following
    interface:

    class Foo:

        def enable(self, exaile):
            pass

        def disable(self, exaile):
            pass

    The object can also have the following optional functions:

        def on_gui_loaded(self):
            - This will be called when the GUI is ready, or
              immediately if already done

        def on_exaile_loaded(self):
            - This will be called when exaile is done loading, or
              immediately if already done

        def teardown(self, exaile):
            - This will be called when exaile is unloading

    Note that the old style of writing plugins is not going away, so you
    can continue to write plugins that way if its simpler.
'''


from . import testlib


class HelloWorld:
    def enable(self, exaile):
        print("Hello, world!")
        testlib.sucess()

    def disable(self, exaile):
        print("Goodbye. :(")

    def teardown(self, exaile):
        '''Optional function'''
        print("Unhello, World!")

    def on_exaile_loaded(self):
        '''Optional function'''
        print('Exaile loaded!')


plugin_class = HelloWorld
