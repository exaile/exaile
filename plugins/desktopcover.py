# desktopcover - displays Exaile album covers on the desktop
# Copyright (C) 2006-2007 Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

PLUGIN_NAME = "Desktop Cover"
PLUGIN_AUTHORS = ["Johannes Sasongko <sasongko@gmail.com>", 
    "Adam Olsen <arolsen@gmail.com>"]

PLUGIN_VERSION = "0.2"
PLUGIN_DESCRIPTION = "Displays the current album cover on the desktop"
PLUGIN_ENABLED = False
PLUGIN_ICON = None

from gettext import gettext as _
import gobject, gtk
import plugins

PLUGIN = None
CONNS = plugins.SignalContainer()

class CoverDisplay:
    DEFAULT_X = DEFAULT_Y = 0
    DEFAULT_WIDTH = DEFAULT_HEIGHT = 200

    def __init__(self):
        self.window = wnd = gtk.Window()
        wnd.set_accept_focus(False)
        wnd.set_decorated(False)
        #wnd.set_keep_below(True)
        wnd.set_resizable(False)
        wnd.set_skip_pager_hint(True)
        wnd.set_skip_taskbar_hint(True)
        wnd.stick()

        self.x = self.DEFAULT_X
        self.y = self.DEFAULT_Y
        self.width = self.DEFAULT_WIDTH
        self.height = self.DEFAULT_HEIGHT
        self.cover = None
        self.set_use_image_size()
        self.set_keep_center()

        self.image = img = gtk.Image()
        wnd.add(img)
        img.show()

    def set_keep_center(self, keep_center=True):
        self.keep_center = keep_center
        if keep_center:
            self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        else:
            self.window.set_position(gtk.WIN_POS_NONE)
            self.set_position()

    def set_gravity(self, gravity):
        self.window.set_gravity(gravity)

    def set_position(self, x=None, y=None):
        if x is None and y is None:
            x = self.x
            y = self.y
        else:
            self.x = x
            self.y = y

        if not self.keep_center and self.window.props.visible:
            grav = self.window.get_gravity()
            if grav == gtk.gdk.GRAVITY_NORTH_WEST:
                xsgn = '+'; ysgn = '+'
            elif grav == gtk.gdk.GRAVITY_NORTH_EAST:
                xsgn = '-'; ysgn = '+'
            elif grav == gtk.gdk.GRAVITY_SOUTH_WEST:
                xsgn = '+'; ysgn = '-'
            elif grav == gtk.gdk.GRAVITY_SOUTH_EAST:
                xsgn = '-'; ysgn = '-'
            else:
                return
            self.window.parse_geometry('%s%s%s%s' % (xsgn, x, ysgn, y))

    def set_use_image_size(self, use_image_size=True):
        self.use_image_size = use_image_size

    def set_size(self, width, height):
        self.width = width
        self.height = height
        self.display(self.cover)

    def display(self, cover):
        self.cover = cover
        if cover is None:
            self.image.clear()
            self.window.hide()
            return

        pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if not self.use_image_size:
            origw = float(width)
            origh = float(height)
            width, height = self.width, self.height
            scale = min(width / origw, height / origh)
            width = int(origw * scale)
            height = int(origh * scale)
            pixbuf = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        self.image.set_from_pixbuf(pixbuf)

        wnd = self.window
        if not wnd.props.visible:
            wnd.show()
            # May be reset by the WM.
            wnd.set_keep_below(True)
        self.set_position()

    def destroy(self):
        self.window.destroy()

GRAVITIES = [
    (_("Northwest"), gtk.gdk.GRAVITY_NORTH_WEST),
    (_("Northeast"), gtk.gdk.GRAVITY_NORTH_EAST),
    (_("Southwest"), gtk.gdk.GRAVITY_SOUTH_WEST),
    (_("Southeast"), gtk.gdk.GRAVITY_SOUTH_EAST),
]

