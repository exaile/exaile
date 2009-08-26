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
from tests.gui import base
from xl import playlist
import time, gtk

class GUIMainTestCase(base.BaseTestCase):
    def setUp(self):
        base.BaseTestCase.setUp(self)

    def testDefaultSizeAndPos(self):
        window = self.gui.main.window
        (x, y) = window.get_position()
        (width, height) = window.get_size()

        assert x == y == 10, "Default position is incorrect, %d" % x
        assert height == 475, "Default height is incorrect"
        assert width >= 660  and width < 750, "Default width is incorrect"


    def testPlaylistNotebook(self):
        # creates a playlist, adds some tracks to it, and adds it to the
        # playlist notebook

        pl = playlist.Playlist(name='Funky Playlist')
        pl.add_tracks(self.collection.search('Delerium'))

        self.gui.main.add_playlist(pl)

        nb = self.gui.main.playlist_notebook
        num = nb.get_current_page()
        page = nb.get_nth_page(num)
        tab = nb.get_tab_label(page)

        # make sure the tab name was set correctly
        assert tab.title == 'Funky Playlist', "Tab label incorrect"

    def testStartStopPlayback(self):

        # set up the notebook
        self.testPlaylistNotebook()

        pl = self.gui.main.get_selected_playlist()
        selection = pl.list.get_selection()

        # select the second track in the list
        selection.select_path((1,))
        main = self.gui.main

        main.stop_button.emit('clicked')
        main.play_button.emit('clicked') # start playback
        main.play_button.emit('clicked') # pause playback

    def testPlaybackSignals(self):
        self.testStartStopPlayback()

        main = self.gui.main

        # make sure the labels reflect the currently playing track
        assert main.track_title_label.get_label() == 'Truly', \
            "Title label is not set correctly"
        assert main.track_info_label.get_label().find('Delerium') > -1, \
            "Info label is not set correctly"

        # make sure the play_button's image is set to pause
        stock = main.play_button.get_image().get_stock()
        assert stock[0] == 'gtk-media-play', "Play button image not set " \
            "correctly"

        main.play_button.emit('clicked')
        stock = main.play_button.get_image().get_stock()
        assert stock[0] == 'gtk-media-pause', "Play button did not set " \
            "pause image correctly"

        # stop playback
        main.stop_button.emit('clicked')

        assert main.track_title_label.get_label() == "Not Playing", \
            "Stop signal did not emit correctly"

    def testCoverBox(self):
        self.testStartStopPlayback()
        cover = self.gui.main.cover

        assert cover.image.loc.find('somesweet') > -1, \
            "Cover did not set on playback event, got %s instead" % \
            cover.image.loc
