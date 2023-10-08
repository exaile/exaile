import itertools
import os
import unittest
import logging
import random
import string
from unittest.mock import Mock, patch

import pytest

from xl.metadata import CoverImage
from xl.player import queue, player
from xl import playlist
import xl.trax.track as track
import xl.settings as settings


class TestQueue:
    def test_remove_on_play(self):
        settings.set_option('queue/remove_item_when_played', True)
        settings.set_option('queue/remove_item_after_played', False)

        p = player.ExailePlayer('player')
        tr1 = track.Track('/foo')
        tr2 = track.Track('/bar')
        q = queue.PlayQueue(p, 'queue')
        q.append(tr1)
        q.append(tr2)

        n1 = q.next()
        assert n1 == tr1
        assert q.current_position == -1
        assert len(q) == 1

        n2 = q.next()
        assert n2 == tr2
        assert q.current_position == -1
        assert len(q) == 0

    def test_remove_after_play(self):
        pytest.skip('not fully implemented')

        settings.set_option('queue/remove_item_when_played', True)
        settings.set_option('queue/remove_item_after_played', True)

        p = player.ExailePlayer('player')
        tr1 = track.Track('/foo')
        tr2 = track.Track('/bar')
        q = queue.PlayQueue(p, 'queue')
        q.append(tr1)
        q.append(tr2)

        n1 = q.next()
        assert n1 == tr1
        assert q.current_position == 0
        assert len(q) == 1

        n2 = q.next()
        assert n2 == tr2

    def test_no_remove(self):
        settings.set_option('queue/remove_item_when_played', False)
        settings.set_option('queue/remove_item_after_played', False)

        p = player.ExailePlayer('player')
        tr1 = track.Track('/foo')
        tr2 = track.Track('/bar')
        tr3 = track.Track('/baz')
        q = queue.PlayQueue(p, 'queue')
        q.append(tr1)
        q.append(tr2)
        q.append(tr3)

        n2 = q.next()
        assert n2 == tr2
        assert len(q) == 3

        n3 = q.next()
        assert n3 == tr3
        assert len(q) == 3

        n4 = q.next()
        assert n4 == None
        assert len(q) == 3

    def test_switch_playlist(self):
        settings.set_option('queue/remove_item_when_played', False)
        settings.set_option('queue/remove_item_after_played', False)

        p = player.ExailePlayer('player')
        tr1 = track.Track('/foo')
        q = queue.PlayQueue(p, 'queue')
        q.append(tr1)

        tr2 = track.Track('/foo1')
        tr3 = track.Track('/bar1')
        p = playlist.Playlist('pl')
        p.append(tr2)
        p.append(tr3)

        q.last_playlist = p

        n1 = q.next()
        assert n1 == tr1

        n2 = q.next()
        assert n2 == tr2

        n3 = q.next()
        assert n3 == tr3

        n4 = q.next()
        assert n4 == None
