from unittest.mock import Mock

import pytest

from xl import playlist, settings
from xl.player.queue import PlayQueue
from xl.trax import Track

REMOVE_BEFORE = (True, False)
REMOVE_AFTER = (True, True)
KEEP_ITEMS = (False, False)


class FakePlayer:
    def __init__(self):
        self.current = None
        self.queue = None
        self.play = Mock(side_effect=self._play)

    def _play(self, track):
        self.current = track

    def is_playing(self):
        return False

    def get_time(self):
        return 10


@pytest.fixture
def tracks():
    return [Track('file:///queue-%d.ogg' % i) for i in range(4)]


@pytest.fixture
def make_queue(monkeypatch):
    queues = []

    def _make(mode, initial_tracks=()):
        remove_when_played, remove_after_played = mode
        options = {
            'queue/remove_item_when_played': remove_when_played,
            'queue/remove_item_after_played': remove_after_played,
            'queue/disable_new_track_when_playing': False,
            'queue/enqueue_begins_playback': False,
        }
        monkeypatch.setattr(
            settings,
            'get_option',
            lambda option, default=None: options.get(option, default),
        )

        player = FakePlayer()
        queue = PlayQueue(player, 'queue')
        queue.extend(initial_tracks)
        queues.append(queue)
        return queue, player

    yield _make

    # Playlist and PlayQueue register weak callbacks, but explicitly detach the
    # live instances so this fixture never leaks callbacks into another test.
    from xl import event

    for queue in queues:
        event.remove_callback(queue._on_option_set, 'queue_option_set')
        event.remove_callback(queue.on_playback_track_start, 'playback_track_start')


@pytest.mark.parametrize('mode', [REMOVE_BEFORE, REMOVE_AFTER, KEEP_ITEMS])
def test_get_next_is_repeatable_without_advancing(mode, make_queue, tracks):
    queue, _player = make_queue(mode, tracks[:3])

    assert queue.get_next() is tracks[0]
    assert queue.get_next() is tracks[0]
    assert queue.current_position == -1
    assert list(queue) == tracks[:3]


@pytest.mark.parametrize(
    ('mode', 'expected_contents', 'expected_positions', 'expected_lengths'),
    [
        (REMOVE_BEFORE, [[1, 2], [2], []], [0, 0, -1], [2, 1, 0]),
        (REMOVE_AFTER, [[0, 1, 2], [1, 2], [2]], [0, 0, 0], [2, 1, 0]),
        (KEEP_ITEMS, [[0, 1, 2]] * 3, [0, 1, 2], [2, 1, 0]),
    ],
)
def test_queue_modes_advance_and_report_remaining_length(
    mode,
    expected_contents,
    expected_positions,
    expected_lengths,
    make_queue,
    tracks,
):
    queue, player = make_queue(mode, tracks[:3])

    for index, track in enumerate(tracks[:3]):
        assert queue.next() is track
        assert player.current is track
        assert [tracks.index(item) for item in queue] == expected_contents[index]
        assert queue.current_position == expected_positions[index]
        assert queue.queue_length() == expected_lengths[index]

    assert player.play.call_count == 3


@pytest.mark.parametrize('mode', [REMOVE_BEFORE, REMOVE_AFTER, KEEP_ITEMS])
def test_exhausted_queue_stops(mode, make_queue, tracks):
    queue, player = make_queue(mode, tracks[:2])

    assert queue.next() is tracks[0]
    assert queue.next() is tracks[1]
    assert queue.next() is None
    assert queue.get_next() is None
    expected_length = 0 if mode == REMOVE_BEFORE else -1
    assert queue.queue_length() == expected_length
    player.play.assert_called_with(None)


@pytest.mark.parametrize('mode', [REMOVE_BEFORE, REMOVE_AFTER, KEEP_ITEMS])
def test_exhausted_queue_continues_with_selected_playlist(mode, make_queue, tracks):
    current_playlist = playlist.Playlist('playing', tracks[2:])
    queue, player = make_queue(mode, tracks[:2])
    queue.set_current_playlist(current_playlist)

    assert [queue.next() for _ in range(4)] == tracks
    assert queue.current_playlist is current_playlist
    assert queue.last_playlist is current_playlist
    assert current_playlist.current_position == 1
    assert player.current is tracks[3]


def test_remove_after_keeps_current_track_until_advance(make_queue, tracks):
    queue, _player = make_queue(REMOVE_AFTER, tracks[:2])

    assert queue.next() is tracks[0]
    assert list(queue) == tracks[:2]
    assert queue.get_next() is tracks[1]

    assert queue.next() is tracks[1]
    assert list(queue) == tracks[1:2]


def test_remove_before_removes_explicitly_played_queue_track(make_queue, tracks):
    queue, player = make_queue(REMOVE_BEFORE, tracks[:3])

    queue.play(tracks[1])

    player.play.assert_called_once_with(tracks[1])
    assert list(queue) == [tracks[0], tracks[2]]


def test_keep_items_uses_normal_playlist_repeat_behavior(make_queue, tracks):
    queue, _player = make_queue(KEEP_ITEMS, tracks[:2])
    queue.repeat_mode = 'all'

    assert queue.next() is tracks[0]
    assert queue.next() is tracks[1]
    assert queue.next() is tracks[0]
    assert list(queue) == tracks[:2]
