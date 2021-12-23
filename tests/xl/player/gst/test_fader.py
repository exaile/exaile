from gi.repository import GLib
import pytest

from xl.player.track_fader import TrackFader, FadeState

NoFade = FadeState.NoFade
FadingIn = FadeState.FadingIn
Normal = FadeState.Normal
FadingOut = FadeState.FadingOut


class FakeStream:
    def __init__(self):
        self.reset()

    def reset(self):
        self.position = 0
        self.volume = 42
        self.fadeout_begin = False
        self.stopped = False

    def get_position(self):
        return self.position

    def set_volume(self, value):
        self.volume = int(value * 100)

    def stop(self):
        self.stopped = True

    def on_fade_out(self):
        self.fadeout_begin = True


class FakeTrack:
    def __init__(self, start_off, stop_off, tracklen):
        self.tags = {
            '__startoffset': start_off,
            '__stopoffset': stop_off,
            '__length': tracklen,
        }

    def get_tag_raw(self, t):
        return self.tags[t]


# TODO: monkeypatch instead
timeout_args = [()]


def glib_timeout_add(*args):
    timeout_args[0] = args[2:]
    return args[1]


def glib_source_remove(src_id):
    pass


GLib.timeout_add = glib_timeout_add
GLib.source_remove = glib_source_remove

TmSt = 1
TmEx = 2


# Test data:
#   Position, Volume, State, TmSt/TmEx/None, [call, [arg1...]]

# fmt: off
@pytest.mark.parametrize('test', [

    # Test don't manage the volume
    [
        (0, 100, NoFade, None, 'play', None, None, None, None),
        (1, 100, NoFade, None, 'pause'),
        (2, 100, NoFade, None, 'unpause'),
        (3, 100, NoFade, None, 'seek', 4),
        (4, 100, NoFade, None, 'stop'),
        (5, 100, NoFade, None),
    ],

    # Test fading in
    [
        (0, 0,  FadingIn, TmEx, 'play', 0, 2, None, None),
        (1, 50, FadingIn, TmEx, 'execute'),
        (3, 100, NoFade,  None, 'execute'),
        (4, 100, NoFade,  None),
        (5, 100, NoFade,  None, 'stop'),
        (6, 100, NoFade,  None),
    ],

    # Test fading in: pause in middle
    [
        (0, 0,  FadingIn, TmEx, 'play', 0, 2, None, None),
        (1, 50, FadingIn, TmEx, 'execute'),
        (1, 50, FadingIn, None, 'pause'),
        (1, 50, FadingIn, TmEx, 'unpause'),
        (1, 50, FadingIn, TmEx, 'execute'),
        (3, 100, NoFade,  None, 'execute'),
        (4, 100, NoFade,  None),
        (5, 100, NoFade,  None, 'stop'),
        (6, 100, NoFade,  None),
    ],

    # Test fading in past the fade point
    [
        (3, 100, NoFade, None, 'play', 0, 2, None, None),
        (4, 100, NoFade, None),
        (5, 100, NoFade, None, 'stop'),
        (6, 100, NoFade, None),
    ],

    # Test fading out
    [
        (3, 100, Normal,    TmSt, 'play', None, None, 4, 6),
        (4, 100, FadingOut, TmEx, 'start'),
        (5, 50,  FadingOut, TmEx, 'execute'),
        (6, 0,   FadingOut, TmEx, 'execute'),
        (6.1, 0, NoFade,    None, 'execute'),
        (7,   0, NoFade,    None),
    ],

    # Test all of them
    [
        (0, 0,  FadingIn,   TmEx, 'play', 0, 2, 4, 6),
        (1, 50, FadingIn,   TmEx, 'execute'),
        (3, 100, Normal,    TmSt, 'execute'),
        (4, 100, FadingOut, TmEx, 'start'),
        (5, 50,  FadingOut, TmEx, 'execute'),
        (6, 0,   FadingOut, TmEx, 'execute'),
        (6.1, 0, NoFade,    None, 'execute'),
        (7,   0, NoFade,    None),
    ],

    # Test fading in with startoffset
    # [
    #     (0, 0,  FadingIn,  TmEx, 'play', 60, 62, 64, 66),
    #     (0, 0,  FadingIn,  TmEx, 'seek', 60),
    #     (61, 50,  FadingIn,  TmEx, 'execute'),
    # ],
])
# fmt: on
def test_fader(test):

    # Test fade_out_on_play

    # Test setup_track

    # Test setup_track is_update=True

    # Test unexpected fading out

    check_fader(test)


def check_fader(test):
    stream = FakeStream()
    fader = TrackFader(stream, stream.on_fade_out, 'test')

    for data in test:
        print(data)
        now = data[0]
        stream.position = int(now * TrackFader.SECOND)
        print(stream.position)
        volume = data[1]
        state = data[2]
        timer_id = data[3]

        if len(data) > 4:
            action = data[4]
            args = data[5:] if len(data) > 5 else ()

            if action == 'start':
                action = '_on_fade_start'
            elif action == 'execute':
                action = '_execute_fade'
                args = timeout_args[0]
                fader.now = now - 0.010

            # Call the function
            getattr(fader, action)(*args)

        # Check to see if timer id exists
        if timer_id is None:
            assert fader.timer_id is None
        elif timer_id == TmSt:
            assert fader.timer_id == fader._on_fade_start
        elif timer_id == TmEx:
            assert fader.timer_id == fader._execute_fade
        else:
            assert False

        assert fader.state == state
        assert stream.volume == volume


def test_calculate_fades():
    fader = TrackFader(None, None, None)

    # fin, fout, start_off, stop_off, tracklen;
    # start, start+fade, end-fade, end
    calcs = [
        # fmt: off
        
        # one is zero/none
        (0, 4, 0, 0, 10,        0, 0, 6, 10),
        (None, 4, 0, 0, 10,     0, 0, 6, 10),

        # other is zero/none
        (4, 0, 0, 0, 10,        0, 4, 10, 10),
        (4, None, 0, 0, 10,     0, 4, 10, 10),

        # both are equal
        (4, 4, 0, 0, 10,        0, 4, 6, 10),

        # both are none
        (0, 0, 0, 0, 10,        0, 0, 10, 10),
        (None, None, 0, 0, 10,  0, 0, 10, 10),

        # Bigger than playlen: all three cases
        (0, 4, 0, 0, 2,         0, 0, 0, 2),
        (4, 0, 0, 0, 2,         0, 2, 2, 2),
        (4, 4, 0, 0, 2,         0, 1, 1, 2),

        # With start offset
        (4, 4, 1, 0, 10,        1, 5, 6, 10),

        # With stop offset
        (4, 4, 0, 9, 10,        0, 4, 5, 9),

        # With both
        (2, 2, 1, 9, 10,        1, 3, 7, 9),

        # With both, constrained
        (4, 4, 4, 8, 10,        4, 6, 6, 8),
        (2, 4, 4, 7, 10,        4, 5, 5, 7),
        (4, 2, 4, 7, 10,        4, 6, 6, 7),
        # fmt: on
    ]

    i = 0
    for fin, fout, start, stop, tlen, t0, t1, t2, t3 in calcs:
        print(
            '%2d: Fade In: %s; Fade Out: %s; start: %s; stop: %s; Len: %s'
            % (i, fin, fout, start, stop, tlen)
        )
        track = FakeTrack(start, stop, tlen)
        assert fader.calculate_fades(track, fin, fout) == (t0, t1, t2, t3)
        i += 1
