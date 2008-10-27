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
import gtk, gobject, gtk.glade
import logging
logger = logging.getLogger(__name__)

COVER_WIDTH = 100
NOCOVER_IMAGE = xdg.get_data_path("images/nocover.png")

class CoverManager(object):
    """
        Cover manager window
    """
    def __init__(self, parent, covers, collection):
        """
            Initializes the window
        """

        self.collection = collection
        self.manager = covers

        self.cover_nodes = {}
        self.covers = {}

        self.xml = gtk.glade.XML(xdg.get_data_path('glade/covermanager.glade'),
            'CoverManager', 'exaile')

        self.window = self.xml.get_widget('CoverManager')
        self.window.set_transient_for(parent)

        self.icons = self.xml.get_widget('cover_icon_view')
        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_item_width(90)

        self.icons.set_text_column(0)
        self.icons.set_pixbuf_column(1)

        self._connect_events()
        self.window.show_all()
        gobject.idle_add(self._find_initial)

    def _find_initial(self):
        """
            Locates covers and sets the icons in the windows
        """
        tracks = self.collection.search('') # find all tracks

        items = list(set([('/'.join(t['artist']), '/'.join(t['album'])) for t
            in tracks if t['artist'] and t['album']]))
        self.items = items

        nocover = gtk.gdk.pixbuf_new_from_file(NOCOVER_IMAGE)
        nocover = nocover.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)
        self.nocover = nocover
        self.count = 0
        for item in items:
            try:
                cover = self.manager.coverdb.get_cover(item[0], item[1])
            except TypeError:
                cover = None

            if cover:
                try:
                    image = gtk.gdk.pixbuf_new_from_file(cover)
                    image = image.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)
                except:
                    image = nocover
            else:
                image = nocover
            self.cover_nodes[item] = self.model.append(
                ["%s - %s" % (item[0], item[1]), 
                image, item[0]])
            self.covers[item] = image
            self.count += 1
        self.icons.set_model(self.model)

    def _connect_events(self):
        """
            Connects the various events
        """
        self.xml.signal_autoconnect({
        })

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
            self.set_image(xdg.get_data_path('images/nocover.png'))
            return

        if self.player.current == self.current_track:
            gobject.idle_add(self.set_image, cov)
            self.loc = cov

    def on_playback_end(self, type, player, object):
        """
            Called when playback stops.  Resets to the nocover image
        """
        self.set_image(xdg.get_data_path('images/nocover.png'))
