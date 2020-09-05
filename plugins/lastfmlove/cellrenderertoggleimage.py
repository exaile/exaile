# -*- coding: utf-8 -*-

from gi.repository import GdkPixbuf, GObject, Gtk, Gdk

from xlgui import icons


class CellRendererToggleImage(Gtk.CellRendererToggle):
    """
    Renders a toggleable state as an image
    """

    __gproperties__ = {
        'icon-name': (
            GObject.TYPE_STRING,
            'icon name',
            'The name of the themed icon to display. This '
            'property only has an effect if not overridden '
            'the "pixbuf" property.',
            '',
            GObject.ParamFlags.READWRITE,
        ),
        'pixbuf': (
            GdkPixbuf.Pixbuf,
            'pixbuf',
            'The pixbuf to render.',
            GObject.ParamFlags.READWRITE,
        ),
        'icon-size': (
            GObject.TYPE_UINT,
            'icon size',
            'The size of the rendered icon.',
            0,
            65535,
            Gtk.IconSize.SMALL_TOOLBAR,
            GObject.ParamFlags.READWRITE,
        ),
        'render-prelit': (
            GObject.TYPE_BOOLEAN,
            'render prelit',
            'Whether to render prelit states or not',
            True,
            GObject.ParamFlags.READWRITE,
        ),
    }

    def __init__(self):
        Gtk.CellRendererToggle.__init__(self)

        self.__icon_name = ''
        self.__pixbuf = None
        self.__insensitive_pixbuf = None
        self.__prelit_pixbuf = None
        self.__pixbuf_width = 0
        self.__pixbuf_height = 0
        self.__icon_size = Gtk.IconSize.SMALL_TOOLBAR
        self.__render_prelit = True

        # Any widget is fine
        self.__render_widget = Gtk.Button()
        self.__icon_theme = Gtk.IconTheme.get_default()

        self.set_property('activatable', True)

    def do_get_property(self, property):
        """
        Getter for custom properties
        """
        if property.name == 'icon-name':
            return self.__icon_name
        elif property.name == 'icon-size':
            return self.__icon_size
        elif property.name == 'pixbuf':
            return self.__pixbuf
        elif property.name == 'render-prelit':
            return self.__render_prelit
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        """
        Setter for custom properties
        """
        if property.name == 'icon-name':
            self.__icon_name = value
        elif property.name == 'icon-size':
            self.__icon_size = value
        elif property.name == 'pixbuf':
            self.__pixbuf = value
        elif property.name == 'render-prelit':
            self.__render_prelit = value
        else:
            raise AttributeError('unknown property %s' % property.name)

        self.__render_pixbufs()

    def __render_pixbufs(self):
        """
        Pre-renders all required pixbufs and caches them
        """
        # Get pixbuf from raw or name in that order
        if self.__pixbuf is None:
            pixbuf = icons.MANAGER.pixbuf_from_icon_name(
                self.__icon_name, self.__icon_size
            )
            if pixbuf is None:
                return
            self.__pixbuf = pixbuf

        # Cache dimensions
        self.__pixbuf_height = self.__pixbuf.get_height()
        self.__pixbuf_width = self.__pixbuf.get_width()

        self.__insensitive_pixbuf = self.__pixbuf.copy()
        # Render insensitive state
        self.__pixbuf.saturate_and_pixelate(
            dest=self.__insensitive_pixbuf, saturation=1, pixelate=True
        )

        if self.__render_prelit:
            self.__prelit_pixbuf = self.__pixbuf.copy()
            # Desaturate the active pixbuf
            self.__pixbuf.saturate_and_pixelate(
                dest=self.__prelit_pixbuf, saturation=0, pixelate=False
            )

    def do_render(self, cairo_context, widget, background_area, cell_area, flags):
        """
        Renders a custom toggle image
        """
        # Ensure pixbufs are rendered
        if self.__pixbuf is None:
            self.__render_pixbufs()

        pixbuf = None
        prelit = flags & Gtk.CellRendererState.PRELIT

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
            area_x, area_y, area_width, area_height = (
                cell_area.x,
                cell_area.y,
                cell_area.width,
                cell_area.height,
            )

            # Make sure to properly align the pixbuf
            x = area_x + area_width * self.props.xalign - self.__pixbuf_width // 2

            y = area_y + area_height * self.props.yalign - self.__pixbuf_height // 2

            Gdk.cairo_set_source_pixbuf(cairo_context, pixbuf, x, y)
            cairo_context.paint()
