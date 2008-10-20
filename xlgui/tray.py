
import gtk

from xl import xdg, event

class BaseTrayIcon(object):

    def __init__(self, guimain):
        self.guimain = guimain
        self.window = guimain.main.window

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

if hasattr(gtk, 'StatusIcon'):
    class GtkTrayIcon(BaseTrayIcon):

        def __init__(self, guimain):
            BaseTrayIcon.__init__(self, guimain)
            self.icon = gtk.StatusIcon()
            self.icon.set_from_file(xdg.get_data_path('images/trayicon.png'))
            self.icon.connect('activate', self.activated)

        def activated(self, icon):
            self.toggle_exaile_visibility()

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

def connect_events(main, settings):
    global MAIN
    MAIN = main
    event.add_callback(get_options, 'option_set')
