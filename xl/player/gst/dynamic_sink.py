# Copyright (C) 2008-2010 Adam Olsen
# Copyright (C) 2013-2015 Dustin Spicuzza
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


import threading

from gi.repository import Gst
from gi.repository import GLib

import logging

logger = logging.getLogger(__name__)


class DynamicAudioSink(Gst.Bin):
    """
    An audio sink that can dynamically switch its output

    TODO: When switching outputs rapidly, sometimes it tends to seek
          ahead quite a bit. Not sure why.
    """

    def __init__(self, name):
        Gst.Bin.__init__(self, name=name)

        self.audio_sink = None
        self.__audio_sink_lock = threading.Lock()

        # Create an identity object so we don't need to deal with linking
        # the audio sink with anything external to this bin
        self.identity = Gst.ElementFactory.make('identity', None)
        self.identity.props.signal_handoffs = False
        self.add(self.identity)

        # Create a ghost sink pad so this bin appears to be an audio sink
        sinkpad = self.identity.get_static_pad("sink")
        self.add_pad(Gst.GhostPad.new('sink', sinkpad))

    def reconfigure(self, audio_sink):

        # don't try to switch more than one source at a time
        release_lock = True
        self.__audio_sink_lock.acquire()

        try:

            # If this is the first time we added a sink, just add it to
            # the pipeline and we're done.

            if not self.audio_sink:
                self._add_audiosink(audio_sink, None)
                return

            old_audio_sink = self.audio_sink

            # Ok, time to replace the old sink. If it's not in a playing state,
            # then this isn't so bad.

            # if we don't use the timeout, when we set it to READY, it may be performing
            # an async wait for PAUSE, so we use the timeout here.

            state = old_audio_sink.get_state(timeout=50 * Gst.MSECOND)[1]

            if state != Gst.State.PLAYING:
                buffer_position = None

                if state != Gst.State.NULL:
                    try:
                        buffer_position = old_audio_sink.query_position(Gst.Format.TIME)
                    except Exception:
                        pass

                self.remove(old_audio_sink)
                old_audio_sink.set_state(Gst.State.NULL)

                # Then add the new sink
                self._add_audiosink(audio_sink, buffer_position)

                return

            #
            # Otherwise, disconnecting the old device is a bit complex. Code is
            # derived from algorithm/code described at the following link:
            #
            # https://gstreamer.freedesktop.org/documentation/application-development/advanced/pipeline-manipulation.html
            #

            # Start off by blocking the src pad of the prior element
            spad = old_audio_sink.get_static_pad('sink').get_peer()
            spad.add_probe(
                Gst.PadProbeType.BLOCK_DOWNSTREAM, self._pad_blocked_cb, audio_sink
            )

            # Don't release the lock until pad block is done
            release_lock = False

        finally:
            if release_lock:
                self.__audio_sink_lock.release()

    def _pad_blocked_cb(self, pad, info, new_audio_sink):
        pad.remove_probe(info.id)

        old_audio_sink = self.audio_sink
        buffer_position = old_audio_sink.query_position(Gst.Format.TIME)

        # No data is flowing at this point. Unlink the element, add the new one
        self.remove(old_audio_sink)

        def _flush_old_sink():
            old_audio_sink.set_state(Gst.State.NULL)

        GLib.timeout_add(2000, _flush_old_sink)

        # Add the new element
        self._add_audiosink(new_audio_sink, buffer_position)

        self.__audio_sink_lock.release()

        # And drop the probe, which will cause data to flow again
        return Gst.PadProbeReturn.DROP

    def _add_audiosink(self, audio_sink, buffer_position):
        '''Sets up the new audiosink and syncs it'''

        self.add(audio_sink)
        audio_sink.sync_state_with_parent()
        self.identity.link(audio_sink)

        if buffer_position is not None:

            # buffer position is the output from get_position. If set, we
            # seek to that position.

            # TODO: this actually seems to skip ahead a tiny bit. why?

            # Note! this is super important in paused mode too, because when
            #       we switch the sinks around the new sink never goes into
            #       the paused state because there's no buffer. This forces
            #       a resync of the buffer, so things still work.

            seek_event = Gst.Event.new_seek(
                1.0,
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH,
                Gst.SeekType.SET,
                buffer_position[1],
                Gst.SeekType.NONE,
                0,
            )

            self.send_event(seek_event)

        self.audio_sink = audio_sink


# vim: et sts=4 sw=4
