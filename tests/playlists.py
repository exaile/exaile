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
from tests.base import BaseTestCase
from xl import playlist
import time, hashlib

class BasePlaylistTestCase(BaseTestCase):
    """
        stub
    """
    pass

class SmartPlaylistTestCase(BasePlaylistTestCase):
    def setUp(self):
        BasePlaylistTestCase.setUp(self)

        self.sp_loc = ".testtemp/sp_exaile%s.playlist" % \
            hashlib.md5(str(time.time())).hexdigest()
        self.sp = playlist.SmartPlaylist(collection=self.collection)
        self.sp.add_param("artist", "=", "TestArtist")
        self.sp.add_param("album", "!=", "First")

    def testSearch(self, sp=None):
        if not sp: sp = self.sp

        p = sp.get_playlist()
        tracks = p.get_tracks()

        for i, track in enumerate(tracks):
            assert i+1 == track.get_track(), \
                "SmartPlaylist search failed"

    def testSaveLoad(self):
        self.sp.set_or_match(True)
        self.sp.save_to_location(self.sp_loc)

        # test playlist
        sp = playlist.SmartPlaylist(collection=self.collection)
        sp.load_from_location(self.sp_loc)

        assert sp.get_or_match() == True, "Loading saved smart playlist failed"
        sp.set_or_match(False)

        self.testSearch(sp)
        self.sp.set_or_match(False)

    def testReturnLimit(self):
        sp = playlist.SmartPlaylist(collection=self.collection)
        sp.set_return_limit(2)

        p = sp.get_playlist()

        assert len(p) == 2, "Return limit test failed"

    def testRandomSort(self):
        sp = playlist.SmartPlaylist(collection=self.collection)
        sp.set_random_sort(True)

        check = False
        p = sp.get_playlist()

        start = p.get_tracks()

        # if it's not different in 50 iterations, something *has* to be wrong
        for i in range(50):
            p = sp.get_playlist()
            if start != p.get_tracks():
                check = True
                break

        assert check == True, "Random sort did not work in 50 iterations"
