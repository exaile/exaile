from tests.gui import base
from xlgui.panel import collection

class CollectionPanelTestCase(base.BaseTestCase):
    def setUp(self):
        base.BaseTestCase.setUp(self)

    def testCollectionPanel(self):
        assert type(self.gui.collection_panel) == collection.CollectionPanel, \
            "Collection panel type is incorrect"
        
