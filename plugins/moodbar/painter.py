# Johannes Sasongko <sasongko@gmail.com>, 2015


from __future__ import division, print_function, unicode_literals

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
        for p in xrange(0, 1000):
            p4 = p * 4
            p3 = p * 3
            arr[p4:(p4+3)] = data[p3:(p3+3)]
        return surf
