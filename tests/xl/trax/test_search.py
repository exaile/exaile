from mox3 import mox
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
        self.strack = get_search_result_track()
        self.strack.track.set_tag_raw('artist', [u'foo', u'bar'])

    def tearDown(self):
        clear_all_tracks()
        self.mox.UnsetStubs()

    def test_match_list_true(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(mox.IsA(basestring)).AndReturn(True)
        self.mox.ReplayAll()
        matcher = search._Matcher('artist', u'bar', lambda x: x)
        self.assertTrue(matcher.match(self.strack))
        self.mox.VerifyAll()

    def test_match_list_false(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        # ensure that both tags are checked
        search._Matcher._matches(mox.IsA(basestring)).AndReturn(False)
        search._Matcher._matches(mox.IsA(basestring)).AndReturn(False)
        self.mox.ReplayAll()
        matcher = search._Matcher('artist', u'bar', lambda x: x)
        self.assertFalse(matcher.match(self.strack))
        self.mox.VerifyAll()

    def test_match_list_none(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(None).AndReturn(True)
        self.mox.ReplayAll()
        matcher = search._Matcher('album', None, lambda x: x)
        self.assertTrue(matcher.match(self.strack))
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


class TestMultiMetaMatcher(TestMetaMatcherClasses):

    def test_true(self):
        matcher = [self._Matcher(True)] * 10
        matcher = search._MultiMetaMatcher(matcher)
        self.assertTrue(matcher.match('foo'))

    def test_false(self):
        matcher = [self._Matcher(True)] * 10 + [self._Matcher(False)]
        matcher = search._MultiMetaMatcher(matcher)
        self.assertFalse(matcher.match('foo'))


class TestManyMultiMetaMatcher(TestMetaMatcherClasses):

    def test_true(self):
        matcher = [self._Matcher(True)] * 10 + [self._Matcher(False)]
        for match in matcher:
            match.tag = 'artist'
        matcher = search._ManyMultiMetaMatcher(matcher)
        self.assertTrue(matcher.match('foo'))

    def test_false(self):
        matcher = [self._Matcher(False)] * 10
        for match in matcher:
            match.tag = 'artist'
        matcher = search._ManyMultiMetaMatcher(matcher)
        self.assertFalse(matcher.match('foo'))


class TestTracksMatcher(unittest.TestCase):

    def setUp(self):
        self.str = get_search_result_track()

    def test_in_matcher(self):
        matcher = search.TracksMatcher("artist=foo")
        self.assertEqual(len(matcher.matchers), 1)
        match = matcher.matchers[0]
        self.match_is_type(match, search._InMatcher)
        self.assertEqual(match.tag, 'artist')
        self.assertEqual(match.content, 'foo')

    def test_exact_matcher(self):
        matcher = search.TracksMatcher("artist==foo")
        self.assertEqual(len(matcher.matchers), 1)
        match = matcher.matchers[0]
        self.match_is_type(match, search._ExactMatcher)
        self.assertEqual(match.tag, 'artist')
        self.assertEqual(match.content, 'foo')

    def match_is_type(self, match, expected):
        self.assertTrue(isinstance(match, expected), match)

    def test_not_matcher(self):
        matcher = search.TracksMatcher("! foo", keyword_tags=['artist'])
        match = matcher
        # NotMetaMatcher
        self.assertEqual(len(match.matchers), 1)
        match = matcher.matchers[0]
        self.match_is_type(match, search._NotMetaMatcher)
        # MultiMetaMatcher
        match = match.matcher
        self.match_is_type(match, search._MultiMetaMatcher)
        # ManyMultiMetaMatcher
        self.assertEqual(len(match.matchers), 1)
        match = match.matchers[0]
        self.match_is_type(match, search._ManyMultiMetaMatcher)
        # InMatcher
        self.assertEqual(len(match.matchers), 1)
        match = match.matchers[0]
        self.match_is_type(match, search._InMatcher)
        self.assertEqual(match.tag, 'artist')
        self.assertEqual(match.content, 'foo')

    def test_or_matcher(self):
        matcher = search.TracksMatcher("foo | bar", keyword_tags=['artist'])
        match = matcher
        # OrMetaMatcher
        self.assertEqual(len(match.matchers), 1)
        match = matcher.matchers[0]
        self.match_is_type(match, search._OrMetaMatcher)
        # MultiMetaMatcher
        self.assertTrue(match.left)
        self.assertTrue(match.right)
        self.match_is_type(match.left, search._MultiMetaMatcher)
        self.match_is_type(match.right, search._MultiMetaMatcher)
        # ManyMultiMetaMatcher
        self.assertEqual(len(match.left.matchers), 1)
        self.assertEqual(len(match.right.matchers), 1)
        match_left = match.left.matchers[0]
        match_right = match.right.matchers[0]
        self.match_is_type(match_left, search._ManyMultiMetaMatcher)
        self.match_is_type(match_right, search._ManyMultiMetaMatcher)
        # InMatcher
        self.assertEqual(len(match_left.matchers), 1)
        self.assertEqual(len(match_right.matchers), 1)
        match_left = match_left.matchers[0]
        match_right = match_right.matchers[0]
        self.match_is_type(match_left, search._InMatcher)
        self.match_is_type(match_right, search._InMatcher)
        self.assertEqual(match_left.tag, 'artist')
        self.assertEqual(match_right.tag, 'artist')
        if match_left.content == 'foo':
            if match_right.content != 'bar':
                self.assertFalse("We lost a search term on an or")
        elif match_left.content == 'bar':
            if match_right.content != 'foo':
                self.assertFalse("We lost a search term on an or")
        else:
            self.assertFalse("We lost both parts of an or")

    def test_paren_matcher(self):
        matcher = search.TracksMatcher("( foo | bar )",
                keyword_tags=['artist'])
        match = matcher
        # MultiMetaMatcher
        self.assertEqual(len(match.matchers), 1)
        match = matcher.matchers[0]
        self.match_is_type(match, search._MultiMetaMatcher)

        self.assertEqual(len(match.matchers), 1)
        match = match.matchers[0]
        self.match_is_type(match, search._OrMetaMatcher)

        # This is the same code as the OrMetaMatcher
        self.assertTrue(match.left)
        self.assertTrue(match.right)
        self.match_is_type(match.left, search._MultiMetaMatcher)
        self.match_is_type(match.right, search._MultiMetaMatcher)
        # ManyMultiMetaMatcher
        self.assertEqual(len(match.left.matchers), 1)
        self.assertEqual(len(match.right.matchers), 1)
        match_left = match.left.matchers[0]
        match_right = match.right.matchers[0]
        self.match_is_type(match_left, search._ManyMultiMetaMatcher)
        self.match_is_type(match_right, search._ManyMultiMetaMatcher)
        # InMatcher
        self.assertEqual(len(match_left.matchers), 1)
        self.assertEqual(len(match_right.matchers), 1)
        match_left = match_left.matchers[0]
        match_right = match_right.matchers[0]
        self.match_is_type(match_left, search._InMatcher)
        self.match_is_type(match_right, search._InMatcher)
        self.assertEqual(match_left.tag, 'artist')
        self.assertEqual(match_right.tag, 'artist')
        if match_left.content == 'foo':
            if match_right.content != 'bar':
                self.assertFalse("We lost a search term on an or")
        elif match_left.content == 'bar':
            if match_right.content != 'foo':
                self.assertFalse("We lost a search term on an or")
        else:
            self.assertFalse("We lost both parts of an or")

    def test_match_true(self):
        matcher = search.TracksMatcher("foo",
                keyword_tags=['artist'])
        self.str.track.set_tag_raw('artist', 'foo')
        self.assertTrue(matcher.match(self.str))
        self.assertEqual(self.str.on_tags, ['artist'])

    def test_match_true_tag(self):
        matcher = search.TracksMatcher("artist=foo")
        self.str.track.set_tag_raw('artist', 'foo')
        self.assertTrue(matcher.match(self.str))
        self.assertEqual(self.str.on_tags, ['artist'])

    def test_match_true_case_insensitive(self):
        matcher = search.TracksMatcher("artist=FoO", case_sensitive=False)
        self.str.track.set_tag_raw('artist', 'foo')
        self.assertTrue(matcher.match(self.str))
        self.assertEqual(self.str.on_tags, ['artist'])

    def test_match_true_none(self):
        matcher = search.TracksMatcher("artist==__null__")
        self.str.track.set_tag_raw('artist', '')
        self.assertTrue(matcher.match(self.str))
        self.assertEqual(self.str.on_tags, ['artist'])

    def test_match_false(self):
        matcher = search.TracksMatcher("foo",
                keyword_tags=['artist'])
        self.str.track.set_tag_raw('artist', 'bar')
        self.assertFalse(matcher.match(self.str))

class TestSearchTracks(unittest.TestCase):

    def test_search_tracks(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks = [search.SearchResultTrack(tr) for tr in tracks]
        tracks[0].track.set_tag_raw('artist', 'foooo')
        tracks[2].track.set_tag_raw('artist', 'foooooo')
        gen = search.search_tracks(tracks, [matcher])
        self.assertEqual(gen.next(), tracks[0])
        self.assertEqual(gen.next(), tracks[2])
        self.assertRaises(StopIteration, gen.next)

    def test_take_not_srt(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[0].set_tag_raw('artist', 'foooo')
        tracks[2].set_tag_raw('artist', 'foooooo')
        gen = search.search_tracks(tracks, [matcher])
        self.assertEqual(gen.next().track, tracks[0])
        self.assertEqual(gen.next().track, tracks[2])
        self.assertRaises(StopIteration, gen.next)

    def test_search_tracks_from_string(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[0].set_tag_raw('artist', 'foooo')
        tracks[2].set_tag_raw('artist', 'foooooo')
        gen = search.search_tracks_from_string(tracks, 'foo',
                keyword_tags=['artist'])
        self.assertEqual(gen.next().track, tracks[0])
        self.assertEqual(gen.next().track, tracks[2])
        self.assertRaises(StopIteration, gen.next)
