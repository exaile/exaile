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


from xl.metadata._base import BaseFormat
from mutagen import asf


class AsfFormat(BaseFormat):
    MutagenType = asf.ASF
    # TODO: figure out the the WM/ prefix is universal
    tag_mapping = {
        # fmt: off
        "artist"        : "Author",
        "album"         : "WM/AlbumTitle",
        "title"         : "Title",
        "genre"         : "WM/Genre",
        "tracknumber"   : "WM/TrackNumber",
        "date"          : "WM/Year",
        "albumartist"   : "WM/AlbumArtist",
        "grouping"      : "WM/ContentGroupDescription"
        # fmt: on
    }
    others = False
    writable = True

    def _get_tag(self, raw, tag_name):
        # the mutagen container for ASF returns the WM/ fields in its own
        # wrappers which are *almost* like a string.. convert them to
        # str so things don't break
        tag = super(AsfFormat, self)._get_tag(raw, tag_name)
        if isinstance(tag, list):
            attrs = [
                asf.ASFUnicodeAttribute,
                asf.ASFDWordAttribute,
                asf.ASFQWordAttribute,
                asf.ASFWordAttribute,
            ]

            def __process_tag(any_tag):
                for attrtype in attrs:
                    if isinstance(any_tag, attrtype):
                        return str(any_tag)
                return any_tag

            return [__process_tag(t) for t in tag]


# vim: et sts=4 sw=4
