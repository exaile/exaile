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
import unittest, time
from xl import collection

class CollectionTestCase(BaseTestCase):
    def testCount(self):
        tracks = list(self.collection.search(''))
        assert len(tracks) == 15, "Number of tracks scanned is incorrect"

    def testSaveLoad(self):
        self.collection.save_to_location()

        # test col
        col = collection.Collection("TestCollection2", self.temp_col_loc)
        tracks = list(col.search(''))
        assert len(tracks) == 15, "Number of tracks scanned is incorrect"

        # test libraries
        l = col.get_libraries()
        assert len(l) == 1, "Number of saved libraries is incorrect" + \
                "\n\tExpected: 1    Found: %s" % len(l)
        assert l[0].location == './tests/data', "Saved library is incorrect"

    def testAllFieldSearch(self):
        c = self.collection

        # search for a keyword in all fields
        tracks = list(c.search('Black', sort_fields=('artist', 'album',
            'tracknumber')))
        assert len(tracks) == 1, "Keyword search failed"
        assert tracks[0]['title'][0].find('black') > -1, "Keyword search failed"

    def testNotSearch(self):
        tracks = list(self.collection.search(
            """
                artist=="TestArtist" NOT album="Second"
            """
        ))

        assert len(tracks) == 2, "Not search failed"
