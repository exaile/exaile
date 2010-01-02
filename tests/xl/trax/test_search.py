import mox
import unittest

from xl.trax import search
from xl.trax import track

def test_search_result_track_get_track():
    val = 'foo'
    search_result_track = search.SearchResultTrack(val)
    assert search_result_track.track == val, search_result_track.track

def get_search_result_track():
    tr = track.Track('file:///foo')
    return search.SearchResultTrack(tr)

def clear_all_tracks():
    for key in track.Track._Track__tracksdict.keys():
        del track.Track._Track__tracksdict[key]

class TestMatcher(unittest.TestCase):

    def setUp(self):
        self.mox = mox.Mox()
        self.str = get_search_result_track()
        self.str.track.set_tag_raw('artist', [u'foo', u'bar'])

    def tearDown(self):
        clear_all_tracks()
        self.mox.UnsetStubs()

    def test_match_list_true(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(mox.IsA(basestring)).AndReturn(True)
        self.mox.ReplayAll()
        matcher = search._Matcher('artist', u'bar', lambda x: x)
        self.assertTrue(matcher.match(self.str))
        self.mox.VerifyAll()

    def test_match_list_false(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(mox.IsA(basestring)).AndReturn(False)
        search._Matcher._matches(mox.IsA(basestring)).AndReturn(False)
        self.mox.ReplayAll()
        matcher = search._Matcher('artist', u'bar', lambda x: x)
        self.assertFalse(matcher.match(self.str))
        self.mox.VerifyAll()

    def test_match_list_none(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(None).AndReturn(True)
        self.mox.ReplayAll()
        matcher = search._Matcher('album', None, lambda x: x)
        self.assertTrue(matcher.match(self.str))
        self.mox.VerifyAll()

    def test_matches(self):
        matcher = search._Matcher('album', None, lambda x: x)
        self.assertRaises(NotImplementedError, matcher._matches, 'foo')

class TestExactMatcher(unittest.TestCase):

    def setUp(self):
        self.str = get_search_result_track()

    def tearDown(self):
        clear_all_tracks()

    def test_exact_matcher_true(self):
        matcher = search._ExactMatcher('album', 'Foo', lambda x: x)
        self.str.track.set_tag_raw('album', 'Foo')
        self.assertTrue(matcher.match(self.str))

    def test_exact_matcher_false(self):
        matcher = search._ExactMatcher('album', 'Foo', lambda x: x)
        self.str.track.set_tag_raw('album', 'FoO')
        self.assertFalse(matcher.match(self.str))

class TestInMatcher(unittest.TestCase):

    def setUp(self):
        self.str = get_search_result_track()

    def tearDown(self):
        clear_all_tracks()

    def test_in_matcher_none(self):
        matcher = search._InMatcher('album', 'Foo', lambda x: x)
        self.str.track.set_tag_raw('album', None)
        self.assertFalse(matcher.match(self.str))

    def test_in_matcher_true(self):
        matcher = search._InMatcher('album', 'hello', lambda x: x)
        self.str.track.set_tag_raw('album', 'Foohelloworld')
        self.assertTrue(matcher.match(self.str))

    def test_in_matcher_error(self):
        matcher = search._InMatcher('album', 2, lambda x: x)
        self.str.track.set_tag_raw('album', 'Foohelloworld')
        self.assertFalse(matcher.match(self.str))

    def test_in_matcher_false(self):
        matcher = search._InMatcher('album', 'hello', lambda x: x)
        self.str.track.set_tag_raw('album', 'Fooheloworld')
        self.assertFalse(matcher.match(self.str))

class TestMetaMatcherClasses(unittest.TestCase):

    class _Matcher(object):

        def __init__(self, val):
            self.val = val

        def matches(self, val):
            return self.val

        def match(self, val):
            return self.val

class TestNotMetaMatcher(TestMetaMatcherClasses):

    def test_true(self):
        matcher = self._Matcher(True)
        matcher = search._NotMetaMatcher(matcher)
        self.assertFalse(matcher.match('foo'))

    def test_false(self):
        matcher = self._Matcher(False)
        matcher = search._NotMetaMatcher(matcher)
        self.assertTrue(matcher.match('foo'))

class TestOrMetaMatcher(TestMetaMatcherClasses):

    def test_true_true(self):
        matcher_1 = self._Matcher(True)
        matcher_2 = self._Matcher(True)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        self.assertTrue(matcher.match('foo'))

    def test_true_false(self):
        matcher_1 = self._Matcher(True)
        matcher_2 = self._Matcher(False)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        self.assertTrue(matcher.match('foo'))

    def test_false_true(self):
        matcher_1 = self._Matcher(False)
        matcher_2 = self._Matcher(True)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        self.assertTrue(matcher.match('foo'))

    def test_false_false(self):
        matcher_1 = self._Matcher(False)
        matcher_2 = self._Matcher(False)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        self.assertFalse(matcher.match('foo'))

class TestAnyMetaMatcher(TestMetaMatcherClasses):

    def test_true(self):
        matcher = [self._Matcher(True)] * 10
        matcher = search._MultiMetaMatcher(matcher)
        self.assertTrue(matcher.match('foo'))

    def test_false(self):
        matcher = [self._Matcher(True)] * 10 + [self._Matcher(False)]
        matcher = search._MultiMetaMatcher(matcher)
        self.assertFalse(matcher.match('foo'))

