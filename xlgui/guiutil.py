# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import gtk, os.path
import gtk.gdk, pango
from xl import xdg

try:
    import sexy
except ImportError:
    sexy = None

def gtkrun(f):
    """
        A decorator that will make any function run in gtk threadsafe mode

        ALL CODE MODIFYING THE UI SHOULD BE WRAPPED IN THIS
    """
    def wrapper(*args, **kwargs):
        gtk.gdk.threads_enter()
        try:
            f(*args, **kwargs)
        finally:
            gtk.gdk.threads_leave()

    wrapper.__name__ = f.__name__
    wrapper.__dict__ = f.__dict__
    wrapper.__doc__ = f.__doc__

    return wrapper

class ScalableImageWidget(gtk.Image):
    """
        Custom resizeable image widget
    """
    def __init__(self):
        """
            Initializes the image
        """
        gtk.Image.__init__(self)
        self.loc = ''

    def set_image_size(self, width, height):
        """
            Scales the size of the image
        """
        self.size = (width, height)

    def set_image(self, image, fill=False):
        """
            Sets the image
        """
        self.loc = image
        pixbuf = gtk.gdk.pixbuf_new_from_file(image)
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

class DragTreeView(gtk.TreeView):
    """
        A TextView that does easy dragging/selecting/popup menu
    """
    def __init__(self, cont, receive=True, source=True):
        """
            Initializes the tree and sets up the various callbacks
        """
        gtk.TreeView.__init__(self)
        self.cont = cont

        self.targets = [("text/uri-list", 0, 0)]

        if source:
            self.drag_source_set(
                gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        if receive:
            self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT)
            self.connect('drag_data_received', 
                self.cont.drag_data_received)
            self.connect('drag_data_delete',
                self.cont.drag_data_delete)
        self.receive = receive
        self.dragging = False
        self.connect('drag_begin', self.drag_begin)
        self.connect('drag_end', self.drag_end)
        self.connect('drag_motion', self.drag_motion)
        self.connect('button_release_event', self.button_release)
        self.connect('button_press_event', self.button_press)

        if source:
            self.connect('drag_data_get', self.cont.drag_get_data)
            self.drag_source_set_icon_stock('gtk-dnd')

    def button_release(self, button, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.dragging: 
            self.dragging = False
            return True
        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True
        selection = self.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.get_path_at_pos(x, y)
        if not path: return False
        selection.unselect_all()
        selection.select_path(path[0])

    def drag_end(self, list, context):
        """
            Called when the dnd is ended
        """
        self.dragging = False
        self.unset_rows_drag_dest()
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets, 
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

    def drag_begin(self, list, context):
        """
            Called when dnd is started
        """
        self.dragging = True

        context.drag_abort(gtk.get_current_event_time())
        selection = self.get_selection()
        if selection.count_selected_rows() > 1:
            self.drag_source_set_icon_stock('gtk-dnd-multiple')
        else: self.drag_source_set_icon_stock('gtk-dnd')
        return False

    def drag_motion(self, treeview, context, x, y, timestamp):
        """
            Called when a row is dragged over this treeview
        """
        if not self.receive:
            return
        self.enable_model_drag_dest(self.targets,
            gtk.gdk.ACTION_DEFAULT)
        info = treeview.get_dest_row_at_pos(x, y)
        if not info: return
        treeview.set_drag_dest_row(info[0], info[1])

    def button_press(self, button, event):
        """
            The popup menu that is displayed when you right click in the
            playlist
        """
        selection = self.get_selection()
        (x, y) = event.get_coords()
        x = int(x)
        y = int(y)
        path = self.get_path_at_pos(x, y)
        if not path: return True
            
        if event.button != 3: 
            if event.type == gtk.gdk._2BUTTON_PRESS:
                self.cont.button_press(button, event)

            if selection.count_selected_rows() <= 1: 
                return False
            else: 
                if selection.path_is_selected(path[0]): 
                    if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        selection.unselect_path(path[0])
                    return True
                elif not event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                    return True
                return False

        if not selection.count_selected_rows():
            selection.select_path(path[0])
        return self.cont.button_press(button, event)

class EntryWithClearButton(object):
    """
        A gtk.Entry with a clear icon
    """
    def __init__(self, change_func):
        """
            Initializes the entry
        """
        if sexy:
            self.entry = sexy.IconEntry()
            image = gtk.Image()
            image.set_from_stock('gtk-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.entry.set_icon(sexy.ICON_ENTRY_SECONDARY, image)
            if change_func:
                self.entry.connect('icon-released', self.icon_released)
        else:
            self.entry = gtk.Entry()
        self.entry.connect('changed', change_func)

    def set_clear_callback(self, cb):
        """
            Sets the callback to be called after the clear button is pressed
        """
        self.clear_callback = cb

    def icon_released(self, *e):
        """
            Called when the user clicks the entry icon
        """
        self.entry.set_text('')

    def __getattr__(self, attr):
        """
            If this object doesn't have the attribute, check the gtk.Entry for
            it
        """
        if attr == 'entry': return self.entry
        return getattr(self.entry, attr)

def get_icon(id, size=gtk.ICON_SIZE_BUTTON):
    """
        Returns a stock icon for the specified id and size
    """
    theme = gtk.icon_theme_get_default()
    try:
        icon = theme.load_icon(id, size, gtk.ICON_LOOKUP_NO_SVG)
        if icon: return icon
    except gobject.GError:
        pass
    
    return gtk.gdk.pixbuf_new_from_file(
        os.path.join(xdg.get_image_dir(), 'default_theme', id + '.png'))

BITMAP_CACHE = dict()
def get_text_icon(widget, text, width, height, bgcolor='#456eac',   
    bordercolor=None):
    """
        Gets a bitmap icon with the specified text, width, and height
    """
    if BITMAP_CACHE.has_key("%s - %sx%s - %s" % (text, width, height, bgcolor)):
        return BITMAP_CACHE["%s - %sx%s - %s" % (text, width, height, bgcolor)]

    default_visual = gtk.gdk.visual_get_system()
    pixmap = gtk.gdk.Pixmap(None, width, height, default_visual.depth)
    colormap = gtk.gdk.colormap_get_system()
    white = colormap.alloc_color(65535, 65535, 65535)
    black = colormap.alloc_color(0, 0, 0)
    pixmap.set_colormap(colormap)
    gc = pixmap.new_gc(foreground=black, background=white)

    if not bordercolor: bordercolor = black
    else: 
        bordercolor = colormap.alloc_color(gtk.gdk.color_parse(bordercolor))
    gc.set_foreground(bordercolor)

    pixmap.draw_rectangle(gc, True, 0, 0, width, height)
    fg = colormap.alloc_color(gtk.gdk.color_parse(bgcolor))
    gc.set_foreground(fg)
    pixmap.draw_rectangle(gc, True, 1, 1, width - 2, height - 2)

    layout = widget.create_pango_layout(str(text))
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
    pixbuf = pixbuf.get_from_drawable(pixmap, colormap, 0, 0, 0,
        0, width, height)

    BITMAP_CACHE["%s - %sx%s - %s" % (text, width, height, bgcolor)] = pixbuf
    return pixbuf
