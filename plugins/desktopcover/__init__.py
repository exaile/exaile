# desktopcover - displays Exaile album covers on the desktop
# Copyright (C) 2006-2008  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import gobject, gtk
from xl import event
from xl.nls import gettext as _
from xl.settings import SettingsManager


timeout_add_seconds = getattr(gobject, 'timeout_add_seconds', None) \
    or (lambda t, *x: gobject.timeout_add(t * 1000, *x))


class CoverDisplay:
    DEFAULT_X = DEFAULT_Y = 0
    DEFAULT_WIDTH = DEFAULT_HEIGHT = 200
    GRAVITY_SIGNS = {
        gtk.gdk.GRAVITY_NORTH_WEST: ('+', '+'),
        gtk.gdk.GRAVITY_NORTH_EAST: ('-', '+'),
        gtk.gdk.GRAVITY_SOUTH_WEST: ('+', '-'),
        gtk.gdk.GRAVITY_SOUTH_EAST: ('-', '-'),
    }

    def __init__(self):
        self.window = wnd = gtk.Window()
        wnd.set_accept_focus(False)
        wnd.set_decorated(False)
        #wnd.set_keep_below(True)
        wnd.set_resizable(False)
        wnd.set_role('desktopcover')
        wnd.set_skip_pager_hint(True)
        wnd.set_skip_taskbar_hint(True)
        wnd.set_title("")
        #wnd.stick()

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
        #~ gtk_do_events()
        if keep_center:
            self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        else:
            self.window.set_position(gtk.WIN_POS_NONE)
            self.set_position()

    def set_gravity(self, gravity):
        #~ gtk_do_events()
        self.window.set_gravity(gravity)

    def set_position(self, x=None, y=None, force=False):
        if x is None or y is None:
            x = self.x
            y = self.y
        else:
            self.x = x
            self.y = y

        #~ gtk_do_events()
        if not self.keep_center and (force or self.window.props.visible):
            xsgn, ysgn = self.GRAVITY_SIGNS[self.window.get_gravity()]
            #~ gtk_do_events()
            self.window.parse_geometry('%s%s%s%s' % (xsgn, x, ysgn, y))

    def set_use_image_size(self, use_image_size=True):
        self.use_image_size = use_image_size

    def set_size(self, width, height):
        self.width = width
        self.height = height
        self.display(self.cover)

    def display(self, cover):
        if self.cover != cover:
            self.cover = cover
            print cover and cover[-8:]
            timeout_add_seconds(1, self._display, cover)

    def _display(self, cover):
        # Only process the last request.
        if cover != self.cover: return True
        print "Proc", cover and cover[-8:]

        if cover is None:
            self.image.clear()
            #~ gtk_do_events()
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
        self.set_position(force=True)
        #~ gtk_do_events()
        if not wnd.props.visible:
            wnd.show()
            #~ gtk_do_events()
            # May be reset by the WM.
            wnd.set_keep_below(True)
            wnd.stick()

        return False # Stop GLib timeout.

    def destroy(self):
        self.window.destroy()


### TODO: Configuration dialog ###

GRAVITIES = [
    # TRANSLATORS: Desktop cover position
    (_("Top left"), gtk.gdk.GRAVITY_NORTH_WEST),
    # TRANSLATORS: Desktop cover position
    (_("Top right"), gtk.gdk.GRAVITY_NORTH_EAST),
    # TRANSLATORS: Desktop cover position
    (_("Bottom left"), gtk.gdk.GRAVITY_SOUTH_WEST),
    # TRANSLATORS: Desktop cover position
    (_("Bottom right"), gtk.gdk.GRAVITY_SOUTH_EAST),
]

