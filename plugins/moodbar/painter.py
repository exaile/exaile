# moodbar - Replace Exaile's seekbar with a moodbar
# Copyright (C) 2015, 2018-2019, 2021  Johannes Sasongko <sasongko@gmail.com>
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


from typing import Tuple

import cairo


class Painter:
    def paint(self, data: bytes) -> cairo.ImageSurface:
        """Paint moodbar to a Cairo surface.

        :param data: Moodbar data
        :return: Cairo surface containing the image to be drawn
        """
        raise NotImplementedError


class NormalPainter(Painter):
    def paint(self, data: bytes) -> cairo.ImageSurface:
        width = len(data) // 3
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, width, 1)
        arr = surf.get_data()
        for index in range(width):
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

    def paint(self, data: bytes) -> cairo.ImageSurface:
        H = 100  # Number of pixels on one side of the waveform
        TOTAL_H = H * 2 + 1  # 1 px in the middle + H px above + H px below

        width = len(data) // 3
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, width, TOTAL_H)
        stride = surf.get_stride()
        arr = surf.get_data()
        for index in range(width):
            index3 = index * 3
            index4 = index * 4
            rgb = data[index3 : index3 + 3]
            level = int(round(self._scale_level(*rgb) * H))
            ystart = H - level
            yend = H + level
            rgb = self._scale_color(*rgb)
            for ic in range(3):
                # Cairo RGB24 is BGRX
                val = rgb[2 - ic]
                for i in range(
                    ystart * stride + index4 + ic,
                    yend * stride + index4 + ic + 1,
                    stride,
                ):
                    arr[i] = val
        return surf

    @staticmethod
    def _scale_color(r: int, g: int, b: int) -> Tuple[int, int, int]:
        """Modify a color so it looks nicer on the waveform moodbar."""

        import colorsys
        import math

        def _clamp(x, low, high):
            return max(low, min(x, high))

        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        # These numbers are pulled out of thin air
        MIN = 80 / 255
        v = v * (1 - MIN) + MIN
        v = math.log(v + 1, 2)

        rf, gf, bf = colorsys.hsv_to_rgb(h, s, v)

        def to_u8(c):
            return int(_clamp(c, 0, 1) * 255)

        return to_u8(rf), to_u8(gf), to_u8(bf)

    @staticmethod
    def _scale_level(r: int, g: int, b: int) -> float:
        """Calculate level based on moodbar color"""

        import math

        level = math.sqrt(r ** 2 + g ** 2 + b ** 2)
        level /= math.sqrt(255 ** 2 * 3)

        # These numbers are pulled out of thin air
        MIN = 10 / 255
        level = level * (1 - MIN) + MIN
        level = math.log(level + 1, 2)

        return level
