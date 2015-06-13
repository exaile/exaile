from __future__ import division, print_function, unicode_literals

import os
import subprocess
import threading
import tempfile

from gi.repository import Gio


class MoodbarGenerator:
    def generate(self, uri, callback=None):
        """
        :type uri: bytes
        :type callback: Callable[[bytes, bytes], None]
        :rtype: Optional[bytes]
        """
        raise NotImplementedError

    def generate_async(self, uri, callback=None):
        """
        :type uri: bytes
        :type callback: Callable[[bytes, bytes], None]
        """
        t = threading.Thread(name=self.__class__.__name__,
            target=self.generate, args=(uri, callback))
        t.daemon = True
        t.start()


class SpectrumMoodbarGenerator(MoodbarGenerator):
    def generate(self, uri, callback=None):
        path = Gio.File.new_for_uri(uri).get_path()
        data = None
        if path:
            # Reserve a temporary file.
            fd, tmppath = tempfile.mkstemp(b'moodbar.')
            os.close(fd)
            f = None
            try:
                cmd = [b'moodbar', path, b'-o', tmppath]
                subprocess.check_call(cmd)
                f = open(tmppath, 'rb')
                data = f.read()
            except (subprocess.CalledProcessError, IOError):
                pass
            finally:
                if f:
                    f.close()
                os.remove(tmppath)
        if callback:
            callback(uri, data)
        return data


# vi: et sts=4 sw=4 ts=4 tw=99
