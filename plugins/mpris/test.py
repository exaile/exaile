import unittest
import dbus
import os
import time

OBJECT_NAME = 'org.mpris.exaile'
INTERFACE = 'org.freedesktop.MediaPlayer'
FILE = os.path.expanduser(os.path.join("~", "Desktop",
                                    "01 Seven Nation Army.mp3"))
assert os.path.isfile(FILE)
FILE = "file://" + FILE
print "Test file will be: " + FILE

class TestExaileMpris(unittest.TestCase):

    def setUp(self):
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
        def inner(*args, **kwargs):
            function(*args, **kwargs)
            time.sleep(0.5)
        return inner

    @__wait_after
    def _stop(self):
        self.player.Stop()

    @__wait_after
    def _play(self):
        self.player.Play()

    @__wait_after
    def _pause(self):
        self.player.Pause()


class TestMprisRoot(TestExaileMpris):
    def testIdentity(self):
        id = self.root.Identity()
        self.assertEqual(id, self.root.Identity())
        self.assertTrue(id.startswith("Exaile"))

    def testMprisVersion(self):
        version = self.root.MprisVersion()
        self.assertEqual(dbus.UInt16(1), version[0])
        self.assertEqual(dbus.UInt16(0), version[1])

class TestTrackList(TestExaileMpris):
    def testGetMetadata(self):
        md = self.track_list.GetMetadata(0)
        md_2 = self.track_list.GetMetadata(0)
        self.assertEqual(md, md_2)

    def testAppendDelWithoutPlay(self):
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
        cur_track = self.track_list.GetCurrentTrack()
        self.assertTrue(cur_track >= 0, "Tests start with playing music")

        self._stop()
        self.assertEqual(dbus.Int32(-1), self.track_list.GetCurrentTrack(),
                    "Our implementation returns -1 if no tracks are playing")

        self._play()
        self.assertEqual(cur_track, self.track_list.GetCurrentTrack(),
                "After a stop and play, we should be at the same track")

    def __test_bools(self, getter, setter):
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
        self.__test_bools(lambda: self.player.GetStatus()[3],
                        lambda x: self.track_list.SetLoop(x))

    def testRandom(self):
        self.__test_bools(lambda: self.player.GetStatus()[1],
                        lambda x: self.track_list.SetRandom(x))

class TestPlayer(TestExaileMpris):
    def testNextPrev(self):
        cur_track = self.track_list.GetCurrentTrack()
        self.player.Next()
        new_track = self.track_list.GetCurrentTrack()
        self.assertNotEqual(cur_track, new_track)
        self.player.Prev()
        self.assertEqual(cur_track, self.track_list.GetCurrentTrack())

    def testStopPlayPause(self):
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
        vol = self.player.VolumeGet()
        self.player.VolumeSet(1 - vol)
        self.assertEqual(1 - vol, self.player.VolumeGet())
        self.player.VolumeSet(vol)
        self.assertEqual(vol, self.player.VolumeGet())

    def testPosition(self):
        self._pause()
        time.sleep(1)

        pos = self.player.PositionGet()
        time.sleep(0.5)
        self.assertEqual(pos, self.player.PositionGet(),
                "Position shouldn't move while paused")

        self._pause()
        time.sleep(1)
        new_pos = self.player.PositionGet()
        self.assertTrue(pos < new_pos,
                "Position shouldn't advance while paused: %d >= %d" %
                    (pos, new_pos))

        self._pause()
        self.player.PositionSet(pos)
        self.assertEqual(pos, self.player.PositionGet(),
                "Set position back to start")

        self._pause()
        time.sleep(0.5)
        self.assertTrue(pos < self.player.PositionGet(),
                "Make sure it still advances")

        self.player.PositionSet(-1)
        self.assertEqual(pos, self.player.PositionGet(),
                "Don't move to invalid position")
        

def suite():
    sub_test = [TestMprisRoot, TestTrackList]

    suites = []

    for test in sub_test:
        suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(test))

    return unittest.TestSuite(suites)

if __name__ == "__main__":
    unittest.main()

