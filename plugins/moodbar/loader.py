from __future__ import division, print_function, unicode_literals

import cairo


class MoodbarLoader:
    def load(self, path):
        """
        :param path: Path of mood file to load
        :type path: bytes
        :return: Cairo surface containing the image to be drawn
        :rtype: cairo.ImageSurface
        """
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1000, 1)
        arr = surf.get_data()
        with open(path, 'rb') as f:
            for p in xrange(0, 4000, 4):
                arr[p + 2] = f.read(1)
                arr[p + 1] = f.read(1)
                arr[p + 0] = f.read(1)
        return surf
