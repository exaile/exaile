import pygtkcompat
pygtkcompat.enable()
pygtkcompat.enable_gtk(version='3.0')
try:
    pygtkcompat.enable_gst()
except Exception:
    pass

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gst, Gtk

# GDK

Gdk.visual_get_system = Gdk.Visual.get_system

# GDK Pixbuf

orig_GdkPixbufLoader = GdkPixbuf.PixbufLoader
class GdkPixbufLoader(orig_GdkPixbufLoader):
    def __new__(cls, type_=None):
        if type_:
            return orig_GdkPixbufLoader.new_with_type(type_)
        return orig_GdkPixbufLoader.new()
Gdk.PixbufLoader = GdkPixbufLoader

# GIO

Gio.Error = GLib.GError
Gio.FILE_QUERY_INFO_NONE = Gio.FileQueryInfoFlags.NONE
Gio.FILE_TYPE_DIRECTORY = Gio.FileType.DIRECTORY
Gio.FILE_TYPE_REGULAR = Gio.FileType.REGULAR

Gio.File.base = Gio.File
class GioFile(Gio.File.base, GObject.GObject):
    def __new__(cls, cmdline):
        return cls.new_for_commandline_arg(cmdline)
Gio.File = GioFile

orig_GioFile_enumerate_children = Gio.File.base.enumerate_children
def GioFile_enumerate_children(self, attributes, flags=Gio.FileQueryInfoFlags.NONE, cancellable=None):
    return orig_GioFile_enumerate_children(self, attributes, flags, cancellable)
Gio.File.base.enumerate_children = GioFile_enumerate_children

orig_GioFile_query_info = Gio.File.base.query_info
def GioFile_query_info(self, attributes, flags=Gio.FileQueryInfoFlags.NONE, cancellable=None):
    return orig_GioFile_query_info(self, attributes, flags, cancellable)
Gio.File.base.query_info = GioFile_query_info

# GStreamer

orig_GstGhostPad = Gst.GhostPad
class GstGhostPad(orig_GstGhostPad):
    def __new__(cls, *a, **kw):
        return orig_GstGhostPad.new(*a, **kw)
Gst.GhostPad = GstGhostPad

Gst.event_new_seek = Gst.Event.new_seek

def Gst_element_link_many(*elements):
    for i, element in enumerate(elements):
        if i != 0:
            elements[i - 1].link(element)
Gst.element_link_many = Gst_element_link_many

orig_GstBin_add = Gst.Bin.add
def GstBin_add(self, *elements):
    for element in elements:
        orig_GstBin_add(self, element)
Gst.Bin.add = GstBin_add

orig_GstElement_get_state = Gst.Element.get_state
def GstElement_get_state(self, timeout=Gst.CLOCK_TIME_NONE):
    return orig_GstElement_get_state(self, timeout)
Gst.Element.get_state = GstElement_get_state

orig_Gst_element_factory_make = Gst.ElementFactory.make
def GstElementFactory_make(factoryname, name=None):
    orig_Gst_element_factory_make(factoryname, name)
Gst.ElementFactory.make = GstElementFactory_make

def GstPad_set_blocked_async(self, *a, **kw):
    Gst.Pad.set_blocked_async_full(self, *a, **kw)
Gst.Pad.set_blocked_async = GstPad_set_blocked_async

# GTK+

orig_GtkCheckMenuItem = Gtk.CheckMenuItem
class GtkCheckMenuItem(orig_GtkCheckMenuItem):
    def __init__(self, label=None, use_underline=True):
        if label:
            orig_GtkCheckMenuItem.__init__(self, label)
        else:
            orig_GtkCheckMenuItem.__init__(self)
        self.props.use_underline = use_underline
Gtk.CheckMenuItem = GtkCheckMenuItem

orig_GtkImageMenuItem = Gtk.ImageMenuItem
class GtkImageMenuItem(orig_GtkImageMenuItem):
    def __init__(self, stock_id=None):
        if stock_id:
            orig_GtkImageMenuItem.__init__(self, stock_id)
            self.props.use_stock = True
            self.props.use_underline = True
        else:
            orig_GtkImageMenuItem.__init__(self)
Gtk.ImageMenuItem = GtkImageMenuItem

orig_GtkMenuItem = Gtk.MenuItem
class GtkMenuItem(orig_GtkMenuItem):
    def __init__(self, label=None, use_underline=True):
        if label:
            orig_GtkMenuItem.__init__(self, label)
        else:
            orig_GtkMenuItem.__init__(self)
        self.props.use_underline = use_underline
Gtk.MenuItem = GtkMenuItem

orig_GtkRadioMenuItem = Gtk.RadioMenuItem
class GtkRadioMenuItem(orig_GtkRadioMenuItem):
    def __init__(self, group=None, label=None, use_underline=True):
        if label:
            orig_GtkRadioMenuItem.__init__(self, label)
        else:
            orig_GtkRadioMenuItem.__init__(self)
        self.props.use_underline = use_underline
        if group:
            self.set_group(group.get_group())
Gtk.RadioMenuItem = GtkRadioMenuItem

Gtk.icon_theme_add_builtin_icon = Gtk.IconTheme.add_builtin_icon
Gtk.image_new_from_icon_name = Gtk.Image.new_from_icon_name
Gtk.widget_get_default_style = Gtk.Widget.get_default_style
Gtk.window_set_auto_startup_notification = Gtk.Window.set_auto_startup_notification

orig_GtkBorder = Gtk.Border
class GtkBorder(orig_GtkBorder):
    def __new__(cls, left=0, right=0, top=0, bottom=0):
        self = orig_GtkBorder.new()
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
        return self
Gtk.Border = GtkBorder

orig_GtkMenu_popup = Gtk.Menu.popup
def GtkMenu_popup(a, b, c, d, e, f):
    return orig_GtkMenu_popup(a, b, c, d, None, e, f)
Gtk.Menu.popup = GtkMenu_popup
