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

import os
import subprocess
import threading
import tempfile

from gi.repository import Gio


class MoodbarGeneratorError(Exception):
    pass


class MoodbarGenerator(object):

    def check(self):
        """Check whether the generator works.

        For example, this can check for the presence of a `moodbar` executable.
        However, it does not guarantee that the moodbar generator will run
        without any errors during the generation process.

        :rtype: None
        :raise MoodbarGeneratorError: if the check fails
        """
        raise NotImplementedError

    def generate(self, uri, callback=None):
        """
        :type uri: bytes
        :type callback: Callable[[bytes, bytes], None]
        :rtype: Optional[bytes]
        :raise MoodbarGeneratorError: on any error while generating moodbar
        """
        raise NotImplementedError

    def generate_async(self, uri, callback=None):
        """
        :type uri: bytes
        :type callback: Callable[[bytes, bytes], None]
        """
        thread = threading.Thread(name=self.__class__.__name__,
                                  target=self.generate, args=(uri, callback))
        thread.daemon = True
        thread.start()


class SpectrumMoodbarGenerator(MoodbarGenerator):

    def check(self):
        try:
            with open(os.devnull, 'wb') as devnull:
                subprocess.check_call(('moodbar', '--help'), stdout=devnull)
        except Exception:
            raise MoodbarGeneratorError("Failed to run moodbar; make sure it is installed")

    def generate(self, uri, callback=None):
        path = Gio.File.new_for_uri(uri).get_path()
        data = None
        if path:
            tmppath = f = None
            try:
                # Reserve a temporary file.
                fd, tmppath = tempfile.mkstemp(prefix=b'moodbar.')
                os.close(fd)

                cmd = (b'moodbar', b'-o', tmppath, path)
                subprocess.check_call(cmd)
                f = open(tmppath, 'rb')
                data = f.read()
            except Exception as e:
                # TODO propagate this error to UI, make sure to install required GStreamer plugins
                raise MoodbarGeneratorError(e)
            finally:
                if f:
                    f.close()
                if tmppath and os.path.exists(tmppath):
                    os.remove(tmppath)
        if callback:
            callback(uri, data)
        return data


# vi: et sts=4 sw=4 tw=99
