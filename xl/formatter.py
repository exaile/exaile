# -*- coding: utf-8 -*-
# Copyright (C) 2010 Mathias Brodala
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
from string import Template
from xl import event, main, settings
from xl.nls import gettext as _

class Formatter(gobject.GObject):
    """
        A generic text formatter based on a format string
    """
    __gsignals__ = {
        'format-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,))
    }
    __gproperties__ = {
        'format': (
            gobject.TYPE_STRING,
            'format string',
            'String the formatting is based on',
            '',
            gobject.PARAM_READWRITE
        )
    }
    def __init__(self, format):
        """
            :param format: The initial format, see the documentation
                of string.Template for details
        """
        if self.__class__.__name__ == 'Formatter':
            raise TypeError("cannot create instance of abstract "
                            "(non-instantiable) type `Formatter'")
        gobject.GObject.__init__(self)

        self._format = format
        self._template = Template(self._format)
        self._substitutions = {}

    def do_get_property(self, property):
        """
            Gets GObject properties
        """
        if property.name == 'format':
            return self._format
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_set_property(self, property, value):
        """
            Sets GObject properties
        """
        if property.name == 'format':
            self._format = value
            self._template = Template(self._format)
            self.emit('format-changed', self._format)
        else:
            raise AttributeError('unkown property %s' % property.name)

    def substitute(self, text, replacement):
        """
            Returns the replacement of a text
            :param text: The text to replace
            :param replacement: The replacement, can
                also be a method or function
        """
        if callable(replacement):
            return replacement(text)

        return replacement

    def format(self, *args):
        """
            Returns a string by formatting the passed data
            :param args: Data to base the formatting on
        """
        pass

class DurationFormatter(Formatter):
    """
        A generic text formatter for durations
        E. g. 1 day, 2 hours, 34 minutes, 21 seconds
        E. g. 45:20
    """
    pass

class ProgressBarTextFormatter(Formatter):
    """
        A text formatter for progress bars
    """
    def __init__(self):
        Formatter.__init__(self, self.get_option_value())

        event.add_callback(self.on_option_set, 'option_set')

        try:
            exaile = main.exaile()
        except AttributeError:
            event.add_callback(self.on_exaile_loaded, 'exaile_loaded')
        else:
            self.on_exaile_loaded('exaile_loaded', exaile, None)

    def format(self, *args):
        """
            Returns a string suitable for progress bar texts
            :param args: Allows for overriding of the values for
                current time and total time, in exactly that order
        """
        try:
            current_time = args[0]
        except KeyError:
            current_time = self.player.get_time()

        try:
            total_time = args[1]
        except KeyError:
            total_time = self.player.current.get_tag_raw('__length')

        remaining_time = total_time - current_time

        self._substitutions = {
            'current_time': self.format_duration(current_time),
            'remaining_time': self.format_duration(remaining_time),
            'total_time': self.format_duration(total_time)
        }
        
        return self._template.safe_substitute(self._substitutions)

    def get_option_value(self):
        """
            Returns the current option value
        """
        return settings.get_option('gui/progress_bar_text_format',
            '$current_time / $remaining_time')

    def format_duration(self, duration):
        """
            Returns a properly formatted duration
            :param duration: The duration to format, in seconds
        """
        hours = duration // 3600
        remainder = duration - hours * 3600
        minutes = remainder // 60
        seconds = remainder % 60

        if hours > 0:
            text = '%d:%02d:%02d' % (hours, minutes, seconds)
        else:
            text = '%d:%02d' % (minutes, seconds)

        return text

    def on_option_set(self, event, settings, option):
        """
            Updates the internal format on setting change
        """
        if option == 'gui/progress_bar_text_format':
            self.props.format = self.get_option_value()

    def on_exaile_loaded(self, e, exaile, nothing):
        """
            Sets up references after controller is loaded
        """
        self.player = exaile.player

        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

