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

import logging
import threading
import os

from gi.repository import GLib

from xl import common, event, formatter, settings, transcoder, trax
from xl.nls import gettext as _
from xlgui.panel import device
import xlgui


logger = logging.getLogger(__name__)


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
            logger.info("Calling queue_draw for %s", str(cdplaylist))
            self.fppanel.tree.queue_draw()

    def do_import(self, tracks):
        if self.__importing:
            return
        self.__importing = True
        cd_importer = CDImporter(tracks)
        thread = CDImportThread(cd_importer)
        thread.connect('done', lambda *e: self._import_finish())
        self.main.controller.progress_manager.add_monitor(
            thread, _("Importing CD..."), 'drive-optical'
        )

    def _import_finish(self):
        self.__importing = False


class CDImporter:
    def __init__(self, tracks):
        self.tracks = [t for t in tracks if t.get_loc_for_io().startswith("cdda")]
        self.duration = sum(t.get_tag_raw('__length') for t in self.tracks)
        self.formatter = formatter.TrackFormatter(
            settings.get_option(
                "cd_import/outpath",
                "%s/$artist/$album/$tracknumber - $title" % os.getenv("HOME"),
            )
        )
        self.current = None
        self.current_len = None
        self.progress = 0.0

        self.running = False

        self.cont = None
        self.__prepare_transcoder()

    def __prepare_transcoder(self):
        formats = transcoder.get_formats()
        default_format = next(formats.keys())
        self.format = settings.get_option("cd_import/format", default_format)
        default_quality = formats[default_format]['default']
        self.quality = settings.get_option("cd_import/quality", default_quality)
        self.transcoder = transcoder.Transcoder(
            self.format, self.quality, self._error_cb, self._end_cb
        )

    def do_import(self):
        self.running = True

        self.cont = threading.Event()

        self.transcoder.set_format(self.format)
        if self.quality != -1:
            self.transcoder.set_quality(self.quality)

        for tr in self.tracks:
            self.cont.clear()
            self.current = tr
            self.current_len = tr.get_tag_raw('__length')
            loc = tr.get_loc_for_io()
            trackno, device = loc[7:].split("/#")
            src = "cdparanoiasrc track=%s device=\"%s\"" % (trackno, device)
            self.transcoder.set_raw_input(src)
            outloc = self.get_output_location(tr)
            self.transcoder.set_output(outloc)
            self.transcoder.start_transcode()
            self.cont.wait()
            if not self.running:
                break
            tr2 = trax.Track("file://" + outloc)
            ntags = {
                t: tr.get_tag_raw(t) for t in tr.list_tags() if not t.startswith("__")
            }
            tr2.set_tags(**ntags)
            tr2.write_tags()
            try:
                incr = tr.get_tag_raw('__length') / self.duration
                self.progress += incr
            except Exception:
                raise
        self.progress = 100.0

    def _end_cb(self):
        self.cont.set()
        xlgui.main.mainwindow().message.show_info("Finished transcoding files")

    def _error_cb(self, gerror, message_string):
        self.running = False
        xlgui.main.mainwindow().message.show_error(
            _("Error transcoding files from CD."), "%s" % gerror.message.encode()
        )

    def get_output_location(self, track):
        path = self.formatter.format(track)
        directorypath = os.path.dirname(path)

        if not os.path.exists(directorypath):
            os.makedirs(directorypath)

        extension = transcoder.FORMATS[self.transcoder.dest_format]['extension']

        return path + '.' + extension

    def stop(self):
        self.running = False
        self.transcoder.stop()

    def get_progress(self):
        if not self.current or not self.current_len:
            return self.progress
        incr = self.current_len / self.duration
        pos = self.transcoder.get_time() / self.current_len
        return self.progress + pos * incr
