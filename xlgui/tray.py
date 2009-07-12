
import gtk

from xl import xdg, event
from xl.nls import gettext as _
from xlgui import guiutil

class TrayIcon(object):
    VOLUME_SCROLL_AMOUNT = 5

    def __init__(self, guimain):
        self.guimain = guimain
        self.main = guimain.main
        self.window = guimain.main.window
        self._setup_menu()

        self.icon = gtk.StatusIcon()
        self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))
        self.icon.connect('activate', self._activated)
        self.icon.connect('popup-menu', self._popup)
        try:
            # Since GTK+ 2.14
            self.icon.connect('button-press-event', self._button_pressed)
            # Since GTK+ 2.16 (or 2.14?)
            self.icon.connect('scroll-event', self._scrolled)
        except TypeError:
            pass
        self.set_tooltip(_("Exaile Music Player"))

        event.add_callback(self._on_playback_change_state, 'playback_player_start')
        event.add_callback(self._on_playback_change_state, 'playback_toggle_pause')
        event.add_callback(self._on_playback_change_state, 'playback_player_end')

    def set_tooltip(self, tip):
        self.icon.set_tooltip(tip)

    def destroy(self):
        """
            Unhides the window and removes the tray icon
        """
        if not self.window.get_property('visible'):
            self.window.present()
        self.icon.set_visible(False)

    def _setup_menu(self):
        """
            Sets up the popup menu for the tray icon
        """
        self.menu = guiutil.Menu()

        self.playpause_image = gtk.Image()
        self.playpause_image.set_from_stock('gtk-media-play',
            gtk.ICON_SIZE_MENU)
        self.label = gtk.Label(_("Play"))
        self.label.set_alignment(0, 0)

        self.playpause = gtk.ImageMenuItem()
        hbox = gtk.HBox()
        hbox.pack_start(self.label, False, True)
        self.playpause.add(hbox)
        self.playpause.set_image(self.playpause_image)
        self.id = self.playpause.connect('activate', self._play)
        self.menu.append_item(self.playpause)

        self.menu.append(_("Next"), lambda *e: self.main.queue.next(), 'gtk-media-next')
        self.menu.append(_("Previous"), lambda *e: self.main.queue.prev(),
            'gtk-media-previous')
        self.menu.append(_("Stop"), lambda *e: self.main.player.stop(),
            'gtk-media-stop')

        self.menu.append_separator()
        self.menu.append(_("Plugins"), self.guimain.show_plugins,
            'gtk-execute')
        self.menu.append(_("Preferences"), 
            lambda e, a: self.guimain.show_preferences(),
            'gtk-preferences')

        self.menu.append_separator()
        self.menu.append(_("Quit"), lambda *e: self.guimain.exaile.quit(), 
                         'gtk-quit')

    def _play(self, *args):
        if self.main.player.current:
            self.main.player.toggle_pause()
        else:
            self.main.queue.play()

    def _update_menu(self):
        track = self.main.player.current
        if not track or not self.main.player.is_playing():
            self.playpause_image.set_from_stock('gtk-media-play',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Play"))
            self.playpause.disconnect(self.id)
            self.id = self.playpause.connect('activate', self._play)
        elif self.main.player.is_playing():
            self.playpause_image.set_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Pause"))
            self.playpause.disconnect(self.id)
            self.id = self.playpause.connect('activate', lambda *e: self.main.player.toggle_pause())

    # Playback state event

    def _on_playback_change_state(self, event, player, current):
        if player.current is None:
            self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))
        elif player.is_paused():
            self.icon.set_from_stock('gtk-media-pause')
        else:
            self.icon.set_from_stock('gtk-media-play') 

    # Mouse events

    def _activated(self, icon):
        w = self.window
        if w.is_active(): # focused
            w.hide()
        else:
            w.present()

    def _button_pressed(self, icon, event):
        if event.button == 2:
            self.main.player.toggle_pause()

    def _popup(self, icon, button, time):
        self.update_menu()
        self.menu.popup(None, None, gtk.status_icon_position_menu,
            button, time, self.icon)

    def _scrolled(self, icon, event):
        exaile = self.main
        if event.state & gtk.gdk.SHIFT_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                exaile.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                exaile.queue.next()
        else:
            if event.direction == gtk.gdk.SCROLL_UP:
                volume = exaile.player.get_volume()
                exaile.player.set_volume(volume + self.VOLUME_SCROLL_AMOUNT)
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                volume = exaile.player.get_volume()
                exaile.player.set_volume(volume - self.VOLUME_SCROLL_AMOUNT)
            elif event.direction == gtk.gdk.SCROLL_LEFT:
                exaile.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_RIGHT:
                exaile.queue.next()

MAIN = None

def get_options(type, settings, option):
    if option == 'gui/use_tray':
        value = settings.get_option(option, False)

        if MAIN.tray_icon and not value:
            MAIN.tray_icon.destroy()
            MAIN.tray_icon = None
        elif value and not MAIN.tray_icon:
            MAIN.tray_icon = TrayIcon(MAIN)

def connect_events(main):
    global MAIN
    MAIN = main
    event.add_callback(get_options, 'option_set')
