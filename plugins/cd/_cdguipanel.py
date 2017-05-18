# Copyright (C) 2009-2010 Aren Olson
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

from gi.repository import Gtk
from gi.repository import GLib
import os
import imp
importer = imp.load_source("importer",
                           os.path.join(os.path.dirname(__file__), "importer.py"))
import logging
logger = logging.getLogger(__name__)

from xl import common, event
from xl.nls import gettext as _
from xlgui.panel import device


class CDImportThread(common.ProgressThread):

    def __init__(self, cd_importer):
        common.ProgressThread.__init__(self)

        self.cd_importer = cd_importer

    def stop(self):
        """
            Stops the thread
        """
        self.cd_importer.stop()
        common.ProgressThread.stop(self)

    def on_progress_update(self, progress=None):
        """
            Notifies about progress changes
        """
        if progress is None:
            progress = self.cd_importer.get_progress() * 100

        self.emit('progress-update', int(progress))

        return True

    def run(self):
        """
            Runs the thread
        """
        progress_id = GLib.timeout_add_seconds(1, self.on_progress_update)
        self.cd_importer.do_import()
        GLib.source_remove(progress_id)
        self.emit('done')


class CDPanel(device.FlatPlaylistDevicePanel):

    def __init__(self, *args):
        device.FlatPlaylistDevicePanel.__init__(self, *args)
        self.__importing = False

        event.add_ui_callback(self._tree_queue_draw, 'cddb_info_retrieved')

    def _tree_queue_draw(self, type, cdplaylist, object=None):
        if not hasattr(self.fppanel, 'tree'):
            return

        if cdplaylist in self.device.playlists:
            logger.info("Calling queue_draw for %s" % str(cdplaylist))
            self.fppanel.tree.queue_draw()

    def do_import(self, tracks):
        if self.__importing:
            return
        self.__importing = True
        cd_importer = importer.CDImporter(tracks)
        thread = CDImportThread(cd_importer)
        thread.connect('done', lambda *e: self._import_finish())
        self.main.controller.progress_manager.add_monitor(thread,
                                                          _("Importing CD..."), 'drive-optical')

    def _import_finish(self):
        self.__importing = False
