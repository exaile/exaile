# Copyright (C) 2006 Adam Olsen
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

from xl import xdg, event, cover, common
from xlgui import guiutil
import gtk, gobject
import logging
logger = logging.getLogger(__name__)

COVER_WIDTH = 100

class CoverWidget(guiutil.ScalableImageWidget):
    """
        Represents the album art widget displayed by the track information
    """
    def __init__(self, main, covers, player):
        """
            Initializes the widget

            @param main: The Main window
            @param player: the xl.player.Player object
        """
        guiutil.ScalableImageWidget.__init__(self)
        self.main = main
        self.current_track = None
        self.covers = covers
        self.player = player

        self.set_image_size(COVER_WIDTH, COVER_WIDTH)
        self.set_image(xdg.get_data_path('images/nocover.png'))

        event.add_callback(self.on_playback_start, 'playback_start', player)
        event.add_callback(self.on_playback_end, 'playback_end', player)

    @common.threaded
    def on_playback_start(self, type, player, object):
        """
            Called when playback starts.  Fetches album covers, and displays
            them
        """
        self.current_track = player.current

        try:
            cov = self.covers.get_cover(self.current_track,
                update_track=True)
        except cover.NoCoverFoundException:
            logger.warning("No covers found")
            return

        if self.player.current == self.current_track:
            gobject.idle_add(self.set_image, cov)
            self.loc = cov

    def on_playback_end(self, type, player, object):
        """
            Called when playback stops.  Resets to the nocover image
        """
        self.set_image(xdg.get_data_path('images/nocover.png'))
