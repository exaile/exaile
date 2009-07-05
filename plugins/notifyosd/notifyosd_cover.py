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

logger = logging.getLogger(__name__)

DEFAULT_COVER = xdg.get_data_path('images/nocover.png')

def notifyosd_get_image_for_track(track, exaile):
    '''Get a path for a track

    '''
    logger.debug("Getting cover for " + str(track))
    item = track.get_album_tuple()
    image = None
    if all(item) and hasattr(exaile, 'covers'):
        image = exaile.covers.coverdb.get_cover(*item)
    if image is None:
        logger.debug("Did not find cover, using DEFAULT_COVER")
        image = DEFAULT_COVER
    logger.debug("Using image %s" % repr(image))
    return image
