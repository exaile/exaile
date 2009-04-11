# Copyright (C) 2009 Abhishek Mukherjee
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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
"""
Simple test case for MPRIS. Make sure you set the global variable FILE with an
absolute path to a valid playable, local music piece before running this test

@warning: DO not run this with an old unpatched Notifications plugin enabled.
Your Galago daemon will get DoS'd. It is normal for your songs to randomly
start over and over
"""
import unittest
import dbus
import os
import time

OBJECT_NAME = 'org.mpris.exaile'
INTERFACE = 'org.freedesktop.MediaPlayer'
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    os.path.pardir, os.path.pardir,
                    'tests', 'data', 'music', 'delerium', 'chimera',
                    '05 - Truly.mp3')
assert os.path.isfile(FILE), FILE + " must be a valid musical piece"
FILE = "file://" + FILE
print "Test file will be: " + FILE

class TestExaileMpris(unittest.TestCase):

    """
        Tests Exaile MPRIS plugin
    """

    def setUp(self):
        """
            Simple setUp that makes dbus connections and assigns them to
            self.player, self.track_list, and self.root. Also begins playing
            a song so every test case can assume that a song is playing
        """
        bus = dbus.SessionBus()
        objects = {'root': '/',
                   'player': '/Player',
                   'track_list': '/TrackList',
                   }
        intfs = {}
        for key in objects:
            object = bus.get_object(OBJECT_NAME, objects[key])
            intfs[key] = dbus.Interface(object, INTERFACE)
        self.root = intfs['root']
        self.player = intfs['player']
        self.track_list = intfs['track_list']
        self.player.Play()
        time.sleep(0.5)

    def __wait_after(function):
        """
            Decorator to add a delay after a function call
        """
        def inner(*args, **kwargs):
            function(*args, **kwargs)
            time.sleep(0.5)
        return inner

    @__wait_after
    def _stop(self):
        """
            Stops playing w/ delay
        """
        self.player.Stop()

    @__wait_after
    def _play(self):
        """
            Starts playing w/ delay
        """
        self.player.Play()

    @__wait_after
    def _pause(self):
        """
            Pauses playing w/ delay
        """
        self.player.Pause()


class TestMprisRoot(TestExaileMpris):

    """
        Check / (Root) object functions for MPRIS. Does not check Quit
    """

    def testIdentity(self):
        """
            Make sure we output Exaile with our identity
        """
        id = self.root.Identity()
        self.assertEqual(id, self.root.Identity())
        self.assertTrue(id.startswith("Exaile"))

    def testMprisVersion(self):
        """
            Checks that we are using MPRIS version 1.0
        """
        version = self.root.MprisVersion()
        self.assertEqual(dbus.UInt16(1), version[0])
        self.assertEqual(dbus.UInt16(0), version[1])

class TestTrackList(TestExaileMpris):

    """
        Tests the /TrackList object for MPRIS
    """

    def testGetMetadata(self):
        """
            Make sure we can get metadata. Also makes sure that locations will
            not change randomly
        """
        md = self.track_list.GetMetadata(0)
        md_2 = self.track_list.GetMetadata(0)
        self.assertEqual(md, md_2)

    def testAppendDelWithoutPlay(self):
        """
            Tests appending and deleting songs from the playlist without
            playing them
        """
        cur_track = self.track_list.GetCurrentTrack()
        len = self.track_list.GetLength()

        self.assertEqual(0, self.track_list.AddTrack(FILE, False))
        self.assertEqual(len + 1, self.track_list.GetLength())
        self.assertEqual(cur_track, self.track_list.GetCurrentTrack())

        md = self.track_list.GetMetadata(len)
        self.assertEqual(FILE, md['location'])

        self.track_list.DelTrack(len)
        self.assertEqual(len, self.track_list.GetLength())
        self.assertEqual(cur_track, self.track_list.GetCurrentTrack())

    def testAppendDelWithPlay(self):
        """
            Tests appending songs into the playlist with playing the songs
        """
        cur_track = self.track_list.GetCurrentTrack()
        cur_md = self.track_list.GetMetadata(cur_track)
        len = self.track_list.GetLength()

        self.assertEqual(0, self.track_list.AddTrack(FILE, True))
        self.assertEqual(len + 1, self.track_list.GetLength())

        md = self.track_list.GetMetadata(len)
        self.assertEqual(FILE, md['location'])
        self.assertEqual(len, self.track_list.GetCurrentTrack())

        self.track_list.DelTrack(len)
        self.assertEqual(len, self.track_list.GetLength())

        self.track_list.AddTrack(cur_md['location'], True)

    def testGetCurrentTrack(self):
        """
            Check the GetCurrentTrack information
        """
        cur_track = self.track_list.GetCurrentTrack()
        self.assertTrue(cur_track >= 0, "Tests start with playing music")

        self._stop()
        self.assertEqual(dbus.Int32(-1), self.track_list.GetCurrentTrack(),
                    "Our implementation returns -1 if no tracks are playing")

        self._play()
        self.assertEqual(cur_track, self.track_list.GetCurrentTrack(),
                "After a stop and play, we should be at the same track")

    def __test_bools(self, getter, setter):
        """
            Generic function for checking that a boolean value changes
        """
        cur_val = getter()
        if cur_val == dbus.Int32(0):
            val = False
        elif cur_val == dbus.Int32(1):
            val = True
        else:
            self.fail("Got an invalid value from status")

        setter(False)
        status = getter()
        self.assertEqual(dbus.Int32(0), status)

        setter(True)
        status = getter()
        self.assertEqual(dbus.Int32(1), status)

        setter(val)
        self.track_list.SetLoop(val)

    def testLoop(self):
        """
            Tests that you can change the loop settings
        """
        self.__test_bools(lambda: self.player.GetStatus()[3],
                        lambda x: self.track_list.SetLoop(x))

    def testRandom(self):
        """
            Tests that you can change the random settings
        """
        self.__test_bools(lambda: self.player.GetStatus()[1],
                        lambda x: self.track_list.SetRandom(x))

