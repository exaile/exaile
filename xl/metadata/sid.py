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
from mutagen import FileType

class SidFormat(BaseFormat):
    MutagenType = FileType #not actually used

    def load(self):
        f = open(self.loc, "rb")
        f.seek(22)
        data = {}
        data['title'] = f.read(32).replace(chr(0), "")
        data['artist'] = f.read(32).replace(chr(0), "")
        data['copyright'] = f.read(32).replace(chr(0), "")
        f.close()
        self.mutagen = data

    def get_length(self):
        return -1

    def get_bitrate(self):
        return -1
