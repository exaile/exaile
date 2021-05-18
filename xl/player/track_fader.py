# Copyright (C) 2015 Dustin Spicuzza
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

from typing import Tuple

from gi.repository import GLib

from xl import common

import logging

FadeState = common.enum(NoFade=1, FadingIn=2, Normal=3, FadingOut=4)


class TrackFader:
    """
    This object manages the volume of a track, and fading it in/out via
    volume. As a bonus, this object can manage the start/stop offset of
    a track also.

    * Fade in only happens once per track play
    * Fade out can happen multiple times

    This fader can be used on any engine, as long as it implements the
    following functions:

    * get_position: return current track position in nanoseconds
    * get_volume/set_volume: volume is 0 to 1.0
    * stop: stops playback

    There is a user volume and a fade volume. The fade volume is used
    internally and the output volume is set by multiplying both of
    them together.

    .. note:: Only intended to be used by engine implementations
    """

    SECOND = 1000000000.0

    def __init__(self, stream, on_fade_out, name):
        self.name = name

        self.logger = logging.getLogger('%s [%s]' % (__name__, name))

        self.stream = stream
        self.state = FadeState.NoFade
        self.on_fade_out = on_fade_out
        self.timer_id = None

        self.fade_volume = 1.0
        self.user_volume = 1.0

        self.fade_in_start = None
        self.fade_out_start = None

    def calculate_fades(self, track, fade_in, fade_out):
        '''duration is in seconds'''

        start_offset = track.get_tag_raw('__startoffset') or 0
        stop_offset = track.get_tag_raw('__stopoffset') or 0
        tracklen = track.get_tag_raw('__length') or 0

        if stop_offset < 1:
            stop_offset = tracklen

        # Deal with bad values..
        start_offset = min(start_offset, tracklen)
        stop_offset = min(stop_offset, tracklen)

        # Give up
        if stop_offset <= start_offset:
            return (tracklen,) * 4

        if fade_in is None:
            fade_in = 0
        else:
            fade_in = max(0, fade_in)

        if fade_out is None:
            fade_out = 0
        else:
            fade_out = max(0, fade_out)

        playlen = stop_offset - start_offset

        total_fade = max(fade_in + fade_out, 0.1)

        if total_fade > playlen:
            fade_in = playlen * (float(fade_in) / total_fade)
            fade_out = playlen * (float(fade_out) / total_fade)

        return (
            start_offset,
            start_offset + fade_in,
            stop_offset - fade_out,
            stop_offset,
        )

    def calculate_user_volume(self, real_volume) -> Tuple[float, bool]:
        """Given the 'real' output volume, calculate what the user
        volume should be and whether they are identical"""

        vol = self.user_volume * self.fade_volume
        real_is_same = abs(real_volume - vol) < 0.01

        if real_is_same:
            return real_volume, True

        if self.fade_volume < 0.01:
            return real_volume, True
        else:
            user_vol = real_volume / self.fade_volume
            is_same = abs(user_vol - self.user_volume) < 0.01
            return user_vol, is_same

    def fade_out_on_play(self):

        if self.fade_out_start is None:
            self.logger.debug("foop: no fade out defined, stopping")
            self.stream.stop()
            return

        self.now = self.stream.get_position() / self.SECOND - 0.010
        fade_len = self.fade_out_end - self.fade_out_start

        # If playing, and is not fading out, then force a fade out
        if self.state == FadeState.Normal:
            start = self.now

        elif self.state == FadeState.FadingIn:
            # Calculate an optimal fadeout given the current volume
            volume = self.fade_volume
            start = -((volume * fade_len) - self.now)
            self.state = FadeState.FadingOut

        else:
            return

        self.logger.debug(
            "foop: starting fade (now: %s, start: %s, len: %s)",
            self.now,
            start,
            fade_len,
        )

        self._cancel()
        if self._execute_fade(start, fade_len):
            self.timer_id = GLib.timeout_add(10, self._execute_fade, start, fade_len)

    def get_user_volume(self):
        return self.user_volume

    def is_fading_out(self):
        return self.state == FadeState.FadingOut

    def setup_track(self, track, fade_in, fade_out, is_update=False, now=None):
        """
        Call this function either when a track first starts, or if the
        crossfade period has been updated.

        As a bonus, calling this function with crossfade_duration=None
        will automatically stop the track at its stop_offset

        :param fade_in: Set to None or fade duration in seconds
        :param fade_out: Set to None or fade duration in seconds
        :param is_update: Set True if this is a settings update
        """

        # If user disables crossfade during a transition, then don't
        # cancel the transition

        has_fade = fade_in is not None or fade_out is not None

        if is_update and has_fade:

            if self.state == FadeState.FadingOut:
                # Don't cancel the current fade out
                return

            elif self.state == FadeState.FadingIn:
                # Don't cancel the current fade in, but adjust the
                # current fade out
                _, _, self.fade_out_start, self.fade_out_end = self.calculate_fades(
                    track, fade_in, fade_out
                )

                self._next(now=now)
                return

        if has_fade:
            self.play(*self.calculate_fades(track, fade_in, fade_out))
        else:
            stop_offset = track.get_tag_raw('__stopoffset') or 0
            if stop_offset > 0:
                self.play(None, None, stop_offset, stop_offset, now=now)
            else:
                self.play(now=now)

    def play(
        self,
        fade_in_start=None,
        fade_in_end=None,
        fade_out_start=None,
        fade_out_end=None,
        now=None,
    ):
        '''Don't call this when doing crossfading'''

        self.fade_in_start = fade_in_start
        self.fade_in_end = fade_in_end

        self.fade_out_start = fade_out_start
        self.fade_out_end = fade_out_end

        if self.fade_in_start is not None:
            self.state = FadeState.FadingIn
        elif self.fade_out_start is None:
            self.state = FadeState.NoFade
        else:
            self.state = FadeState.Normal

        self._next(now=now)

    def pause(self):
        self._cancel()

    def seek(self, to):
        self._next(now=to)

    def set_user_volume(self, volume):
        self.user_volume = volume
        self.stream.set_volume(self.user_volume * self.fade_volume)

    def set_fade_volume(self, volume):
        self.fade_volume = volume
        self.stream.set_volume(self.user_volume * self.fade_volume)

    def unpause(self):
        self._next()

    def stop(self):
        self.state = FadeState.NoFade
        self._cancel()

    def _next(self, now=None):

        self._cancel()

        if self.state == FadeState.NoFade:
            self.set_fade_volume(1.0)
            return

        if now is None:
            now = self.stream.get_position() / self.SECOND

        msg = "Fade data: now: %.2f; in: %s,%s; out: %s,%s"
        self.logger.debug(
            msg,
            now,
            self.fade_in_start,
            self.fade_in_end,
            self.fade_out_start,
            self.fade_out_end,
        )

        if self.state == FadeState.FadingIn:
            if now < self.fade_in_end:
                self._on_fade_start(now=now)
                return

            self.state = FadeState.Normal

        if self.fade_out_start is None:
            self.state = FadeState.NoFade
            self.set_fade_volume(1.0)
            return

        fade_tm = int((self.fade_out_start - now) * 1000)
        if fade_tm > 0:
            self.logger.debug("- Will fade out in %.2f seconds", fade_tm / 1000.0)
            self.timer_id = GLib.timeout_add(fade_tm, self._on_fade_start)
            self.set_fade_volume(1.0)
        else:
            # do the fade now
            self._on_fade_start(now=now)

    def _cancel(self):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

    def _on_fade_start(self, now=None):

        if now is None:
            now = self.stream.get_position() / self.SECOND

        self.now = now - 0.010

        if self.state == FadeState.FadingIn:
            self.logger.debug("Fade in begins")
            end = self.fade_in_end
            start = self.fade_in_start
        else:
            end = self.fade_out_end
            start = self.fade_out_start

            if self.state != FadeState.FadingOut:
                self.logger.debug("Fade out begins at %s", self.now)
                self.state = FadeState.FadingOut
                self.on_fade_out()

        fade_len = float(end - start)

        if self._execute_fade(start, fade_len):
            self.timer_id = GLib.timeout_add(10, self._execute_fade, start, fade_len)
        return False

    def _execute_fade(self, fade_start, fade_len):
        """
        Executes a fade for a period of time, then ends

        :param fade_start:  When the fade should have started
        :param fade_len:    _total_ length of fade, regardless of start
        """

        # Don't query the stream, just assume this is close enough
        self.now += 0.010
        fading_in = self.state == FadeState.FadingIn

        if fade_len < 0.01:
            volume = 0.0
        else:
            volume = (self.now - fade_start) / fade_len

        if not fading_in:
            volume = 1.0 - volume

        volume = min(max(0.0, volume), 1.0)
        self.set_fade_volume(volume)

        if self.now > fade_start + fade_len:
            self.timer_id = None

            if fading_in:
                self.logger.debug("Fade in ends")
                self.state = FadeState.Normal
                self._next()
            else:
                self.logger.debug("Fade out ends")
                self.state = FadeState.NoFade
                self.stream.stop()

            return False

        return True
