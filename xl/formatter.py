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

import gio
import glib
import gobject
import re
from datetime import date
from string import Template, _TemplateMetaclass

from xl import event, main, providers, settings, trax
from xl.common import TimeSpan
from xl.nls import gettext as _, ngettext

class _ParameterTemplateMetaclass(_TemplateMetaclass):
    pattern = r"""
    %(delim)s(?:
      (?P<escaped>%(delim)s) |   # Escape sequence of two delimiters
      (?P<named>%(id)s)      |   # delimiter and a Python identifier
      {(?P<braced>%(id_param)s)}   |   # delimiter and a braced identifier
      (?P<invalid>)              # Other ill-formed delimiter exprs
    )
    """
    # Allows for $tag, ${tag}, ${tag:parameter} and ${tag:parameter=argument}
    match_pattern = r"""
    %(delim)s(?:
      (?P<escaped>%(delim)s) |   # Escape sequence of two delimiters
      (?P<named>%(id)s)      |   # Delimiter and a Python identifier
      {
        (?P<braced>%(id)s)       # Delimiter and a braced identifier
        (!?:
          (?P<parameters>
            %(id)s               # First optional parameter indicated with ':'
            (!?=[^,}=]*)?        # Optional argument indicated with '='
            (!?,\s*%(id)s        # Further optional parameters separated with ','
              (!?=[^,}=]*)?      # Optional argument indicated with '='
            )*      
          )
        )?
      }                      |
      (?P<invalid>)              # Other ill-formed delimiter expressions
    )
    """

    def __init__(cls, name, bases, dct):
        super(_ParameterTemplateMetaclass, cls).__init__(name, bases, dct)
        if 'pattern' in dct:
            pattern = cls.pattern
        else:
            pattern = _ParameterTemplateMetaclass.pattern % {
                'delim'   : re.escape(cls.delimiter),
                'id'      : cls.idpattern,
                'id_param': cls.idpattern_param
            }
        cls.pattern = re.compile(pattern, re.IGNORECASE | re.VERBOSE)

        if 'match_pattern' in dct:
            match_pattern = cls.match_pattern
        else:
            match_pattern = _ParameterTemplateMetaclass.match_pattern % {
                'delim'   : re.escape(cls.delimiter),
                'id'      : cls.idpattern
            }
        cls.match_pattern = re.compile(match_pattern, re.IGNORECASE | re.VERBOSE)

class ParameterTemplate(Template):
    """
        An extended template class which additionally
        accepts parameters assigned to identifiers.

        This introduces another pattern group named
        "parameters" in addition to the groups
        created by string.Template.

        Examples:
        * ${foo:parameter1}
        * ${bar:parameter1, parameter2}
        * ${qux:parameter1=argument1, parameter2}
    """
    __metaclass__ = _ParameterTemplateMetaclass

    idpattern_param = r'[_a-z][_a-z0-9:=,]*'

    def __init__(self, template):
        """
            :param template: The template string
        """
        Template.__init__(self, template)

