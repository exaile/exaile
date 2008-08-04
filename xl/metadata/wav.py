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
import wave

class WavFormat(BaseFormat):
    def load(self):
        try:
            f = wave.open(self.loc, "rb")
            bitrate = f.getframerate()
            length = f.getnframes() / bitrate
            self.mutagen = {'bitrate': bitrate, 'length': length}
        except IOError:
            pass
        self.mutagen = {'bitrate': -1, 'length': -1}
        

