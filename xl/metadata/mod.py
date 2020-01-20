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

import logging
import os


logger = logging.getLogger(__name__)


try:
    import ctypes

    modplug = ctypes.cdll.LoadLibrary("libmodplug.so.1")
    modplug.ModPlug_Load.restype = ctypes.c_void_p
    modplug.ModPlug_Load.argtypes = (ctypes.c_void_p, ctypes.c_int)
    modplug.ModPlug_GetName.restype = ctypes.c_char_p
    modplug.ModPlug_GetName.argtypes = (ctypes.c_void_p,)
    modplug.ModPlug_GetLength.restype = ctypes.c_int
    modplug.ModPlug_GetLength.argtypes = (ctypes.c_void_p,)
except (ImportError, OSError):
    logger.debug('No support for Mod metadata because libmodplug could not be found.')
    modplug = None


class ModFormat(BaseFormat):
    writable = False

    def load(self):
        if modplug:
            data = open(self.loc, "rb").read()
            f = modplug.ModPlug_Load(data, len(data))
            if f:
                name = modplug.ModPlug_GetName(f) or os.path.split(self.loc)[-1]
                length = modplug.ModPlug_GetLength(f) / 1000.0 or -1
                self.mutagen = {'title': name, '__length': length}
        else:
            self.mutagen = {}

    def get_length(self):
        try:
            return self.mutagen['__length']
        except KeyError:
            return -1

    def get_bitrate(self):
        return -1


# vim: et sts=4 sw=4
