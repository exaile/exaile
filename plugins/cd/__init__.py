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


from xl.nls import gettext as _
from xl import providers, event
from xl.hal import Handler, UDisksProvider
from xl.devices import Device, KeyedDevice
import logging
logger = logging.getLogger(__name__)

import dbus
import threading
import os
import struct
from fcntl import ioctl
from xl import playlist, trax, common
from xl import settings
import os.path

try:
    import DiscID
    import CDDB
    CDDB_AVAIL = True
except Exception:
    CDDB_AVAIL = False

import cdprefs


TOC_HEADER_FMT = 'BB'
TOC_ENTRY_FMT = 'BBBix'
ADDR_FMT = 'BBB' + 'x' * (struct.calcsize('i') - 3)
CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306
CDROM_LEADOUT = 0xAA
CDROM_MSF = 0x02
CDROM_DATA_TRACK = 0x04


class CdPlugin(object):

    def enable(self, exaile):
        self.exaile = exaile
        self.hal = None
        self.udisks = None
        self.udisks2 = None

    def on_exaile_loaded(self):

        # verify that hal/whatever is loaded, load correct provider

        if self.exaile.udisks2 is not None:
            self.udisks2 = UDisks2CdProvider()
            providers.register('udisks2', self.udisks2)

        elif self.exaile.udisks is not None:
            self.udisks = UDisksCdProvider()
            providers.register('udisks', self.udisks)

        elif self.exaile.hal is not None:
            self.udisks = HALCdProvider()
            providers.register('hal', self.udisks)

    def disable(self, exaile):
        if self.hal is not None:
            providers.unregister('hal', self.hal)
        if self.udisks is not None:
            providers.unregister('udisks', self.udisks)
        if self.udisks2 is not None:
            providers.unregister('udisks2', self.udisks2)

    def get_preferences_pane(self):
        return cdprefs

plugin_class = CdPlugin


class CDTocParser(object):
    # based on code from http://carey.geek.nz/code/python-cdrom/cdtoc.py

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
        try:
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

                self.raw_tracks.append((track, m, s, f, (m * 60 + s) * 75 + f, data))
        finally:
            os.close(fd)

    def get_raw_info(self):
        return self.raw_tracks[:]

    def get_track_lengths(self):
        offset = self.raw_tracks[0][4]
        lengths = []
        for track in self.raw_tracks[1:]:
            lengths.append((track[4] - offset) / 75)
            offset = track[4]
        return lengths


class CDPlaylist(playlist.Playlist):

    def __init__(self, name=_("Audio Disc"), device=None):
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
            song = trax.Track("cdda://%d/#%s" % (count, self.device))
            song.set_tag_raw('title', "Track %d" % count)
            song.set_tag_raw('tracknumber', str(count))
            song.set_tag_raw('__length', length)
            songs[song.get_loc_for_io()] = song

        # FIXME: this can probably be cleaner
        sort_tups = sorted([(int(s.get_tag_raw('tracknumber')[0]), s)
                            for s in songs.values()])
        sorted = [s[1] for s in sort_tups]

        self.extend(sorted)

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
            tr = self[i]
            tr.set_tag_raw('title',
                           info['TTITLE' + str(i)].decode('iso-8859-15', 'replace'))
            tr.set_tag_raw('album',
                           title[1].decode('iso-8859-15', 'replace'))
            tr.set_tag_raw('artist',
                           title[0].decode('iso-8859-15', 'replace'))
            tr.set_tag_raw('year',
                           info['EXTD'].replace("YEAR: ", ""))
            tr.set_tag_raw('genre',
                           info['DGENRE'])

        self.name = title[1].decode('iso-8859-15', 'replace')
        event.log_event('cddb_info_retrieved', self, True)


class CDDevice(KeyedDevice):
    """
        represents a CD
    """
    class_autoconnect = True

    def __init__(self, dev):
        Device.__init__(self, dev)
        self.name = _("Audio Disc")
        self.dev = dev

    def _get_panel_type(self):
        import imp
        try:
            _cdguipanel = imp.load_source("_cdguipanel",
                                          os.path.join(os.path.dirname(__file__), "_cdguipanel.py"))
            return _cdguipanel.CDPanel
        except Exception:
            logger.exception("Could not import cd gui panel")
            return 'flatplaylist'

    panel_type = property(_get_panel_type)

    def connect(self):
        cdpl = CDPlaylist(device=self.dev)
        self.playlists.append(cdpl)
        self.connected = True

    def disconnect(self):
        self.playlists = []
        self.connected = False
        CDDevice.destroy(self)


class HALCdProvider(Handler):
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
            return

        device = str(cd.GetProperty("block.device"))

        cddev = CDDevice(dev=device)

        return cddev


class UDisksCdProvider(UDisksProvider):
    name = 'cd'
    PRIORITY = UDisksProvider.NORMAL

    def get_priority(self, obj, udisks):
        # DeviceChanged is called before and after tracks are read. We only want
        # the second case, so use number of audio tracks to identify supported
        # media. As a bonus, this means we never have to care about the type of
        # disc (CD, DVD, etc.).
        ntracks = obj.props.Get('OpticalDiscNumAudioTracks')
        return self.PRIORITY if ntracks > 0 else None

    def get_device(self, obj, udisks):
        return CDDevice(str(obj.props.Get('DeviceFile')))

    def on_device_changed(self, obj, udisks, device):
        if obj.props.Get('OpticalDiscNumAudioTracks') <= 0:
            return 'remove'


class UDisks2CdProvider(UDisksProvider):
    name = 'cd'
    PRIORITY = UDisksProvider.NORMAL

    def _get_num_tracks(self, obj, udisks):
        if obj.iface_type != 'org.freedesktop.UDisks2.Block':
            return

        try:
            drive = udisks.get_object_by_path(obj.props.Get('Drive'))
        except KeyError:
            return

        # Use number of audio tracks to identify supported media
        ntracks = drive.props.Get('OpticalNumAudioTracks')
        if ntracks > 0:
            return ntracks

    def get_priority(self, obj, udisks):
        ntracks = self._get_num_tracks(obj, udisks)
        if ntracks is not None:
            return self.PRIORITY

    def get_device(self, obj, udisks):
        device = obj.props.Get('Device', byte_arrays=True).strip('\0')
        return CDDevice(str(device))

    def on_device_changed(self, obj, udisks, device):
        if self._get_num_tracks(obj, udisks) is None:
            return 'remove'

# vim: et sts=4 sw=4
