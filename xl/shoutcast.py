# Copyright (C) 2006 Adam Olsen 
#
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

import urllib, re, sys, threading, xlmisc
import gobject
try:
    import media
except: pass
PLS = re.compile("<a href=\"(/sbin/shoutcast-playlist\.pls\?rn=\d+&file="
    "filename\.pls)\">.*?<a.*?href=\"[^\"]*\">([^<]*)</a>.*?Now Playing:</font>"
    "([^<]*)</font>.*?size=\"2\" color=\"\#FFFFFF\">(\d+/\d+)</font>.*?"
    "size=\"2\" color=\"#FFFFFF\">(\d+)</font>")

NEXT = re.compile("startat=(\d+)\">\[ Next")

def parse_genre(genre, stations, url=None, func=None):
    """
        Parses a genre for all streams
    """
    if url == None:
        url = "http://www.shoutcast.com/directory/" \
            "index.phtml?sgenre=%s&numresult=500" % urllib.quote(genre)
    h = urllib.urlopen(url)
    data = h.read().replace("\n", " ")
    h.close()
    xlmisc.log('read url %s' % url)

    tup = re.findall(PLS, data)
    for station in tup:
        new = []
        check = True
        # make sure the track information is unicode worthy (I have found that
        # not all are)
        for a in station:
            try:
                new.append(unicode(a))
            except:
                check = False

        if not check: continue
        station = new
        s = dict()
        s['url'] = "http://www.shoutcast.com%s" % station[0]
        s['artist'] = station[1]
        s['title'] = station[2]
        s['bitrate'] = station[4]

        stations.append(s)
        if func:
            gobject.idle_add(func, s)

    if len(stations) >= 100:
        return
    m = NEXT.search(data)
    if m != None:
        # check the next page
        parse_genre(genre, stations,
            "http://www.shoutcast.com/directory/index.phtml" \
            "?startat=%s&genre=%s&numresult=500" % (m.group(1), genre), func)

class ShoutcastThread(threading.Thread):
    """
        A thread that will gather all stations for a genre
    """
    def __init__(self, tracks, genre):
        """
            Expects a RadioTrackList and a genre to search
        """
        threading.Thread.__init__(self)
        self.tracks = tracks
        self.genre = genre
        self.count = 0
        self.add = []

    def run(self):
        """
            Called when the thread is started
        """
        stations = []
        parse_genre(self.genre, stations, None, self.update)
        gobject.idle_add(self.update, None)

        xlmisc.log("%d stations were found." % len(stations))

    def update(self, track):
        """
            Updates the RadioTracksList with found tracks
        """
        if not track:
            if len(self.add):
                songs = self.tracks.songs
                for track in self.add:
                    songs.append(media.RadioTrack(track))
                self.tracks.set_songs(songs)
            self.tracks.exaile.status.set_first(None)
            self.tracks.save(self.genre)
            self.tracks.playlist_songs = self.tracks.songs
        elif self.count <= 60:
            self.tracks.append_song(media.RadioTrack(track))
        else:
            self.add.append(track)

        self.count += 1
