# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

__all__ = ['main', 'panel', 'playlist']

import gtk, gtk.glade, gobject
from xl import xdg
import xl.main as xlmain
from xlgui import main, panel, guiutil
from xlgui.panel import collection, radio, playlists, files
from gettext import gettext as _

gtk.window_set_default_icon_from_file(xdg.get_data_path("images/icon.png"))

def mainloop():
    gtk.main()

class Main(object):
    """
        This is the main gui controller for exaile
    """
    @guiutil.gtkrun
    def __init__(self, exaile):
        """ 
            Initializes the GUI

            @param exaile: The Exaile instance
        """
        self.exaile = exaile
        self.first_removed = False
        self.xml = gtk.glade.XML(xdg.get_data_path("glade/main.glade"),
            'ExaileWindow', 'exaile')

        self.main = main.MainWindow(self, self.xml, exaile.settings, 
            exaile.collection,
            exaile.player, exaile.queue)
        self.panel_notebook = self.xml.get_widget('panel_notebook')
        self._connect_events()

        self.collection_panel = collection.CollectionPanel(self,
            exaile.settings, exaile.collection)
        self.radio_panel = radio.RadioPanel(self, exaile.settings, 
            exaile.collection, exaile.radio, exaile.stations)
        self.playlists_panel = playlists.PlaylistsPanel(self,
            exaile.playlists, exaile.smart_playlists, exaile.collection)
        self.files_panel = files.FilesPanel(self, exaile.settings,
            exaile.collection)

        self.main.window.show_all()

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.xml.signal_autoconnect({
            'on_about_item_activated': self.show_about_dialog
        })

    def add_panel(self, child, name):
        """
            Adds a panel to the panel notebook
        """
        label = gtk.Label(name)
        label.set_angle(90)
        self.panel_notebook.append_page(child, label)

        if not self.first_removed:
            self.first_removed = True

            # the first tab in the panel is a stub that just stops libglade from
            # complaining
            self.panel_notebook.remove_page(0)

    def show_about_dialog(self, *e):
        """
            Displays the about dialog
        """
        xml = gtk.glade.XML(xdg.get_data_path('glade/about_dialog.glade'),
            'AboutDialog', 'exaile')
        dialog = xml.get_widget('AboutDialog')
        logo = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/exailelogo.png'))
        dialog.set_logo(logo)
        # HACK: GTK+ < 2.12 (2007-09-14) use set_name.
        try:
            dialog.set_program_name(_("Exaile"))
        except AttributeError:
            dialog.set_name(_("Exaile"))
        dialog.set_version("\n" + str(xlmain.__version__))
        dialog.set_transient_for(self.main.window)
        dialog.run()
        dialog.destroy()
        
    def quit(self):
        """
            Quits the gui, saving anything that needs to be saved
        """

        # save open tabs
        self.main.save_current_tabs()

@guiutil.gtkrun
def show_splash(show=True):
    """
        Show a splash screen

        @param show: [bool] show the splash screen
    """
    image = gtk.Image()
    image.set_from_file(xdg.get_data_path("images/splash.png"))
    xml = gtk.glade.XML(xdg.get_data_path("glade/splash.glade"), 'SplashScreen', 'exaile')
    splash_screen = xml.get_widget('SplashScreen')
    box = xml.get_widget('splash_box')
    box.pack_start(image, True, True)
    splash_screen.set_transient_for(None)
    splash_screen.show_all()
    #FIXME: should disappear when loading finishes, not at a fixed time
    gobject.timeout_add(2500, splash_screen.destroy) 
