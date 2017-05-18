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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import division, print_function, unicode_literals

import hashlib
import os


class MoodbarCache(object):
    """ Abstract class for a cache for moodbar metadata files """

    def get(self, uri):
        """
        :type uri: bytes
        :rtype: bytes
        """
        raise NotImplementedError

    def put(self, uri, data):
        """
        :type uri: bytes
        :type data: bytes
        """
        raise NotImplementedError


class ExaileMoodbarCache(MoodbarCache):
    """ Exaile's implementation of a cache for moodbar files """

    __loc = None

    def __init__(self, location):
        try:
            os.mkdir(location)
        except OSError:
            pass
        self.__loc = location

    def get(self, uri):
        try:
            with open(self._get_cache_path(uri), 'rb') as cachefile:
                return cachefile.read()
        except IOError:
            return None

    def put(self, uri, data):
        if data is None:
            return
        with open(self._get_cache_path(uri), 'wb') as cachefile:
            cachefile.write(data)

    def _get_cache_path(self, uri):
        hex_str = hashlib.sha256(uri).hexdigest()
        return os.path.join(self.__loc, hex_str + b'.mood')


# vi: et sts=4 sw=4 tw=99