class TestPlayer(TestExaileMpris):

    """
        Tests the /Player object for MPRIS
    """

    def testNextPrev(self):
        """
            Make sure you can skip back and forward
        """
        cur_track = self.track_list.GetCurrentTrack()
        self.player.Next()
        new_track = self.track_list.GetCurrentTrack()
        self.assertNotEqual(cur_track, new_track)
        self.player.Prev()
        self.assertEqual(cur_track, self.track_list.GetCurrentTrack())

    def testStopPlayPause(self):
        """
            Make sure play, pause, and stop behaive as designed
        """
        self._stop()
        self.assertEqual(dbus.Int32(2), self.player.GetStatus()[0])

        self._play()
        self.assertEqual(dbus.Int32(0), self.player.GetStatus()[0])
        self._play()
        self.assertEqual(dbus.Int32(0), self.player.GetStatus()[0])
        
        self._pause()
        self.assertEqual(dbus.Int32(1), self.player.GetStatus()[0])
        self._pause()
        self.assertEqual(dbus.Int32(0), self.player.GetStatus()[0])

        self._stop()
        self.assertEqual(dbus.Int32(2), self.player.GetStatus()[0])
        self._pause()
        self.assertEqual(dbus.Int32(2), self.player.GetStatus()[0])

    def testVolume(self):
        """
            Test to make sure volumes are set happily
        """
        vol = self.player.VolumeGet()
        self.player.VolumeSet(1 - vol)
        self.assertEqual(1 - vol, self.player.VolumeGet())
        self.player.VolumeSet(vol)
        self.assertEqual(vol, self.player.VolumeGet())

    def testPosition(self):
        """
            Test the PositionGet and PositionSet functions. Unfortuantely this
            is very time sensitive and thus has about a 10 second sleep in the
            function
        """
        time.sleep(3)
        self._pause()

        pos = self.player.PositionGet()
        time.sleep(1)
        self.assertEqual(pos, self.player.PositionGet(),
                "Position shouldn't move while paused")

        self._pause()
        time.sleep(4)
        last_pos = self.player.PositionGet()
        self.assertTrue(pos < last_pos,
                "Position shouldn't advance while paused: %d >= %d" %
                    (pos, last_pos))

        self.player.PositionSet(pos)
        time.sleep(2)
        self._pause()
        mid_pos = self.player.PositionGet(),
        self.assertTrue(mid_pos[0] < last_pos,
                "Resetting to position %d, %d should be between that at %d"
                         % (pos, mid_pos[0], last_pos))

        self._pause()
        time.sleep(0.5)
        self.assertTrue(pos < self.player.PositionGet(),
                "Make sure it still advances")

        self.player.PositionSet(-1)
        self.assertTrue(pos < self.player.PositionGet(),
                "Don't move to invalid position")
        

def suite():
    sub_test = [TestMprisRoot, TestTrackList]

    suites = []

    for test in sub_test:
        suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(test))

    return unittest.TestSuite(suites)

if __name__ == "__main__":
    unittest.main()

