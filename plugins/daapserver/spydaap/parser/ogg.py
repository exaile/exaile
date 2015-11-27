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

import spydaap.parser.vorbis
import re
from spydaap.daap import do


class OggParser(spydaap.parser.vorbis.VorbisParser):
    file_re = re.compile(".*\\.[oO][gG][gG]$")

    def understands(self, filename):
        return self.file_re.match(filename)

    def parse_extra_vorbis(self, filename, md, daap):
        daap.extend([do('daap.songbitrate', md.info.bitrate / 1000),
                     do('daap.songformat', 'ogg'),
                     do('daap.songdescription', 'Ogg/Vorbis Audio File')])
