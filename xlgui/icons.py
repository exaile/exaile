# Copyright (C) 2008-2010 Adam Olsen
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

"""
    Provides methods for convenient icons and image handling
"""

import glob
from gi.repository import (
    Gdk,
    GdkPixbuf,
    GLib,
    Gtk
)
import logging
import os

from xl import (
    common,
    settings,
    xdg
)

logger = logging.getLogger(__name__)


class ExtendedPixbuf(object):
    """
        A :class:`GdkPixbuf.Pixbuf` wrapper class allowing for
        interaction using standard operators

        Thus you can do the following:

        * ``pixbuf1 + pixbuf2`` (horizontally appends ``pixbuf2`` to ``pixbuf1``)
        * ``pixbuf * 5`` (multiplies the content of ``pixbuf``)
        * ``pixbuf1 & pixbuf2`` (simple composition of ``pixbuf2`` on ``pixbuf1``, the desired alpha value has to be included in the pixbufs themselves)
        * ``pixbuf1 < pixbuf2``, ``pixbuf1 > pixbuf2`` (compares the pixbuf dimensions)
        * ``pixbuf1 == pixbuf2`` (compares the pixel data, use the *is* operator to check for identity)

        Even more is possible with the provided verbose methods
    """

    def __init__(self, pixbuf):
        self.pixbuf = GdkPixbuf.Pixbuf.new(
            pixbuf.get_colorspace(),
            pixbuf.get_has_alpha(),
            pixbuf.get_bits_per_sample(),
            pixbuf.get_width(),
            pixbuf.get_height()
        )
        pixbuf.copy_area(
            src_x=0, src_y=0,
            width=self.pixbuf.get_width(), height=self.pixbuf.get_height(),
            dest_pixbuf=self.pixbuf,
            dest_x=0, dest_y=0
        )

    def get_width(self):
        return self.pixbuf.get_width()

    def get_height(self):
        return self.pixbuf.get_height()

    def __add__(self, other):
        """
            Horizontally appends a pixbuf to the current

            :param other: the pixbuf to append
            :type other: :class:`GdkPixbuf.Pixbuf`
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        return self.add_horizontal(other)

    def __mul__(self, multiplier):
        """
            Horizontally multiplies the current pixbuf content

            :param multiplier: How often the pixbuf
                shall be multiplied
            :type multiplier: int
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        return self.multiply_horizontal(multiplier)

    def __and__(self, other):
        """
            Composites a pixbuf on the current
            pixbuf at the location (0, 0)

            :param other: the pixbuf to composite
            :type other: :class:`GdkPixbuf.Pixbuf`
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        return self.composite_simple(other)

    def __lt__(self, other):
        """
            True if the size (width * height) of the current
            pixbuf is lower than the size of the other pixbuf
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf
        self_size = self.pixbuf.get_width() * self.pixbuf.get_height()
        other_size = other.get_width() * other.get_height()

        return self_size < other_size

    def __le__(self, other):
        """
            True if the size (width * height) of the current
            pixbuf is lower than or equal to the size of the
            other pixbuf
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf
        self_size = self.pixbuf.get_width() * self.pixbuf.get_height()
        other_size = other.get_width() * other.get_height()

        return self_size <= other_size

    def __gt__(self, other):
        """
            True if the size (width * height) of the current
            pixbuf is higher than the size of the other pixbuf
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf
        self_size = self.pixbuf.get_width() * self.pixbuf.get_height()
        other_size = other.get_width() * other.get_height()

        return self_size > other_size

    def __ge__(self, other):
        """
            True if the size (width * height) of the current
            pixbuf is higher than or equal to the size of the
            other pixbuf
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf
        self_size = self.pixbuf.get_width() * self.pixbuf.get_height()
        other_size = other.get_width() * other.get_height()

        return self_size >= other_size

    def __eq__(self, other):
        """
            True if the pixels of the current pixbuf are
            the same as the pixels from the other pixbuf
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf
        return self.pixbuf.get_pixels() == other.get_pixels()

    def __ne__(self, other):
        """
            True if the pixels of the current pixbuf are
            not the same as the pixels from the other pixbuf
        """
        return not self.__eq__(other)

    def add_horizontal(self, other, spacing=0):
        """
            Horizontally appends a pixbuf to the current

            :param other: the pixbuf to append
            :type other: :class:`GdkPixbuf.Pixbuf`
            :param spacing: amount of pixels between the pixbufs
            :type spacing: int
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf

        height = max(self.pixbuf.get_height(), other.get_height())
        spacing = max(0, spacing)

        new_pixbuf = GdkPixbuf.Pixbuf.new(
            self.pixbuf.get_colorspace(),
            self.pixbuf.get_has_alpha(),
            self.pixbuf.get_bits_per_sample(),
            self.pixbuf.get_width() + spacing + other.get_width(),
            height
        )
        new_pixbuf.fill(0xffffff00)

        self.pixbuf.copy_area(
            src_x=0, src_y=0,
            width=self.pixbuf.get_width(), height=self.pixbuf.get_height(),
            dest_pixbuf=new_pixbuf,
            dest_x=0, dest_y=0
        )
        other.copy_area(
            src_x=0, src_y=0,
            width=other.get_width(), height=other.get_height(),
            dest_pixbuf=new_pixbuf,
            dest_x=self.pixbuf.get_width() + spacing, dest_y=0
        )

        return ExtendedPixbuf(new_pixbuf)

    def add_vertical(self, other, spacing=0):
        """
            Vertically appends a pixbuf to the current

            :param other: the pixbuf to append
            :type other: :class:`GdkPixbuf.Pixbuf`
            :param spacing: amount of pixels between the pixbufs
            :type spacing: int
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf

        width = max(self.pixbuf.get_width(), other.get_width())
        spacing = max(0, spacing)

        new_pixbuf = GdkPixbuf.Pixbuf.new(
            self.pixbuf.get_colorspace(),
            self.pixbuf.get_has_alpha(),
            self.pixbuf.get_bits_per_sample(),
            width,
            self.pixbuf.get_height() + spacing + other.get_height()
        )
        new_pixbuf.fill(0xffffff00)

        self.pixbuf.copy_area(
            src_x=0, src_y=0,
            width=self.pixbuf.get_width(), height=self.pixbuf.get_height(),
            dest_pixbuf=new_pixbuf,
            dest_x=0, dest_y=0
        )
        other.copy_area(
            src_x=0, src_y=0,
            width=other.get_width(), height=other.get_height(),
            dest_pixbuf=new_pixbuf,
            dest_x=0, dest_y=self.pixbuf.get_height() + spacing
        )

        return ExtendedPixbuf(new_pixbuf)

    def multiply_horizontal(self, multiplier, spacing=0):
        """
            Horizontally multiplies the current pixbuf content

            :param multiplier: How often the pixbuf
                shall be multiplied
            :type multiplier: int
            :param spacing: amount of pixels between the pixbufs
            :type spacing: int
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        spacing = max(0, spacing)
        new_pixbuf = GdkPixbuf.Pixbuf.new(
            self.pixbuf.get_colorspace(),
            self.pixbuf.get_has_alpha(),
            self.pixbuf.get_bits_per_sample(),
            self.pixbuf.get_width() * multiplier + spacing * multiplier,
            self.pixbuf.get_height()
        )
        new_pixbuf.fill(0xffffff00)

        for n in xrange(0, multiplier):
            self.pixbuf.copy_area(
                src_x=0, src_y=0,
                width=self.pixbuf.get_width(), height=self.pixbuf.get_height(),
                dest_pixbuf=new_pixbuf,
                dest_x=n * self.pixbuf.get_width() + n * spacing, dest_y=0
            )

        return ExtendedPixbuf(new_pixbuf)

    def multiply_vertical(self, multiplier, spacing=0):
        """
            Vertically multiplies the current pixbuf content

            :param multiplier: How often the pixbuf
                shall be multiplied
            :type multiplier: int
            :param spacing: amount of pixels between the pixbufs
            :type spacing: int
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        spacing = max(0, spacing)
        new_pixbuf = GdkPixbuf.Pixbuf.new(
            self.pixbuf.get_colorspace(),
            self.pixbuf.get_has_alpha(),
            self.pixbuf.get_bits_per_sample(),
            self.pixbuf.get_width(),
            self.pixbuf.get_height() * multiplier + spacing * multiplier
        )
        new_pixbuf.fill(0xffffff00)

        for n in xrange(0, multiplier):
            self.pixbuf.copy_area(
                src_x=0, src_y=0,
                width=self.pixbuf.get_width(), height=self.pixbuf.get_height(),
                dest_pixbuf=new_pixbuf,
                dest_x=0, dest_y=n * self.pixbuf.get_height() + n * spacing
            )

        return ExtendedPixbuf(new_pixbuf)

    def composite_simple(self, other):
        """
            Composites a pixbuf on the current
            pixbuf at the location (0, 0)

            :param other: the pixbuf to composite
            :type other: :class:`GdkPixbuf.Pixbuf`
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        if isinstance(other, ExtendedPixbuf):
            other = other.pixbuf

        width = max(self.pixbuf.get_width(), other.get_width())
        height = max(self.pixbuf.get_height(), other.get_height())

        new_pixbuf = GdkPixbuf.Pixbuf.new(
            self.pixbuf.get_colorspace(),
            self.pixbuf.get_has_alpha(),
            self.pixbuf.get_bits_per_sample(),
            width, height
        )
        new_pixbuf.fill(0xffffff00)

        for pixbuf in (self.pixbuf, other):
            pixbuf.composite(
                dest=new_pixbuf,
                dest_x=0, dest_y=0,
                dest_width=pixbuf.get_width(),
                dest_height=pixbuf.get_height(),
                offset_x=0, offset_y=0,
                scale_x=1, scale_y=1,
                interp_type=GdkPixbuf.InterpType.BILINEAR,
                # Alpha needs to be embedded in the pixbufs
                overall_alpha=255
            )

        return ExtendedPixbuf(new_pixbuf)

    def move(self, offset_x, offset_y, resize=False):
        """
            Moves the content of the current pixbuf within
            its boundaries (clips overlapping data) and
            optionally resizes the pixbuf to contain the
            movement

            :param offset_x: the amount of pixels to move
                in horizontal direction
            :type offset_x: int
            :param offset_y: the amount of pixels to move
                in vertical direction
            :type offset_y: int
            :param resize: whether to resize the pixbuf
                on movement
            :type resize: bool
            :returns: a new pixbuf
            :rtype: :class:`ExtendedPixbuf`
        """
        width = self.pixbuf.get_width()
        height = self.pixbuf.get_height()

        if resize:
            width += offset_x
            height += offset_y

        new_pixbuf = GdkPixbuf.Pixbuf.new(
            self.pixbuf.get_colorspace(),
            self.pixbuf.get_has_alpha(),
            self.pixbuf.get_bits_per_sample(),
            width, height
        )
        new_pixbuf.fill(0xffffff00)

        self.pixbuf.copy_area(
            src_x=0, src_y=0,
            width=self.pixbuf.get_width(),
            height=self.pixbuf.get_height(),
            dest_pixbuf=new_pixbuf,
            dest_x=offset_x, dest_y=offset_y
        )

        return ExtendedPixbuf(new_pixbuf)

    def copy(self):
        """
            Override to return same type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.copy(self.pixbuf))

    def add_alpha(self, substitute_color, r, g, b):
        """
            Override to return same type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.add_alpha(
            self.pixbuf, substitute_color, r, g, b))

    def scale_simple(self, dest_width, dest_height, interp_type):
        """
            Override to return same type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.scale_simple(
            self.pixbuf, dest_width, dest_height, interp_type))

    def composite_color_simple(self, dest_width, dest_height, interp_type,
                               overall_alpha, check_size, color1, color2):
        """
            Override to return same type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.composite_color_simple(
            self.pixbuf, dest_width, dest_height, interp_type,
            overall_alpha, check_size, color1, color2))

    def new_subpixbuf(self, src_x, src_y, width, height):
        """
            Override to return same type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.new_subpixbuf(
            self.pixbuf, src_x, src_y, width, height))

    def rotate_simple(self, angle):
        """
            Override to return same type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.rotate_simple(self.pixbuf, angle))

    def flip(self, horizontal):
        """
            Override to return sampe type
        """
        return ExtendedPixbuf(GdkPixbuf.Pixbuf.flip(self.pixbuf, horizontal))


def extended_pixbuf_new_from_file(filename):
    """
        Returns a new :class:`ExtendedPixbuf` containing
        an image loaded from the specified file

        :param filename: the name of the file
            containing the image to load
        :type filename: string
        :returns: a new pixbuf
        :rtype: :class:`ExtendedPixbuf`
    """
    return ExtendedPixbuf(GdkPixbuf.Pixbuf.new_from_file(filename))


class IconManager(object):
    """
        Provides convenience functions for
        managing icons and images in general
    """

    def __init__(self):
        self.icon_theme = Gtk.IconTheme.get_default()
        # TODO: Make svg actually recognized
        self._sizes = [16, 22, 24, 32, 48, 128, 'scalable']
        self._cache = {}

        self.rating_active_pixbuf = extended_pixbuf_new_from_file(
            xdg.get_data_path('images', 'star.png'))
        self.rating_inactive_pixbuf = extended_pixbuf_new_from_file(
            xdg.get_data_path('images', 'emptystar.png'))

        # nobody actually sets the rating option, so don't handle it for now
        #event.add_ui_callback(self.on_option_set, 'rating_option_set')

    def add_icon_name_from_directory(self, icon_name, directory):
        """
            Registers an icon name from files found in a directory

            :param icon_name: the name for the icon
            :type icon_name: string
            :param directory: the location to search for icons
            :type directory: string
            :return: filesystem location of the highest-quality icon of this
                name, or None if not found
            :rtype: Optional[str]
        """
        path = None
        for size in self._sizes:
            if isinstance(size, int):  # WxH/icon_name.png and scalable/icon_name.svg
                sizedir = '%dx%d' % (size, size)
            else:
                sizedir = size
            filepath = os.path.join(directory, sizedir, icon_name)
            files = glob.glob('%s.*' % filepath)
            if files:
                path = files[0]
                icon_size = size if size != 'scalable' else -1
                self.add_icon_name_from_file(icon_name, path, icon_size)
            else:  # icon_nameW.png and icon_name.svg
                if isinstance(size, int):
                    filename = '%s%d' % (icon_name, size)
                else:
                    filename = icon_name
                filepath = os.path.join(directory, filename)
                files = glob.glob('%s.*' % filepath)
                if files:
                    path = files[0]
                    icon_size = size if size != 'scalable' else -1
                    self.add_icon_name_from_file(icon_name, path, icon_size)
                else:  # Give up
                    pass
        return path

    def add_icon_name_from_file(self, icon_name, filename, size=None):
        """
            Registers an icon name from a filename

            :param icon_name: the name for the icon
            :type icon_name: string
            :param filename: the filename of an image
            :type filename: string
            :param size: the size the icon shall be registered for
            :type size: int
        """
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)
            self.add_icon_name_from_pixbuf(icon_name, pixbuf, size)
        except Exception as e:
            # Happens if, e.g., librsvg is not installed.
            logger.warning('Failed to add icon name "{icon_name}" '
                           'from file "{filename}": {error}'.format(
                               icon_name=icon_name,
                               filename=filename,
                               error=e.message
                           ))
            pass

    def add_icon_name_from_pixbuf(self, icon_name, pixbuf, size=None):
        """
            Registers an icon name from a pixbuf

            :param icon_name: the name for the icon
            :type icon_name: string
            :param pixbuf: the pixbuf of an image
            :type pixbuf: :class:`GdkPixbuf.Pixbuf`
            :param size: the size the icon shall be registered for
            :type size: int
        """
        if size is None:
            size = pixbuf.get_width()

        Gtk.IconTheme.add_builtin_icon(icon_name, size, pixbuf)

    def pixbuf_from_icon_name(self, icon_name, size=Gtk.IconSize.BUTTON):
        """
            Generates a pixbuf from an icon name

            :param icon_name: an icon name
            :type icon_name: string
            :param size: the size of the icon, will be
                tried to converted to a GTK icon size
            :type size: int or GtkIconSize

            :returns: the generated pixbuf
            :rtype: :class:`GdkPixbuf.Pixbuf` or None
        """
        if not isinstance(size, int):
            icon_size = Gtk.icon_size_lookup(size)
            size = icon_size[1]

        try:
            pixbuf = self.icon_theme.load_icon(
                icon_name, size, Gtk.IconLookupFlags.NO_SVG)
        except GLib.GError as e:
            logger.warning('Failed to get pixbuf from "{icon_name}": {error}'.format(
                icon_name=icon_name,
                error=e.message
            ))
            pixbuf = None

        # TODO: Check if fallbacks are necessary
        return pixbuf

    def pixbuf_from_data(self, data, size=None, keep_ratio=True, upscale=False):
        """
            Generates a pixbuf from arbitrary image data

            :param data: The raw image data
            :type data: byte
            :param size: Size to scale to; if not specified,
                the image will render to its native size
            :type size: tuple of int
            :param keep_ratio: Whether to keep the original
                image ratio on resizing operations
            :type keep_ratio: bool
            :param upscale: Whether to upscale if the requested
                size exceeds the native size
            :type upscale: bool

            :returns: the generated pixbuf
            :rtype: :class:`GdkPixbuf.Pixbuf` or None
        """
        if not data:
            return None

        pixbuf = None
        loader = GdkPixbuf.PixbufLoader()

        if size is not None:
            def on_size_prepared(loader, width, height):
                """
                    Keeps the ratio if requested
                """
                if keep_ratio:
                    scale = min(size[0] / float(width), size[1] / float(height))

                    if scale > 1.0 and upscale:
                        width = int(width * scale)
                        height = int(height * scale)
                    elif scale <= 1.0:
                        width = int(width * scale)
                        height = int(height * scale)
                else:
                    if upscale:
                        width, height = size
                    else:
                        width = height = max(width, height)

                loader.set_size(width, height)
            loader.connect('size-prepared', on_size_prepared)

        try:
            loader.write(data)
            loader.close()
        except GLib.GError as e:
            logger.warning('Failed to get pixbuf from data: {error}'.format(
                error=e.message
            ))
        else:
            pixbuf = loader.get_pixbuf()

        return pixbuf

    @common.cached(limit=settings.get_option('rating/maximum', 5) * 3)
    def pixbuf_from_rating(self, rating, size_ratio=1):
        """
            Returns a pixbuf representing a rating

            :param rating: the rating
            :type rating: int

            :returns: the rating pixbuf
            :rtype: :class:`GdkPixbuf.Pixbuf`
        """
        maximum = settings.get_option('rating/maximum', 5)
        width = self.rating_active_pixbuf.get_width()
        height = self.rating_active_pixbuf.get_height()

        active_pixbuf = self.rating_active_pixbuf.scale_simple(int(width * size_ratio),
                                                               int(height * size_ratio),
                                                               GdkPixbuf.InterpType.BILINEAR)
        inactive_pixbuf = self.rating_inactive_pixbuf.scale_simple(int(width * size_ratio),
                                                                   int(height * size_ratio),
                                                                   GdkPixbuf.InterpType.BILINEAR)
        rating = max(0, rating)
        rating = min(rating, maximum)

        if rating == 0:
            return inactive_pixbuf * maximum
        elif rating == maximum:
            return active_pixbuf * maximum

        active_pixbufs = active_pixbuf * rating
        inactive_pixbufs = inactive_pixbuf * (maximum - rating)
        return active_pixbufs + inactive_pixbufs

if 'EXAILE_BUILDING_DOCS' not in os.environ:
    MANAGER = IconManager()

# vim: et sts=4 sw=4
