# Copyright (C) 2009 Abhishek Mukherjee <abhishek.mukher.g@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import gtk.gdk
import logging
from xl import xdg
from xl import cover

logger = logging.getLogger(__name__)

DEFAULT_COVER = xdg.get_data_path('images/nocover.png')
RESIZE_SIZE = 48

def get_image_for_track(track, exaile, resize=False):
    '''Get a Pixbuf for a track

    If resize is True, the image will be resized so the maximum dimension is
    RESIZE_SIZE

    '''
    logger.debug("Getting cover for " + str(track))
    item = cover.get_album_tuple(track)
    image = None
    if all(item) and hasattr(exaile, 'covers'):
        image = exaile.covers.coverdb.get_cover(*item)
    if image is None:
        logger.debug("Did not find cover, using DEFAULT_COVER")
        image = DEFAULT_COVER
    logger.debug("Using image %s" % repr(image))
    pixbuf = gtk.gdk.pixbuf_new_from_file(image)
    if resize:
        logger.debug("Resizing cover")
        width, height = pixbuf.get_width(), pixbuf.get_height()
        if width > height:
            little, big = height, width
        else:
            little, big = width, height
        scale = RESIZE_SIZE * 1.0 / big
        big = RESIZE_SIZE
        little = int(round(scale * little, 0))
        if width > height:
            height, width = little, big
        else:
            width, height = little, big
        pixbuf = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
    logger.debug("Returning new cover pixbuf")
    return pixbuf

