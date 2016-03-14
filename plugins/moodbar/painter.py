# moodbar - Replace Exaile's seekbar with a moodbar
# Copyright (C) 2015  Johannes Sasongko <sasongko@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import division, print_function, unicode_literals

from six.moves import range
import cairo


class MoodbarPainter:
    """Turn moodbar data into Cairo surface, ready to be drawn"""

    def paint(self, data):
        """Paint moodbar to a surface.

        :param data: Moodbar data
        :type data: bytes
        :return: Cairo surface containing the image to be drawn
        :rtype: cairo.ImageSurface
        """
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 1)
        arr = surf.get_data()
        for p in range(0, 1000):
            p4 = p * 4
            p3 = p * 3
            # Cairo RGB24 is BGRX
            arr[p4 + 0] = data[p3 + 2]
            arr[p4 + 1] = data[p3 + 1]
            arr[p4 + 2] = data[p3 + 0]
        return surf


# vi: et sts=4 sw=4 tw=99
