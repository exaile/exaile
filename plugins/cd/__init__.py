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

import dbus
from fcntl import ioctl
import logging
import os
import struct

from xl.nls import gettext as _
from xl import providers, event, main
from xl.hal import Handler, UDisksProvider
from xl.devices import Device, KeyedDevice

from xl import playlist, trax, common
import os.path

import cdprefs
from sys import exc_info


logger = logging.getLogger(__name__)

try:
    try:
        from libdiscid.compat import discid
    except ImportError:
        import discid
    import musicbrainzngs

    DISCID_AVAILABLE = True
except ImportError:
    logger.warn('Cannot import dependency for plugin cd.', exc_info=True)
    DISCID_AVAILABLE = False


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
        self.__exaile = exaile
        self.__udisks2 = None

    def on_exaile_loaded(self):
        # verify that hal/whatever is loaded, load correct provider
        if self.__exaile.udisks2 is not None:
            self.__udisks2 = UDisks2CdProvider()
            providers.register('udisks2', self.__udisks2)

    def teardown(self, exaile):
        if self.__udisks2 is not None:
            providers.unregister('udisks2', self.__udisks2)
        self.__udisks2 = None
        self.__exaile = None

    def disable(self, exaile):
        self.teardown(exaile)

    def get_preferences_pane(self):
        return cdprefs


plugin_class = CdPlugin


class _CDTrack(object):
    """
        @ivar track: Track number. Starts with 1, which is used for the TOC and contains data.
        @ivar data: `True` if this "track" contains data, `False` if it is audio
        @ivar minutes: Minutes from begin of CD
        @ivar seconds: Seconds after `minutes`, from begin of CD
        @ivar frames: Frames after `seconds`, from begin of CD
    """

    def __init__(self, entry):
        self.track, adrctrl, _format, addr = struct.unpack(TOC_ENTRY_FMT, entry)
        self.minutes, self.seconds, self.frames = struct.unpack(
            ADDR_FMT, struct.pack('i', addr)
        )

        # adr = adrctrl & 0xf
        ctrl = (adrctrl & 0xF0) >> 4

        self.data = False
        if ctrl & CDROM_DATA_TRACK:
            self.data = True

    def get_frame_count(self):
        return (self.minutes * 60 + self.seconds) * 75 + self.frames


class CDTocParser(object):
    # based on code from http://carey.geek.nz/code/python-cdrom/cdtoc.py

    def __init__(self, device):
        self.__raw_tracks = []
        self.__read_toc(device)

    def __read_toc(self, device):
        fd = os.open(device, os.O_RDONLY)
        try:
            toc_header = struct.pack(TOC_HEADER_FMT, 0, 0)
            toc_header = ioctl(fd, CDROMREADTOCHDR, toc_header)
            start, end = struct.unpack(TOC_HEADER_FMT, toc_header)

            for trnum in range(start, end + 1) + [CDROM_LEADOUT]:
                entry = struct.pack(TOC_ENTRY_FMT, trnum, 0, CDROM_MSF, 0)
                entry = ioctl(fd, CDROMREADTOCENTRY, entry)
                self.__raw_tracks.append(_CDTrack(entry))
        finally:
            os.close(fd)

    def _get_track_lengths(self):
        """ returns track length in seconds """
        track = self.__raw_tracks[0]
        offset = track.get_frame_count()
        lengths = []
        for track in self.__raw_tracks[1:]:
            frame_end = track.get_frame_count()
            lengths.append((frame_end - offset) / 75)
            offset = frame_end
        return lengths


class CDPlaylist(playlist.Playlist):
    def __init__(self, name=_("Audio Disc"), device=None):
        playlist.Playlist.__init__(self, name=name)

        if not device:
            self.__device = "/dev/cdrom"
        else:
            self.__device = device

        self.open_disc()

    def open_disc(self):

        toc = CDTocParser(self.__device)
        lengths = toc._get_track_lengths()

        songs = []

        for count, length in enumerate(lengths):
            count += 1
            song = trax.Track("cdda://%d/#%s" % (count, self.__device))
            song.set_tags(
                title="Track %d" % count, tracknumber=str(count), __length=length
            )
            songs.append(song)

        self.extend(songs)

        if DISCID_AVAILABLE:
            try:
                musicbrainz_data = self.__get_discid_info()
                self.__parse_musicbrainz_data(musicbrainz_data)
            except WebServiceError as web_error:
                logger.warn('Failed to fetch data from musicbrainz', exc_info=True)

    @common.threaded
    def __get_discid_info(self):
        disc_id = discid.read(self.__device)
        version = main.exaile().get_user_agent_for_musicbrainz()
        musicbrainzngs.set_useragent(*version)
        result = musicbrainzngs.get_releases_by_discid(
            disc_id.id, toc=disc_id.toc_string, includes=["artists", "recordings"])
        return result
    
    def __parse_musicbrainz_data(self, musicbrainz_data):
        if musicbrainz_data.get('disc'):  # preferred: good quality
            # arbitrarily choose first release. There may be more!
            release = musicbrainz_data['disc']['release-list'][0]
            artist = release['artist-credit-phrase']
            album_title = release['title']
            date = release['date']
            if release['medium-count'] > 1 or release['medium-list'][0]['disc-count'] > 1:
                raise NotImplementedError
            if len(self) is not release['medium-list'][0]['track-count']:
                raise NotImplementedError
            track_list = release['medium-list'][0]['track-list']
            disc_number = '{0}/{1}'.format(
                release['medium-list'][0]['position'],
                1)  # TODO calculate disk number?
            
            for track_index in range(0, len(self)):
                # TODO put this into a new musicbrainz parser in xl/metadata
                track = self[track_index]
                track_number = '{0}/{1}'.format(
                    track_list[track_index]['number'],  # TODO or position?
                    release['medium-list'][0]['track-count'])
                track.set_tags(
                    artist=artist,
                    title=track_list[track_index]['recording']['title'],
                    albumartist=artist,
                    album=album_title,
                    tracknumber=track_number,
                    discnumber=disc_number,
                    date=date,
                    # TODO Get more data with secondary query, e.g. genre ("tags")? 
                    )
            
            self.name = album_title
            
        elif musicbrainz_data.get('cdstub'):  # not so nice
            raise NotImplementedError
        event.log_event('cd_info_retrieved', self, True)


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
            _cdguipanel = imp.load_source(
                "_cdguipanel", os.path.join(os.path.dirname(__file__), "_cdguipanel.py")
            )
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
