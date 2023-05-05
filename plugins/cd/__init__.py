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
import importlib
import logging
import os.path
import sys

from gi.repository import GLib

from xl.nls import gettext as _
from xl import providers, event, main
from xl.hal import Handler, UDisksProvider
from xl.devices import Device, KeyedDevice
from xl import playlist, trax, common, settings
from xl.trax import Track

from . import cdprefs, _cdguipanel
from sys import exc_info


logger = logging.getLogger(__name__)


if sys.platform.startswith('linux'):
    from . import linux_cd_parser


class CdPlugin:
    discid_parser = None
    musicbrainzngs_parser = None

    def __import_dependency(self, module_name):
        try:
            sys.path.append(os.path.dirname(__file__))
            full_name = module_name + '_parser'
            imported = importlib.import_module(full_name)
            sys.path.pop()
            return imported
        except ImportError:
            logger.warn(
                'Cannot import optional dependency "%s" for plugin cd.', module_name
            )
            logger.debug(
                'Traceback for importing dependency "%s" for plugin cd.',
                module_name,
                exc_info=True,
            )
            return None

    def enable(self, exaile):
        CdPlugin.discid_parser = self.__import_dependency('discid')
        CdPlugin.musicbrainzngs_parser = self.__import_dependency('musicbrainzngs')
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


class _CDTrack:
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


class CDTocParser:
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

            # All tracks plus leadout
            for trnum in list(range(start, end + 1)) + [CDROM_LEADOUT]:
                entry = struct.pack(TOC_ENTRY_FMT, trnum, 0, CDROM_MSF, 0)
                entry = ioctl(fd, CDROMREADTOCENTRY, entry)
                self.__raw_tracks.append(_CDTrack(entry))
        finally:
            os.close(fd)

    def _get_track_lengths(self):
        """returns track length in seconds"""
        track = self.__raw_tracks[0]
        offset = track.get_frame_count()
        lengths = []
        for track in self.__raw_tracks[1:]:
            frame_end = track.get_frame_count()
            lengths.append((frame_end - offset) // 75)
            offset = frame_end
        return lengths


class CDPlaylist(playlist.Playlist):
    def __init__(self, name=_("Audio Disc"), device=None):
        playlist.Playlist.__init__(self, name=name)

        if not device:
            self.__device = "/dev/cdrom"
        else:
            self.__device = device
        self.__read_disc_index_async(device)

    @common.threaded
    def __read_disc_index_async(self, device):
        """This function must be run async because it does slow I/O"""
        logger.info('Starting to read disc index')

        if CdPlugin.discid_parser is not None:
            try:
                disc_id = CdPlugin.discid_parser.read_disc_id(device)
                logger.debug(
                    'Successfully read CD using discid with %i tracks. '
                    'Musicbrainz id: %s',
                    len(disc_id.tracks),
                    disc_id.id,
                )
                GLib.idle_add(self.__apply_disc_index, disc_id, None, None)
                return
            except Exception:
                logger.warn('Failed to read from cd using discid.', exc_info=True)

        if sys.platform.startswith('linux'):
            try:
                (toc_entries, mcn) = linux_cd_parser.read_cd_index(device)
                GLib.idle_add(self.__apply_disc_index, None, toc_entries, mcn)
                return
            except Exception:
                logger.warn('Failed to read metadata from CD.', exc_info=True)

        GLib.idle_add(self.__apply_disc_index, None, None, None)

    def __apply_disc_index(self, disc_id, toc_entries, mcn):
        """This function must be run sync because it accesses the track database"""
        logger.debug('Applying disc contents to playlist')
        if disc_id is not None:
            tracks = CdPlugin.discid_parser.parse_disc(disc_id, self.__device)
            if tracks is not None:
                allow_internet = settings.get_option(
                    'cd_import/fetch_metadata_from_internet', True
                )
                if allow_internet:
                    logger.info('Starting to get disc metadata')
                    self.__fetch_disc_metadata(disc_id, tracks)
        elif toc_entries is not None:
            tracks = linux_cd_parser.parse_tracks(toc_entries, mcn, self.__device)
        else:
            logger.error('Could not read disc index')
            tracks = None
        if tracks is not None:
            logger.debug('Read disc with tracks %s', tracks)
            self.extend(tracks)
        event.log_event('cd_info_retrieved', self, None)

    @common.threaded
    def __fetch_disc_metadata(self, disc_id, tracks):
        # TODO: show progress during work

        # TODO: Add more providers?
        # Discogs:
        #    Problem: Barely documented, no known support for disc_id
        # * https://github.com/discogs/discogs_client
        # * https://www.discogs.com/developers/
        # CDDB/freedb:
        # * old python code: http://pycddb.sourceforge.net/
        # * even older python code: http://cddb-py.sourceforge.net/
        # * http://ftp.freedb.org/pub/freedb/latest/DBFORMAT
        # * http://ftp.freedb.org/pub/freedb/latest/CDDBPROTO
        # * Servers: http://freedb.freedb.org/,
        if CdPlugin.musicbrainzngs_parser is not None:
            musicbrainz_data = CdPlugin.musicbrainzngs_parser.fetch_with_disc_id(
                disc_id
            )
            GLib.idle_add(
                self.__musicbrainz_metadata_fetched, musicbrainz_data, disc_id, tracks
            )

    def __musicbrainz_metadata_fetched(self, musicbrainz_data, disc_id, tracks):
        metadata = CdPlugin.musicbrainzngs_parser.parse(
            musicbrainz_data, disc_id, tracks
        )
        # TODO: progress: finished
        if metadata is not None:
            (tracks, title) = metadata
            logger.info('Finished getting disc metadata. Disc title: %s', title)
            event.log_event('cd_info_retrieved', self, title)
            self.name = title


class CDDevice(KeyedDevice):
    """
    represents a CD
    """

    class_autoconnect = True

    def __init__(self, dev):
        Device.__init__(self, dev)
        self.name = _("Audio Disc")
        self.dev = dev

    panel_type = _cdguipanel.CDPanel

    def __on_cd_info_retrieved(self, _event_type, cd_playlist, _disc_title):
        self.playlists.append(cd_playlist)
        self.connected = True

    def connect(self):
        if self.connected:
            return
        event.add_ui_callback(self.__on_cd_info_retrieved, 'cd_info_retrieved')
        CDPlaylist(device=self.dev)

    def disconnect(self):
        if not self.connected:
            return
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
        device = obj.props.Get('Device', byte_arrays=True).decode('utf-8')
        device = device.strip('\0')
        return CDDevice(device)

    def on_device_changed(self, obj, udisks, device):
        if self._get_num_tracks(obj, udisks) is None:
            return 'remove'


# vim: et sts=4 sw=4