#~ class DesktopCoverConfig(plugins.PluginConfigDialog):
    #~ def __init__(self, exaile, title, plugin, plugin_name):
        #~ super(type(self), self).__init__(exaile.window, title)
        #~ self.exaile = exaile
        #~ settings = exaile.settings
        #~ self.plugin = plugin
        #~ self.plugin_name = plugin_name

        #~ table = gtk.Table(6, 2)
        #~ table.set_border_width(12)
        #~ table.set_col_spacings(6)
        #~ self.main.add(table)

        #~ self.position_widgets = position_widgets = []
        #~ self.size_widgets = size_widgets = []

        #~ n_rows = 0

        #~ self.position_check = check = gtk.CheckButton(_("Manual positioning"))
        #~ table.attach(check, 0, 2, n_rows, n_rows + 1)
        #~ check.connect('toggled', self._positioning_toggled)
        #~ check.set_active(not settings.get_boolean('keep_center',
            #~ default=True, plugin=plugin_name))
        #~ n_rows += 1

        #~ label = gtk.Label(_("Position"))
        #~ table.attach(label, 0, 1, n_rows, n_rows + 1)
        #~ position_widgets.append(label)
        #~ self.gravity_combo = combo = gtk.combo_box_new_text()
        #~ table.attach(combo, 1, 2, n_rows, n_rows + 1)
        #~ position_widgets.append(combo)
        #~ for grav in GRAVITIES:
            #~ combo.append_text(grav[0])
        #~ combo.set_active(settings.get_int('gravity', default=0,
            #~ plugin=plugin_name))
        #~ n_rows += 1

        #~ # TRANSLATORS: Offset from the desktop border
        #~ label = gtk.Label(_("X offset"))
        #~ table.attach(label, 0, 1, n_rows, n_rows + 1)
        #~ position_widgets.append(label)
        #~ x = settings.get_int('x', default=CoverDisplay.DEFAULT_X,
            #~ plugin=plugin_name)
        #~ adj = gtk.Adjustment(x, 0, 32767, 1, 10, 10)
        #~ self.x_spin = spin = gtk.SpinButton(adj)
        #~ table.attach(spin, 1, 2, n_rows, n_rows + 1)
        #~ position_widgets.append(spin)
        #~ n_rows += 1

        #~ # TRANSLATORS: Offset from the desktop border
        #~ label = gtk.Label(_("Y offset"))
        #~ table.attach(label, 0, 1, n_rows, n_rows + 1)
        #~ position_widgets.append(label)
        #~ y = settings.get_int('y', default=CoverDisplay.DEFAULT_Y,
            #~ plugin=plugin_name)
        #~ adj = gtk.Adjustment(y, 0, 32767, 1, 10, 10)
        #~ self.y_spin = spin = gtk.SpinButton(adj)
        #~ position_widgets.append(spin)
        #~ table.attach(spin, 1, 2, n_rows, n_rows + 1)
        #~ n_rows += 1

        #~ self.sizing_check = check = gtk.CheckButton(_("Manual sizing"))
        #~ table.attach(check, 0, 2, n_rows, n_rows + 1)
        #~ check.connect('toggled', self._sizing_toggled)
        #~ check.set_active(not settings.get_boolean('use_image_size',
            #~ default=True, plugin=plugin_name))
        #~ n_rows += 1

        #~ label = gtk.Label(_("Width"))
        #~ table.attach(label, 0, 1, n_rows, n_rows + 1)
        #~ size_widgets.append(label)
        #~ w = settings.get_int('width', default=CoverDisplay.DEFAULT_WIDTH,
            #~ plugin=plugin_name)
        #~ adj = gtk.Adjustment(w, 0, 32767, 1, 10, 10)
        #~ self.width_spin = spin = gtk.SpinButton(adj)
        #~ table.attach(spin, 1, 2, n_rows, n_rows + 1)
        #~ size_widgets.append(spin)
        #~ n_rows += 1

        #~ label = gtk.Label(_("Height"))
        #~ table.attach(label, 0, 1, n_rows, n_rows + 1)
        #~ size_widgets.append(label)
        #~ h = settings.get_int('height', default=CoverDisplay.DEFAULT_HEIGHT,
            #~ plugin=plugin_name)
        #~ adj = gtk.Adjustment(h, 0, 32767, 1, 10, 10)
        #~ self.height_spin = spin = gtk.SpinButton(adj)
        #~ table.attach(spin, 1, 2, n_rows, n_rows + 1)
        #~ size_widgets.append(spin)
        #~ n_rows += 1

        #~ self._setup_position_widgets()
        #~ self._setup_size_widgets()
        #~ table.show_all()

    #~ def run(self):
        #~ response = super(type(self), self).run()
        #~ if response != gtk.RESPONSE_OK: return response

        #~ settings = self.exaile.settings
        #~ plugin = self.plugin
        #~ plugin_name = self.plugin_name

        #~ keep_center = not self.position_check.get_active()
        #~ if plugin:
            #~ plugin.set_keep_center(keep_center)
        #~ settings.set_boolean('keep_center', keep_center, plugin=plugin_name)

        #~ gravity = self.gravity_combo.get_active()
        #~ if plugin:
            #~ plugin.set_gravity(GRAVITIES[gravity][1])
        #~ settings.set_int('gravity', gravity, plugin=plugin_name)

        #~ use_image_size = not self.sizing_check.get_active()
        #~ if plugin:
            #~ plugin.set_use_image_size(use_image_size)
        #~ settings.set_boolean('use_image_size', use_image_size,
            #~ plugin=plugin_name)

        #~ width = self.width_spin.get_value_as_int()
        #~ height = self.height_spin.get_value_as_int()
        #~ if plugin:
            #~ plugin.set_size(width, height)
        #~ settings.set_int('width', width, plugin=plugin_name)
        #~ settings.set_int('height', height, plugin=plugin_name)

        #~ x = self.x_spin.get_value_as_int()
        #~ y = self.y_spin.get_value_as_int()
        #~ if plugin:
            #~ plugin.set_position(x, y)
        #~ settings.set_int('x', x, plugin=plugin_name)
        #~ settings.set_int('y', y, plugin=plugin_name)

        #~ return response

    #~ def _positioning_toggled(self, check, *data):
        #~ self._setup_position_widgets(check.get_active())

    #~ def _sizing_toggled(self, check, *data):
        #~ self._setup_size_widgets(check.get_active())

    #~ def _setup_position_widgets(self, enabled=None):
        #~ if enabled is None:
            #~ enabled = not self.exaile.settings.get_boolean('keep_center',
                #~ default=True, plugin=self.plugin_name)
        #~ for w in self.position_widgets:
            #~ w.set_sensitive(enabled)

    #~ def _setup_size_widgets(self, enabled=None):
        #~ if enabled is None:
            #~ enabled = not self.exaile.settings.get_boolean('use_image_size',
                #~ default=True, plugin=self.plugin_name)
        #~ for w in self.size_widgets:
            #~ w.set_sensitive(enabled)


