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
