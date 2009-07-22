
import gobject, gtk

from xl import xdg, event, settings
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

class TrayIcon(gobject.GObject):
    VOLUME_SCROLL_AMOUNT = 5

    __gsignals__ = {'toggle-tray': (gobject.SIGNAL_RUN_LAST, bool, ())}

    def __init__(self, main):
        gobject.GObject.__init__(self)

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
            self.icon.connect('query-tooltip', self._query_tooltip)
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
        self.emit('toggle-tray')
        if not self.window.get_property('visible'):
            self.window.present()

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

        self.playpause = self.menu.append(stock_id='gtk-media-play',
            callback=lambda *e: self._play_pause_clicked())
        self.menu.append(stock_id='gtk-media-next',
            callback=lambda *e: self.queue.next())
        self.menu.append(stock_id='gtk-media-previous',
            callback=lambda *e: self.queue.prev())
        self.menu.append(stock_id='gtk-media-stop',
            callback=lambda *e: self.player.stop())

        self.menu.append_separator()

        self.check_shuffle = gtk.CheckMenuItem(_("Shuffle playback order"))
        self.check_shuffle.set_active(settings.get_option('playback/shuffle', False))
        self.check_shuffle.connect('toggled', self._update_shuffle)
        self.menu.append_item(self.check_shuffle)
        
        self.check_repeat = gtk.CheckMenuItem(_("Repeat playlist"))
        self.check_repeat.set_active(settings.get_option('playback/repeat', False))
        self.check_repeat.connect('toggled', self._update_repeat)
        self.menu.append_item(self.check_repeat)
        
        self.check_dyna = gtk.CheckMenuItem(_("Dynamically add similar tracks"))
        self.check_dyna.set_active(settings.get_option('playback/dynamic', False))
        self.check_dyna.connect('toggled', self._update_dynamic)
        self.menu.append_item(self.check_dyna)

        self.menu.append_separator()

        self.rating_item = guiutil.MenuRatingWidget(self.controller, 
            self._get_current_track_list)
        self.menu.append_item(self.rating_item)
        self.rm_item = self.menu.append(label=_("Remove current track from playlist"),
            stock_id='gtk-remove',
            callback=lambda *e: self._remove_current_song())
        
        self.menu.append_separator()

        self.menu.append(stock_id='gtk-quit',
            callback=lambda *e: self.controller.exaile.quit())

        event.add_callback(self._update_menu, 'playback_track_start')
    
    def _get_current_track_list(self):
        l = []
        l.append(self.player.current)
        return l
    
    def _update_menu(self, type=None, object=None, data=None):
        track = self.player.current
        if not track or not self.player.is_playing():
            self.playpause.destroy()
            self.playpause = self.menu.prepend(stock_id='gtk-media-play',
                callback=lambda *e: self._play_pause_clicked())
        elif self.player.is_playing():
            self.playpause.destroy()
            self.playpause = self.menu.prepend(stock_id='gtk-media-pause',
                callback=lambda *e: self._play_pause_clicked())
        
        if track:
            self.rating_item.set_sensitive(True)
            self.rm_item.set_sensitive(True)
        else:
            self.rating_item.set_sensitive(False)
            self.rm_item.set_sensitive(False)
        self.rating_item.on_rating_change()

    def _update_shuffle(self, data):
        settings.set_option('playback/shuffle', self.check_shuffle.get_active())

    def _update_repeat(self, data):
        settings.set_option('playback/repeat', self.check_repeat.get_active())

    def _update_dynamic(self, data):
        settings.set_option('playback/dynamic', self.check_dyna.get_active())

    def _remove_current_song(self):
        _pl = self.controller.main.get_current_playlist ().playlist
        if _pl and self.player.current:
            _pl.remove (_pl.index (self.player.current))
    

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
            toggle_handled = self.emit('toggle-tray')
            if not toggle_handled and self.window.is_active():
                self.window.hide()
            elif not toggle_handled:
                self.window.present()
        if event.button == 2:
            self._play_pause_clicked()
        if event.button == 3:
            self._update_menu()
            self.menu.popup(None, None, None,
                event.button, event.time, self.icon)
    
    def _play_pause_clicked(self):
        if self.player.is_paused() or self.player.is_playing():
            self.player.toggle_pause()
        else:
            pl = self.controller.main.get_selected_playlist()
            self.queue.set_current_playlist(pl.playlist)
            if pl:
                track = pl.get_selected_track()
                if track:
                    pl.playlist.set_current_pos(
                        pl.playlist.index(track))
            self.queue.play()

    def _activated(self, icon):
        toggle_handled = self.emit('toggle-tray')
        if not toggle_handled and self.window.is_active():
            self.window.hide()
        elif not toggle_handled:
            self.window.present()

    def _query_tooltip(self, *e):
        if settings.get_option('osd/hover_tray', False):
            self.controller.main.osd.show(self.player.current)

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

