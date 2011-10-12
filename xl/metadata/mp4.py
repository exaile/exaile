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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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



from xl.metadata._base import BaseFormat
from mutagen import mp4

class MP4Format(BaseFormat):
    MutagenType = mp4.MP4
    tag_mapping = {
            'title':       '\xa9nam',
            'artist':      '\xa9ART',
            'albumartist': '\x61ART',
            'album':       '\xa9alb',
            'genre':       '\xa9gen',
            'date':        '\xa9day',
            'tracknumber': 'trkn',
            'discnumber':  'disk',
            'copyright':   'cprt',
            'grouping':    '\xa9grp'
        }
    others = False
    writable = True

    def _get_tag(self, f, name):
        if not f.has_key(name):
            return []
        elif name in ['trkn', 'disk']:
            ret = []
            for value in f[name]:
                ret.append("%d/%d" % (value[0], value[1]))
            return ret
        else: return [t for t in f[name]]

    def _set_tag(self, f, name, value):
        if type(value) is not list: value = [value]
        if name in ['trkn', 'disk']:
            try:
                f[name] = []
                for val in value:
                    tmp = map(int, val.split('/'))
                    f[name].append(tuple(tmp))
            except TypeError:
                pass
        else:
            f[name] = value

# vim: et sts=4 sw=4
