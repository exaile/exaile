from __future__ import division, print_function, unicode_literals

import collections

import cairo
from gi.repository import (
    Gtk,
    Pango,
    PangoCairo,
)


Extents = collections.namedtuple('Extents', 'x_bearing y_bearing width height x_advance y_advance')


class Moodbar(Gtk.DrawingArea):
    pos_size = 0.4  # Size of seek notch, in fraction of bar height
    pos_linesize = 2

    def __init__(self, loader):
        super(Moodbar, self).__init__()
        self.loader = loader
        # TODO: Handle screen-changed. See https://developer.gnome.org/gtk3/stable/GtkWidget.html#gtk-widget-create-pango-layout
        self.pango_layout = self.create_pango_layout()
        self.surf = self.text = self.text_extents = self.tint = None
        self.seek_position = -1
        self.connect('draw', self._on_draw)

    def load_mood(self, path):
        """
        :type path: bytes
        """
        self.surf = None
        if path is None:
            return
        try:
            self.surf = self.loader.load(path)
        except Exception:
            return False
        finally:
            self._invalidate()
        return True

    def set_seek_position(self, pos):
        """
        :type pos: float
        """
        old_pos = self.seek_position
        if pos != old_pos:
            self.seek_position = pos
            self._invalidate()

    def set_text(self, text):
        """
        :type text: str
        """
        old_text = self.text
        if text != old_text:
            self.text = text
            if text is not None:
                layout = self.pango_layout
                layout.set_text(text, -1)
                self.text_extents = layout.get_extents()[1]
            self._invalidate()

    def set_tint(self, tint):
        """
        :type tint: Gdk.ARGB
        """
        old_tint = self.tint
        if tint != old_tint:
            self.tint = tint
            self._invalidate()

    def _invalidate(self):
        if self.surf:
            alloc = self.get_allocation()
            self.queue_draw_area(0, 0, alloc.width, alloc.height)

    def _on_draw(self, _, cr):
        """
        :type cr: cairo.Context
        """
        if self.surf is None:
            return False
        alloc = self.get_allocation()
        width, height = alloc.width, alloc.height

        # Draw mood.
        cr.save()
        cr.scale(width / 1000, height)
        cr.set_source_surface(self.surf, 0, 0)
        cr.paint()
        cr.restore()

        # Draw tint.
        tint = self.tint
        if tint is not None:
            cr.save()
            cr.set_source_rgba(tint.red, tint.green, tint.blue, tint.alpha)
            cr.paint()
            cr.restore()

        # Draw text.
        text = self.text
        if text:
            cr.save()
            # TODO: Do we need PangoCairo.update_layout anywhere?
            ext = self.text_extents
            scale = Pango.SCALE
            tx = int((width - ext.width / scale) / 2 - ext.x / scale)
            ty = int((height - ext.height / scale) / 2 - ext.y / scale)
            cr.move_to(tx, ty)
            cr.set_line_width(4)
            PangoCairo.layout_path(cr, self.pango_layout)
            cr.set_source_rgba(1, 1, 1, 0.8)
            cr.stroke_preserve()
            cr.set_source_rgb(0, 0, 0)
            cr.fill()
            cr.restore()

        # Draw seek position.
        pos = self.seek_position
        if pos is not None:
            cr.save()
            x = pos * width
            y = height * self.pos_size
            xd = y
            linesize = self.pos_linesize
            top = linesize / 2 - 0.5
            # Triangle
            cr.move_to(x, y)
            cr.line_to(x - xd, top)
            cr.line_to(x + xd, top)
            cr.close_path()
            # White fill
            cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            # Black stroke
            cr.set_source_rgb(0, 0, 0)
            cr.set_line_width(linesize)
            cr.stroke()
            cr.restore()

        return False


# vi: et sts=4 sw=4 ts=4 tw=99
