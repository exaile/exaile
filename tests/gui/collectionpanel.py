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
from tests.gui import base
from xlgui.panel import collection
from xl import playlist
import gtk, gtk.gdk

class CollectionPanelTestCase(base.BaseTestCase):
    def setUp(self):
        base.BaseTestCase.setUp(self)

    def testCollectionPanel(self):
        assert type(self.gui.panels['collection']) == collection.CollectionPanel, \
            "Collection panel type is incorrect"

    def testAddAlbum(self):
        pl = playlist.Playlist('CollectionPanelTest')
        self.gui.main.add_playlist(pl)

        panel = self.gui.panels['collection']
        selection = panel.tree.get_selection()

        selection.select_path((0,))

        model = panel.tree.get_model()
        
        panel.append_to_playlist()
        page = self.gui.main.get_selected_playlist()
        selection = page.list.get_selection()
        selection.select_path((3,))
    
        track = page.get_selected_tracks()[0]
        assert track['title'][0] == 'Truly', "Collection panel " \
            "append_to_playlist failed"
