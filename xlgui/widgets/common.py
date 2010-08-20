# Copyright (C) 2010 Adam Olsen
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

"""
    Shared GUI widgets
"""

import gobject
import gtk

class ClickableCellRendererPixbuf(gtk.CellRendererPixbuf):
    """
        Custom :class:`gtk.CellRendererPixbuf` emitting
        an *clicked* signal upon activation of the pixbuf
    """
    __gsignals__ = {
        'clicked': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gobject.TYPE_PYOBJECT,),
            gobject.signal_accumulator_true_handled
        )
    }

    def __init__(self):
        gtk.CellRendererPixbuf.__init__(self)
        self.props.mode = gtk.CELL_RENDERER_MODE_ACTIVATABLE

    def do_activate(self, event, widget, path,
            background_area, cell_area, flags):
        """
            Emits the *clicked* signal
        """
        if event is None: # Keyboard activation
            return

        pixbuf_width = self.props.pixbuf.get_width()
        pixbuf_height = self.props.pixbuf.get_height()

        click_area = gtk.gdk.Rectangle(
            x=int(cell_area.x \
              + self.props.xpad \
              + self.props.xalign * cell_area.width \
              - pixbuf_width),
            y=int(cell_area.y \
              + self.props.ypad \
              + self.props.yalign * cell_area.height \
              - self.props.yalign * pixbuf_height),
            width=pixbuf_width,
            height=pixbuf_height
        )

        if click_area.x <= event.x <= click_area.x + click_area.width and \
           click_area.y <= event.y <= click_area.y + click_area.height:
            self.emit('clicked', path)

