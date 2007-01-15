from xl.formats import mp3, ogg, flac
import xl.media
import os.path

__all__ = ['flac', 'mp3', 'm4a', 'ogg', 'wma']

formats = {
    'mp3':      mp3,
    'mp2':      mp3,
    'ogg':      ogg,
    'flac':     flac
}

# for m4a support
try:
    from xl.formats import m4a
    formats['m4a'] = m4a
except ImportError: pass

# for wma support
try:
    from xl.formats import wma
    formats['wma'] = wma
except ImportError: pass

SUPPORTED_MEDIA = ['.%s' % x for x in formats.keys()]
# generic functions
def read_from_path(uri):
    """
        Reads tags from a specified uri
    """
    (path, ext) = os.path.splitext(uri.lower())
    ext = ext.replace('.', '')

    if not formats.has_key(ext):
        raise Exception('%s format is not understood' % ext)

    tr = xl.media.Track(uri)
    tr.type = ext
    formats[ext].fill_tag_from_path(tr)
    return tr
