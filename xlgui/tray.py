
import gtk

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
            lambda *e: self._play_pause_clicked())
        self.menu.append_item(self.playpause)

        self.menu.append(_("Next"),
            lambda *e: self.queue.next(),
            'gtk-media-next')
        self.menu.append(_("Previous"),
            lambda *e: self.queue.prev(),
            'gtk-media-previous')

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

        self.rating = gtk.MenuItem()
        hbox2 = gtk.HBox()
        hbox2.pack_start(gtk.Label(_("Rating:   ")), False, False)
        self.rating_image = gtk.image_new_from_pixbuf (self._get_rating_pixbuf(self.queue.get_current ()))
        hbox2.pack_start(self.rating_image, False, False, 4)
        self.rating.add(hbox2)
        self.menu.append_item(self.rating)
        self.rating.connect('button-release-event', self._change_rating)
        event.add_callback(self._on_rating_change, 'playback_track_start')
        event.add_callback(self._on_rating_change, 'rating_changed')
        
        self.menu.append(_("Remove current track from playlist"), lambda *e: self._remove_current_song (), 'gtk-remove')

        self.menu.append_separator()

        self.menu.append(_("Quit"),
            lambda *e: self.controller.exaile.quit(), 
            'gtk-quit')
    
    def _change_rating(self, w, e):
        current = self.controller.main.queue.get_current ()
        if current:
            steps = settings.get_option('miscellaneous/rating_steps', 5)
            (x, y) = e.get_coords()
            (u, v) =  self.rating.translate_coordinates(self.rating_image, int(x), int(y))
            if -12 <= u < 0:
                r = 0
            elif 0 <= u < steps*12:
                r = (u / 12) + 1
            else:
                r = -1
            
            if r >= 0:
                if r == current.get_rating():
                    r = 0
                current.set_rating(r)
                event.log_event('rating_changed', self, r)
        
    def _on_rating_change(self, type = None, dontuse1 = None, dontuse2 = None):
        self.rating_image.set_from_pixbuf (self._get_rating_pixbuf (self.queue.get_current ()))
    
    def _get_rating_pixbuf(self, track):
        if track:
            try:
                return self.controller.main.get_current_playlist ().rating_images[track.get_rating()]
            except IndexError:
                steps = settings.get_option('miscellaneous/rating_steps', 5)
                idx = track.get_rating()
                if idx > steps: idx = steps
                elif idx < 0: idx = 0
                return self.controller.main.get_current_playlist ().rating_images[idx]
        else:
            return self.controller.main.get_current_playlist ().rating_images[0]

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

    def _update_shuffle(self, data):
        settings.set_option('playback/shuffle', self.check_shuffle.get_active())

    def _update_repeat(self, data):
        settings.set_option('playback/repeat', self.check_repeat.get_active())

    def _update_dynamic(self, data):
        settings.set_option('playback/dynamic', self.check_dyna.get_active())

    def _remove_current_song(self):
        _pl = self.controller.main.get_current_playlist ().playlist
        if _pl:
            _pl.remove (_pl.index (self.queue.get_current ()))
    

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
        if self.window.is_active():
            self.window.hide()
        else:
            self.window.present()

    def _query_tooltip(self, *e):
        if settings.get_option('osd/hover_tray', False):
            self.controller.main.osd.show(self.queue.get_current())

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

