# Copyright (C) 2008-2009 Adam Olsen 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
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
#
#
# The developers of the Exaile media player hereby grant permission 
# for non-GPL compatible GStreamer and Exaile plugins to be used and 
# distributed together with GStreamer and Exaile. This permission is 
# above and beyond the permissions granted by the GPL license by which 
# Exaile is covered. If you modify this code, you may extend this 
# exception to your version of the code, but you are not obligated to 
# do so. If you do not wish to do so, delete this exception statement 
# from your version.

from xl import settings, xdg
import gtk, pango, gtk.gdk, gobject

steps = settings.get_option('miscellaneous/rating_steps', 5)
_rating_width = 12 * steps

# creates the rating images for the caller
def create_rating_images(rating_width):
    """
        Called to (re)create the pixmaps used for the Rating column.
    """
    if rating_width != 0:
        rating_images = []
        steps = settings.get_option("miscellaneous/rating_steps", 5)
        icon_size = rating_width / steps

        icon = gtk.gdk.pixbuf_new_from_file_at_size(
            xdg.get_data_path('images/star.png'), icon_size, icon_size)
        void_icon = gtk.gdk.pixbuf_new_from_file_at_size(
            xdg.get_data_path('images/brightstar.png'), icon_size, icon_size)

        icons_image = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8,
            rating_width, icon_size)
        icons_image.fill(0xffffff00) # transparent white
        for x in range(0, steps + 1):
            for y in range(0, steps):
                if y < x:
                    icon.copy_area(0, 0, icon_size, icon_size, icons_image, icon_size * y, 0)
                else:
                    void_icon.copy_area(0, 0, icon_size, icon_size, icons_image, icon_size * y, 0)
            rating_images.append(icons_image)
            icons_image = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8,
                rating_width, icon_size)
            icons_image.fill(0xffffff00) # transparent white

        return rating_images

def set_rating(tracks, new_rating):
    steps = settings.get_option('miscellaneous/rating_steps', 5)
    for track in tracks:
        track['__rating'] = float((100.0*rating)/steps)

rating_images = create_rating_images(_rating_width)
