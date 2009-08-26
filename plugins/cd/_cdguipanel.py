# Copyright (C) 2009 Aren Olson
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


from xl.nls import gettext as _

from xlgui.panel import device
from xl import event

import imp, os
importer = imp.load_source("importer", 
        os.path.join(os.path.dirname(__file__), "importer.py"))

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

