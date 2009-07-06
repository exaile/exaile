
import gtk

import warnings
warnings.filterwarnings('ignore', 'the module egg.trayicon is deprecated',
                        DeprecationWarning)
try:
    import egg.trayicon
    EGG_AVAIL = True
except ImportError:
    EGG_AVAIL = False
    
from xl import xdg, event
from xl.nls import gettext as _
from xlgui import guiutil

class BaseTrayIcon(object):

    def __init__(self, guimain):
        self.guimain = guimain
        self.main = guimain.main
        self.window = guimain.main.window
        self.setup_menu()

        event.add_callback(self._on_playback_change_state, 'playback_player_start')
        event.add_callback(self._on_playback_change_state, 'playback_toggle_pause')
        event.add_callback(self._on_playback_change_state, 'playback_player_end')

    def _on_playback_change_state(self, event, player, current):
        pass # To be overridden

    def setup_menu(self):
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

    def update_menu(self):
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

    def toggle_exaile_visibility(self):
        w = self.window
        if w.is_active(): # focused
            w.hide()
        else:
            w.present()

    def activated(self):
        pass # ovderride this

    def destroy(self): # to be overridden
        """
            Unhides the window and removes the tray icon

            The unhiding is done here, while the removal needs to be
            done in a subclass. Don't forget to call this superclass
            method when you override it.
        """
        if not self.window.get_property('visible'):
            self.window.present()

TrayIcon = BaseTrayIcon

if EGG_AVAIL:
    class EggTrayIcon(BaseTrayIcon):
        def __init__(self, guimain):
            BaseTrayIcon.__init__(self, guimain)
    
            self.tips = gtk.Tooltips()
            self.icon = egg.trayicon.TrayIcon('Exaile')
            self.box = gtk.EventBox()
            self.icon.add(self.box)
    
            self.image = gtk.Image()
            self.image.set_from_file(xdg.get_data_path('images/trayicon.png'))
            self.box.add(self.image)
            self.box.connect('button_press_event', self.button_pressed)
            self.icon.show_all()
            self.set_tooltip(_("Exaile Music Player"))

        def _on_playback_change_state(self, event, player, current):
            if player.current is not None:
                if player.is_paused():
                    self.image.set_from_stock('gtk-media-pause', gtk.ICON_SIZE_MENU)
                else:
                    self.image.set_from_stock('gtk-media-play', gtk.ICON_SIZE_MENU) 
            else:
                self.image.set_from_file(xdg.get_data_path('images/trayicon.png'))
    
        def button_pressed(self, item, event, data=None):
            """
                Called when someone clicks on the icon
            """
            if event.button == 3:
                self.update_menu()
                self.menu.popup(None, None, None, event.button, event.time)
            elif event.button == 2:
                self.main.player.toggle_pause()
            elif event.button == 1: 
                self.toggle_exaile_visibility()
    
        def set_tooltip(self, tip):
            self.tips.set_tip(self.icon, tip)
    
        def destroy(self):
            BaseTrayIcon.destroy(self)
            self.icon.destroy()
            
    TrayIcon = EggTrayIcon

elif hasattr(gtk, 'StatusIcon'):
    class GtkTrayIcon(BaseTrayIcon):

        def __init__(self, guimain):
            BaseTrayIcon.__init__(self, guimain)
            self.icon = gtk.StatusIcon()
            self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))
            self.icon.connect('activate', self.activated)
            self.icon.connect('popup-menu', self.popup)
            self.set_tooltip(_("Exaile Music Player"))
            
        def _on_playback_change_state(self, event, player, current):
            if player.current is not None:
                if player.is_paused():
                    self.icon.set_from_stock('gtk-media-pause')
                else:
                    self.icon.set_from_stock('gtk-media-play') 
            else:
                self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))

        def activated(self, icon):
            self.toggle_exaile_visibility()
            
        def set_tooltip(self, tip):
            self.icon.set_tooltip(tip)

        def popup(self, icon, button, time):
            self.update_menu()
            self.menu.popup(None, None, gtk.status_icon_position_menu,
                button, time, self.icon)

        def destroy(self):
            BaseTrayIcon.destroy(self)
            self.icon.set_visible(False)

    TrayIcon = GtkTrayIcon

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
