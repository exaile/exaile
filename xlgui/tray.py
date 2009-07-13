
import gtk

from xl import xdg, event
from xl.nls import gettext as _
from xlgui import guiutil

try:
    import egg.trayicon

    class EggTrayIcon(egg.trayicon.TrayIcon):
        """
            Wrapper class to make EggTrayIcon behave like GtkStatusIcon
        """

        def __init__(self):
            egg.trayicon.TrayIcon.__init__(self, 'Exaile')
            self.tips = gtk.Tooltips()
            self.image = gtk.Image()
            self.add(self.image)
            self.show_all()

            self.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.SCROLL_MASK)

        def set_tooltip(self, tip):
            self.tips.set_tip(self, tip)

        def set_from_file(self, file):
            self.image.set_from_file(file)

        def set_from_stock(self, stock_id):
            self.image.set_from_stock(stock_id, gtk.ICON_SIZE_MENU)
except ImportError:
    pass

class TrayIcon(object):
    VOLUME_SCROLL_AMOUNT = 5

    def __init__(self, main):
        self.controller = main.controller
        self.player = main.controller.exaile.player
        self.queue = main.controller.exaile.queue
        self.window = main.window
        self._setup_menu()

        self.icon = gtk.StatusIcon()
        try:
            # Available if PyGtk was built against GTK >= 2.15.0
            self.icon.connect('button-press-event', self._button_pressed)
            self.icon.connect('scroll-event', self._scrolled)
        except TypeError:
            try:
                self.icon = EggTrayIcon()
                self.icon.connect('button-press-event', self._button_pressed)
                self.icon.connect('scroll-event', self._scrolled)
            except NameError:
                self.icon.connect('activate', self._activated)
                self.icon.connect('popup-menu', self._popup_menu)
        self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))
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
        self.icon.destroy()

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
        self.playpause.connect('activate',
            lambda *e: self.player.toggle_pause())
        self.menu.append_item(self.playpause)

        self.menu.append(_("Next"),
            lambda *e: self.queue.next(),
            'gtk-media-next')
        self.menu.append(_("Previous"),
            lambda *e: self.queue.prev(),
            'gtk-media-previous')
        self.menu.append(_("Stop"),
            lambda *e: self.player.stop(),
            'gtk-media-stop')

        self.menu.append_separator()

        self.menu.append(_("Plugins"),
            lambda *e: self.controller.show_plugins(),
            'gtk-execute')
        self.menu.append(_("Preferences"), 
            lambda e, page: self.controller.show_preferences(),
            'gtk-preferences')

        self.menu.append_separator()

        self.menu.append(_("Quit"),
            lambda *e: self.controller.exaile.quit(), 
            'gtk-quit')

    def _update_menu(self):
        track = self.player.current
        if not track or not self.player.is_playing():
            self.playpause_image.set_from_stock('gtk-media-play',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Play"))
        elif self.player.is_playing():
            self.playpause_image.set_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_MENU)
            self.label.set_label(_("Pause"))

    # Playback state event
    def _on_playback_change_state(self, event, player, current):
        if player.current is None:
            self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))
        elif player.is_paused():
            self.icon.set_from_stock('gtk-media-pause')
        else:
            self.icon.set_from_stock('gtk-media-play')

    def _button_pressed(self, icon, event):
        if event.button == 1:
            if self.window.is_active():
                self.window.hide()
            else:
                self.window.present()
        if event.button == 2:
            self.player.toggle_pause()
        if event.button == 3:
            self._update_menu()
            self.menu.popup(None, None, None,
                event.button, event.time, self.icon)

    def _activated(self, icon):
        if self.window.is_active():
            self.window.hide()
        else:
            self.window.present()

    def _popup_menu(self, icon, button, time):
        self._update_menu()
        self.menu.popup(None, None, None,
            button, time, icon)

    def _scrolled(self, icon, event):
        if event.state & gtk.gdk.SHIFT_MASK:
            if event.direction == gtk.gdk.SCROLL_UP:
                self.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                self.queue.next()
        else:
            if event.direction == gtk.gdk.SCROLL_UP:
                volume = self.player.get_volume()
                self.player.set_volume(volume + self.VOLUME_SCROLL_AMOUNT)
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                volume = self.player.get_volume()
                self.player.set_volume(volume - self.VOLUME_SCROLL_AMOUNT)
            elif event.direction == gtk.gdk.SCROLL_LEFT:
                self.queue.prev()
            elif event.direction == gtk.gdk.SCROLL_RIGHT:
                self.queue.next()

