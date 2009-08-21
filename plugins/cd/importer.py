
import os, threading, copy
from xl import transcoder, track, settings, common


class CDImporter(object):
    def __init__(self, tracks):
        self.tracks = [ t for t in tracks if 
                t.get_loc_for_io().startswith("cdda") ]
        self.duration = float(sum( [ t['__length'] for t in self.tracks ] ))
        self.transcoder = transcoder.Transcoder()
        self.current = None
        self.current_len = None
        self.progress = 0.0

        self.running = False

        self.outpath = settings.get_option("cd_import/outpath", 
                "%s/$artist/$album/$tracknumber - $title" % \
                os.getenv("HOME"))

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
            self.current_len = tr['__length']
            tags = copy.copy(tr.tags)
            for t in tags.keys():
                if t.startswith("__"):
                    del tags[t]
            loc = tr.get_loc_for_io()
            trackno, device = loc[7:].split("#")
            src = "cdparanoiasrc track=%s device=\"%s\""%(trackno, device)
            self.transcoder.set_raw_input(src)
            outloc = self.get_output_location(tr)
            self.transcoder.set_output(outloc)
            self.transcoder.start_transcode()
            self.cont.wait()
            if not self.running:
                break
            tr2 = track.Track("file://"+outloc)
            tr2.tags.update(tags)
            try:
                incr = tr['__length'] / self.duration
                self.progress += incr
            except:
                raise
        self.progress = 100.0

    def _end_cb(self):
        self.cont.set()

    def get_output_location(self, tr):
        parts = self.outpath.split(os.sep)
        parts2 = []
        replacedict = {}
        # TODO: make this handle arbitrary tags
        for tag in common.VALID_TAGS:
            replacedict["$%s"%tag] = tag
        for part in parts:
            for k, v in replacedict.iteritems():
                val = tr[v]
                if type(val) in (list, tuple):
                    val = u" & ".join(val) 
                part = part.replace(k, str(val))
            part = part.replace(os.sep, "") # strip os.sep
            parts2.append(part)
        dirpath = "/" + os.path.join(*parts2[:-1]) 
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        ext = transcoder.FORMATS[self.transcoder.dest_format]['extension']
        path = "/" + os.path.join(*parts2) + "." + ext
        return path

    def stop(self):
        self.running = False
        self.transcoder.stop()

    def get_progress(self):
        if not self.current or not self.current_len:
            return self.progress
        incr = self.current_len / self.duration
        pos = self.transcoder.get_time()/float(self.current_len)
        return self.progress + pos*incr
