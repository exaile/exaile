import unittest

import mox
import gobject

import xl.trax.track as track

class Test_MetadataCacher(unittest.TestCase):

    TIMEOUT = 2000
    MAX_ENTRIES = 2048

    def setUp(self):
        self.mox = mox.Mox()
        self.mc = track._MetadataCacher(self.TIMEOUT, self.MAX_ENTRIES)

    def test_add(self):
        timeout_id = 1
        self.mox.StubOutWithMock(gobject, 'timeout_add')
        self.mox.StubOutWithMock(gobject, 'source_remove')
        gobject.timeout_add(
                self.TIMEOUT,
                self.mc.remove,
                'foo').AndReturn(timeout_id)

        self.mox.ReplayAll()
        self.mc.add('foo', 'bar')
        self.assertEqual(self.mc.get('foo'), ['bar', 1])
        self.mox.VerifyAll()

    def test_double_add(self):
        timeout_id = 1
        self.mox.StubOutWithMock(gobject, 'timeout_add')
        self.mox.StubOutWithMock(gobject, 'source_remove')
        gobject.timeout_add(
                self.TIMEOUT,
                self.mc.remove,
                'foo').AndReturn(timeout_id)
        gobject.timeout_add(
                self.TIMEOUT,
                self.mc.remove,
                'foo').AndReturn(timeout_id + 1)
        gobject.source_remove(timeout_id)

        self.mox.ReplayAll()
        self.mc.add('foo', 'bar')
        self.assertEqual(self.mc.get('foo'), ['bar', 1])
        self.mc.add('foo', 'bar')
        self.assertEqual(self.mc.get('foo'), ['bar', 2])
        self.mox.VerifyAll()

    def test_remove(self):
        timeout_id = 1
        self.mox.StubOutWithMock(gobject, 'timeout_add')
        gobject.timeout_add(
                self.TIMEOUT,
                self.mc.remove,
                'foo').AndReturn(timeout_id)

        self.mox.ReplayAll()
        self.mc.add('foo', 'bar')
        self.mc.remove('foo')
        self.assertEqual(self.mc.get('foo'), None)
        self.mox.VerifyAll()

    def test_remove_not_exist(self):
        self.assertEqual(self.mc.remove('foo'), None)

    def tearDown(self):
        self.mox.UnsetStubs()
