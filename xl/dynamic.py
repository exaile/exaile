# Copyright (C) 2008-2009 Adam Olsen 
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
from xl import xdg, common, event, providers, settings, metadata
import logging, os, random, time

logger = logging.getLogger(__name__)

class DynamicManager(providers.ProviderHandler):
    """
        handles matching of songs for dynamic playlists
    """
    def __init__(self, collection):
        providers.ProviderHandler.__init__(self, "dynamic_playlists")
        self.buffersize = settings.get_option("playback/dynamic_buffer", 5)
        self.collection = collection
        self.cachedir = os.path.join(xdg.get_cache_dir(), 'dynamic')
        if not os.path.exists(self.cachedir):
            os.makedirs(self.cachedir)

    def find_similar_tracks(self, track, limit=-1, exclude=[]):
        """
            finds tracks from the collection that are similar 
            to the passed track.

            @param track: the track to find similar tracks to
            @param limit: limit the returned list to this many
                tracks. If there are more tracks than this
                found, a random selection of those tracks is
                returned.
        """
        logger.debug(u"Searching for %(limit)s tracks related to %(track)s" % 
                {'limit' : limit, 'track' : track})
        artists = self.find_similar_artists(track)
        if artists == []:
            return []
        tracks = []
        random.shuffle(artists)
        i = 0
        while limit > len(tracks) and  limit > 0 and i < len(artists):
            artist = artists[i][1]
            i += 1
            choices = self.collection.search('artist=="%s"'%artist.lower().replace('"', ''))
            if choices == []:
                continue
            random.shuffle(choices)
            j = 0
            while j < len(choices):
                track = choices[j]
                if track not in exclude:
                    tracks.append(track)
                    break
                j += 1
        return tracks

    def find_similar_artists(self, track):
        info = self._load_saved_info(track)
        if info == []:
            info = self._query_sources(track)
            self._save_info(track, info)

        return info

    def _query_sources(self, track):
        info = []
        if not track['artist']: return info
        for source in self.get_providers():
            sinfo = source.get_results(','.join(track['artist']))
            info += sinfo
        info.sort(reverse=True) #TODO: merge artists that are the same
        return info

    def _load_saved_info(self, track):
        if not track['artist']: return []
        filename = os.path.join(self.cachedir, ','.join(track['artist']))
        if not os.path.exists(filename):
            return []
        f = open(filename)
        line = f.readline()
        if line == '':
            return []
        last_update = float(line)
        if 604800 < time.time() - last_update: # one week
            info = self._query_sources(track)
            if info != []:
                self._save_info(track, info)
                return info
        info = []
        for line in f:
            try:
                rel, artist = line.strip().split(" ",1)
                info.append((rel, artist))
            except:
                pass
        f.close()
        return info

    def _save_info(self, track, info):
        if info == []:
            return
        filename = os.path.join(self.cachedir, metadata.j(track['artist']))
        f = open(filename, 'w')
        f.write("%s\n"%time.time())
        for item in info:
            f.write("%.2f %s\n"%item)
        f.close()

    def populate_playlist(self, playlist):
        """
            adds tracks to playlists as needed.
            called when the position of a playlist changes.
        """
        if not playlist: # or not playlist.is_dynamic():
            return
        current_pos = playlist.get_current_pos()
        if current_pos < 0 or current_pos >= len(playlist):
            return
        needed = self.buffersize - (len(playlist) - current_pos)
        
        if needed < 1:
            needed = 1
        curr = playlist.get_current()
        tracks = self.find_similar_tracks(curr, needed, 
                playlist.get_tracks())

        time.sleep(5)   # wait five seconds before adding to allow for skips
                        # we're searching for new tracks during this time 
                        # anyway so its not wasted 
        if playlist.get_current_pos() != current_pos:
            return # we skipped in that 5 seconds, so ignore it
        playlist.add_tracks(tracks)
        logger.debug("Added %s tracks." % len(tracks))

class DynamicSource(object):
    def __init__(self):
        pass

    def get_results(self, artist):
        raise NotImplementedError

    def _set_manager(self, manager):
        self.manager = manager

# vim: et sts=4 sw=4