class Formatter(gobject.GObject):
    """
        A generic text formatter based on a format string
    """
    __gsignals__ = {
        'format-changed': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)
        )
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
            :type format: string
        """
        if self.__class__.__name__ == 'Formatter':
            raise TypeError("cannot create instance of abstract "
                            "(non-instantiable) type `Formatter'")
        gobject.GObject.__init__(self)

        self._template = ParameterTemplate(format)
        self._substitutions = {}

    def do_get_property(self, property):
        """
            Gets GObject properties
        """
        if property.name == 'format':
            return self._template.template
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_set_property(self, property, value):
        """
            Sets GObject properties
        """
        if property.name == 'format':
            if value != self._template.template:
                self._template.template = value
                self.emit('format-changed', value)
        else:
            raise AttributeError('unkown property %s' % property.name)

    def substitute(self, text, replacement):
        """
            Returns the replacement of a text

            :param text: The text to replace
            :type text: string
            :param replacement: The replacement
            :type replacement: string or callable
            :returns: The replacement
            :rtype: string
        """
        if callable(replacement):
            return replacement(text)

        return replacement

    def format(self, *args):
        """
            Returns a string by formatting the passed data

            :param args: Data to base the formatting on
            :returns: The formatted text
            :rtype: string
        """
        pass

class ProgressTextFormatter(Formatter):
    """
        A text formatter for progress indicators
    """
    def __init__(self):
        Formatter.__init__(self, self.get_option_value())

        event.add_callback(self.on_option_set, 'gui_option_set')

        try:
            exaile = main.exaile()
        except AttributeError:
            event.add_callback(self.on_exaile_loaded, 'exaile_loaded')
        else:
            self.on_exaile_loaded('exaile_loaded', exaile, None)

    def format(self, current_time=None, total_time=None):
        """
            Returns a string suitable for progress indicators

            :param current_time: the current progress
            :type current_time: float
            :param total_time: the total length of a track
            :type total_time: float
            :returns: The formatted text
            :rtype: string
        """
        if current_time is None:
            current_time = self.player.get_time()

        if total_time is None:
            total_time = self.player.current.get_tag_raw('__length')

        if total_time is None:
            total_time = remaining_time = 0
        else:
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
            :type duration: float
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

class TrackFormatter(Formatter, providers.ProviderHandler):
    """
        A formatter for track data
    """
    def __init__(self, format):
        """
            :param format: The initial format, see the documentation
                of string.Template for details
            :type format: string
        """
        Formatter.__init__(self, format)
        providers.ProviderHandler.__init__(self, 'tag_formatting')

    def format(self, track, markup_escape=False):
        """
            Returns a string suitable for progress indicators

            :param track: A single track to take data from
            :type track: :class:`xl.trax.Track`
            :param markup_escape: Whether to escape markup-like
                characters in tag values
            :type markup_escape: bool
            :returns: The formatted text
            :rtype: string
        """
        if not isinstance(track, trax.Track):
            raise TypeError('First argument to format() needs '
                            'to be of type xl.trax.Track')

        matches = self._template.match_pattern.finditer(self._template.template)
        tags = {}
        self._substitutions = {}

        # Extract list of tags contained in the format string
        for match in matches:
            groups = match.groupdict()

            # We don't care about escaped and invalid
            if groups['braced'] is not None:
                tag = groups['braced']
            elif groups['named'] is not None:
                tag = groups['named']
            else:
                continue

            idparts = [tag]
            parameters = {}

            if groups['parameters'] is not None:
                parameters = groups['parameters'].split(',')
                # Turns [['foo', 'arg'], ['bar']] into {'foo': 'arg', 'bar': True}
                parameters = dict([(p.split('=', 1) + [True])[:2] for p in parameters])
                idparts += [groups['parameters']]

            tags[':'.join(idparts)] = (tag, parameters)

        for id, (tag, parameters) in tags.iteritems():
            provider = self.get_provider(tag)

            if provider is None:
                self._substitutions[id] = track.get_tag_display(tag)
            else:
                self._substitutions[id] = provider.format(track, parameters)

        if markup_escape:
            for id in self._substitutions.iterkeys():
                self._substitutions[id] = glib.markup_escape_text(
                    self._substitutions[id])

        return self._template.safe_substitute(self._substitutions)

class TagFormatter():
    """
        A formatter for a tag of a track
    """
    def __init__(self, name):
        """
            :param name: The name of the tag
            :type name: string
        """
        self.name = name

    def format(self, track, parameters):
        """
            Formats a raw tag value. Accepts optional
            parameters to manipulate the formatting
            process.

            :param track: The track to get the tag from
            :type value: xl.trax.Track
            :param parameters: Optionally passed parameters
            :type parameters: dictionary
                Parameters specified via 'parameter=value'
                will be directly mapped into the dictionary,
                parameters without argument will be set to True
            :returns: The formatted value
            :rtype: string
        """
        pass

class TrackNumberTagFormatter(TagFormatter):
    """
        A formatter for the tracknumber of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, 'tracknumber')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: The track to get the tag from
            :type track: xl.trax.Track
            :param parameters: Optionally passed parameters
                Possible values are:
                * pad: n [n being an arbitrary number]
                  Influences the amount of leading zeros
            :type parameters: dictionary
            :returns: The formatted value
            :rtype: string
        """
        value = track.get_tag_raw(self.name, join=True)

        if not value:
            return ''

        pad = parameters.get('pad', 1)

        return self.format_value(value, pad)

    @staticmethod
    def format_value(value, pad=1):
        """
            Formats a tracknumber value

            :param value: A tracknumber
            :type value: int or string
            :param pad: Amount of leading zeros
            :type pad: int
            :returns: The formatted value
            :rtype: string
        """
        try:
            pad = int(pad)
        except ValueError: # No int
            pad = 1

        try: # n/n
            value, count = value.split('/')
        except ValueError: # n
            pass

        format_string = '%%0%(pad)dd' % {'pad': pad}

        try:
            value = format_string % int(value)
        except ValueError: # Invalid number
            pass

        return value

providers.register('tag_formatting', TrackNumberTagFormatter())

class LengthTagFormatter(TagFormatter):
    """
        A formatter for the length of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, '__length')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: The track to get the tag from
            :type track: xl.trax.Track
            :param parameters: Optionally passed parameters
                Possible values are:
                * format: (short|long|verbose)
                  Yields "1:02:42",
                  "1h, 2m, 42s" or
                  "1 hour, 2 minutes, 42 seconds"
            :type parameters: dictionary
            :returns: The formatted value
            :rtype: string
        """
        value = track.get_tag_raw(self.name)
        format = parameters.get('format', 'short')

        return self.format_value(value, format)

    @staticmethod
    def format_value(value, format='short'):
        """
            Formats a length value

            :param value: The length in seconds
            :type value: float
            :param format: Verbosity of the output
                Possible values are short, long or verbose
                yielding "1:02:42", "1h, 2m, 42s" or
                "1 hour, 2 minutes, 42 seconds"
            :type format: string
            :returns: The formatted value
            :rtype: string
        """
        span = TimeSpan(value)
        text = ''

        if format == 'verbose':
            if span.years > 0:
                text += ngettext('%d year, ', '%d years, ', span.years) % span.years

            if span.days > 0:
                text += ngettext('%d day, ', '%d days, ', span.days) % span.days

            if span.hours > 0:
                text += ngettext('%d hour, ', '%d hours, ', span.hours) % span.hours

            text += ngettext('%d minute, ', '%d minutes, ', span.minutes) % span.minutes
            text += ngettext('%d second', '%d seconds', span.seconds) % span.seconds
        elif format == 'long':
            if span.years > 0:
                # TRANSLATORS: Short form of an amount of years
                text += _('%dy, ') % span.years

            if span.days > 0:
                # TRANSLATORS: Short form of an amount of days
                text += _('%dd, ') % span.days

            if span.hours > 0:
                # TRANSLATORS: Short form of an amount of hours
                text += _('%dh, ') % span.hours

            # TRANSLATORS: Short form of an amount of minutes
            text += _('%dm, ') % span.minutes
            # TRANSLATORS: Short form of an amount of seconds
            text += _('%ds') % span.seconds
        elif format == 'short':
            durations = []

            if span.years > 0:
                durations += [span.years]

            if span.days > 0:
                durations += [span.days]

            if span.hours > 0:
                durations += [span.hours]

            durations += [span.minutes, span.seconds]

            first = durations.pop(0)
            values = ['%02d' % duration for duration in durations]
            values = ['%d' % first] + values

            text = ':'.join(values)
        else:
            raise ValueError('Invalid argument "%s" passed to parameter '
                '"format" for tag "__length", possible arguments are '
                '"short", "long" and "verbose"' % format)

        return text

providers.register('tag_formatting', LengthTagFormatter())

class RatingTagFormatter(TagFormatter):
    """
        A formatter for the rating of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, '__rating')

        self._rating_steps = 5
        self.on_option_set('option_set', settings,
            'miscellaneous/rating_steps')
        event.add_callback(self.on_option_set, 'miscellaneous_option_set')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: The track to get the tag from
            :type track: xl.trax.Track
            :param parameters: Optionally passed parameters
            :type parameters: dictionary
            :returns: The formatted value
            :rtype: string
        """
        value = track.get_tag_raw(self.name)

        try:
            value = float(value) / 100
        except TypeError:
            value = 0

        value *= self._rating_steps
        filled = '★' * int(value)
        empty = '☆' * int(self._rating_steps - value)

        return ('%s%s' % (filled, empty)).decode('utf-8')

    def on_option_set(self, event, settings, option):
        """
            Updates the internal rating steps value
        """
        if option == 'miscellaneous/rating_steps':
            self._rating_steps = settings.get_option(option, 5)

providers.register('tag_formatting', RatingTagFormatter())

class LastPlayedTagFormatter(TagFormatter):
    """
        A formatter for the last time a track was played
    """
    def __init__(self):
        TagFormatter.__init__(self, '__last_played')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: The track to get the tag from
            :type track: xl.trax.Track
            :param parameters: Optionally passed parameters
            :type parameters: dictionary
            :returns: The formatted value
            :rtype: string
        """
        value = track.get_tag_raw(self.name)
        text = _('Never')

        try:
            last_played = date.fromtimestamp(value)
        except TypeError, ValueError:
            text = _('Never')
        else:
            today = date.today()
            delta = today - last_played

            if delta.days == 0:
                text = _('Today')
            elif delta.days == 1:
                text = _('Yesterday')
            else:
                text = last_played.strftime('%x')

        return text
providers.register('tag_formatting', LastPlayedTagFormatter())

class FilenameTagFormatter(TagFormatter):
    """
        A formatter for the filename of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, 'filename')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: The track to get the tag from
            :type track: xl.trax.Track
            :param parameters: Optionally passed parameters
            :type parameters: dictionary
            :returns: The formatted value
            :rtype: string
        """
        gfile = gio.File(track.get_loc_for_io())

        return gfile.get_basename()
providers.register('tag_formatting', FilenameTagFormatter())

# vim: et sts=4 sw=4
