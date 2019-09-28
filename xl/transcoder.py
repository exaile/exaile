# Copyright (C) 2008-2010 Adam Olsen
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

from gi.repository import Gst

from xl.nls import gettext as _
import logging

logger = logging.getLogger(__name__)

"""
    explanation of format dicts:
    default:    the default quality to use, must be a member of raw_steps.
    raw_steps:  a value defining the quality of encoding that will be passed
                to the encoder.
    kbs_steps:  a value defining the quality of encoding that will be displayed
                to the user. must be a one-to-one mapping with raw_steps.
    command:    the gstreamer pipeline to execute. should contain exactly one
                python string format operator, like %s or %f, which will be
                replaced with the value from raw_steps.
    extension:  the default filename extension for this format
    plugins:    the gstreamer plugins needed for this transcode pipeline
    desc:       a description of the encoder to display to the user
"""

FORMATS = {
    # fmt: off
    "Ogg Vorbis" : {
        "default"   : 0.5,
        "raw_steps" : [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
        "kbs_steps" : [64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
        "command"   : "vorbisenc quality=%1.1f ! oggmux",
        "extension" : "ogg",
        "plugins"   : ["vorbisenc", "oggmux"],
        "desc"      : _("Vorbis is an open source, lossy audio codec with "
                        "high quality output at a lower file size than MP3.")
    },
    "FLAC" : {
        "default"   : 5,
        "raw_steps" : [0, 1, 2, 3, 4, 5, 6, 7, 8],
        "kbs_steps" : [0, 1, 2, 3, 4, 5, 6, 7, 8],
        "command"   : "flacenc quality=%i",
        "extension" : "flac",
        "plugins"   : ["flacenc"],
        "desc"      : _("Free Lossless Audio Codec (FLAC) is an open "
                        "source codec that compresses but does not degrade audio "
                        "quality.")
    },
    "AAC"       : {
        "default"   : 160000,
        "raw_steps" : [32000, 48000, 64000, 96000, 128000, 160000,
                       192000, 224000, 256000, 320000],
        "kbs_steps" : [32, 48, 64, 96, 128, 160, 192, 224, 256, 320],
        "command"   : "faac bitrate=%i ! ffmux_mp4",
        "extension" : "m4a",
        "plugins"   : ["faac", "ffmux_mp4"],
        "desc"      : _("Apple's proprietary lossy audio format that "
                        "achieves better sound quality than MP3 at "
                        "lower bitrates.")
    },
    "MP3 (VBR)" : {
        "default"   : 160,
        "raw_steps" : [32, 48, 64, 96, 128, 160, 192, 224, 256, 320],
        "kbs_steps" : [32, 48, 64, 96, 128, 160, 192, 224, 256, 320],
        "command"   : "lame vbr=4 vbr-mean-bitrate=%i",
        "extension" : "mp3",
        "plugins"   : ["lamemp3enc"],
        "desc"      : _("A proprietary and older, but also popular, lossy "
                        "audio format. VBR gives higher quality than CBR, but may "
                        "be incompatible with some players.")
    },
    "MP3 (CBR)" : {
        "default"   : 160,
        "raw_steps" : [32, 48, 64, 96, 128, 160, 192, 224, 256, 320],
        "kbs_steps" : [32, 48, 64, 96, 128, 160, 192, 224, 256, 320],
        "command"   : "lame bitrate=%i",
        "extension" : "mp3",
        "plugins"   : ["lamemp3enc"],
        "desc"      : _("A proprietary and older, but also popular, "
                        "lossy audio format. CBR gives less quality than VBR, "
                        "but is compatible with any player.")
    },
    "WavPack" : {
        "default"   : 2,
        "raw_steps" : [1, 2, 3, 4],
        "kbs_steps" : [1, 2, 3, 4],
        "command"   : "wavpackenc mode=%i",
        "extension" : "wv",
        "plugins"   : ["wavpackenc"],
        "desc"      : _("A very fast Free lossless audio format with "
                        "good compression."),
    },
    # fmt: on
}

# NOTE: the transcoder is NOT designed to transfer tags. You will need to
# manually write the tags after transcoding has completed.


def get_formats():
    ret = {}
    for name, val in FORMATS.items():
        try:
            for plug in val['plugins']:
                x = Gst.ElementFactory.find(plug)
                if not x:
                    raise
            ret[name] = val
        except Exception:
            pass
    return ret


def add_format(name, fmt):
    global FORMATS
    FORMATS[name] = fmt


class TranscodeError(Exception):
    pass


class Transcoder:
    def __init__(self, destformat, quality, error_callback, end_callback):
        self.src = None
        self.sink = None
        self.set_format(destformat)
        self.set_quality(quality)
        self.input = None
        self.output = None
        self.encoder = None
        self.pipe = None
        self.bus = None
        self.running = False
        self.__last_time = 0.0
        self.error_cb = error_callback
        self.end_cb = end_callback

    def set_format(self, name):
        if name in FORMATS:
            self.dest_format = name

    def set_quality(self, value):
        if value in FORMATS[self.dest_format]['raw_steps']:
            self.quality = value

    def _construct_encoder(self):
        fmt = FORMATS[self.dest_format]
        quality = self.quality
        self.encoder = fmt["command"] % quality

    def set_input(self, uri):
        self.input = """filesrc location="%s" """ % uri

    def set_raw_input(self, raw):
        self.input = raw

    def set_output(self, uri):
        self.output = """filesink location="%s" """ % uri

    def set_output_raw(self, raw):
        self.output = raw

    def start_transcode(self):
        self._construct_encoder()
        elements = [
            self.input,
            "decodebin name=\"decoder\"",
            "audioconvert",
            self.encoder,
            self.output,
        ]
        pipestr = " ! ".join(elements)
        logger.info("Starting GStreamer decoder with pipestring: %s", pipestr)
        pipe = Gst.parse_launch(pipestr)
        self.pipe = pipe
        self.bus = pipe.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::error', self.on_error)
        self.bus.connect('message::eos', self.on_eof)

        pipe.set_state(Gst.State.PLAYING)
        self.running = True
        return pipe

    def stop(self):
        self.pipe.set_state(Gst.State.NULL)
        self.running = False
        self.__last_time = 0.0
        self.end_cb()

    def on_error(self, bus, message):
        self.pipe.set_state(Gst.State.NULL)
        self.running = False
        gerror, message_string = message.parse_error()
        self.error_cb(gerror, message_string)
        logger.error(message_string)
        raise gerror

    def on_eof(self, bus, message):
        self.stop()

    def get_time(self):
        if not self.running:
            return 0.0
        try:
            tim = self.pipe.query_position(Gst.Format.TIME)[0]
            tim = tim / Gst.SECOND
            self.__last_time = tim
            return tim
        except Exception:
            return self.__last_time

    def is_running(self):
        return self.running
