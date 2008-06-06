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
            song['track'] = tracknum
            song['length'] = length
            total += length
            songs[song.get_loc()] = song

        sort_tups = [ (int(s['track']),s) for s in songs.values() ]
        sort_tups.sort()

        sorted = [ s[1] for s in sort_tups ]

        self.add_tracks(sorted)

        self.get_cddb_info()
    
    @common.threaded
    def get_cddb_info(self):
        status, info = CDDB.query(self.info)
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




