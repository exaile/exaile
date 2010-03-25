# Copyright (C) 2008-2009 Adam Olsen
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
        # TODO: Make svg actually recognized
        self._sizes = [16, 22, 24, 32, 48, 'scalable']
        self._cache = {}

    def add_icon_name_from_directory(self, icon_name, directory):
        """
            Registers an icon name from files found in a directory
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
        """
        if size is None:
            size = pixbuf.get_width()

        gtk.icon_theme_add_builtin_icon(icon_name, size, pixbuf)

    def add_stock_from_directory(self, stock_id, directory):
        """
            Registers a stock icon from files found in a directory
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
        """
        self.add_stock_from_files([filename])

    def add_stock_from_files(self, stock_id, filenames):
        """
            Registers a stock icon from filenames
        """
        pixbufs = [gtk.gdk.pixbuf_new_from_file(filename) for filename in filenames]
        self.add_stock_from_pixbufs(stock_id, pixbufs)

    def add_stock_from_pixbuf(self, stock_id, pixbuf):
        """
            Registers a stock icon from a pixbuf
        """
        self.add_stock_from_pixbufs(stock_id, [pixbuf])

    def add_stock_from_pixbufs(self, stock_id, pixbufs):
        """
            Registers a stock icon from pixbufs
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

            Returns None on failure
        """
        # TODO: Check if fallbacks are necessary
        return self.render_widget.render_icon(stock_id, size)

    def pixbuf_from_icon_name(self, icon_name, size=gtk.ICON_SIZE_BUTTON):
        """
            Generates a pixbuf from an icon name

            Returns None on failure
        """
        try:
            pixbuf = self.icon_theme.load_icon(
                icon_name, size, gtk.ICON_LOOKUP_NO_SVG)
        except gobject.GError:
            pixbuf = None

        # TODO: Check if fallbacks are necessary
        return pixbuf

    def pixbuf_from_text(self, text, width, height, bgcolor='#456eac',
            bordercolor=None):
        """
            Generates a pixbuf based on a text, width and height
        """
        key = '%s - %sx%s - %s' % (text, width, height, bgcolor)
        
        if self._cache.has_key(key):
            return self._cache[key]

        default_visual = gtk.gdk.visual_get_system()
        pixmap = gtk.gdk.Pixmap(None, width, height, default_visual.depth)
        colormap = gtk.gdk.colormap_get_system()
        white = colormap.alloc_color(65535, 65535, 65535)
        black = colormap.alloc_color(0, 0, 0)
        pixmap.set_colormap(colormap)
        gc = pixmap.new_gc(foreground=black, background=white)

        if not bordercolor:
            bordercolor = black
        else:
            bordercolor = colormap.alloc_color(gtk.gdk.color_parse(bordercolor))
        gc.set_foreground(bordercolor)

        pixmap.draw_rectangle(gc, True, 0, 0, width, height)
        fg = colormap.alloc_color(gtk.gdk.color_parse(bgcolor))
        gc.set_foreground(fg)
        pixmap.draw_rectangle(gc, True, 1, 1, width - 2, height - 2)

        layout = self.render_widget.create_pango_layout(str(text))
        desc = pango.FontDescription("Sans 8")
        layout.set_font_description(desc)
        layout.set_alignment(pango.ALIGN_RIGHT)

        gc.set_foreground(white)
        inkRect, logicalRect = layout.get_pixel_extents()
        l, b, w, h = logicalRect
        x = ((width) / 2 - w / 2)
        y = ((height) / 2 - h / 2)
        pixmap.draw_layout(gc, x, y, layout)

        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, width, height)
        pixbuf = pixbuf.get_from_drawable(pixmap, colormap, 0, 0, 0, 0, width, height)

        self._cache[key] = pixbuf

        return pixbuf

MANAGER = IconManager()
# vim: et sw=4 st=4
