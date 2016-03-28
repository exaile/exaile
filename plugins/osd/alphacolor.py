# Copyright (C) 2012 Mathias Brodala
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

from gi.repository import Gdk

class AlphaColor(Gdk.Color):
    """
        Wrapper around :class:`Gdk.Color`
        to incorporate an alpha value
    """
    __gtype_name__ = 'Color'

    def __init__(self, *args, **kwargs):
        """
            :param red: The red color component in the range 0-65535
            :param green: The green color component in the range 0-65535
            :param blue: The blue color component in the range 0-65535
            :param alpha: The alpha intensity in the range 0-65535
            :param pixel: The index of the color when allocated in its colormap
            :param spec: String containing color specification

            :returns: a new :class:`AlphaColor` object
        """
        if len(args) == 1:
            if 'spec' not in kwargs:
                kwargs['spec'] = args[0]
                args = ()

        if 'spec' in kwargs:
            # Error out early if there are other keyword
            # arguments or regular arguments specified
            if len(kwargs) > 1 or len(args) > 0:
                raise TypeError('Usage:\n'
                                '  Color(red, green, blue, alpha, pixel)  '
                                '[all are optional]\n'
                                '  Color(spec)                            '
                                '[see color_parse_with_alpha()]')
            color = color_parse_with_alpha(kwargs.pop('spec'))
            args = (color.red, color.green, color.blue, color.alpha)

        # Create mapping of available parameters and arguments
        parameters = dict(list(zip(('red', 'green', 'blue', 'alpha', 'pixel'), args)))

        for parameter in parameters.keys():
            if parameter in kwargs:
                raise TypeError('Usage:\n'
                                '  Color(red, green, blue, alpha, pixel)  '
                                '[all are optional]\n'
                                '  Color(spec)                            '
                                '[see color_parse_with_alpha()]')

        parameters.update(kwargs)
        kwargs = parameters
        args = ()
        self.__alpha = kwargs.pop('alpha', 0)

        Gdk.Color.__init__(self, *args, **kwargs)

    def __get_alpha(self):
        return self.__alpha

    def __set_alpha(self, value):
        self.__alpha = int(value)

    def __get_alpha_float(self):
        return self.alpha / 65535.0

    def __set_alpha_float(self, value):
        self.alpha = min(max(0, value), 1) * 65535

    alpha = property(__get_alpha, __set_alpha)
    alpha_float = property(__get_alpha_float, __set_alpha_float)

    def to_string(self):
        """
            Returns a textual specification of color in the 
            hexadecimal form #rrrrggggbbbbaaaa, where r, g,
            b and a are hex digits representing the red, green,
            blue and alpha components respectively.

            :rtype: string
        """
        return '#%04x%04x%04x%04x' % (self.red, self.green, self.blue, self.alpha)

    def __eq__(self, other):
        if other is None:
            return False

        return (self.red == other.red and
                self.green == other.green and
                self.blue == other.blue and
                self.alpha == other.alpha)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self))

    def __str__(self):
        return self.to_string()

def alphacolor_parse(spec):
    """
        Parses the given color specification and
        its contained alpha value if any. Will always
        prefer evaluating the last digit as alpha.

        :param spec: a string containing a color specification
        :type spec: string
        :returns: alphacolor
        :rtype: :class:`AlphaColor`
    """
    if not len(spec):
        raise ValueError('unable to parse colour specification')

    alpha = 0

    if spec[0] == '#':
        if (len(spec) - 1) % 4 == 0:
            digits = len(spec) // 4
            alpha_spec = spec[-digits:]
            spec = spec[:-digits]
            # Example 'f':              15 / float(16**1 - 1) = 1.0
            # Example 'cc':            204 / float(16**2 - 1) = 0.8
            fraction = int(alpha_spec, 16) / float(16**digits - 1)
            alpha = int(fraction * 65535)

    color = Gdk.color_parse(spec)

    return AlphaColor(
        red=color.red,
        green=color.green,
        blue=color.blue,
        alpha=alpha
    )
