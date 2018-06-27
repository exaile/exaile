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


from xl.metadata._base import BaseFormat, CoverImage
from mutagen import mp4


class MP4Format(BaseFormat):
    MutagenType = mp4.MP4
    tag_mapping = {
        # fmt: off
        'title':       '\xa9nam',
        'artist':      '\xa9ART',
        'albumartist': '\x61ART',
        'album':       '\xa9alb',
        'composer':    '\xa9wrt',
        'genre':       '\xa9gen',
        'lyrics':      '\xa9lyr',
        'encodedby':   '\xa9too',
        'date':        '\xa9day',
        'tracknumber': 'trkn',
        'discnumber':  'disk',
        'copyright':   'cprt',
        'bpm':         'tmpo',
        'grouping':    '\xa9grp',
        'comment':     '\xa9cmt',
        'originaldate': '----:com.apple.iTunes:ORIGYEAR',
        'cover':       'covr',
        'language':    '----:com.apple.iTunes:LANGUAGE',
        # fmt: on
    }
    others = False
    writable = True

    def _get_tag(self, f, name):
        if name not in f:
            return []
        elif name == 'covr':
            ret = []
            for value in f[name]:
                if value.imageformat == mp4.MP4Cover.FORMAT_PNG:
                    mime = 'image/png'
                else:
                    mime = 'image/jpeg'
                ret.append(CoverImage(type=None, desc=None, mime=mime, data=value))
            return ret
        elif name in ['trkn', 'disk']:
            ret = []
            for value in f[name]:
                ret.append("%d/%d" % (value[0], value[1]))
            return ret
        else:
            return [t for t in f[name]]

    def _set_tag(self, f, name, value):
        if not isinstance(value, list):
            value = [value]
        if name in ['trkn', 'disk']:
            try:
                f[name] = []
                for val in value:
                    tmp = map(int, val.split('/'))
                    f[name].append(tuple(tmp))
            except (TypeError, ValueError):
                pass
        elif name == 'covr':
            f[name] = []

            for val in value:
                if val.mime == 'image/jpeg':
                    f[name].append(mp4.MP4Cover(val.data, mp4.MP4Cover.FORMAT_JPEG))
                elif val.mime == 'image/png':
                    f[name].append(mp4.MP4Cover(val.data, mp4.MP4Cover.FORMAT_JPEG))
                else:
                    raise ValueError(
                        'MP4 does not support cover image type %s' % val.type
                    )
        elif name == 'tmpo':
            f[name] = [int(v) for v in value]
        elif name == '----:com.apple.iTunes:ORIGYEAR':
            f[name] = [str(v) for v in value]
        else:
            f[name] = value


# vim: et sts=4 sw=4