SETTINGS_PREFIX = 'plugin/desktopcover/'

cover_display = None
cover_connection = None
cover_widget = None
settings = SettingsManager.settings

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def disable(exaile):
    global cover_display, cover_connection
    cover_display.destroy()
    cover_display = None
    cover_widget.disconnect(cover_connection)
    cover_connection = None

def _enable(eventname, exaile, nothing):
    global cover_display, cover_connection

    cover_widget = exaile.gui.main.cover

    cover_display = CoverDisplay()
    cover_display.set_keep_center(settings.get_option(SETTINGS_PREFIX + 'keep_center', True))
    gravity = settings.get_option(SETTINGS_PREFIX + 'gravity', 0)
    cover_display.set_gravity(GRAVITIES[gravity][1])
    x = settings.get_option(SETTINGS_PREFIX + 'x', cover_display.DEFAULT_X)
    y = settings.get_option(SETTINGS_PREFIX + 'y', cover_display.DEFAULT_Y)
    cover_display.set_position(x, y)
    cover_display.set_use_image_size(settings.get_option(SETTINGS_PREFIX + 'use_image_size', True))
    width = settings.get_option(SETTINGS_PREFIX + 'width', cover_display.DEFAULT_WIDTH)
    height = settings.get_option(SETTINGS_PREFIX + 'height', cover_display.DEFAULT_HEIGHT)
    cover_display.set_size(width, height)

    player = exaile.player
    if player.current and (player.is_playing() or player.is_paused()):
        _display(cover_widget.loc)
    cover_connection = cover_widget.connect('cover-found', lambda w, c: _display(c))

def _display(cover):
    global stopped
    if 'nocover' in cover:
        cover_display.display(None)
    else:
        cover_display.display(cover)


# vi: et sts=4 sw=4 tw=80
