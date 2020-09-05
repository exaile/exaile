# -*- coding: utf-8

from mox3 import mox

from xl.trax import search
from xl.trax import track
import pytest


def test_search_result_track_get_track():
    val = 'foo'
    search_result_track = search.SearchResultTrack(val)
    assert search_result_track.track == val, search_result_track.track


def get_search_result_track():
    tr = track.Track('file:///foo')
    return search.SearchResultTrack(tr)


class TestMatcher:
    def setup(self):
        self.mox = mox.Mox()
        self.strack = get_search_result_track()
        self.strack.track.set_tag_raw('artist', ['foo', 'bar'])

    def teardown(self):
        self.mox.UnsetStubs()

    def test_match_list_true(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(mox.IsA(str)).AndReturn(True)
        self.mox.ReplayAll()
        matcher = search._Matcher('artist', 'bar', lambda x: x)
        assert matcher.match(self.strack)
        self.mox.VerifyAll()

    def test_match_list_false(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        # ensure that both tags are checked
        search._Matcher._matches(mox.IsA(str)).AndReturn(False)
        search._Matcher._matches(mox.IsA(str)).AndReturn(False)
        self.mox.ReplayAll()
        matcher = search._Matcher('artist', 'bar', lambda x: x)
        assert not matcher.match(self.strack)
        self.mox.VerifyAll()

    def test_match_list_none(self):
        self.mox.StubOutWithMock(search._Matcher, '_matches')
        search._Matcher._matches(None).AndReturn(True)
        self.mox.ReplayAll()
        matcher = search._Matcher('album', None, lambda x: x)
        assert matcher.match(self.strack)
        self.mox.VerifyAll()

    def test_matches(self):
        matcher = search._Matcher('album', None, lambda x: x)
        with pytest.raises(NotImplementedError):
            matcher._matches('foo')


class TestExactMatcher:
    def setup(self):
        self.str = get_search_result_track()

    def test_exact_matcher_true(self):
        matcher = search._ExactMatcher('album', 'Foo', lambda x: x)
        self.str.track.set_tag_raw('album', 'Foo')
        assert matcher.match(self.str)

    def test_exact_matcher_false(self):
        matcher = search._ExactMatcher('album', 'Foo', lambda x: x)
        self.str.track.set_tag_raw('album', 'FoO')
        assert not matcher.match(self.str)


class TestInMatcher:
    def setup(self):
        self.str = get_search_result_track()

    def test_in_matcher_none(self):
        matcher = search._InMatcher('album', 'Foo', lambda x: x)
        self.str.track.set_tag_raw('album', None)
        assert not matcher.match(self.str)

    def test_in_matcher_true(self):
        matcher = search._InMatcher('album', 'hello', lambda x: x)
        self.str.track.set_tag_raw('album', 'Foohelloworld')
        assert matcher.match(self.str)

    def test_in_matcher_error(self):
        matcher = search._InMatcher('album', 2, lambda x: x)
        self.str.track.set_tag_raw('album', 'Foohelloworld')
        assert not matcher.match(self.str)

    def test_in_matcher_false(self):
        matcher = search._InMatcher('album', 'hello', lambda x: x)
        self.str.track.set_tag_raw('album', 'Fooheloworld')
        assert not matcher.match(self.str)


class TestGtLtMatchers:
    def setup(self):
        self.str = get_search_result_track()

    def test_gt_bitrate_matcher_true(self):
        matcher = search._GtMatcher('__bitrate', 100000, lambda x: x)
        self.str.track.set_tag_raw('__bitrate', 128000)
        assert matcher.match(self.str)

    def test_gt_bitrate_matcher_false(self):
        matcher = search._GtMatcher('__bitrate', 100000, lambda x: x)
        self.str.track.set_tag_raw('__bitrate', 28000)
        assert not matcher.match(self.str)

    def test_lt_bitrate_matcher_true(self):
        matcher = search._LtMatcher('__bitrate', 100000, lambda x: x)
        self.str.track.set_tag_raw('__bitrate', 28000)
        assert matcher.match(self.str)

    def test_lt_bitrate_matcher_false(self):
        matcher = search._LtMatcher('__bitrate', 100000, lambda x: x)
        self.str.track.set_tag_raw('__bitrate', 128000)
        assert not matcher.match(self.str)


class TestMetaMatcherClasses:
    class _Matcher:
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
        assert not matcher.match('foo')

    def test_false(self):
        matcher = self._Matcher(False)
        matcher = search._NotMetaMatcher(matcher)
        assert matcher.match('foo')


class TestOrMetaMatcher(TestMetaMatcherClasses):
    def test_true_true(self):
        matcher_1 = self._Matcher(True)
        matcher_2 = self._Matcher(True)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        assert matcher.match('foo')

    def test_true_false(self):
        matcher_1 = self._Matcher(True)
        matcher_2 = self._Matcher(False)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        assert matcher.match('foo')

    def test_false_true(self):
        matcher_1 = self._Matcher(False)
        matcher_2 = self._Matcher(True)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        assert matcher.match('foo')

    def test_false_false(self):
        matcher_1 = self._Matcher(False)
        matcher_2 = self._Matcher(False)
        matcher = search._OrMetaMatcher(matcher_1, matcher_2)
        assert not matcher.match('foo')


class TestMultiMetaMatcher(TestMetaMatcherClasses):
    def test_true(self):
        matcher = [self._Matcher(True)] * 10
        matcher = search._MultiMetaMatcher(matcher)
        assert matcher.match('foo')

    def test_false(self):
        matcher = [self._Matcher(True)] * 10 + [self._Matcher(False)]
        matcher = search._MultiMetaMatcher(matcher)
        assert not matcher.match('foo')


class TestManyMultiMetaMatcher(TestMetaMatcherClasses):
    def test_true(self):
        matcher = [self._Matcher(True)] * 10 + [self._Matcher(False)]
        for match in matcher:
            match.tag = 'artist'
        matcher = search._ManyMultiMetaMatcher(matcher)
        assert matcher.match('foo')

    def test_false(self):
        matcher = [self._Matcher(False)] * 10
        for match in matcher:
            match.tag = 'artist'
        matcher = search._ManyMultiMetaMatcher(matcher)
        assert not matcher.match('foo')


class TestTracksMatcher:
    def setup(self):
        self.str = get_search_result_track()

    def test_in_matcher(self):
        matcher = search.TracksMatcher("artist=foo")
        assert len(matcher.matchers) == 1
        match = matcher.matchers[0]
        self.match_is_type(match, search._InMatcher)
        assert match.tag == 'artist'
        assert match.content == 'foo'

    def test_exact_matcher(self):
        matcher = search.TracksMatcher("artist==foo")
        assert len(matcher.matchers) == 1
        match = matcher.matchers[0]
        self.match_is_type(match, search._ExactMatcher)
        assert match.tag == 'artist'
        assert match.content == 'foo'

    def match_is_type(self, match, expected):
        assert isinstance(match, expected), match

    def test_not_matcher(self):
        matcher = search.TracksMatcher("! foo", keyword_tags=['artist'])
        match = matcher
        # NotMetaMatcher
        assert len(match.matchers) == 1
        match = matcher.matchers[0]
        self.match_is_type(match, search._NotMetaMatcher)
        # MultiMetaMatcher
        match = match.matcher
        self.match_is_type(match, search._MultiMetaMatcher)
        # ManyMultiMetaMatcher
        assert len(match.matchers) == 1
        match = match.matchers[0]
        self.match_is_type(match, search._ManyMultiMetaMatcher)
        # InMatcher
        assert len(match.matchers) == 1
        match = match.matchers[0]
        self.match_is_type(match, search._InMatcher)
        assert match.tag == 'artist'
        assert match.content == 'foo'

    def test_or_matcher(self):
        matcher = search.TracksMatcher("foo | bar", keyword_tags=['artist'])
        match = matcher
        # OrMetaMatcher
        assert len(match.matchers) == 1
        match = matcher.matchers[0]
        self.match_is_type(match, search._OrMetaMatcher)
        # MultiMetaMatcher
        assert match.left
        assert match.right
        self.match_is_type(match.left, search._MultiMetaMatcher)
        self.match_is_type(match.right, search._MultiMetaMatcher)
        # ManyMultiMetaMatcher
        assert len(match.left.matchers) == 1
        assert len(match.right.matchers) == 1
        match_left = match.left.matchers[0]
        match_right = match.right.matchers[0]
        self.match_is_type(match_left, search._ManyMultiMetaMatcher)
        self.match_is_type(match_right, search._ManyMultiMetaMatcher)
        # InMatcher
        assert len(match_left.matchers) == 1
        assert len(match_right.matchers) == 1
        match_left = match_left.matchers[0]
        match_right = match_right.matchers[0]
        self.match_is_type(match_left, search._InMatcher)
        self.match_is_type(match_right, search._InMatcher)
        assert match_left.tag == 'artist'
        assert match_right.tag == 'artist'
        if match_left.content == 'foo':
            if match_right.content != 'bar':
                assert not "We lost a search term on an or"
        elif match_left.content == 'bar':
            if match_right.content != 'foo':
                assert not "We lost a search term on an or"
        else:
            assert not "We lost both parts of an or"

    def test_paren_matcher(self):
        matcher = search.TracksMatcher("( foo | bar )", keyword_tags=['artist'])
        match = matcher
        # MultiMetaMatcher
        assert len(match.matchers) == 1
        match = matcher.matchers[0]
        self.match_is_type(match, search._MultiMetaMatcher)

        assert len(match.matchers) == 1
        match = match.matchers[0]
        self.match_is_type(match, search._OrMetaMatcher)

        # This is the same code as the OrMetaMatcher
        assert match.left
        assert match.right
        self.match_is_type(match.left, search._MultiMetaMatcher)
        self.match_is_type(match.right, search._MultiMetaMatcher)
        # ManyMultiMetaMatcher
        assert len(match.left.matchers) == 1
        assert len(match.right.matchers) == 1
        match_left = match.left.matchers[0]
        match_right = match.right.matchers[0]
        self.match_is_type(match_left, search._ManyMultiMetaMatcher)
        self.match_is_type(match_right, search._ManyMultiMetaMatcher)
        # InMatcher
        assert len(match_left.matchers) == 1
        assert len(match_right.matchers) == 1
        match_left = match_left.matchers[0]
        match_right = match_right.matchers[0]
        self.match_is_type(match_left, search._InMatcher)
        self.match_is_type(match_right, search._InMatcher)
        assert match_left.tag == 'artist'
        assert match_right.tag == 'artist'
        if match_left.content == 'foo':
            if match_right.content != 'bar':
                assert not "We lost a search term on an or"
        elif match_left.content == 'bar':
            if match_right.content != 'foo':
                assert not "We lost a search term on an or"
        else:
            assert not "We lost both parts of an or"

    def test_match_true(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        self.str.track.set_tag_raw('artist', 'foo')
        assert matcher.match(self.str)
        assert self.str.on_tags == ['artist']

    def test_match_true_tag(self):
        matcher = search.TracksMatcher("artist=foo")
        self.str.track.set_tag_raw('artist', 'foo')
        assert matcher.match(self.str)
        assert self.str.on_tags == ['artist']

    def test_match_true_case_insensitive(self):
        matcher = search.TracksMatcher("artist=FoO", case_sensitive=False)
        self.str.track.set_tag_raw('artist', 'foo')
        assert matcher.match(self.str)
        assert self.str.on_tags == ['artist']

    def test_match_true_none(self):
        matcher = search.TracksMatcher("artist==__null__")
        self.str.track.set_tag_raw('artist', '')
        assert matcher.match(self.str)
        assert self.str.on_tags == ['artist']

    def test_match_false(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        self.str.track.set_tag_raw('artist', 'bar')
        assert not matcher.match(self.str)


class TestSearchTracks:
    def test_search_tracks(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks = [search.SearchResultTrack(tr) for tr in tracks]
        tracks[0].track.set_tag_raw('artist', 'foooo')
        tracks[2].track.set_tag_raw('artist', 'foooooo')
        gen = search.search_tracks(tracks, [matcher])
        assert next(gen) == tracks[0]
        assert next(gen) == tracks[2]
        with pytest.raises(StopIteration):
            next(gen)

    def test_take_not_srt(self):
        matcher = search.TracksMatcher("foo", keyword_tags=['artist'])
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[0].set_tag_raw('artist', 'foooo')
        tracks[2].set_tag_raw('artist', 'foooooo')
        gen = search.search_tracks(tracks, [matcher])
        assert next(gen).track == tracks[0]
        assert next(gen).track == tracks[2]
        with pytest.raises(StopIteration):
            next(gen)

    def test_search_tracks_from_string(self):
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[0].set_tag_raw('artist', 'foooo')
        tracks[2].set_tag_raw('artist', 'foooooo')
        gen = search.search_tracks_from_string(tracks, 'foo', keyword_tags=['artist'])
        assert next(gen).track == tracks[0]
        assert next(gen).track == tracks[2]
        with pytest.raises(StopIteration):
            next(gen)

    @pytest.mark.parametrize("sstr", ["motley crue", "mötley crüe", "motley crüe"])
    def test_search_tracks_ignore_diacritic_from_string(self, sstr):
        """Ensure that searching for tracks with diacritics return
        appropriately normalized results"""
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[0].set_tag_raw('artist', 'motley crue')
        tracks[1].set_tag_raw('artist', 'rubbish')
        tracks[2].set_tag_raw('artist', 'motley crüe')

        gen = search.search_tracks_from_string(tracks, sstr, keyword_tags=['artist'])

        assert next(gen).track == tracks[0]
        assert next(gen).track == tracks[2]
        with pytest.raises(StopIteration):
            next(gen)

    def test_search_tracks_with_unicodemark_from_string(self):
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[0].set_tag_raw('artist', 'foooo')
        tracks[2].set_tag_raw('artist', '中')

        # the weird character is normalized, so you can't search based on that
        gen = search.search_tracks_from_string(tracks, '中', keyword_tags=['artist'])

        assert next(gen).track == tracks[2]
        with pytest.raises(StopIteration):
            next(gen)

    def test_search_tracks_with_int_from_string(self):
        # unlike mp3, mp4 will return integers for BPM.. make sure that works
        tracks = [track.Track(x) for x in ('foo', 'bar', 'baz', 'quux')]
        tracks[1].set_tag_raw('bpm', '2')
        tracks[2].set_tag_raw('bpm', 2)
        gen = search.search_tracks_from_string(tracks, '2', keyword_tags=['bpm'])
        assert next(gen).track == tracks[1]
        assert next(gen).track == tracks[2]
        with pytest.raises(StopIteration):
            next(gen)
