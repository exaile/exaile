# desktopcover - displays Exaile album covers on the desktop
# Copyright (C) 2006-2009  Johannes Sasongko <sasongko@gmail.com>
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
from xl import event, settings
from xl.nls import gettext as _
from xlgui import guiutil
import prefs


class CoverDisplay:
    DEFAULT_SETTINGS = dict(x=0, y=0, width=200, height=200,
        gravity=gtk.gdk.GRAVITY_NORTH_WEST)
    GRAVITY_SIGNS = {
        gtk.gdk.GRAVITY_NORTH_WEST: ('+', '+'),
        gtk.gdk.GRAVITY_NORTH_EAST: ('-', '+'),
        gtk.gdk.GRAVITY_SOUTH_WEST: ('+', '-'),
        gtk.gdk.GRAVITY_SOUTH_EAST: ('-', '-'),
    }

    def __init__(self, settings=None):
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

        if settings is None:
            self.settings = self.DEFAULT_SETTINGS.copy()
        else:
            self.settings = settings
        self.cover = None
        self.set_use_image_size()
        self.set_keep_center()

        self.image = img = gtk.Image()
        wnd.add(img)
        img.show()

    def set_keep_center(self, keep_center=False):
        self.keep_center = keep_center
        #~ gtk_do_events()
        if keep_center:
            self.window.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        else:
            self.window.set_position(gtk.WIN_POS_NONE)
            self.set_position()

    def set_gravity(self, gravity=None):
        #~ gtk_do_events()
        if gravity is None:
            gravity = self.settings['gravity']
        else:
            self.settings['gravity'] = gravity
        self.window.set_gravity(gravity)
        return gravity

    def set_position(self, x=None, y=None, force=False):
        settings = self.settings
        if x is None or y is None:
            x = settings['x']
            y = settings['y']
        else:
            settings['x'] = x
            settings['y'] = y

        #~ gtk_do_events()
        if not self.keep_center and (force or self.window.props.visible):
            gravity = self.set_gravity()
            xsgn, ysgn = self.GRAVITY_SIGNS[gravity]
            #~ gtk_do_events()
            #~ self.window.parse_geometry('%s%s%s%s' % (xsgn, x, ysgn, y))
            width, height = self.window.get_size()
            if xsgn == '-':
                x = gtk.gdk.screen_get_default().get_width() - width - x
            if ysgn == '-':
                y = gtk.gdk.screen_get_default().get_height() - height - y
            self.window.move(int(x), int(y))

    def set_use_image_size(self, use_image_size=False):
        self.use_image_size = use_image_size

    def set_size(self, width, height):
        settings = self.settings
        settings['width'] = width
        settings['height'] = height
        self.display(self.cover)

    def display(self, cover):
        if self.cover != cover:
            self.cover = cover
            gobject.timeout_add_seconds(1, self._display, cover)

    def _display(self, cover):
        # Only process the last request.
        if cover != self.cover: return True

        if cover is None:
            self.image.clear()
            #~ gtk_do_events()
            self.window.hide()
            return

        pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if not self.use_image_size:
            settings = self.settings
            origw = float(width)
            origh = float(height)
            width, height = settings['width'], settings['height']
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


SETTINGS_PREFIX = 'plugin/desktopcover/'
GRAVITIES = [
    gtk.gdk.GRAVITY_NORTH_WEST,
    gtk.gdk.GRAVITY_NORTH_EAST,
    gtk.gdk.GRAVITY_SOUTH_WEST,
    gtk.gdk.GRAVITY_SOUTH_EAST,
]

class SettingsBridge:
    settings_map = dict(width='size', height='size', gravity='anchor')
    def __getitem__(self, key):
        settings_key = self.settings_map.get(key, key)
        default = CoverDisplay.DEFAULT_SETTINGS[key]
        if key == 'gravity':
            default = GRAVITIES.index(default)
        value = settings.get_option(SETTINGS_PREFIX + settings_key, default)
        if key == 'gravity':
            value = GRAVITIES[value]
        return value

cover_display = None
cover_connection = None
cover_widget = None

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

def get_prefs_pane():
    return prefs

@guiutil.idle_add()
def _enable(eventname, exaile, nothing):
    global cover_display, cover_connection

    cover_display = CoverDisplay(settings=SettingsBridge())
    cover_widget = exaile.gui.main.cover

    player = exaile.player
    if player.current and (player.is_playing() or player.is_paused()):
        _display(cover_widget.loc)
    cover_connection = cover_widget.connect('cover-found',
        lambda w, c: _display(c))

def _display(cover):
    global stopped
    if 'nocover' in cover:
        cover_display.display(None)
    else:
        cover_display.display(cover)


# vi: et sts=4 sw=4 tw=80
