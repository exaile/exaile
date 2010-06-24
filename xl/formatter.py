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
    # Allows for $tag, ${tag}, ${tag:parameter} and ${tag:parameter=argument}
    pattern = r"""
    %(delim)s(?:
      (?P<escaped>%(delim)s) |     # Escape sequence of two delimiters
      (?P<named>%(id)s)      |     # Delimiter and a Python identifier
      {
        (?P<braced>%(id)s)         # Delimiter and a braced identifier
        (!?:
          (?P<parameters>
            %(id)s                 # First optional parameter indicated with ':'
            (!?=(!?%(arg)s)+?)?    # Optional argument indicated with '='
            (!?,\s*%(id)s          # Further optional parameters separated with ','
              (!?=(!?%(arg)s)+?)?  # Optional argument indicated with '='
            )*      
          )
        )?
      }                      |
      (?P<invalid>)                # Other ill-formed delimiter expressions
    )
    """
    def __init__(cls, name, bases, dct):
        super(_ParameterTemplateMetaclass, cls).__init__(name, bases, dct)
        if 'pattern' in dct:
            pattern = cls.pattern
        else:
            pattern = _ParameterTemplateMetaclass.pattern % {
                'delim': re.escape(cls.delimiter),
                'id': cls.idpattern,
                'arg': cls.argpattern,
            }
        cls.pattern = re.compile(pattern, re.IGNORECASE | re.VERBOSE)

class ParameterTemplate(Template):
    """
        An extended template class which additionally
        accepts parameters assigned to identifiers.

        This introduces another pattern group named
        "parameters" in addition to the groups
        created by :class:`string.Template`

        Examples:
        * ${foo:parameter1}
        * ${bar:parameter1, parameter2}
        * ${qux:parameter1=argument1, parameter2}
    """
    __metaclass__ = _ParameterTemplateMetaclass
    argpattern = r'[^,}=]|\,|\}|\='

    def __init__(self, template):
        """
            :param template: The template string
        """
        Template.__init__(self, template)

    def safe_substitute(self, *args, **kwargs):
        """
            Overridden to allow for parametrized identifiers
        """
        if len(args) > 1:
            raise TypeError('Too many positional arguments')

        if not args:
            mapping = kwargs
        elif kwargs:
            mapping = _multimap(kwargs, args[0])
        else:
            mapping = args[0]

        # Helper function for .sub()
        def convert(mo):
            named = mo.group('named')

            if named is not None:
                try:
                    # We use this idiom instead of str() because the latter
                    # will fail if val is a Unicode containing non-ASCII
                    return '%s' % (mapping[named],)
                except KeyError:
                    return self.delimiter + named

            braced = mo.group('braced')

            if braced is not None:
                parts = [braced]
                parameters = mo.group('parameters')

                if parameters is not None:
                    parts += [parameters]

                try:
                    return '%s' % (mapping[':'.join(parts)],)
                except KeyError:
                    return self.delimiter + '{' + ':'.join(parts) + '}'

            if mo.group('escaped') is not None:
                return self.delimiter

            if mo.group('invalid') is not None:
                return self.delimiter

            raise ValueError('Unrecognized named group in pattern',
                             self.pattern)

        return self.pattern.sub(convert, self.template)

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

    def extract(self):
        """
            Retrieves the identifiers and their optional parameters

            Format of the returned dictionary:
            extractions = {
                'identifier1': (
                    'identifier1', {}),
                'identifier2:parameter': (
                    'identifier2', {'parameter': True}),
                'identifier3:parameter=argument': (
                    'identifier3', {'parameter': 'argument'})
            }

            :returns: the extractions
            :rtype: dict
        """
        matches = self._template.pattern.finditer(self._template.template)
        extractions = {}

        # Extract list of identifiers and parameters from the format string
        for match in matches:
            groups = match.groupdict()

            # We only care about braced and named, not escaped and invalid
            identifier = groups['braced'] or groups['named']

            if identifier is None:
                continue

            identifier_parts = [identifier]
            parameters = {}

            if groups['parameters'] is not None:
                # Split parameters on unescaped comma
                parameters = [p.lstrip() \
                    for p in re.split(r'(?<!\\),', groups['parameters'])]
                # Split arguments on unescaped equals sign
                parameters = [(re.split(r'(?<!\\)=', p, 1) + [True])[:2] \
                    for p in parameters]
                # Turn list of lists into a proper dictionary
                parameters = dict(parameters)

                # Remove now obsolete escapes
                for p in parameters:
                    argument = parameters[p]

                    if type(argument) is not bool:
                        argument = argument.replace(r'\,', ',')
                        argument = argument.replace(r'\}', '}')
                        argument = argument.replace(r'\=', '=')
                        parameters[p] = argument

                identifier_parts += [groups['parameters']]

            # Required to make multiple occurences of the same
            # identifier with different parameters work
            extractions[':'.join(identifier_parts)] = (identifier, parameters)

        return extractions

    def format(self, *args):
        """
            Returns a string by formatting the passed data

            :param args: Data to base the formatting on
            :returns: The formatted text
            :rtype: string
        """
        extractions = self.extract()
        substitutions = {}

        for needle, (identifier, parameters) in extractions.iteritems():
            substitute = None

            if needle in self._substitutions:
                substitute = self._substitutions[needle]
            elif identifier in self._substitutions:
                substitute = self._substitutions[identifier]

            if substitute is not None:
                prefix = parameters.pop('prefix', '')
                suffix = parameters.pop('suffix', '')
                pad = int(parameters.pop('pad', 0))
                padstring = parameters.pop('padstring', '')

                if callable(substitute):
                    substitute = substitute(*args, **parameters)

                if pad > 0 and padstring:
                    # Decrease pad length by value length
                    pad = max(0, pad - len(substitute))
                    # Retrieve the maximum multiplier for the pad string
                    padcount = pad / len(padstring) + 1
                    # Generate pad string
                    padstring = padcount * padstring
                    # Clamp pad string
                    padstring = padstring[0:pad]
                    substitute = '%s%s' % (padstring, substitute)

                if substitute:
                    substitute = '%s%s%s' % (prefix, substitute, suffix)

                substitutions[needle] = substitute

        return self._template.safe_substitute(substitutions)

