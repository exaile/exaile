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

import os

try:
    import ctypes
    modplug = ctypes.cdll.LoadLibrary("libmodplug.so.0")
    modplug.ModPlug_GetName.restype = ctypes.c_char_p
except (ImportError, OSError):
    modplug = None

class ModFormat(BaseFormat):
    MutagenType = FileType #not actually used

    def load(self):
        if modplug:
            data = open(self.loc, "rb").read()
            f = modplug.ModPlug_Load(data, len(data))
            if f:
                name = modplug.ModPlug_GetName(f) or os.path.split(self.loc)[-1]
                length = modplug.ModPlug_GetLength(f) / 1000.0 or -1
                self.mutagen = {'title': name, 'length':length}
        else:
            self.mutagen = {'title':os.path.split(self.loc)[-1]}

    def save(self):
        pass

    def get_length(self):
        try:
            return self.mutagen['length']
        except:
            return -1

    def get_bitrate(self):
        return -1

# vim: et sts=4 sw=4

