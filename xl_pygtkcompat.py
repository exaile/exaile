import pygtkcompat
pygtkcompat.enable()
pygtkcompat.enable_gtk(version='3.0')

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk

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
def GtkMenu_popup(self, parent_shell, parent_item, func, button, time_, data=None):
    return orig_GtkMenu_popup(self, parent_shell, parent_item, func, data, button, time_)
Gtk.Menu.popup = GtkMenu_popup
