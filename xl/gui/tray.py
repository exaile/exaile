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

import gtk, gobject, gtk.gdk

from xl.gui import playlist
import xl.library as library

from xl import xlmisc, prefs
import xl.path
from gettext import gettext as _

USE_TRAY = None
import warnings
warnings.filterwarnings('ignore', 'the module egg.trayicon is deprecated',
    DeprecationWarning)

try:
    import egg.trayicon
    USE_TRAY = 'egg'
except ImportError:
    if hasattr(gtk, 'StatusIcon'):
        USE_TRAY = 'gtk'

class BaseTrayIcon(gobject.GObject):
    """
        System tray icon
    """
    rating_images = []
    rating_width = 64
    old_r_w = -1
    __gsignals__ = {
        'toggle-hide': (gobject.SIGNAL_RUN_LAST, bool, tuple())
    }
    def __init__(self, exaile):
        """
            Initializes the tray icon
        """
        gobject.GObject.__init__(self)
        self.exaile = exaile
        self.setup_menu()

    def setup_menu(self):
        """
            Sets up the popup menu for the tray icon
        """
        self.menu = xlmisc.Menu()

        playlist.create_rating_images(self)
        self.image = gtk.Image()
        self.image.set_from_stock('gtk-media-play',
            gtk.ICON_SIZE_MENU)
        self.label = gtk.Label(_("Play"))
        self.label.set_alignment(0, 0)

        self.playpause = gtk.MenuItem()
        hbox = gtk.HBox()
        hbox.set_spacing(5)
        hbox.pack_start(self.image, False, True)
        hbox.pack_start(self.label, True, True)
        self.playpause.add(hbox)
        self.playpause.connect('activate', lambda *e: self.exaile.player.toggle_pause())
        self.menu.append_item(self.playpause)

        self.menu.append(_("Next"), lambda *e: self.exaile.player.next(), 'gtk-media-next')
        self.menu.append(_("Previous"), lambda *e: self.exaile.player.previous(),
            'gtk-media-previous')
        self.menu.append(_("Stop"), lambda *e: self.exaile.player.stop(),
            'gtk-media-stop')


        star_icon = gtk.gdk.pixbuf_new_from_file_at_size(
            xl.path.get_data('images', 'star.png'), 16, 16)
        icon_set = gtk.IconSet(star_icon)
        factory = gtk.IconFactory()
        factory.add_default()        
        factory.add('exaile-star-icon', icon_set)
        self.rm  = xlmisc.Menu()
        for i in range(0, 5):
            if i == 0:
                item = self.rm.append('-', lambda w, e, i=i:
                    self.update_rating(self.exaile, i,
                    [self.exaile.player.current]))
            else:
                item = self.rm.append_image(self.rating_images[i],
                    lambda w, e, i=i: self.update_rating(self.exaile, i,
                    [self.exaile.player.current]))
        self.menu.append_menu(_("Rating"), self.rm, 'exaile-star-icon')

        self.menu.append_separator()
        self.menu.append(_("Plugins"), self.exaile.show_plugin_manager,
            'gtk-execute')
        self.menu.append(_("Preferences"), 
            lambda e, a: prefs.Preferences(self.exaile).run(),
            'gtk-preferences')

        self.menu.append_separator()
        self.menu.append(_("Quit"), self.exaile.on_quit, 'gtk-quit')

    def update_rating(self, caller, num, tracks=None):
        """
            Updates the rating based on which menu id was clicked
        """
        rating = num + 1

        cur = caller.db.cursor()
        if tracks is None: tracks = caller.get_selected_tracks()
        for track in tracks:
            path_id = library.get_column_id(caller.db, 'paths', 'name',
                track.loc)
            caller.db.execute("UPDATE tracks SET user_rating=? WHERE path=?",
                (rating, path_id)) 
            track.rating = rating
            self.exaile.tracks.refresh_row(track)

    def update_menu(self):
        track = self.exaile.player.current
        self.rm.set_sensitive(True)
        if not track: self.rm.set_sensitive(False)
        if not track or not self.exaile.player.is_playing():
            self.image.set_from_stock('gtk-media-play',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Play"))
        elif self.exaile.player.is_playing():
            self.image.set_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Pause"))

    def toggle_exaile_visibility(self):
        w = self.exaile.window
        if w.is_active(): # focused
            if self.emit('toggle-hide'): return
            w.hide()
        elif w.get_property('visible'): # unfocused
            w.present()
        else: # hidden
            if self.emit('toggle-hide'): return
            w.present()
            self.exaile.setup_location()

    def set_tooltip(self, tip): # to be overridden
        """
            Sets the tooltip for the tray icon
        """
        pass

    def destroy(self): # to be overridden
        """
            Unhides the window and removes the tray icon

            The unhiding is done here, while the removal needs to be
            done in a subclass. Don't forget to call this superclass
            method when you override it.
        """
        self.emit('toggle-hide') # FIXME: should this be vetoable?
        if not self.exaile.window.get_property('visible'):
            self.exaile.window.present()
            self.exaile.setup_location()

class EggTrayIcon(BaseTrayIcon):
    def __init__(self, exaile):
        BaseTrayIcon.__init__(self, exaile)

        self.tips = gtk.Tooltips()
        self.icon = egg.trayicon.TrayIcon('Exaile')
        self.box = gtk.EventBox()
        self.icon.add(self.box)

        image = gtk.Image()
        image.set_from_file(xl.path.get_data('images', 'trayicon.png'))
        self.box.add(image)
        self.box.connect('button_press_event',
            self.button_pressed)
        self.box.connect('scroll-event',
            self.scroll)
        self.box.connect('enter-notify-event', lambda *e: 
            self.exaile.show_osd(tray=True))
        self.icon.show_all()
        self.set_tooltip(_("Exaile Music Player"))

    def scroll(self, widget, ev):
        """
            Called when the user scrolls their mouse wheel over the tray icon
        """
        if ev.direction in [SCROLL_LEFT, SCROLL_RIGHT]:
            ev.state = gtk.gdk.SHIFT_MASK
        if ev.state & gtk.gdk.SHIFT_MASK:
            if ev.direction in [SCROLL_UP, SCROLL_LEFT]: self.exaile.on_previous()
            elif ev.direction in [SCROLL_DOWN, SCROLL_RIGHT]: self.exaile.on_next()
        else:
            if ev.direction in [SCROLL_RIGHT, SCROLL_UP]:
                self.exaile.volume.page_up()
            else:
                self.exaile.volume.page_down()

    def button_pressed(self, item, event, data=None):
        """
            Called when someone clicks on the icon
        """
        if event.button == 3:
            self.update_menu()
            self.menu.popup(None, None, None, event.button, event.time)
        elif event.button == 2:
            self.exaile.player.toggle_pause()
        elif event.button == 1: 
            self.toggle_exaile_visibility()

    def set_tooltip(self, tip):
        self.tips.set_tip(self.icon, tip)

    def destroy(self):
        BaseTrayIcon.destroy(self)
        self.icon.destroy()

class GtkTrayIcon(BaseTrayIcon):
    def __init__(self, exaile):
        BaseTrayIcon.__init__(self, exaile)
        self.icon = icon = gtk.StatusIcon()
        icon.set_tooltip('Exaile')
        icon.set_from_file(xl.path.get_data('images', 'trayicon.png'))
        icon.connect('activate', self.activated)
        icon.connect('popup-menu', self.popup)
        self.set_tooltip(_("Exaile Music Player"))

    def activated(self, icon):
        self.toggle_exaile_visibility()

    def popup(self, icon, button, time):
        self.update_menu()
        self.menu.popup(None, None, gtk.status_icon_position_menu,
            button, time, self.icon)

    def set_tooltip(self, tip):
        self.icon.set_tooltip(tip)

    def destroy(self):
        BaseTrayIcon.destroy(self)
        self.icon.set_visible(False)

if USE_TRAY == 'egg':
    TrayIcon = EggTrayIcon
elif USE_TRAY == 'gtk':
    TrayIcon = GtkTrayIcon
else:
    TrayIcon = None
