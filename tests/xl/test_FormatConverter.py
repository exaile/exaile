# -*- coding: utf-8  -*-

import logging

import pytest

from xl.playlist import FormatConverter, PlaylistExportOptions, import_playlist

LOG = logging.getLogger(__name__)


class Test_FormatConverter:
    TIMEOUT = 2000
    MAX_ENTRIES = 2

    def test_get_track_export_path_relative(self):
        fc = FormatConverter('test')
        peo = PlaylistExportOptions
        peo.relative = True

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'file:///tmp/track1', peo
        )
        assert test == 'track1'

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'file:///tmp123/track1', peo
        )
        assert test == '../tmp123/track1'

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'file:///tmp123/track1%202', peo
        )
        assert test == '../tmp123/track1 2'

        test = fc.get_track_export_path(
            'gvfs:///tmp/playlist', 'gvfs:///tmp/track1', peo
        )
        assert test == 'track1'

        test = fc.get_track_export_path(
            'gvfs:///tmp/playlist', 'gvfs:///tmp123/track1', peo
        )
        assert test == '../tmp123/track1'

        test = fc.get_track_export_path(
            'gvfs:///tmp/playlist', 'http://ec3.yesstreaming.net:3420/stream', peo
        )
        assert test == 'http://ec3.yesstreaming.net:3420/stream'

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'http://ec3.yesstreaming.net:3420/stream', peo
        )
        assert test == 'http://ec3.yesstreaming.net:3420/stream'

    def test_track_export_path_stream(self):
        fc = FormatConverter('test')

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'http://ec3.yesstreaming.net:3420/stream', None
        )
        assert test == 'http://ec3.yesstreaming.net:3420/stream'

    def test_track_export_path_absolute(self):
        fc = FormatConverter('test')

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'file:///tmp/track1', None
        )
        assert test == '/tmp/track1'

        test = fc.get_track_export_path(
            'file:///tmp/playlist', 'file:///tmp123/track1%202', None
        )
        assert test == '/tmp123/track1 2'


@pytest.mark.parametrize(
    'duration, expected_length',
    [('3.5', 3), ('0.75', None), ('-1.0', None), ('3', 3), ('0', None), ('-1', None)],
)
def test_import_m3u_duration(tmp_path, duration, expected_length):
    playlist_path = tmp_path / 'local.m3u'
    playlist_path.write_text(
        '#EXTM3U\n'
        f'#EXTINF:{duration},Artist - First track\n'
        'first.ogg\n'
        '#EXTINF:4,Artist - Second track\n'
        'second.ogg\n'
    )

    playlist = import_playlist(playlist_path.as_uri())

    assert len(playlist) == 2
    assert playlist[0].get_loc_for_io() == (tmp_path / 'first.ogg').as_uri()
    assert playlist[0].get_tag_raw('__length') == expected_length
    assert playlist[0].get_tag_raw('title') == ['First track']
    assert playlist[0].get_tag_raw('artist') == ['Artist']
    assert playlist[1].get_loc_for_io() == (tmp_path / 'second.ogg').as_uri()
    assert playlist[1].get_tag_raw('__length') == 4
    assert playlist[1].get_tag_raw('title') == ['Second track']
