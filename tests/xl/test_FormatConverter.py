# -*- coding: utf-8  -*-

import logging

from xl.playlist import FormatConverter, PlaylistExportOptions

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
