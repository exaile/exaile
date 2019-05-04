# moodbar - Replace Exaile's seekbar with a moodbar
# Copyright (C) 2015, 2018-2019  Johannes Sasongko <sasongko@gmail.com>
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


from __future__ import division, print_function, unicode_literals

import cairo


class Painter:
    def paint(data):
        """Paint moodbar to a Cairo surface.

        :param data: Moodbar data
        :type data: bytes
        :return: Cairo surface containing the image to be drawn
        :rtype: cairo.ImageSurface
        """
        raise NotImplementedError


class NormalPainter(Painter):
    def paint(self, data):
        width = len(data) // 3
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, width, 1)
        arr = surf.get_data()
        for index in xrange(0, width):
            index4 = index * 4
            index3 = index * 3
            # Cairo RGB24 is BGRX
            r, g, b = data[index3 : index3 + 3]
            arr[index4 + 0] = b
            arr[index4 + 1] = g
            arr[index4 + 2] = r
        return surf


class WaveformPainter(Painter):
    """Paint a waveform-like representation of the moodbar"""

    def paint(self, data):
        import math

        H = 100  # Number of pixels on one side of the waveform
        TOTAL_H = H * 2 + 1  # 1 px in the middle + H px above + H px below

        width = len(data) // 3
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, width, TOTAL_H)
        stride = surf.get_stride()
        arr = surf.get_data()
        for index in xrange(width):
            index3 = index * 3
            index4 = index * 4
            rgb = data[index3 : index3 + 3]
            level = int(round(self._scale_level(*rgb) * H))
            ystart = H - level
            yend = H + level
            rgb = self._scale_color(*rgb)
            for ic in xrange(0, 3):
                # Cairo RGB24 is BGRX
                val = rgb[2 - ic]
                for i in xrange(
                    ystart * stride + index4 + ic,
                    yend * stride + index4 + ic + 1,
                    stride,
                ):
                    arr[i] = val
        return surf

    @staticmethod
    def _scale_color(r, g, b):
        """Modify a color so it looks nicer on the waveform moodbar.

        :type r: bytes
        :type g: bytes
        :type b: bytes
        :rtype: Tuple[bytes, bytes, bytes]
        """
        import colorsys
        import math

        def _clamp(x, low, high):
            return max(low, min(x, high))

        r, g, b = map(ord, (r, g, b))
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        # These numbers are pulled out of thin air
        MIN = 80 / 255
        v = v * (1 - MIN) + MIN
        v = math.log(v + 1, 2)

        r, g, b = colorsys.hsv_to_rgb(h, s, v)

        def to_chr(c):
            return chr(int(_clamp(c, 0, 1) * 255))

        return to_chr(r), to_chr(g), to_chr(b)

    @staticmethod
    def _scale_level(r, g, b):
        """Calculate level based on moodbar color

        :type r: bytes
        :type g: bytes
        :type b: bytes
        :rtype: float
        """
        import math

        level = math.sqrt(ord(r) ** 2 + ord(g) ** 2 + ord(b) ** 2)
        level /= math.sqrt(255 ** 2 * 3)

        # These numbers are pulled out of thin air
        MIN = 10 / 255
        level = level * (1 - MIN) + MIN
        level = math.log(level + 1, 2)

        return level


# vi: et sts=4 sw=4 tw=99
