import traceback
import os
import oldtrack
from xl import common


def already_added(t, added):
    """
        Checks to see if the title, artist, album and genre
        has already been added to the list of tracks
    """

    if not t.title:
        t.title = ""
    if not t.album:
        t.album = ""
    if not t.artist:
        t.artist = ""
    if not t.genre:
        t.genre = ""

    h = "%s - %s - %s - %s" % (t.title, t.album, t.artist, t.genre)

    if h in added:
        return True
    added[h] = 1
    return False


class TrackData(object):
    """
        Represents a list of tracks
    """

    def __init__(self, tracks=None):
        """
            Initializes the list
        """
        self.total_length = 0
        self.paths = {}
        self._inner = []
        if tracks:
            for track in tracks:
                self.append(track)

    def __getitem__(self, index):
        return self._inner[index]

    def __setitem__(self, index, value):
        old = self._inner[index]
        try:
            del self.paths[old.loc]
        except KeyError:
            pass
        self.paths[value.loc] = value
        self._inner[index] = value

    def __len__(self):
        return len(self._inner)

    def index(self, item):
        return self._inner.index(item)

    def append(self, track):
        """
            Adds a track to the list
        """
        if not track:
            return
        self.paths[track.loc] = track
        self._inner.append(track)
        self.update_total_length(track.get_duration(), appending=True)

    def remove(self, track):
        """
            Removes a track from the list
        """
        if not track:
            return
        try:
            del self.paths[track.loc]
        except KeyError:
            return
        else:
            self._inner.remove(track)
        self.update_total_length(track.get_duration(), appending=False)

    def update_total_length(self, track_duration, appending):
        if appending:
            self.total_length += track_duration
        else:
            self.total_length -= track_duration

    def get_total_length(self):
        """
            Returns length of all tracks in the table as preformatted string
        """
        s = self.total_length
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)

        text = []
        if d:
            text.append(ngettext("%d day", "%d days", d) % d)
        if h:
            text.append(ngettext("%d hour", "%d hours", h) % h)
        if m:
            text.append(ngettext("%d minute", "%d minutes", m) % m)
        if s:
            text.append(ngettext("%d second", "%d seconds", s) % s)

        text = ", ".join(text)

        return text


def load_tracks(db, current=None):
    """
        Loads all tracks currently stored in the database
    """
    global ALBUMS

    items = ('PATHS', 'ARTISTS', 'RADIO', 'PLAYLISTS')
    for item in items:
        globals()[item] = dict()
    ALBUMS = {}
    added = dict()

    tracks = TrackData()
    for row in db.select("""
        SELECT
            paths.name,
            title,
            artists.name,
            albums.name,
            disc_id,
            tracks.genre,
            track,
            length,
            bitrate,
            year,
            modified,
            user_rating,
            rating,
            blacklisted,
            time_added,
            encoding,
            plays
        FROM tracks, paths, artists, albums
        WHERE
            (
                paths.id=tracks.path AND
                artists.id = tracks.artist AND
                albums.id = tracks.album
            ) AND
            blacklisted=0
        ORDER BY
            THE_CUTTER(artists.name),
            LOWER(albums.name),
            disc_id,
            track,
            title
        """):

        t = oldtrack.Track(*row)
        path, ext = os.path.splitext(row[0].lower().encode('utf-8'))
        t.type = "file"

        if already_added(t, added):
            continue

        tracks.append(t)
    cur = db.cursor(new=True)

    for item in items:
        cur.execute("SELECT id, name FROM %s" % item.lower())
        while True:
            try:
                row = cur.fetchone()
                if not row:
                    break
                globals()[item][row[1]] = row[0]
            except:
                common.log_exception()

    cur.execute("SELECT artist, name, id FROM albums")
    while True:
        try:
            row = cur.fetchone()
            if not row:
                break
            ALBUMS["%d - %s" % (row[0], row[1])] = row[2]
        except:
            common.log_exception()

    cur.close()
    db._close_thread()
    return tracks
