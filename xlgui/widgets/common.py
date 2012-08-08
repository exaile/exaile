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

from xlgui.guiutil import get_workarea_size

class AttachedWindow(gtk.Window):
    """
        A window attachable to arbitrary widgets,
        follows the movement of its parent
    """
    __gsignals__ = {'show': 'override'}

    def __init__(self, parent):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)

        self.set_decorated(False)
        self.props.skip_taskbar_hint = True
        self.set_keep_above(True)

        self.realize()
        self.window.set_functions(gtk.gdk.FUNC_RESIZE) # Only allow resizing

        self.parent_widget = parent
        realize_id = self.parent_widget.connect('realize',
            self.on_parent_realize)
        self.parent_widget.set_data('%s_realize_id' % id(self),
            realize_id)

    def update_location(self):
        """
            Makes sure the window is
            always fully visible
        """
        workarea = gtk.gdk.Rectangle(0, 0, *get_workarea_size())
        parent = self.parent_widget.allocation
        toplevel_position = self.parent_widget.get_toplevel().get_position()
        # Use absolute screen position
        parent.x += toplevel_position[0]
        parent.y += toplevel_position[1]

        if workarea.width - parent.x < self.allocation.width:
            # Parent rightmost
            x = parent.x + parent.width - self.allocation.width
        else:
            # Parent leftmost
            x = parent.x

        if workarea.height - parent.y < self.allocation.height:
            # Parent at bottom
            y = parent.y - self.allocation.height
        else:
            # Parent at top
            y = parent.y + parent.height
        
        self.move(x, y)

    def do_show(self):
        """
            Updates the location upon show
        """
        gtk.Window.do_show(self)
        self.update_location()

    def on_parent_realize(self, parent):
        """
            Prepares the window to
            follow its parent window
        """
        realize_id = parent.get_data('%s_realize_id' % id(self))
        
        if realize_id is not None:
            parent.disconnect(realize_id)

        parent_window = parent.get_toplevel()
        parent_window.connect('configure-event',
            self.on_parent_window_configure_event)
        parent_window.connect('window-state-event',
            self.on_parent_window_state_event)

    def on_parent_window_configure_event(self, *e):
        """
            Handles movement of the topmost window
        """
        if self.props.visible:
            self.update_location()

    def on_parent_window_state_event(self, window, e):
        """
            Handles state changes of the topmost window
        """
        if e.changed_mask & gtk.gdk.WINDOW_STATE_ICONIFIED:
            self.hide()

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

class ScalableImageWidget(gtk.Image):
    """
        Custom resizeable image widget
    """
    def __init__(self):
        """
            Initializes the image
        """
        self.loc = ''
        gtk.Image.__init__(self)

    def set_image_size(self, width, height):
        """
            Scales the size of the image
        """
        self.size = (width, height)

    def set_image(self, image, fill=False):
        """
            Sets the image
        """
        self.loc = gio.File(image).get_path()
        self.pixbuf = gtk.gdk.pixbuf_new_from_file(self.loc)

        self._set_image(self.pixbuf, fill)

    def set_image_data(self, data, fill=False):
        if not data:
            return

        self.pixbuf = icons.MANAGER.pixbuf_from_data(data)
        self._set_image(self.pixbuf, fill)

    def _set_image(self, pixbuf, fill=False):
        width, height = self.size
        if not fill:
            origw = float(pixbuf.get_width())
            origh = float(pixbuf.get_height())
            scale = min(width / origw, height / origh)
            width = int(origw * scale)
            height = int(origh * scale)
        self.width = width
        self.height = height
        scaled = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        self.set_from_pixbuf(scaled)

        scaled = pixbuf = None
