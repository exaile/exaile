from unittest.mock import patch

from gi.repository import Gio

import xl.collection
import xl.trax.search
import xl.trax.track
import xl.trax.util


def test_is_valid_track_valid(test_track):
    fname = test_track.filename
    assert xl.trax.util.is_valid_track(fname), fname


def test_is_valid_track_invalid():
    assert not xl.trax.util.is_valid_track('/')
    assert not xl.trax.util.is_valid_track('/tmp')
    assert not xl.trax.util.is_valid_track(__file__)
    assert not xl.trax.util.is_valid_track('http:///tmp')


class TestGetTracksFromUri:
    def test_invalid(self):
        uri = __file__  # Not a URI, should fail
        assert xl.trax.util.get_tracks_from_uri(uri) == []
        uri = Gio.File.new_for_path('__nonexistent_file__').get_uri()
        assert xl.trax.util.get_tracks_from_uri(uri) == []

    def test_single(self):
        uri = Gio.File.new_for_path(__file__).get_uri()
        assert xl.trax.util.get_tracks_from_uri(uri) == [xl.trax.track.Track(uri)]

    def test_directory(self):
        uri = Gio.File.new_for_path(__file__).get_parent()
        assert uri
        uri = uri.get_uri()

        with patch('xl.collection.Library.rescan'):
            xl.trax.util.get_tracks_from_uri(uri)


class TestSortTracks:
    def setup_method(self):
        self.tracks = [
            xl.trax.track.Track(url) for url in ('/tmp/foo', '/tmp/bar', '/tmp/baz')
        ]
        for track, val in zip(self.tracks, 'aab'):
            track.set_tag_raw('artist', val)
        for track, val in zip(self.tracks, '212'):
            track.set_tag_raw('discnumber', val)
        self.fields = ('artist', 'discnumber')
        self.result = [self.tracks[1], self.tracks[0], self.tracks[2]]

    def test_sorted(self):
        assert xl.trax.util.sort_tracks(self.fields, self.tracks) == self.result

    def test_reversed(self):
        assert xl.trax.util.sort_tracks(self.fields, self.tracks, reverse=True) == list(
            reversed(self.result)
        )


class TestSortResultTracks:
    def setup_method(self):
        tracks = [
            xl.trax.track.Track(url) for url in ('/tmp/foo', '/tmp/bar', '/tmp/baz')
        ]
        for track, val in zip(tracks, 'aab'):
            track.set_tag_raw('artist', val)
        for track, val in zip(tracks, '212'):
            track.set_tag_raw('discnumber', val)
        self.tracks = [xl.trax.search.SearchResultTrack(track) for track in tracks]
        self.fields = ('artist', 'discnumber')
        self.result = [self.tracks[1], self.tracks[0], self.tracks[2]]

    def test_sorted(self):
        assert xl.trax.util.sort_result_tracks(self.fields, self.tracks) == self.result

    def test_reversed(self):
        assert xl.trax.util.sort_result_tracks(self.fields, self.tracks, True) == list(
            reversed(self.result)
        )
