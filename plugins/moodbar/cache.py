# moodbar - Replace Exaile's seekbar with a moodbar
# Copyright (C) 2015  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import hashlib
import os
from typing import Optional


class MoodbarCache:
    """Cache for moodbar files"""

    def __init__(self, location: str):
        try:
            os.mkdir(location)
        except OSError:
            pass
        self.__loc = location

    def get(self, uri: str) -> Optional[bytes]:
        try:
            with open(self._get_cache_path(uri), 'rb') as cachefile:
                return cachefile.read()
        except IOError:
            return None

    def put(self, uri: str, data: bytes) -> None:
        if data is None:
            return
        with open(self._get_cache_path(uri), 'wb') as cachefile:
            cachefile.write(data)

    def _get_cache_path(self, uri: str) -> str:
        hex_str = hashlib.sha256(uri.encode('utf-8')).hexdigest()
        return os.path.join(self.__loc, hex_str + '.mood')
