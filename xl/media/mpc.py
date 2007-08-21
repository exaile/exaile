import os
import mutagen.apev2

TYPE = 'mpc'

# the tags are nearly identical, but we do this anyway for consistency
TAG_TRANSLATION = {
    'artist':       'artist',
    'title':        'title',
    'album':        'album',
    'genre':        'genre',
    'track':        'tracknumber',
    'copyright':    'copyright',
    'isrc':         'isrc',
}

# this code taken from quodlibet
try:
    import ctypes
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    _mpcdec = ctypes.cdll.LoadLibrary("libmpcdec.so.3")
except (ImportError, OSError):
    _libc = None
else:
    def _get_errno():
        return ctypes.c_int.in_dll(_libc, "errno").value

    mpc_bool_t = ctypes.c_uint8
    mpc_int16_t = ctypes.c_int16
    mpc_int32_t = ctypes.c_int32
    mpc_int64_t = ctypes.c_int64
    mpc_uint16_t = ctypes.c_uint16
    mpc_uint32_t = ctypes.c_uint32
    mpc_streaminfo_off_t = mpc_int32_t

    class _MPCReader(ctypes.Structure):
        _fields_ = [('read', ctypes.c_void_p),
                    ('seek', ctypes.c_void_p),
                    ('tell', ctypes.c_void_p),
                    ('get_size', ctypes.c_void_p),
                    ('canseek', ctypes.c_void_p),
                    # Actually, all the above are function pointers
                    ('data', ctypes.c_void_p)
                    ]

    class _MPCReaderFile(ctypes.Structure):
        _fields_ = [("reader", _MPCReader),
                    ("file", ctypes.c_void_p), # actually FILE*
                    ("file_size", ctypes.c_long),
                    ("is_seekable", mpc_bool_t)]

    class _MPCStreamInfo(ctypes.Structure):
        _fields_ = [("sample_freq", mpc_uint32_t),
                    ("channels", mpc_uint32_t),
                    ("header_position", mpc_streaminfo_off_t),
                    ("stream_version", mpc_uint32_t),
                    ("bitrate", mpc_uint32_t),
                    ("average_bitrate", ctypes.c_double),
                    ("frames", mpc_uint32_t),
                    ("pcm_samples", mpc_int64_t),
                    ("max_band", mpc_uint32_t),
                    ("istereo", mpc_uint32_t), # 'is' is a Python keyword
                    ('ms', mpc_uint32_t),
                    ("block_size", mpc_uint32_t),
                    ("profile", mpc_uint32_t),
                    ("profile_name", ctypes.c_char_p),
                    ("gain_title", mpc_int16_t),
                    ("gain_album", mpc_int16_t),
                    ("peak_title", mpc_uint16_t),
                    ("peak_album", mpc_uint16_t),

                    ("is_true_gapless", mpc_uint32_t),
                    ("last_frame_samples", mpc_uint32_t),
                    ("encoder_version", mpc_uint32_t),
                    ("encoder", ctypes.c_char * 256),
                    ("tag_offset", mpc_streaminfo_off_t),
                    ("total_file_length", mpc_streaminfo_off_t),
                    ]

    _mpcdec.mpc_reader_setup_file_reader.argtypes = [
        ctypes.POINTER(_MPCReaderFile), ctypes.c_void_p]

    _mpcdec.mpc_streaminfo_read.argtypes = [
        ctypes.POINTER(_MPCStreamInfo), ctypes.POINTER(_MPCReader)]

    _mpcdec.mpc_streaminfo_get_length.restype = ctypes.c_double

def get_tag(tagset, tag):
    try:
        return [unicode(t) for t in tagset[tag]]
    except KeyError:
        return []
    
def write_tag(tr):
    try: info = mutagen.apev2.APEv2(tr.io_loc)
    except mutagen.apev2.APENoHeaderError:
        info = mutagen.apev2.APEv2()

    for mpc_tag, tag in TAG_TRANSLATION.iteritems():
        if tr.tags[tag]:
            info[mpc_tag] = tr.tags[tag]

    tag.save(tr.io_loc)

def can_change(tag):
    return tag in TAG_TRANSLATION.values()

def is_multi():
    return True

def fill_tag_from_path(tr):
    try: info = mutagen.apev2.APEv2(tr.io_loc)
    except mutagen.apev2.APENoHeaderError: return

    for mpc_tag, tag in TAG_TRANSLATION.iteritems():
        tr.tags[tag] = get_tag(info, mpc_tag)

    # determine length and bitrate with the code from quodlibet
    if _libc:
        reader = _MPCReaderFile()
        f = _libc.fopen(tr.io_loc, "r")
        if not f: raise OSError(os.strerror(_get_errno()))
        _mpcdec.mpc_reader_setup_file_reader(
            ctypes.pointer(reader), ctypes.c_void_p(f))
        info = _MPCStreamInfo()

        if _mpcdec.mpc_streaminfo_read(
            ctypes.byref(info), ctypes.byref(reader.reader)):
            raise IOError("not a valid Musepack file")

        tr.length = int(
            _mpcdec.mpc_streaminfo_get_length(ctypes.byref(info)))
        tr.bitrate = int(info.average_bitrate)
        _libc.fclose(reader.file)
                   
