# mpris2 - Support MPRIS 2 in Exaile
# Copyright (C) 2015-2016  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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


from __future__ import division

import tempfile

from gi.repository import (
    Gio,
    GLib,
)

import xl.covers
import xl.event
import xl.player
import xl.settings

Variant = GLib.Variant


class MprisObject:
    def __init__(self, exaile, connection):
        self.exaile = exaile
        self.connection = connection
        self.cover_file = f = tempfile.NamedTemporaryFile(
            prefix='exaile.mpris2.cover.', suffix='.tmp')
        self.cover_uri = Gio.File.new_for_path(f.name).get_uri()
        self.event_callbacks = callbacks = [
            (self._on_playback_track_start, 'playback_track_start', xl.player.PLAYER),
            (self._on_playback_track_end, 'playback_track_end', xl.player.PLAYER),
            (self._on_playback_toggle_pause, 'playback_toggle_pause', xl.player.PLAYER),
            (self._on_player_option_set, 'player_option_set'),
        ]
        for cb in callbacks:
            xl.event.add_ui_callback(*cb)

    def __del__(self):
        self.destroy()

    def destroy(self):
        for cb in self.event_callbacks:
            xl.event.remove_callback(*cb)
        self.teardown()

    def teardown(self):
        """Quick destroy; just clean up our mess"""
        self.cover_file.close()

    def _emit(self, interface, signame, *args):
        self.connection.emit_signal(None, '/org/mpris/MediaPlayer2', interface,
            signame, Variant.new_tuple(*args))

    def _emit_propchange(self, interface, changed_props={}, invalidated_props=[]):
        self._emit('org.freedesktop.DBus.Properties', 'PropertiesChanged',
            Variant('s', interface),
            Variant('a{sv}', changed_props),
            Variant('as', invalidated_props))

    def _get_metadata(self):
        track = xl.player.PLAYER.current
        if not track:
            return {}

        # TODO: Add more from https://www.freedesktop.org/wiki/Specifications/mpris-spec/metadata/

        # mpris

        meta = {
            'mpris:trackid': Variant('o', '/org/exaile/track/%d' % id(track)),
        }
        v = track.get_tag_raw('__length')
        if v:
            meta['mpris:length'] = Variant('x', v * 1e6)
        v = xl.covers.MANAGER.get_cover(track, set_only=True, use_default=False)
        if v:
            f = self.cover_file
            f.seek(0)
            f.truncate(len(v))
            f.write(v)
            f.flush()
            meta['mpris:artUrl'] = Variant('s', self.cover_uri)

        # xesam

        v = track.get_tag_display('album')
        if v:
            meta['xesam:album'] = Variant('s', v)
        v = track.get_tag_display('artist', join=False)
        if v:
            meta['xesam:artist'] = Variant('as', v)
        v = track.get_tag_raw('album')
        if v:
            # TODO: I've seen a client expect 'radio' on streams;
            # is that common usage?
            meta['xesam:genre'] = Variant('as', v)
        try:
            v = int(track.get_tag_display('tracknumber')[0])
        except (IndexError, TypeError, ValueError):
            pass
        else:
            meta['xesam:trackNumber'] = Variant('i', v)
        v = track.get_tag_display('title')
        if v:
            meta['xesam:title'] = Variant('s', v)
        v = track.get_loc_for_io()
        if v:
            meta['xesam:url'] = Variant('s', v)
        v = track.get_tag_raw('__rating')
        if v:
            meta['xesam:userRating'] = Variant('d', v / 100)

        return meta

    def _on_playback_track_start(self, event, player, track):
        self._emit_propchange('org.mpris.MediaPlayer2.Player', {
            'Metadata': self.Metadata,
            'PlaybackStatus': Variant('s', 'Playing'),
        })

    def _on_playback_track_end(self, event, player, track):
        self._emit_propchange('org.mpris.MediaPlayer2.Player', {
            'Metadata': Variant('a{sv}', {}),
            'PlaybackStatus': Variant('s', 'Stopped'),
        })

    def _on_playback_toggle_pause(self, event, player, track):
        self._emit_propchange('org.mpris.MediaPlayer2.Player', {
            'PlaybackStatus': Variant('s',
                'Paused' if xl.player.PLAYER.is_paused() else 'Playing'),
        })

    def _on_player_option_set(self, event, settings, option):
        if option == 'player/volume':
            self._emit_propchange('org.mpris.MediaPlayer2.Player', {
                'Volume': self.Volume,
            })

    def _return_true(self):  # Positive reply for the "Can*" properties
        return Variant('b', True)

    # Root properties

    CanRaise = CanQuit = CanSetFullScreen = property(_return_true)
    @property
    def DesktopEntry(self):
        return Variant('s', 'exaile')
    @property
    def FullScreen(self):
        return Variant('b', False)  # TODO
    @FullScreen.setter
    def FullScreen(self, value):
        window = self.exaile.gui.main.window
        if value:
            window.fullscreen()
        else:
            window.unfullscreen()
        # TODO: Signal
    @property
    def HasTrackList(self):
        return Variant('b', False)
    @property
    def Identity(self):
        return Variant('s', 'Exaile')
    @property
    def SupportedMimeTypes(self):
        return Variant('as', ['application/ogg'])  # TODO
    @property
    def SupportedUriSchemes(self):
        return Variant('as', ['file'])  # TODO

    # Root methods

    def Raise(self):
        self.exaile.gui.main.window.present()
    def Quit(self):
        self.exaile.quit()

    # Player properties

    CanControl = CanGoNext = CanGoPrevious = CanPause = CanPlay = CanSeek = property(_return_true)
    @property
    def LoopStatus(self):
        return Variant('s', 'None')  # TODO
    @property
    def MaximumRate(self):
        return Variant('d', 1)
    @property
    def Metadata(self):
        return Variant('a{sv}', self._get_metadata())
    @property
    def MinimumRate(self):
        return Variant('d', 1)
    @property
    def PlaybackStatus(self):
        state = xl.player.PLAYER.get_state()
        assert state in ('playing', 'paused', 'stopped')
        return Variant('s', state.capitalize())
    @property
    def Position(self):
        return Variant('x', xl.player.PLAYER.get_time() * 1e6)
    @property
    def Rate(self):
        return Variant('d', 1)
    @Rate.setter
    def Rate(self, value):
        pass
    @property
    def Shuffle(self):
        return self._return_true()  # TODO
    @Shuffle.setter
    def Shuffle(self, value):
        pass  # TODO
    @property
    def Volume(self):
        return Variant('d', xl.settings.get_option('player/volume', 1))
    @Volume.setter
    def Volume(self, value):
        xl.settings.set_option('player/volume', value.get_double())

    # Player methods

    def Next(self):
        # TODO: Match behavior with spec
        xl.player.QUEUE.next()
    def OpenUri(self, uri):
        pass  # TODO
    def Pause(self):
        xl.player.PLAYER.pause()
    def Play(self):
        # TODO: Match behavior with spec
        xl.player.QUEUE.play()
    def PlayPause(self):
        # TODO: Match behavior with spec
        xl.player.PLAYER.toggle_pause()
    def Previous(self):
        # TODO: Match behavior with spec
        xl.player.QUEUE.prev()
    def Seek(self, offset):
        pass  # TODO
    def SetPosition(self, track_id, position):
        if track_id != '/org/exaile/track/%d' % id(xl.player.PLAYER.current):
            return
        xl.player.PLAYER.seek(position.get_int64() / 1e6)
        self._emit('org.mpris.MediaPlayer2.Player', 'Seeked', position)
    def Stop(self):
        xl.player.PLAYER.stop()
