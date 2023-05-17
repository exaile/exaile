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
from xl.metadata._base import CaseInsensitiveBaseFormat, CoverImage
from xl import settings
from mutagen import oggvorbis, oggopus
from mutagen.flac import Picture
import base64


class OggFormat(CaseInsensitiveBaseFormat):
    MutagenType = oggvorbis.OggVorbis
    tag_mapping = {
        'cover': 'metadata_block_picture',
        '__rating': 'rating',
    }
    writable = True

    def _get_tag(self, raw, tag):
        value = CaseInsensitiveBaseFormat._get_tag(self, raw, tag)
        if value and tag == 'metadata_block_picture':
            new_value = []
            for v in value:
                picture = Picture(base64.b64decode(v))
                new_value.append(
                    CoverImage(
                        type=picture.type,
                        desc=picture.desc,
                        mime=picture.mime,
                        data=picture.data,
                    )
                )
            value = new_value
        if value and tag == 'rating':
            value = [str(self._rating_to_stars(int(value[0])))]

        elif tag == 'bpm':
            if (
                settings.get_option('collection/use_legacy_metadata_mapping', False)
                and 'tempo' in raw
            ):
                value = CaseInsensitiveBaseFormat._get_tag(self, raw, 'tempo')

        elif tag == 'comment':
            if (
                settings.get_option('collection/use_legacy_metadata_mapping', False)
                and 'description' in raw
            ):
                value = CaseInsensitiveBaseFormat._get_tag(self, raw, 'description')

        return value

    def _set_tag(self, raw, tag, value):
        if tag == 'metadata_block_picture':
            new_value = []
            for v in value:
                picture = Picture()
                picture.type = v.type
                picture.desc = v.desc
                picture.mime = v.mime
                picture.data = v.data
                tmp = base64.b64encode(picture.write())
                tmp = tmp.decode('ascii')  # needs to be a str
                new_value.append(tmp)
            value = new_value
        elif tag == 'rating':
            rating = self._stars_to_rating(value[0])
            value = [str(rating)]
        elif tag == 'bpm':
            if settings.get_option('collection/use_legacy_metadata_mapping', False):
                tag = 'tempo'
            value = [xl.unicode.to_unicode(v) for v in value]
        elif tag == 'comment':
            if settings.get_option('collection/use_legacy_metadata_mapping', False):
                tag = 'description'
            value = [xl.unicode.to_unicode(v) for v in value]
        else:
            # vorbis has text based attributes, so convert everything to unicode
            value = [xl.unicode.to_unicode(v) for v in value]
        CaseInsensitiveBaseFormat._set_tag(self, raw, tag, value)


class OggOpusFormat(OggFormat):
    MutagenType = oggopus.OggOpus
