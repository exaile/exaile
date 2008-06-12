# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xl import playlist, settings, track, common

try:
    import DiscID, CDDB
    CDDB_AVAIL=True
except:
    CDDB_AVAIL=False

class NoCddbError(Exception):
    pass

class CDPlaylist(playlist.Playlist):
    def __init__(self, name="Audio CD", device=None):
        playlist.Playlist.__init__(self, name=name)

        if not device:
            self.device = "/dev/cdrom"
        else:
            self.device = device

        if not CDDB_AVAIL:
            raise NoCddbError

        self.open_disc()

    def open_disc(self):
        disc = DiscID.open(self.device)
        try:
            self.info = info = DiscID.disc_id(disc)
        except:
            return False

        songs = {}
        minus = 0; total = 0

        for i in range(info[1]):
            length = ( info[i + 3] / 75 ) - minus
            if i + 1 == info[1]:
                length = info[i + 3] - total
            minus = info[i + 3] / 75
            tracknum = i + 1
            song = track.Track()
            song.set_loc("cdda://%d#%s" % (tracknum, self.device))
            song['title'] = "Track %d" % tracknum
            song['tracknumber'] = tracknum
            song['length'] = length
            total += length
            songs[song.get_loc()] = song

        sort_tups = [ (int(s['tracknumber']),s) for s in songs.values() ]
        sort_tups.sort()

        sorted = [ s[1] for s in sort_tups ]

        self.add_tracks(sorted)

        self.get_cddb_info()
    
    @common.threaded
    def get_cddb_info(self):
        try:
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



# vim: et sts=4 sw=4

