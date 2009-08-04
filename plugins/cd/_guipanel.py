from xlgui.panel import device
from xl import event
import logging
logger = logging.getLogger(__name__)

class CDPanel(device.FlatPlaylistDevicePanel):
    def __init__(self, *args):
        device.FlatPlaylistDevicePanel.__init__(self, *args)

        event.add_callback(self._tree_queue_draw, 'cddb_info_retrieved')

    def _tree_queue_draw(self, type, cdplaylist, object=None):
        if not hasattr(self.fppanel, 'tree'): return

        if cdplaylist in self.device.playlists:
            logger.info("Calling queue_draw for %s" % str(cdplaylist))
            self.fppanel.tree.queue_draw()
