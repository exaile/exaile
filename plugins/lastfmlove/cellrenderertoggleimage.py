#! /usr/bin/env python
# -*- coding: utf-8 -*-

import gobject, gtk

class CellRendererToggleImage(gtk.CellRendererToggle):
    """
        Renders a toggleable state as an image
    """
    __gproperties__ = {
        'icon-name': (
            gobject.TYPE_STRING,
            'icon name',
            'The name of the themed icon to display. This '
            'property only has an effect if not overridden '
            'by "stock_id" or "pixbuf" properties.',
            '',
            gobject.PARAM_READWRITE
        ),
        'pixbuf': (
            gtk.gdk.Pixbuf,
            'pixbuf',
            'The pixbuf to render.',
            gobject.PARAM_READWRITE
        ),
        'stock-id': (
            gobject.TYPE_STRING,
            'stock id',
            'The stock ID of the stock icon to render.',
            '',
            gobject.PARAM_READWRITE
        ),
        'stock-size': (
            gobject.TYPE_UINT,
            'stock size',
            'The size of the rendered icon.',
            0,
            65535,
            gtk.ICON_SIZE_SMALL_TOOLBAR,
            gobject.PARAM_READWRITE
        ),
        'render-prelit': (
            gobject.TYPE_BOOLEAN,
            'render prelit',
            'Whether to render prelit states or not',
            True,
            gobject.PARAM_READWRITE
        )
    }

    def __init__(self):
        gtk.CellRendererToggle.__init__(self)

        self.__icon_name = ''
        self.__pixbuf = None
        self.__insensitive_pixbuf = None
        self.__prelit_pixbuf = None
        self.__pixbuf_width = 0
        self.__pixbuf_height = 0
        self.__stock_id = ''
        self.__stock_size = gtk.ICON_SIZE_SMALL_TOOLBAR
        self.__render_prelit = True

        # Any widget is fine
        self.__render_widget = gtk.Button()
        self.__icon_theme = gtk.icon_theme_get_default()

        self.set_property('activatable', True)

    def do_get_property(self, property):
        """
            Getter for custom properties
        """
        if property.name == 'icon-name':
            return self.__icon_name
        elif property.name == 'pixbuf':
            return self.__pixbuf
        elif property.name == 'stock-id':
            return self.__stock_id
        elif property.name == 'stock-size':
            return self.__stock_size
        elif property.name == 'render-prelit':
            return self.__render_prelit
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        """
            Setter for custom properties
        """
        if property.name == 'icon-name':
            self.__icon_name = value
        elif property.name == 'pixbuf':
            self.__pixbuf = value
        elif property.name == 'stock-id':
            self.__stock_id = value
        elif property.name == 'stock-size':
            self.__stock_size = value
        elif property.name == 'render-prelit':
            self.__render_prelit = value
        else:
            raise AttributeError, 'unknown property %s' % property.name

        self.__render_pixbufs()

    def __pixbuf_from_icon_name(self):
        """
            Loads a pixbuf from an icon name
        """
        try:
            return self.__icon_theme.load_icon(
                icon_name=self.__icon_name,
                size=self.__stock_size,
                flags=0
            )
        except gobject.GError:
            return None

    def __pixbuf_from_stock(self):
        """
            Loads a pixbuf from a stock id
        """
        return self.__render_widget.render_icon(
            self.__stock_id, self.__stock_size)

    def __render_pixbufs(self):
        """
            Pre-renders all required pixbufs and caches them
        """
        # Get pixbuf from raw, stock or name in that order
        if self.__pixbuf is None:
            pixbuf = self.__pixbuf_from_stock()
            if pixbuf is None:
                pixbuf = self.__pixbuf_from_icon_name()
                if pixbuf is None:
                    return
            self.__pixbuf = pixbuf

        # Cache dimensions
        self.__pixbuf_height = self.__pixbuf.get_height()
        self.__pixbuf_width = self.__pixbuf.get_width()

        self.__insensitive_pixbuf = self.__pixbuf.copy()
        # Render insensitive state
        self.__pixbuf.saturate_and_pixelate(
            dest=self.__insensitive_pixbuf,
            saturation=1,
            pixelate=True
        )

        if self.__render_prelit:
            self.__prelit_pixbuf = self.__pixbuf.copy()
            # Desaturate the active pixbuf
            self.__pixbuf.saturate_and_pixelate(
                dest=self.__prelit_pixbuf,
                saturation=0,
                pixelate=False
            )

    def do_render(self, window, widget, background_area,
                  cell_area, expose_area, flags):
        """
            Renders a custom toggle image
        """
        # Ensure pixbufs are rendered
        if self.__pixbuf is None:
            self.__render_pixbufs()

        pixbuf = None
        prelit = flags & gtk.CELL_RENDERER_PRELIT

        # Either draw the sensitive or insensitive state
        if self.props.sensitive:
            # Either draw the regular or the prelight state
            if self.props.active:
                pixbuf = self.__pixbuf
            elif self.__render_prelit and prelit:
                pixbuf = self.__prelit_pixbuf
        elif self.props.active:
            pixbuf = self.__insensitive_pixbuf

        # Do nothing if we are inactive or not prelit
        if pixbuf is not None:
            area_x, area_y, area_width, area_height = cell_area

            # Make sure to properly align the pixbuf
            x = area_x + \
                area_width * self.props.xalign - \
                self.__pixbuf_width / 2

            y = area_y + \
                area_height * self.props.yalign - \
                self.__pixbuf_height / 2

            context = window.cairo_create()
            context.set_source_pixbuf(pixbuf, x, y)
            context.paint()

