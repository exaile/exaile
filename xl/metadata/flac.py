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

import xl.unicode
from xl.metadata._base import CaseInsensitveBaseFormat, CoverImage
from mutagen import flac
from mutagen.flac import Picture


class FlacFormat(CaseInsensitveBaseFormat):
    MutagenType = flac.FLAC
    tag_mapping = {
        'bpm': 'tempo',
        'cover': '__cover',
        'comment': 'description',
        'language': "Language",
    }
    writable = True
    case_sensitive = False

    def get_bitrate(self):
        return -1

    def get_keys_disk(self):
        keys = CaseInsensitveBaseFormat.get_keys_disk(self)
        if self.mutagen.pictures:
            keys.append('cover')
        return keys

    def _get_tag(self, raw, tag):
        if tag == '__cover':
            return [
                CoverImage(type=p.type, desc=p.desc, mime=p.mime, data=p.data)
                for p in raw.pictures
            ]

        return CaseInsensitveBaseFormat._get_tag(self, raw, tag)

    def _set_tag(self, raw, tag, value):
        if tag == '__cover':
            raw.clear_pictures()
            for v in value:
                picture = Picture()
                picture.type = v.type
                picture.desc = v.desc
                picture.mime = v.mime
                picture.data = v.data
                raw.add_picture(picture)
            return

        # flac has text based attributes, so convert everything to unicode
        value = [xl.unicode.to_unicode(v) for v in value]
        CaseInsensitveBaseFormat._set_tag(self, raw, tag, value)

    def _del_tag(self, raw, tag):
        if tag == '__cover':
            raw.clear_pictures()
        elif tag in raw:
            del raw[tag]


# vim: et sts=4 sw=4
