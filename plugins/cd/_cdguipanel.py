from xl.nls import gettext as _

from xlgui.panel import device
from xl import event

import imp, os
mod = imp.find_module("importer", [os.path.dirname(__file__)])
importer = imp.load_module("importer", *mod)
del mod, imp, os

import gobject
import logging, threading
logger = logging.getLogger(__name__)

class CDImportThread(threading.Thread):
    def __init__(self, imp, panel):
        threading.Thread.__init__(self)
        self.setDaemon(True)

        self.imp = imp
        self.panel = panel

    def stop_thread(self):
        self.imp.stop()

    def progress_update(self, progress=None):
        if progress is None:
            progress = self.imp.get_progress()*100
        event.log_event("progress_update", self, progress)
        return True

    def run(self):
        id = gobject.timeout_add(1000, self.progress_update)
        self.imp.do_import()
        gobject.source_remove(id)
        self.progress_update(100)


class CDPanel(device.FlatPlaylistDevicePanel):
    def __init__(self, *args):
        device.FlatPlaylistDevicePanel.__init__(self, *args)
        self.__importing = False

        event.add_callback(self._tree_queue_draw, 'cddb_info_retrieved')

    def _tree_queue_draw(self, type, cdplaylist, object=None):
        if not hasattr(self.fppanel, 'tree'): 
            return

        if cdplaylist in self.device.playlists:
            logger.info("Calling queue_draw for %s" % str(cdplaylist))
            self.fppanel.tree.queue_draw()

    def do_import(self, tracks):
        if self.__importing:
            return
        self.__importing == True
        imp = importer.CDImporter(tracks)
        impthread = CDImportThread(imp, self)
        self.main.controller.progress_manager.add_monitor(impthread,
                _("Importing CD..."), 'gtk-harddisk')


    def _import_finish(self):
        self.__importing = False

