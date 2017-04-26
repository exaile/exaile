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

# It seems like cairo does not support GObject Introspection.
import cairo


def paint(data):
    """Paint moodbar to a surface.

    :param data: Moodbar data
    :type data: bytes
    :return: Cairo surface containing the image to be drawn
    :rtype: cairo.ImageSurface
    """
    width = len(data) // 3
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, width, 1)
    arr = surf.get_data()
    for index in xrange(0, width):
        index4 = index * 4
        index3 = index * 3
        # Cairo RGB24 is BGRX
        arr[index4 + 0] = data[index3 + 2]
        arr[index4 + 1] = data[index3 + 1]
        arr[index4 + 2] = data[index3 + 0]
    return surf


# vi: et sts=4 sw=4 tw=99
