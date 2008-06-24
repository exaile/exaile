
import pygst
pygst.require("0.10")
import gst

"""
    explanation of format dicts:
    default:    the default quality to use, must be a member of raw_steps.
    raw_steps:  a value defining the quality of encoding that will be passed 
                to the encoder.
    kbs_steps:  a value defining the quality of encoding that will be displayed
                to the user. must be a one-to-one mapping with raw_steps.
    command:    the gstreamer pipeline to execute. should contain exactly one 
                %s, which will be replaced with the value from raw_steps.
    plugins:    the gstreamer plugins needed for this transcode pipeline
    desc:       a description of the encoder to display to the user
"""

FORMATS = {
        "Ogg Vorbis" : {
            "default"   : 5,
            "raw_steps" : (0 ,  1,  2,   3,   4,   5,   6,   7,   8,   9,  10),
            "kbs_steps" : (64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 400),
            "command"   : "vorbisenc quality=0.%s ! oggmux",
            "extension" : "ogg",
            "plugins"   : ("vorbisenc", "oggmux"),
            "desc"      : "Vorbis is an open source, lossy audio codec with high quality output at a lower file size than MP3."
            },
        "FLAC" : {
            "default"   : 5,
            "raw_steps" : (0 ,  1,  2,   3,   4,   5,   6,   7,   8,   9),
            "command"   : "flacenc quality=%s",
            "extension" : "flac",
            "plugins"   : ("flacenc"),
            "desc"      : "Free Lossless Audio Codec (FLAC) is an open source codec that compresses but does not degrade audio quality."
            },
        "AAC"       : {
            "default"   : 160000,
            "raw_steps" : (32000, 48000, 64000, 96000, 128000, 160000, 
                    192000, 224000, 256000, 320000),
            "kbs_steps" : (32, 48, 64, 96, 128, 160, 192, 224, 256, 320),
            "command"   : "faac bitrate=%s ! ffmux_mp4",
            "extension" : "aac",
            "plugins"   : ("faac", "ffmux_mp4"),
            "desc"      : "Apple's proprietary lossy audio format that achieves better sound quality than MP3 at lower bitrates."
            },
        "MP3 (VBR)" : {
            "default"   : 160,
            "raw_steps" : (32, 48, 64, 96, 128, 160, 192, 224, 256, 320),
            "kbs_steps" : (32, 48, 64, 96, 128, 160, 192, 224, 256, 320),
            "command"   : "lame vbr=4 vbr-mean-bitrate=%s ! id3mux",
            "extension" : "mp3",
            "plugins"   : ("lame", "id3mux"),
            "desc"      : "A proprietary and older, but also popular, lossy audio format that produces larger files at lower bitrates. VBR gives higher quality than CBR, but may be incompatible with some players."
            },
        "MP3 (CBR)" : {
            "default"   : 160,
            "raw_steps" : (32, 48, 64, 96, 128, 160, 192, 224, 256, 320),
            "kbs_steps" : (32, 48, 64, 96, 128, 160, 192, 224, 256, 320),
            "command"   : "lame bitrate=%s ! id3mux",
            "extension" : "mp3",
            "plugins"   : ("lame", "id3mux"),
            "desc"      : "A proprietary and older, but also popular, lossy audio format that produces larger files at lower bitrates. CBR gives less quality than VBR, but is compatible with any player."
            }
        }

def get_formats(self):
    ret = {}
    for name, val in FORMATS.iteritems():
        try:
            for plug in val['plugins']:
                x = gst.element_factory_find(plug)
                if not x:
                    raise
            ret[name] = val
        except:
            pass
    return ret

def add_format(self, name, format):
    global FORMATS
    FORMATS[name] = format


class Transcoder(object):
    def __init__(self):
        self.src = None
        self.sink = None
        self.dest_format = None
        self.quality = None
        self.input = None
        self.output = None
        self.encoder = None
        self.pipe = None
        self.bus = None

    def set_format(self, name):
        self.dest_format = name

    def set_quality(self, value):
        self.quality = value

    def _construct_encoder(self):
        if not self.dest_format:
            format = FORMATS["Ogg Vorbis"]
        else:
            format = FORMATS[self.dest_format]
        if self.quality not in format["raw_steps"]:
            quality = format["default"]
        else:
            quality = self.quality
        self.encoder = format["command"]%quality

    def set_input(self, uri):
        self.input = """filesrc location="%s" """%uri

    def set_raw_input(self, raw):
        self.input = raw

    def set_output(self, uri):
        self.output = """filesink location="%s" """%uri

    def set_output_raw(self, raw):
        self.output = raw

    def start_transcode(self): 
        self._construct_encoder()
        elements = [ self.input, "decodebin", "audioconvert", 
                self.encoder, self.output ]
        pipestr = " ! ".join( elements )
        print pipestr
        pipe = gst.parse_launch(pipestr)
        self.pipe = pipe
        self.bus = pipe.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::error', self.on_error)
        self.bus.connect('message::eof', self.on_eof)

        pipe.set_state(gst.STATE_PLAYING)
        return pipe

    def stop(self):
        self.pipe.set_state(gst.STATE_NULL)

    def on_error(self, *args):
        print args #FIXME: actually do something here

    def on_eof(self, *args):
        self.pipe.set_state(gst.STATE_NULL)

    def get_progress(self):
        raise NotImplementedError #TODO: implement
