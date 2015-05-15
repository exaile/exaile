import pygtkcompat
pygtkcompat.enable()
pygtkcompat.enable_gtk(version='3.0')

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

orig_GioFile_monitor_directory = Gio.File.base.monitor_directory
def GioFile_monitor_directory(self, flags=Gio.FileMonitorFlags.NONE, cancellable=None):
    return orig_GioFile_monitor_directory(self, flags, cancellable)
Gio.File.base.monitor_directory = GioFile_monitor_directory

orig_GioFile_query_info = Gio.File.base.query_info
def GioFile_query_info(self, attributes, flags=Gio.FileQueryInfoFlags.NONE, cancellable=None):
    return orig_GioFile_query_info(self, attributes, flags, cancellable)
Gio.File.base.query_info = GioFile_query_info

# GStreamer

# Mostly copied from pygtkcompat
def enable_gst():
    import sys
    from pygtkcompat.pygtkcompat import _install_enums
    sys.modules['gst'] = Gst
    _install_enums(Gst)
    #Gst.registry_get_default = Gst.Registry.get_default
    Gst.element_register = Gst.Element.register
    Gst.element_factory_make = Gst.ElementFactory.make
    Gst.caps_new_any = Gst.Caps.new_any
    Gst.get_pygst_version = Gst.version
    Gst.get_gst_version = Gst.version

    #from gi.repository import GstInterfaces
    #sys.modules['gst.interfaces'] = GstInterfaces
    #_install_enums(GstInterfaces)

    from gi.repository import GstAudio
    sys.modules['gst.audio'] = GstAudio
    _install_enums(GstAudio)

    from gi.repository import GstVideo
    sys.modules['gst.video'] = GstVideo
    _install_enums(GstVideo)

    from gi.repository import GstBase
    sys.modules['gst.base'] = GstBase
    _install_enums(GstBase)

    Gst.BaseTransform = GstBase.BaseTransform
    Gst.BaseSink = GstBase.BaseSink

    from gi.repository import GstController
    sys.modules['gst.controller'] = GstController
    _install_enums(GstController, dest=Gst)

    from gi.repository import GstPbutils
    sys.modules['gst.pbutils'] = GstPbutils
    _install_enums(GstPbutils)

enable_gst()

orig_GstBin = Gst.Bin
class GstBin(orig_GstBin):
    def __init__(self, name):
        orig_GstBin.__init__(self)
        self.set_name(name)
    def add(self, *elements):
        for element in elements:
            orig_GstBin.add(self, element)
Gst.Bin = GstBin

orig_GstCaps = Gst.Caps
class GstCaps(orig_GstCaps):
    def __new__(cls, s):
        return orig_GstCaps.from_string(s)
    def __init__(self, s):
        orig_GstCaps.__init__(self)  # Suppress warning
Gst.Caps = GstCaps

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

orig_GstPipeline_add = Gst.Pipeline.add
def GstPipeline_add(self, *elements):
    for element in elements:
        orig_GstPipeline_add(self, element)
Gst.Pipeline.add = GstPipeline_add

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
    def __new__(cls, *args, **kwargs):
        return orig_GtkBorder.new()  # Remove arguments
    def __init__(self, left=0, right=0, top=0, bottom=0):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
Gtk.Border = GtkBorder

orig_GtkMenu_popup = Gtk.Menu.popup
def GtkMenu_popup(a, b, c, d, e, f):
    return orig_GtkMenu_popup(a, b, c, d, None, e, f)
Gtk.Menu.popup = GtkMenu_popup