class DesktopCoverConfig(plugins.PluginConfigDialog):
    def __init__(self, exaile, title, plugin, plugin_name):
        super(type(self), self).__init__(exaile.window, title)
        self.exaile = exaile
        settings = exaile.settings
        self.plugin = plugin
        self.plugin_name = plugin_name

        table = gtk.Table(6, 2)
        table.set_border_width(12)
        table.set_col_spacings(6)
        self.main.add(table)

        self.position_widgets = position_widgets = []
        self.size_widgets = size_widgets = []

        n_rows = 0

        self.position_check = check = gtk.CheckButton(_("Manual positioning"))
        table.attach(check, 0, 2, n_rows, n_rows + 1)
        check.connect('toggled', self._positioning_toggled)
        check.set_active(not settings.get_boolean('keep_center',
            default=True, plugin=plugin_name))
        n_rows += 1

        label = gtk.Label(_("Gravity"))
        table.attach(label, 0, 1, n_rows, n_rows + 1)
        position_widgets.append(label)
        self.gravity_combo = combo = gtk.combo_box_new_text()
        table.attach(combo, 1, 2, n_rows, n_rows + 1)
        position_widgets.append(combo)
        for grav in GRAVITIES:
            combo.append_text(grav[0])
        combo.set_active(settings.get_int('gravity', default=0,
            plugin=plugin_name))
        n_rows += 1

        label = gtk.Label(_("X offset"))
        table.attach(label, 0, 1, n_rows, n_rows + 1)
        position_widgets.append(label)
        x = settings.get_int('x', default=self.plugin.DEFAULT_X,
            plugin=plugin_name)
        adj = gtk.Adjustment(x, 0, 32767, 1, 10, 10)
        self.x_spin = spin = gtk.SpinButton(adj)
        table.attach(spin, 1, 2, n_rows, n_rows + 1)
        position_widgets.append(spin)
        n_rows += 1

        label = gtk.Label(_("Y offset"))
        table.attach(label, 0, 1, n_rows, n_rows + 1)
        position_widgets.append(label)
        y = settings.get_int('y', default=self.plugin.DEFAULT_Y,
            plugin=plugin_name)
        adj = gtk.Adjustment(y, 0, 32767, 1, 10, 10)
        self.y_spin = spin = gtk.SpinButton(adj)
        position_widgets.append(spin)
        table.attach(spin, 1, 2, n_rows, n_rows + 1)
        n_rows += 1

        self.sizing_check = check = gtk.CheckButton(_("Manual sizing"))
        table.attach(check, 0, 2, n_rows, n_rows + 1)
        check.connect('toggled', self._sizing_toggled)
        check.set_active(not settings.get_boolean('use_image_size',
            default=True, plugin=plugin_name))
        n_rows += 1

        label = gtk.Label(_("Width"))
        table.attach(label, 0, 1, n_rows, n_rows + 1)
        size_widgets.append(label)
        w = settings.get_int('width', default=self.plugin.DEFAULT_WIDTH,
            plugin=plugin_name)
        adj = gtk.Adjustment(w, 0, 32767, 1, 10, 10)
        self.width_spin = spin = gtk.SpinButton(adj)
        table.attach(spin, 1, 2, n_rows, n_rows + 1)
        size_widgets.append(spin)
        n_rows += 1

        label = gtk.Label(_("Height"))
        table.attach(label, 0, 1, n_rows, n_rows + 1)
        size_widgets.append(label)
        h = settings.get_int('height', default=self.plugin.DEFAULT_HEIGHT,
            plugin=plugin_name)
        adj = gtk.Adjustment(h, 0, 32767, 1, 10, 10)
        self.height_spin = spin = gtk.SpinButton(adj)
        table.attach(spin, 1, 2, n_rows, n_rows + 1)
        size_widgets.append(spin)
        n_rows += 1

        self._setup_position_widgets()
        self._setup_size_widgets()
        table.show_all()

    def run(self):
        response = super(type(self), self).run()
        if response != gtk.RESPONSE_OK: return response

        settings = self.exaile.settings
        plugin = self.plugin
        plugin_name = self.plugin_name

        keep_center = not self.position_check.get_active()
        plugin.set_keep_center(keep_center)
        settings.set_boolean('keep_center', keep_center, plugin=plugin_name)

        gravity = self.gravity_combo.get_active()
        plugin.set_gravity(GRAVITIES[gravity][1])
        settings.set_int('gravity', gravity, plugin=plugin_name)

        x = self.x_spin.get_value_as_int()
        y = self.y_spin.get_value_as_int()
        plugin.set_position(x, y)
        settings.set_int('x', x, plugin=plugin_name)
        settings.set_int('y', y, plugin=plugin_name)

        use_image_size = not self.sizing_check.get_active()
        plugin.set_use_image_size(use_image_size)
        settings.set_boolean('use_image_size', use_image_size,
            plugin=plugin_name)

        width = self.width_spin.get_value_as_int()
        height = self.height_spin.get_value_as_int()
        plugin.set_size(width, height)
        settings.set_int('width', width, plugin=plugin_name)
        settings.set_int('height', height, plugin=plugin_name)

        return response

    def _positioning_toggled(self, check, *data):
        self._setup_position_widgets(check.get_active())

    def _sizing_toggled(self, check, *data):
        self._setup_size_widgets(check.get_active())

    def _setup_position_widgets(self, enabled=None):
        if enabled is None:
            enabled = not self.exaile.settings.get_boolean('keep_center',
                default=True, plugin=self.plugin_name)
        for w in self.position_widgets:
            w.set_sensitive(enabled)

    def _setup_size_widgets(self, enabled=None):
        if enabled is None:
            enabled = not self.exaile.settings.get_boolean('use_image_size',
                default=True, plugin=self.plugin_name)
        for w in self.size_widgets:
            w.set_sensitive(enabled)

