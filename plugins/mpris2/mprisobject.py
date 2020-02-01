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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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


import tempfile

from gi.repository import Gio, GLib

import xl.covers
import xl.event
import xl.player
import xl.settings

Variant = GLib.Variant


class MprisObject:
    def __init__(self, exaile, connection):
        self.exaile = exaile
        self.connection = connection
        self.cover_file = None
        self.signal_connections = []
        self.event_callbacks = callbacks = [
            (self._on_playback_track_start, 'playback_track_start', xl.player.PLAYER),
            (self._on_playback_track_end, 'playback_track_end', xl.player.PLAYER),
            (self._on_playback_toggle_pause, 'playback_toggle_pause', xl.player.PLAYER),
            (self._on_player_option_set, 'player_option_set'),
        ]
        for cb in callbacks:
            xl.event.add_ui_callback(*cb)
        if exaile.loading:
            xl.event.add_ui_callback(self._init_gui, 'exaile_loaded')
        else:
            self._init_gui()

    def __del__(self):
        self.destroy()

    def destroy(self):
        for obj, conn in self.signal_connections:
            obj.disconnect(conn)
        for cb in self.event_callbacks:
            xl.event.remove_callback(*cb)
        self.teardown()

    def _init_gui(self, *_args):
        if not hasattr(self.exaile.gui, 'main'):
            return  # No GUI
        conns = [
            (self.exaile.gui.main, 'notify::is-fullscreen', self._on_notify_fullscreen)
        ]
        self.signal_connections.extend(
            (obj, obj.connect(sig, handler)) for obj, sig, handler in conns
        )

    def teardown(self):
        """Quick destroy; just clean up our mess"""
        f = self.cover_file
        if f:
            f.close()

    def _new_cover_file(self):
        f = self.cover_file
        if f:
            f.close()
        self.cover_file = f = tempfile.NamedTemporaryFile(
            prefix='exaile.mpris2.cover.', suffix='.tmp'
        )
        uri = Gio.File.new_for_path(f.name).get_uri()
        return f, uri

    def _emit(self, interface, signame, *args):
        self.connection.emit_signal(
            None,
            '/org/mpris/MediaPlayer2',
            interface,
            signame,
            Variant.new_tuple(*args),
        )

    def _emit_propchange(self, interface, changed_props={}, invalidated_props=[]):
        self._emit(
            'org.freedesktop.DBus.Properties',
            'PropertiesChanged',
            Variant('s', interface),
            Variant('a{sv}', changed_props),
            Variant('as', invalidated_props),
        )

    def _get_metadata(self):
        track = xl.player.PLAYER.current
        if not track:
            return {}

        # TODO: Add more from https://www.freedesktop.org/wiki/Specifications/mpris-spec/metadata/

        # mpris

        meta = {'mpris:trackid': Variant('o', '/org/exaile/track/%d' % id(track))}
        v = track.get_tag_raw('__length')
        if v:
            meta['mpris:length'] = Variant('x', v * 1e6)
        v = xl.covers.MANAGER.get_cover(track, set_only=True, use_default=False)
        if v:
            f, uri = self._new_cover_file()
            f.write(v)
            f.flush()
            meta['mpris:artUrl'] = Variant('s', uri)

        # xesam

        v = track.get_tag_display('album')
        if v:
            meta['xesam:album'] = Variant('s', v)
        v = track.get_tag_display('artist', join=False)
        if v:
            meta['xesam:artist'] = Variant('as', v)
        v = track.get_tag_raw('genre')
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

    def _on_notify_fullscreen(self, obj, param):
        self._emit_propchange('org.mpris.MediaPlayer2', {'FullScreen': self.FullScreen})

    def _on_playback_track_start(self, event, player, track):
        self._emit_propchange(
            'org.mpris.MediaPlayer2.Player',
            {'Metadata': self.Metadata, 'PlaybackStatus': Variant('s', 'Playing')},
        )

    def _on_playback_track_end(self, event, player, track):
        self._emit_propchange(
            'org.mpris.MediaPlayer2.Player',
            {
                'Metadata': Variant('a{sv}', {}),
                'PlaybackStatus': Variant('s', 'Stopped'),
            },
        )

    def _on_playback_toggle_pause(self, event, player, track):
        self._emit_propchange(
            'org.mpris.MediaPlayer2.Player',
            {
                'PlaybackStatus': Variant(
                    's', 'Paused' if xl.player.PLAYER.is_paused() else 'Playing'
                )
            },
        )

    def _on_player_option_set(self, event, settings, option):
        if option == 'player/volume':
            self._emit_propchange(
                'org.mpris.MediaPlayer2.Player', {'Volume': self.Volume}
            )

    def _return_true(self):  # Positive reply for the "Can*" properties
        return Variant('b', True)

    # Root properties

    CanRaise = CanQuit = CanSetFullScreen = property(_return_true)

    @property
    def DesktopEntry(self):
        return Variant('s', 'exaile')

    @property
    def FullScreen(self):
        return Variant('b', self.exaile.gui.main.props.is_fullscreen)

    @FullScreen.setter
    def FullScreen(self, value):
        self.exaile.gui.main.props.is_fullscreen = value

    @property
    def HasTrackList(self):
        return Variant('b', False)

    @property
    def Identity(self):
        return Variant('s', 'Exaile')

    @property
    def SupportedMimeTypes(self):
        # Taken from exaile.desktop
        mimetypes = [
            'audio/musepack',
            'application/musepack',
            'application/x-ape',
            'audio/ape',
            'audio/x-ape',
            'audio/x-musepack',
            'application/x-musepack',
            'audio/x-mp3',
            'application/x-id3',
            'audio/mpeg',
            'audio/x-mpeg',
            'audio/x-mpeg-3',
            'audio/mpeg3',
            'audio/mp3',
            'audio/x-m4a',
            'audio/mpc',
            'audio/x-mpc',
            'audio/mp',
            'audio/x-mp',
            'application/ogg',
            'application/x-ogg',
            'audio/vorbis',
            'audio/x-vorbis',
            'audio/ogg',
            'audio/x-ogg',
            'audio/x-flac',
            'application/x-flac',
            'audio/flac',
        ]
        return Variant('as', mimetypes)

    @property
    def SupportedUriSchemes(self):
        # TODO: Call GstUriHandler.get_protocols on all GStreamer sources
        # and check if there are other useful protocols.
        return Variant('as', ['file', 'http', 'https', 'nfs', 'smb', 'sftp'])

    # Root methods

    def Raise(self):
        self.exaile.gui.main.window.present()

    def Quit(self):
        self.exaile.quit()

    # Player properties

    CanControl = CanGoNext = CanGoPrevious = CanPause = CanPlay = CanSeek = property(
        _return_true
    )

    @property
    def LoopStatus(self):
        playlist = xl.player.QUEUE.current_playlist
        state = playlist.get_repeat_mode()
        state_map = {'disabled': 'None', 'all': 'Playlist', 'track': 'Track'}
        assert state in state_map
        return Variant('s', state_map[state])

    @LoopStatus.setter
    def LoopStatus(self, value):
        value_s = value.get_string()
        state_map = {'None': 'disabled', 'Playlist': 'all', 'Track': 'track'}
        state = state_map.get(value_s)
        if not state:
            raise ValueError("invalid LoopStatus: %r" % value_s)
        playlist = xl.player.QUEUE.current_playlist
        playlist.set_repeat_mode(state)
        # TODO: Connect to actual event in playlist
        self._emit_propchange('org.mpris.MediaPlayer2.Player', {'LoopStatus': value})

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
        playlist = xl.player.QUEUE.current_playlist
        return Variant('b', playlist.get_shuffle_mode() != 'disabled')

    @Shuffle.setter
    def Shuffle(self, value):
        value_b = value.get_boolean()
        playlist = xl.player.QUEUE.current_playlist
        playlist.set_shuffle_mode('track' if value_b else 'disabled')
        # TODO: Connect to actual event in playlist
        self._emit_propchange(
            'org.mpris.MediaPlayer2.Player', {'Shuffle': Variant('b', value_b)}
        )

    @property
    def Volume(self):
        return Variant('d', xl.settings.get_option('player/volume', 1))

    @Volume.setter
    def Volume(self, value):
        xl.settings.set_option('player/volume', value.get_double())

    # Player methods

    def Next(self):
        if xl.player.PLAYER.is_playing():
            xl.player.QUEUE.next()

    def OpenUri(self, uri):
        pass  # TODO

    def Pause(self):
        xl.player.PLAYER.pause()

    def Play(self):
        player = xl.player.PLAYER
        state = player.get_state()
        if state == 'paused':
            player.unpause()
        elif state == 'stopped':
            queue = xl.player.QUEUE
            queue.play(queue.get_current())
        else:
            assert state == 'playing'  # Don't need to do anything

    def PlayPause(self):
        player = xl.player.PLAYER
        state = player.get_state()
        if state in ('playing', 'paused'):
            player.toggle_pause()
        else:
            assert state == 'stopped'
            queue = xl.player.QUEUE
            queue.play(queue.get_current())

    def Previous(self):
        if xl.player.PLAYER.is_playing():
            xl.player.QUEUE.prev()

    def Seek(self, offset):
        pass  # TODO

    def SetPosition(self, track_id, position):
        if track_id != '/org/exaile/track/%d' % id(xl.player.PLAYER.current):
            return
        xl.player.PLAYER.seek(position / 1e6)
        # TODO: Can we get this event from Exaile?
        self._emit(
            'org.mpris.MediaPlayer2.Player', 'Seeked', GLib.Variant('x', position)
        )

    def Stop(self):
        xl.player.PLAYER.stop()