class ProgressTextFormatter(Formatter):
    """
        A text formatter for progress indicators
    """
    def __init__(self, format):
        """
            :param format: The initial format, see the documentation
                of string.Template for details
            :type format: string
        """
        Formatter.__init__(self, format)

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

        self._substitutions['current_time'] = \
            LengthTagFormatter.format_value(current_time)
        self._substitutions['remaining_time'] = \
            LengthTagFormatter.format_value(remaining_time)
        self._substitutions['total_time'] = \
            LengthTagFormatter.format_value(total_time)

        return Formatter.format(self)

    def on_exaile_loaded(self, e, exaile, nothing):
        """
            Sets up references after controller is loaded
        """
        self.player = exaile.player
        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

class TrackFormatter(Formatter):
    """
        A formatter for track data
    """
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

        extractions = self.extract()
        self._substitutions = {}

        for identifier, (tag, parameters) in extractions.iteritems():
            provider = providers.get_provider('tag-formatting', tag)

            if provider is None:
                substitute = track.get_tag_display(tag)
            else:
                substitute = provider.format(track, parameters)

            if markup_escape:
                substitute = glib.markup_escape_text(substitute)

            self._substitutions[identifier] = substitute

        return Formatter.format(self)

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

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
            :type parameters: dictionary
                Parameters specified via 'parameter=value'
                will be directly mapped into the dictionary,
                parameters without argument will be set to True
            :returns: the formatted value
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

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
            :type parameters: dictionary
            :returns: the formatted value
            :rtype: string
        """
        value = track.get_tag_raw(self.name, join=True)

        if not value:
            return ''

        try: # n/n
            value, count = value.split('/')
        except ValueError: # n
            pass

        if value == "":
            return ""
        return '%d' % int(value)
providers.register('tag-formatting', TrackNumberTagFormatter())

class DiscNumberTagFormatter(TagFormatter):
    """
        A formatter for the tracknumber of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, 'discnumber')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
            :type parameters: dictionary
            :returns: the formatted value
            :rtype: string
        """
        value = track.get_tag_raw(self.name, join=True)

        if not value:
            return ''

        try: # n/n
            value, count = value.split('/')
        except ValueError: # n
            pass

        if value == "":
            return ""
        return '%d' % int(value)
providers.register('tag-formatting', DiscNumberTagFormatter())

class ArtistTagFormatter(TagFormatter):
    """
        A formatter for the artist of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, 'artist')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
                Possible values are:
                * compilate:
                  Allows for proper handling of compilations,
                  either via albumartist tag, a fallback value,
                  or simply all artists
            :returns: the formatted value
            :rtype: string
        """
        compilate = parameters.get('compilate', False)
        value = track.get_tag_display(self.name,
            artist_compilations=compilate)

        return value
providers.register('tag-formatting', ArtistTagFormatter())

class LengthTagFormatter(TagFormatter):
    """
        A formatter for the length of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, '__length')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
                Possible values are:
                * format: (short|long|verbose)
                  Yields "1:02:42",
                  "1h, 2m, 42s" or
                  "1 hour, 2 minutes, 42 seconds"
            :type parameters: dictionary
            :returns: the formatted value
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
            :returns: the formatted value
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
providers.register('tag-formatting', LengthTagFormatter())

class RatingTagFormatter(TagFormatter):
    """
        A formatter for the rating of a track
    """
    def __init__(self):
        TagFormatter.__init__(self, '__rating')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
            :type parameters: dictionary
            :returns: the formatted value
            :rtype: string
        """
        rating = track.get_rating()
        maximum = settings.get_option('rating/maximum', 5)

        filled = '★' * int(rating)
        empty = '☆' * int(maximum - rating)

        return ('%s%s' % (filled, empty)).decode('utf-8')
providers.register('tag-formatting', RatingTagFormatter())

class LastPlayedTagFormatter(TagFormatter):
    """
        A formatter for the last time a track was played
    """
    def __init__(self):
        TagFormatter.__init__(self, '__last_played')

    def format(self, track, parameters):
        """
            Formats a raw tag value

            :param track: the track to get the tag from
            :type track: :class:`xl.trax.Track`
            :param parameters: optionally passed parameters
            :type parameters: dictionary
            :returns: the formatted value
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
providers.register('tag-formatting', LastPlayedTagFormatter())

# vim: et sts=4 sw=4
