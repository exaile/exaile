# Copyright (C) 2024  Johannes Sasongko <johannes sasongko org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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


import io
import os
import struct
from typing import Tuple

from xl.metadata._base import BaseFormat, NotReadable


class AuFormat(BaseFormat):
    writable = False

    def load(self):
        try:
            with open(self.loc, 'rb', buffering=0) as f:
                file_size = os.stat(f.fileno()).st_size
                bitrate, length = _read_metadata(f, file_size)
        except IOError:
            raise NotReadable
        self.mutagen = {'__bitrate': bitrate, '__length': length}


def _read_metadata(f: io.FileIO, file_size: int) -> Tuple[float, float]:
    """
    :return: bitrate, length
    """

    # See https://en.wikipedia.org/wiki/Au_file_format

    try:
        header = f.read(24)
    except IOError:
        return -1, -1

    # > = big-endian; I = uint32
    magic, data_offset, data_size, encoding, sample_rate, channels = struct.unpack(
        '>IIIIII', header
    )
    if magic != 0x2E736E64:  # '.snd'
        return -1, -1

    # Data size can be unknown (uint32_max) or wrong; try to guess it
    data_size = min(data_size, file_size - data_offset)

    # fmt: off
    ENCODING_WIDTHS = {
        1: 1,
        2: 1, 3: 2, 4: 3, 5: 4,
        6: 4, 7: 8,
        11: 1, 12: 2, 13: 3, 14: 4,
        18: 2, 19: 2, 20: 2,
        27: 1,
    }
    # fmt: on
    try:
        sample_width = ENCODING_WIDTHS[encoding]
    except KeyError:
        return -1, -1

    byterate = sample_rate * sample_width * channels
    return byterate * 8, data_size / byterate
