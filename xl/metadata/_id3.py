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
from mutagen import id3


class ID3Format(BaseFormat):
    MutagenType = id3.ID3
    tag_mapping = {
        "originalalbum": "TOAL",
        "lyricist": "TEXT",
        "part": "TSST",
        "website": "WOAR",
        "cover": "APIC",
        "originalartist": "TOPE",
        "author": "TOLY",
        "originaldate": "TDOR",
        "date": "TDRC",
        "arranger": "TPE4",
        "conductor": "TPE3",
        "albumartist": "TPE2",
        "artist": "TPE1",
        "album": "TALB",
        "copyright": "TCOP",
        "lyrics": "USLT",
        "tracknumber": "TRCK",
        "version": "TIT3",
        "title": "TIT2",
        "isrc": "TSRC",
        "genre": "TCON",
        "composer": "TCOM",
        "encodedby": "TENC",
        "organization": "TPUB",
        "discnumber": "TPOS",
        "bpm": "TBPM",
        "grouping": "TIT1",
        "comment": "COMM",
        'language': "TLAN",
    }
    writable = True
    others = False  # make this true once custom tag support actually works

    def get_keys_disk(self):
        keys = []
        for v in self._get_raw().values():
            # Have to use this because some ID3 tags have a colon
            # in them, and so self._get_raw().keys() doesn't return
            # the expected value
            k = v.FrameID
            if k in self._reverse_mapping:
                keys.append(self._reverse_mapping[k])
            else:
                keys.append(k)
        return keys

    def _get_tag(self, raw, t):
        if not raw.tags:
            return []
        if t not in self.tag_mapping.values():
            t = "TXXX:" + t
        field = raw.tags.getall(t)
        if len(field) <= 0:
            return []
        ret = []
        if t in ('TDRC', 'TDOR'):  # values are ID3TimeStamps, need str conversion
            for value in field:
                ret.extend([str(x) for x in value.text])
        elif t == 'USLT':  # Lyrics are stored in a single str object
            for value in field:
                ret.append(value.text)
        elif (
            t == 'WOAR'
        ):  # URLs are stored in url field instead of text field (as a single str object)
            for value in field:
                ret.append(value.url.replace('\n', '').replace('\r', ''))
        elif t == 'APIC':
            ret = [
                CoverImage(type=f.type, desc=f.desc, mime=f.mime, data=f.data)
                for f in field
            ]
        elif t == 'COMM':  # Newlines within comments are allowed, keep them
            for item in field:
                ret.extend([value for value in item.text])
        else:
            for value in field:
                try:
                    ret.extend(
                        [x.replace('\n', '').replace('\r', '') for x in value.text]
                    )
                except Exception:
                    pass
        return ret

    def _set_tag(self, raw, tag, data):
        if tag not in self.tag_mapping.values():
            tag = "TXXX:" + tag

        if raw.tags is not None:
            raw.tags.delall(tag)

        # FIXME: Properly set and retrieve multiple values
        if tag == 'USLT':
            data = data[0]

        if tag == 'APIC':
            frames = [
                id3.Frames[tag](
                    encoding=3,
                    mime=info.mime,
                    type=info.type,
                    desc=info.desc,
                    data=info.data,
                )
                for info in data
            ]
        elif tag == 'COMM':
            frames = [
                id3.COMM(encoding=3, text=d, desc='', lang='\x00\x00\x00') for d in data
            ]
        elif tag == 'WOAR':
            frames = [id3.WOAR(encoding=3, url=d) for d in data]
        else:
            frames = [id3.Frames[tag](encoding=3, text=data)]

        if raw.tags is not None:
            for frame in frames:
                raw.tags.add(frame)

    def _del_tag(self, raw, tag):
        if tag not in self.tag_mapping.values():
            tag = "TXXX:" + tag
        if raw.tags is not None:
            raw.tags.delall(tag)


# vim: et sts=4 sw=4
