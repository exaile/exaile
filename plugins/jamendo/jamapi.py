# Copyright (C) 2009-2010 Erin Drummond
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

import json
from . import jamtree
import threading

from xl import common

USER_AGENT = None


def set_user_agent(s):
    global USER_AGENT
    USER_AGENT = s


def get_json(url):
    return json.loads(common.get_url_contents(url, USER_AGENT))


# Gets a list of jamtree.Artist objects matching the specified criteria
class get_artist_list(threading.Thread):
    def __init__(self, search_term, order_by, num_results, callback):
        threading.Thread.__init__(self)
        self.search_term = search_term
        self.order_by = order_by
        self.num_results = num_results
        self.callback = callback

    def run(self):
        url = (
            "http://api.jamendo.com/get2/name+id/artist/json/?searchquery=%s&order=%s&n=%s"
            % (self.search_term, self.order_by, self.num_results)
        )
        # print('get_artist_list: %s' % url)
        results = get_json(url)
        artists = []
        for result in results:
            item = jamtree.Artist(result['id'], result['name'].strip())
            artists.append(item)
        if artists == []:
            artists = None

        self.callback(artists)


# Gets a list of jamtree.Album objects matching the specified criteria


class get_album_list(threading.Thread):
    def __init__(self, search_term, order_by, num_results, callback):
        threading.Thread.__init__(self)
        self.search_term = search_term
        self.order_by = order_by
        self.num_results = num_results
        self.callback = callback

    def run(self):
        url = (
            "http://api.jamendo.com/get2/name+id/album/json/?searchquery=%s&order=%s&n=%s"
            % (self.search_term, self.order_by, self.num_results)
        )
        results = get_json(url)
        albums = []
        for result in results:
            ar = jamtree.Album(result['id'], result['name'].strip())
            albums.append(ar)

        if albums == []:
            albums = None

        self.callback(albums)


# Gets a list of jamtree.Artist objects matching the specified criteria


class get_artist_list_by_genre(threading.Thread):
    def __init__(self, search_term, order_by, num_results, callback):
        threading.Thread.__init__(self)
        self.search_term = search_term
        self.order_by = order_by
        self.num_results = num_results
        self.callback = callback

    def run(self):
        url = (
            "http://api.jamendo.com/get2/name+id/artist/json/?tag_idstr=%s&order=%s&n=%s"
            % (self.search_term, self.order_by, self.num_results)
        )
        results = get_json(url)
        artists = []
        for result in results:
            item = jamtree.Artist(result['id'], result['name'].strip())
            artists.append(item)
        if artists == []:
            artists = None

        self.callback(artists)


# Gets a list of jamtree.Track objects matching the specified criteria


class get_track_list(threading.Thread):
    def __init__(self, search_term, order_by, num_results, callback):
        threading.Thread.__init__(self)
        self.search_term = search_term
        self.order_by = order_by
        self.num_results = num_results
        self.callback = callback

    def run(self):
        url = (
            "http://api.jamendo.com/get2/id+name+stream+album_id+album_name/"
            "track/json/?searchquery=%s&order=%s&n=%s&streamencoding=ogg2"
            % (self.search_term, self.order_by, self.num_results)
        )
        # print('get_track_list: %s' % url)
        tracks = get_json(url)
        track_list = []
        for track in tracks:
            item = jamtree.Track(track['id'], track['name'].strip(), track['stream'])
            item.album_name = track['album_name']
            track_list.append(item)
        if track_list == []:
            track_list = None

        self.callback(track_list)


# Gets a list of jamtree.Album objects for the specified jamtree.Artist
class get_albums(threading.Thread):
    def __init__(self, artist, callback, add_to_playlist=False):
        threading.Thread.__init__(self)
        self._artist = artist
        self._callback = callback
        self._add_to_playlist = add_to_playlist

    def run(self):
        url = (
            "http://api.jamendo.com/get2/id+name/album/json/?artist_id=%s"
            % self._artist.id
        )
        # print('get_albums: %s' % url)
        albumresults = get_json(url)
        for albumresult in albumresults:
            item = jamtree.Album(albumresult['id'], albumresult['name'].strip())
            self._artist.add_album(item)

        self._callback(self._artist, self._add_to_playlist)


# Gets a list of jamtree.Track objects for the specified jamtree.Album
class get_tracks(threading.Thread):
    def __init__(self, album, callback, add_to_playlist=False):
        threading.Thread.__init__(self)
        self._album = album
        self._callback = callback
        self._add_to_playlist = add_to_playlist

    def run(self):
        url = (
            "http://api.jamendo.com/get2/id+name+stream/track/json/?album_id=%s&streamencoding=ogg2"
            % self._album.id
        )
        # print('get_tracks: %s' % url)
        tracks = get_json(url)
        for track in tracks:
            item = jamtree.Track(track['id'], track['name'].strip(), track['stream'])
            self._album.add_track(item)
        self._callback(self._album, self._add_to_playlist)


# Gets the URL for an album image based on a track id


def get_album_image_url_from_track(track_id):
    url = (
        "http://api.jamendo.com/get2/album_image/track/json/?id=%s&album_imagesize=400"
        % track_id
    )
    imageurl = get_json(url)
    return "".join(imageurl)
