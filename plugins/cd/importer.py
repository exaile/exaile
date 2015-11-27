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

import copy
import os
import threading

from xl import (
    common,
    formatter,
    settings,
    transcoder,
    trax
)


class CDImporter(object):

    def __init__(self, tracks):
        self.tracks = [t for t in tracks if
                       t.get_loc_for_io().startswith("cdda")]
        self.duration = float(
            sum([t.get_tag_raw('__length') for t in self.tracks]))
        self.transcoder = transcoder.Transcoder()
        self.formatter = formatter.TrackFormatter(settings.get_option("cd_import/outpath",
                                                                      "%s/$artist/$album/$tracknumber - $title" % os.getenv("HOME")))
        self.current = None
        self.current_len = None
        self.progress = 0.0

        self.running = False

        self.format = settings.get_option("cd_import/format",
                                          "Ogg Vorbis")
        self.quality = settings.get_option("cd_import/quality", -1)

        self.cont = None

    def do_import(self):
        self.running = True

        self.cont = threading.Event()

        self.transcoder.set_format(self.format)
        if self.quality != -1:
            self.transcoder.set_quality(self.quality)
        self.transcoder.end_cb = self._end_cb

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
            for t in tr.list_tags():
                if not t.startswith("__"):
                    tr2.set_tag_raw(t, tr.get_tag_raw(t))
            tr2.write_tags()
            try:
                incr = tr.get_tag_raw('__length') / self.duration
                self.progress += incr
            except:
                raise
        self.progress = 100.0

    def _end_cb(self):
        self.cont.set()

    def get_output_location(self, track):
        path = self.formatter.format(track)
        directorypath = os.path.dirname(path)

        if not os.path.exists(directorypath):
            os.makedirs(directorypath)

        extension = transcoder.FORMATS[
            self.transcoder.dest_format]['extension']

        return path + '.' + extension

    def stop(self):
        self.running = False
        self.transcoder.stop()

    def get_progress(self):
        if not self.current or not self.current_len:
            return self.progress
        incr = self.current_len / self.duration
        pos = self.transcoder.get_time() / float(self.current_len)
        return self.progress + pos * incr