def initialize():
    global PLUGIN
    PLUGIN = CoverDisplay()

    settings = APP.settings
    plugin_name = plugins.name(__file__)

    PLUGIN.set_keep_center(settings.get_boolean('keep_center', default=True,
        plugin=plugin_name))
    gravity = settings.get_int('gravity', default=0, plugin=plugin_name)
    PLUGIN.set_gravity(GRAVITIES[gravity][1])
    x = settings.get_int('x', default=PLUGIN.DEFAULT_X, plugin=plugin_name)
    y = settings.get_int('y', default=PLUGIN.DEFAULT_Y, plugin=plugin_name)
    PLUGIN.set_position(x, y)
    PLUGIN.set_use_image_size(settings.get_boolean('use_image_size',
        default=True, plugin=plugin_name))
    width = settings.get_int('width', default=PLUGIN.DEFAULT_WIDTH,
        plugin=plugin_name)
    height = settings.get_int('height', default=PLUGIN.DEFAULT_HEIGHT,
        plugin=plugin_name)
    PLUGIN.set_size(width, height)

    player = APP.player
    if player.current and (player.is_playing() or player.is_paused()):
        _display(APP.cover.loc)

    CONNS.connect(APP.cover, 'image-changed', lambda w, c: _display(c))

    return True

def destroy():
    global PLUGIN
    CONNS.disconnect_all()
    PLUGIN.destroy()
    PLUGIN = None

def configure():
    dialog = DesktopCoverConfig(APP, PLUGIN_NAME, PLUGIN,
        plugins.name(__file__))
    dialog.run()
    dialog.destroy()

STOPPED = None

def _display(cover):
    global STOPPED
    if 'nocover' in cover:
        STOPPED = True
        # Wait to make sure playback is really stopped. This should alleviate
        # bug #274, but not fix it completely.
        gobject.timeout_add(200, _set_no_cover)
    else:
        STOPPED = False
        PLUGIN.display(cover)

def _set_no_cover():
    if STOPPED:
        PLUGIN.display(None)
    return False # Stop GLib timeout.

# vi: et ts=4 sts=4 sw=4
