# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

__all__ = ['main', 'panel', 'playlist']

import gtk, gtk.glade, gobject
from xl import xdg

class Main(object):
    """
        This is the main gui controller for exaile
    """
    def __init__(self, exaile):
        """ 
            Initializes the GUI

            @param exaile: The Exaile instance
        """
        self.exaile = exaile

def show_splash(show=True):
    """
        Show a splash screen

        @param show: [bool] show the splash screen
    """
    image = gtk.Image()
    image.set_from_file("%ssplash.png" % xdg.get_image_dir())
    xml = gtk.glade.XML('%ssplash.glade' % xdg.get_glade_dir(), 'SplashScreen', 'exaile')
    splash_screen = xml.get_widget('SplashScreen')
    box = xml.get_widget('splash_box')
    box.pack_start(image, True, True)
    splash_screen.set_transient_for(None)
    splash_screen.show_all()
    gobject.timeout_add(2500, splash_screen.destroy) 
