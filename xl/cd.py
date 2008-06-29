# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

# CD.py
#
# Handles cd playback, burning, import
#
#

import dbus, threading, os, struct
from fcntl import ioctl
from xl import playlist, settings, track, common, hal, devices, transcoder
settings=settings.SettingsManager.settings

try:
    import DiscID, CDDB
    CDDB_AVAIL=True
except:
    CDDB_AVAIL=False

class NoCddbError(Exception):
    pass

TOC_HEADER_FMT = 'BB'
TOC_ENTRY_FMT = 'BBBix'
ADDR_FMT = 'BBB' + 'x' * (struct.calcsize('i') - 3)
CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306
CDROM_LEADOUT = 0xAA
CDROM_MSF = 0x02
CDROM_DATA_TRACK = 0x04

class CDTocParser(object):
    #based on code from http://carey.geek.nz/code/python-cdrom/cdtoc.py
    def __init__(self, device):
        self.device = device

        # raw_tracks becomes a list of tuples in the form
        # (track number, minutes, seconds, frames, total frames, data)
        # minutes, seconds, frames and total trames are absolute offsets
        # data is 1 if this is a track containing data, 0 if audio
        self.raw_tracks = []

        self.read_toc()

    def read_toc(self):
        fd = os.open(self.device, os.O_RDONLY)
        toc_header = struct.pack(TOC_HEADER_FMT, 0, 0)
        toc_header = ioctl(fd, CDROMREADTOCHDR, toc_header)
        start, end = struct.unpack(TOC_HEADER_FMT, toc_header)

        self.raw_tracks = []

        for trnum in range(start, end + 1) + [CDROM_LEADOUT]:
            entry = struct.pack(TOC_ENTRY_FMT, trnum, 0, CDROM_MSF, 0)
            entry = ioctl(fd, CDROMREADTOCENTRY, entry)
            track, adrctrl, format, addr = struct.unpack(TOC_ENTRY_FMT, entry)
            m, s, f = struct.unpack(ADDR_FMT, struct.pack('i', addr))
                
            adr = adrctrl & 0xf
            ctrl = (adrctrl & 0xf0) >> 4

            data = 0
            if ctrl & CDROM_DATA_TRACK:
                data = 1

            self.raw_tracks.append( (track, m, s, f, (m*60+s) * 75 + f, data) ) 

    def get_raw_info(self):
        return self.raw_tracks[:]

    def get_track_lengths(self):
        offset = self.raw_tracks[0][4]
        lengths = []
        for track in self.raw_tracks[1:]:
            lengths.append((track[4]-offset)/75)
            offset = track[4]
        return lengths

class CDPlaylist(playlist.Playlist):
    def __init__(self, name="Audio CD", device=None):
        playlist.Playlist.__init__(self, name=name)

        if not device:
            self.device = "/dev/cdrom"
        else:
            self.device = device

        self.open_disc()

    def open_disc(self):

        toc = CDTocParser(self.device)
        lengths = toc.get_track_lengths()

        songs = {}
        
        for count, length in enumerate(lengths):
            count += 1
            song = track.Track()
            song.set_loc("cdda://%d#%s" % (count, self.device))
            song['title'] = "Track %d" % count
            song['tracknumber'] = count
            song['length'] = length
            songs[song.get_loc()] = song

        sort_tups = [ (int(s['tracknumber']),s) for s in songs.values() ]
        sort_tups.sort()

        sorted = [ s[1] for s in sort_tups ]

        self.add_tracks(sorted)

        if CDDB_AVAIL:
            self.get_cddb_info()
    
    @common.threaded
    def get_cddb_info(self):
        try:
            disc = DiscID.open(self.device)
            self.info = DiscID.disc_id(disc) 
            status, info = CDDB.query(self.info)
        except IOError:
            return

        if status in (210, 211):
            info = info[0]
            status = 200
        if status != 200:
            return
        
        
        (status, info) = CDDB.read(info['category'], info['disc_id'])
        
        title = info['DTITLE'].split(" / ")
        for i in range(self.info[1]):
            self.ordered_tracks[i]['title'] = \
                    info['TTITLE' + `i`].decode('iso-8859-15', 'replace')
            self.ordered_tracks[i]['album'] = \
                    title[1].decode('iso-8859-15', 'replace')
            self.ordered_tracks[i]['artist'] = \
                    title[0].decode('iso-8859-15', 'replace')
            self.ordered_tracks[i]['year'] = \
                    info['EXTD'].replace("YEAR: ", "")
            self.ordered_tracks[i]['genre'] = \
                    info['DGENRE']

        self.set_name(title[1].decode('iso-8859-15', 'replace'))


class CDDevice(devices.Device):
    """
        represents a CD
    """
    def __init__(self, dev="/dev/cdrom"):
        devices.Device.__init__(self, dev)
        self.dev = dev

    def connect(self):
        cdpl = CDPlaylist(device=self.dev)
        self.playlists.append(cdpl)

    def disconnect(self):
        self.playlists = []


class CDHandler(hal.Handler):
    name = "cd"
    def is_type(self, device, capabilities):
        if "volume.disc" in capabilities:
            return True
        return False

    def get_udis(self, hal):
        udis = hal.hal.FindDeviceByCapability("volume.disc")
        return udis

    def device_from_udi(self, hal, udi):
        cd_obj = hal.bus.get_object("org.freedesktop.Hal", udi)
        cd = dbus.Interface(cd_obj, "org.freedesktop.Hal.Device")
        if not cd.GetProperty("volume.disc.has_audio"):
            return #not CD-Audio
            #TODO: implement mp3 cd support
        device = str(cd.GetProperty("block.device"))

        cddev = CDDevice( dev=device)

        return cddev

class CDImporter(object):
    def __init__(self, tracks):
        self.tracks = [ t for t in tracks if t.get_loc_for_io().startswith("cdda") ]
        self.duration = float(sum( [ t['length'] for t in self.tracks ] ))
        self.transcoder = transcoder.Transcoder()
        self.current = None
        self.progress = 0.0

        self.running = False

        self.outpath = settings.get_option("cd_import/outpath", "%s/${artist}/${album}/${tracknumber} - ${title}"%os.getenv("HOME"))

        self.format = settings.get_option("cd_import/format", "Ogg Vorbis")
        self.quality = settings.get_option("cd_import/quality", -1)

        self.cont = None

    @common.threaded
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
            loc = tr.get_loc_for_io()
            track, device = loc[7:].split("#")
            src = "cdparanoiasrc track=%s device=\"%s\""%(track, device)
            self.transcoder.set_raw_input(src)
            self.transcoder.set_output(self.get_output_location(tr))
            self.transcoder.start_transcode()
            self.cont.wait()
            if not self.running:
                break
            incr = tr['length'] / self.duration
            self.progress += incr
        self.progress = 100.0

    def _end_cb(self):
        self.cont.set()

    def get_output_location(self, tr):
        parts = self.outpath.split(os.sep)
        parts2 = []
        replacedict = {}
        for tag in common.VALID_TAGS:
            replacedict["${%s}"%tag] = tag
        for part in parts:
            for k, v in replacedict.iteritems():
                part = part.replace(k, str(tr[v]))
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
        incr = self.current['length'] / self.duration
        pos = self.transcoder.get_time()/float(self.current['length'])
        return self.progress + pos*incr

# vim: et sts=4 sw=4

