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
import logging
import os.path
import sys

from xl.nls import gettext as _
from xl import providers, event, main
from xl.hal import Handler, UDisksProvider
from xl.devices import Device, KeyedDevice
from xl import playlist, trax, common
from xl.trax import Track

import cdprefs


logger = logging.getLogger(__name__)


if sys.platform.startswith('linux'):
    import linux_cd_parser

try:
    try:  # allow both python-discid and python-libdiscid
        from libdiscid.compat import discid
    except ImportError:
        import discid
    import discid_parser
    DISCID_AVAILABLE = True
except ImportError:
    logger.warn('Cannot import dependency for plugin cd.', exc_info=True)
    DISCID_AVAILABLE = False

try:
    import musicbrainzngs
    import musicbrainzngs_parser
    MUSICBRAINZNGS_AVAILABLE = True
except ImportError:
    logger.warn('Cannot import dependency for plugin cd.', exc_info=True)
    MUSICBRAINZNGS_AVAILABLE = False


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


class CDPlaylist(playlist.Playlist):
    def __init__(self, name=_("Audio Disc"), device=None):
        playlist.Playlist.__init__(self, name=name)

        if not device:
            self.__device = "/dev/cdrom"
        else:
            self.__device = device

        self.__read_disc_index()

    # TODO make this threaded later!
    #@common.threaded
    def __read_disc_index(self):
        self.__read_disc_index_internal(self.__device)
        event.log_event('cd_info_retrieved', self, True)

    def __read_disc_index_internal(self, device):
        """
            priority (corresponds with expected data quality):
            1. LibdiscID+Musicbrainzngs: Requires internet connection
            2. LibdiscID+parsing
            3. linux_cd_parser: Parse from CD TOC (linux only)
        """
        
        # TODO: Add more providers?
        # Discogs:
        # * https://github.com/discogs/discogs_client
        # * https://www.discogs.com/developers/
        # CDDB/freedb:
        # * old python code: http://pycddb.sourceforge.net/
        # * even older python code: http://cddb-py.sourceforge.net/
        # * http://ftp.freedb.org/pub/freedb/latest/DBFORMAT
        # * http://ftp.freedb.org/pub/freedb/latest/CDDBPROTO
        # * Servers: http://freedb.freedb.org/, 

        if DISCID_AVAILABLE:
            try:
                disc_id = discid_parser.read_disc_id(device)
                logger.debug('Successfully read CD using discid with %i tracks. '
                             'Musicbrainz id: %s',
                             len(disc_id.tracks), disc_id.id)
                
                if MUSICBRAINZNGS_AVAILABLE: # TODO add setting to let user choose whether he wants internet connections
                    try:
                        result = musicbrainzngs_parser.fetch_with_disc_id(disc_id, device)
                        if result is not None:
                            (tracks, title) = result
                            self.extend(tracks)
                            print(title)  # TODO: set as playlist title, panel title?
                            return # TODO commented out for debugging purposes
                    except musicbrainzngs.WebServiceError as web_error:
                        # This is expected to fail if user is offline or behind an
                        # aggressive firewall.
                        logger.info('Failed to fetch data from musicbrainz database.', exc_info=True)
                    except:
                        logger.warn('Failed to parse data from musicbrainz database.', exc_info=True)
                
                tracks = discid_parser.parse_disc(disc_id, device)
                self.extend(tracks)
                return # TODO commented out for debugging purposes
            except:
                logger.warn('Failed to fetch data from cd using discid.', exc_info=True)
        
        if sys.platform.startswith('linux'):
            try:
                tracks = linux_cd_parser.read_cd_index(device)
                self.extend(tracks)
            except:
                logger.warn('Failed to read metadata from CD.', exc_info=True)


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
