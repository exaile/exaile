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

import collections

import gi
gi.require_version('PangoCairo', '1.0')

from gi.repository import (
    Gtk,
    Pango,
    PangoCairo,
)

import painter


Extents = collections.namedtuple('Extents', 'x_bearing y_bearing width height x_advance y_advance')


class Moodbar(Gtk.DrawingArea):
    pos_size = 0.4  # Size of seek notch, in fraction of bar height
    pos_linesize = 2

    def __init__(self):
        super(Moodbar, self).__init__()
        # TODO: Handle screen-changed.
        # See https://developer.gnome.org/gtk3/stable/GtkWidget.html#gtk-widget-create-pango-layout
        self.pango_layout = self.create_pango_layout()
        self.surf = self.text = self.text_extents = self.tint = None
        self._seek_position = None

    def set_mood(self, data):
        """
        :param data: Mood data, or None to not show any
        :type data: bytes|None
        :return: Whether the mood data is successfully set
        :rtype: bool
        """
        if data:
            self.surf = painter.paint(data)
            self._invalidate()
            return bool(self.surf)
        else:
            self.surf = None
            self._invalidate()
            return True

    @property
    def seek_position(self):
        return self._seek_position

    @seek_position.setter
    def seek_position(self, pos):
        """
        :param pos: Seek position, between 0 and 1 inclusive, or None to hide
        :type pos: float|None
        """
        old_pos = self._seek_position
        if pos != old_pos:
            self._seek_position = pos
            self._invalidate()

    def set_text(self, text):
        """Set the text in the middle of the moodbar.

        :type text: str|None
        """
        old_text = self.text
        if text != old_text:
            self.text = text
            if text:
                layout = self.pango_layout
                layout.set_text(text, -1)
                self.text_extents = layout.get_extents()[1]
            self._invalidate()

    def set_tint(self, tint):
        """Add a color layer to the whole moodbar, or None to disable.

        :type tint: Gdk.ARGB|None
        """
        old_tint = self.tint
        if tint != old_tint:
            self.tint = tint
            self._invalidate()

    def _invalidate(self):
        alloc = self.get_allocation()
        self.queue_draw_area(0, 0, alloc.width, alloc.height)

    def do_draw(self, cr):
        """Handler for the 'draw' signal.

        :type cr: cairo.Context
        :rtype: bool
        """
        alloc = self.get_allocation()
        width, height = alloc.width, alloc.height

        if self.surf:
            # Mood
            cr.save()
            cr.scale(width / self.surf.get_width(), height)
            cr.set_source_surface(self.surf, 0, 0)
            cr.paint()
            cr.restore()

        # Text
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

        # Seek position
        pos = self._seek_position
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

        # Border
        cr.save()
        cr.rectangle(0, 0, width, height)
        if self.surf or pos is not None:
            cr.set_source_rgb(0, 0, 0)
        else:
            cr.set_source_rgb(0.63, 0.63, 0.63)
        cr.stroke()
        cr.restore()

        # Tint
        tint = self.tint
        if tint is not None:
            cr.save()
            cr.set_source_rgba(tint.red, tint.green, tint.blue, tint.alpha)
            cr.paint()
            cr.restore()

        return False


# vi: et sts=4 sw=4 tw=99
