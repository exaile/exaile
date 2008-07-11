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
from xlgui import main, panel, guiutil
from xlgui.panel import collection, radio, playlists, files

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
        self.main = main.MainWindow(self)

        self.collection_panel = collection.CollectionPanel(self,
            exaile.collection)
        self.radio_panel = radio.RadioPanel(self, exaile.collection,
            exaile.radio, exaile.stations)
        self.playlists_panel = playlists.PlaylistsPanel(self,
            exaile.playlists, exaile.smart_playlists, exaile.collection)
        self.files_panel = files.FilesPanel(self, exaile.collection)

        self.main.window.show_all()
        
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
