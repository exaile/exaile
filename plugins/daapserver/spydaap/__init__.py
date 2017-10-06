# Copyright (C) 2008 Erik Hetzner

# This file is part of Spydaap. Spydaap is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.

# Spydaap is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Spydaap. If not, see <http://www.gnu.org/licenses/>.

import os
import playlists
import spydaap.parser.mp3
import spydaap.parser.ogg
import spydaap.parser.flac

spydaap_dir = os.path.expanduser("~/.spydaap")
if not(os.path.isdir(spydaap_dir)):
    os.mkdir(spydaap_dir)

server_name = "spydaap"
port = 3689
media_path = os.path.expanduser("~/Music/")
cache_dir = os.path.join(spydaap_dir, "cache")
container_list = [playlists.Library()]
parsers = [spydaap.parser.mp3.Mp3Parser(),
           spydaap.parser.flac.FlacParser(),
           spydaap.parser.ogg.OggParser()]


class ContentRangeFile(object):

    def __init__(self, name, parent, start, end=None, chunk=1024):
        self.name = name
        self.parent = parent
        self.start = start
        self.end = end
        self.chunk = chunk
        self.parent.seek(self.start)
        self.read = start
        self.length = self.end - self.start

    def __len__(self):
        return self.length

    def next(self):
        to_read = self.chunk
        if (self.end is not None):
            if (self.read >= self.end):
                self.parent.close()
                raise StopIteration
            if (to_read + self.read > self.end):
                to_read = self.end - self.read
            retval = self.parent.read(to_read)
            self.read = self.read + len(retval)
        else:
            retval = self.parent.read(to_read)
        if retval == '':
            self.parent.close()
            raise StopIteration
        else:
            return retval

    def __iter__(self):
        return self
