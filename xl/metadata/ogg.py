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

from xl.metadata._base import (
    BaseFormat,
    CoverImage
)
from mutagen import oggvorbis
import mutagen.flac
import base64

class OggFormat(BaseFormat):
    MutagenType = oggvorbis.OggVorbis
    writable = True

    def read_tags(self, tags):        
        if "cover" in tags:
            tags[tags.index("cover")]= "metadata_block_picture" 
        td = super(OggFormat, self).read_tags(tags)        
        if 'metadata_block_picture' in td:
            td['cover'] = []
            for d in td["metadata_block_picture"]:
                picture = mutagen.flac.Picture(base64.standard_b64decode(d))
                td['cover'] += [CoverImage(type=picture.type, desc=picture.desc, mime=picture.mime, data=picture.data)]
        return td
# vim: et sts=4 sw=4

