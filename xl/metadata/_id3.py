# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

from xl.metadata import BaseFormat
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
        "performer": "TPE2",
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
        }
    others = False #disallow tags not in the mapping
    writable = True

    def _get_tag(self, raw, t):
        if not raw.tags: return []
        field = raw.tags.getall(t)
        if len(field) <= 0:
            return []
        ret = []
        if t == 'TDRC' or t == 'TDOR': # values are ID3TimeStamps
            for value in field:
                ret.extend([unicode(x) for x in value.text])
        elif t == 'USLT': # Lyrics are stored in plan old strings
            for value in field:
                ret.append(value.text)
        elif t == 'WOAR': # URLS are stored in url not text
            for value in field:
                ret.extend([unicode(x.replace('\n','').replace('\r','')) \
                        for x in value.url])
        else:
            for value in field:
                try:
                    ret.extend([unicode(x.replace('\n','').replace('\r','')) \
                        for x in value.text])
                except:
                    logger.warning("Can't parse ID3 field")
                    common.log_exception()
        return ret

    def _set_tag(self, raw, tag, data):
        raw.delall(tag)
        frame = id3.Frames[tag](encoding=3, text=data)
        raw.add(frame)


# vim: et sts=4 sw=4

