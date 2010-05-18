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

import glob
import os
import cairo
import gtk
import pango

class IconManager(object):
    """
        Provides convenience functions for managing icons
    """
    def __init__(self):
        self.icon_theme = gtk.icon_theme_get_default()
        self.icon_factory = gtk.IconFactory()
        self.icon_factory.add_default()
        # Any arbitrary widget is fine
        self.render_widget = gtk.Button()
        self.system_visual = gtk.gdk.visual_get_system()
        self.system_colormap = gtk.gdk.colormap_get_system()
        # TODO: Make svg actually recognized
        self._sizes = [16, 22, 24, 32, 48, 'scalable']
        self._cache = {}

    def add_icon_name_from_directory(self, icon_name, directory):
        """
            Registers an icon name from files found in a directory
            
            :param icon_name: the name for the icon
            :type icon_name: string
            :param directory: the location to search for icons
            :type directory: string
        """
        for size in self._sizes:
            try: # WxH/icon_name.png and scalable/icon_name.svg
                sizedir = '%dx%d' % (size, size)
            except TypeError:
                sizedir = size
            filepath = os.path.join(directory, sizedir, icon_name)
            files = glob.glob('%s.*' % filepath)
            try:
                icon_size = size if size != 'scalable' else -1
                self.add_icon_name_from_file(icon_name, files[0], icon_size)
            except IndexError: # icon_nameW.png and icon_name.svg
                try:
                    filename = '%s%d' % (icon_name, size)
                except TypeError:
                    filename = icon_name
                filepath = os.path.join(directory, filename)
                files = glob.glob('%s.*' % filepath)
                try:
                    icon_size = size if size != 'scalable' else -1
                    self.add_icon_name_from_file(icon_name, files[0], icon_size)
                except IndexError: # Give up
                    pass

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
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
            self.add_icon_name_from_pixbuf(icon_name, pixbuf, size)
        except Exception:
            # Happens if, e.g., librsvg is not installed.
            pass

    def add_icon_name_from_pixbuf(self, icon_name, pixbuf, size=None):
        """
            Registers an icon name from a pixbuf
            
            :param icon_name: the name for the icon
            :type icon_name: string
            :param pixbuf: the pixbuf of an image
            :type pixbuf: :class:`gtk.gdk.Pixbuf`
            :param size: the size the icon shall be registered for
            :type size: int
        """
        if size is None:
            size = pixbuf.get_width()

        gtk.icon_theme_add_builtin_icon(icon_name, size, pixbuf)

    def add_stock_from_directory(self, stock_id, directory):
        """
            Registers a stock icon from files found in a directory

            :param stock_id: the stock id for the icon
            :type stock_id: string
            :param directory: the location to search for icons
            :type directory: string
        """
        files = []
        self._sizes.reverse() # Prefer small over downscaled icons

        for size in self._sizes:
            try: # WxH/stock_id.png and scalable/stock_id.svg
                sizedir = '%dx%d' % (size, size)
            except TypeError:
                sizedir = size
            filepath = os.path.join(directory, sizedir, stock_id)
            try:
                files += [glob.glob('%s.*' % filepath)[0]]
            except IndexError: # stock_idW.png and stock_id.svg
                try:
                    filename = '%s%d' % (stock_id, size)
                except TypeError:
                    filename = stock_id
                filepath = os.path.join(directory, filename)
                try:
                    files += [glob.glob('%s.*' % filepath)[0]]
                except IndexError: # Give up
                    pass

        self.add_stock_from_files(stock_id, files)

    def add_stock_from_file(self, stock_id, filename):
        """
            Registers a stock icon from a filename

            :param stock_id: the stock id for the icon
            :type stock_id: string
            :param filename: the filename of an image
            :type filename: string
        """
        self.add_stock_from_files([filename])

    def add_stock_from_files(self, stock_id, filenames):
        """
            Registers a stock icon from filenames

            :param stock_id: the stock id for the icon
            :type stock_id: string
            :param filenames: the filenames of images
            :type filenames: list of string
        """
        pixbufs = [gtk.gdk.pixbuf_new_from_file(filename) for filename in filenames]
        self.add_stock_from_pixbufs(stock_id, pixbufs)

    def add_stock_from_pixbuf(self, stock_id, pixbuf):
        """
            Registers a stock icon from a pixbuf

            :param stock_id: the stock id for the icon
            :type stock_id: string
            :param pixbuf: the pixbuf of an image
            :type pixbuf: :class:`gtk.gdk.Pixbuf`
        """
        self.add_stock_from_pixbufs(stock_id, [pixbuf])

    def add_stock_from_pixbufs(self, stock_id, pixbufs):
        """
            Registers a stock icon from pixbufs

            :param stock_id: the stock id for the icon
            :type stock_id: string
            :param pixbuf: the pixbufs of images
            :type pixbuf: list of :class:`gtk.gdk.Pixbuf`
        """
        icon_set = gtk.IconSet()

        for pixbuf in pixbufs:
            icon_source = gtk.IconSource()
            icon_source.set_pixbuf(pixbuf)
            icon_set.add_source(icon_source)

        self.icon_factory.add(stock_id, icon_set)

    def pixbuf_from_stock(self, stock_id, size=gtk.ICON_SIZE_BUTTON):
        """
            Generates a pixbuf from a stock id

            :param stock_id: a stock id
            :type stock_id: string
            :param size: the size of the icon
            :type size: GtkIconSize

            :returns: the generated pixbuf
            :rtype: :class:`gtk.gdk.Pixbuf` or None
        """
        # TODO: Check if fallbacks are necessary
        return self.render_widget.render_icon(stock_id, size)

    def pixbuf_from_icon_name(self, icon_name, size=gtk.ICON_SIZE_BUTTON):
        """
            Generates a pixbuf from an icon name

            :param stock_id: an icon name
            :type stock_id: string
            :param size: the size of the icon
            :type size: GtkIconSize

            :returns: the generated pixbuf
            :rtype: :class:`gtk.gdk.Pixbuf` or None
        """
        try:
            pixbuf = self.icon_theme.load_icon(
                icon_name, size, gtk.ICON_LOOKUP_NO_SVG)
        except gobject.GError:
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
            :rtype: :class:`gtk.gdk.Pixbuf`
        """
        def on_size_prepared(loader, width, height):
            """
                Keeps the ratio if requested
            """
            if size is not None:
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

        loader = gtk.gdk.PixbufLoader()
        loader.connect('size-prepared', on_size_prepared)
        loader.write(data)
        loader.close()

        return loader.get_pixbuf()

    def pixbuf_from_text(self, text, size, background_color='#456eac',
            border_color='#000', text_color='#fff'):
        """
            Generates a pixbuf based on a text, width and height

            :param size: A tuple describing width and height
            :type size: tuple of int
            :param background_color: The color of the background as
                hexadecimal value
            :type background_color: string
            :param border_color: The color of the border as
                hexadecimal value
            :type border_color: string
            :param text_color: The color of the text as
                hexadecimal value
            :type text_color: string
        """
        pixmap_width, pixmap_height = size
        key = '%s - %sx%s - %s' % (text, pixmap_width, pixmap_height,
            background_color)
        
        if self._cache.has_key(key):
            return self._cache[key]

        pixmap = gtk.gdk.Pixmap(None, pixmap_width, pixmap_height,
            self.system_visual.depth)
        context = pixmap.cairo_create()

        context.set_source_color(gtk.gdk.Color(background_color))
        context.set_line_width(1)
        context.rectangle(1, 1, pixmap_width - 2, pixmap_height - 2)
        context.fill()

        context.set_source_color(gtk.gdk.Color(text_color))
        context.select_font_face('sans-serif 10')
        x_bearing, y_bearing, width, height = context.text_extents(text)[:4]
        x = pixmap_width / 2 - width / 2 - x_bearing
        y = pixmap_height / 2 - height / 2 - y_bearing
        context.move_to(x, y)
        context.show_text(text)

        context.set_source_color(gtk.gdk.Color(border_color))
        context.set_antialias(cairo.ANTIALIAS_NONE)
        context.rectangle(0, 0, pixmap_width - 1, pixmap_height - 1)
        context.stroke()

        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8,
            pixmap_width, pixmap_height)
        pixbuf = pixbuf.get_from_drawable(pixmap, self.system_colormap,
            0, 0, 0, 0, pixmap_width, pixmap_height)

        self._cache[key] = pixbuf

        return pixbuf

MANAGER = IconManager()

# vim: et sts=4 sw=4
