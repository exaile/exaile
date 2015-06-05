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
        t.run()


class SpectrumMoodbarGenerator(MoodbarGenerator):
    def generate(self, uri, callback=None):
        f, tmppath = tempfile.mkstemp(prefix=b'moodbar.')
        os.close(f)
        inpath = Gio.File.new_for_uri(uri).get_path()
        data = None
        if inpath:
            cmd = [b'moodbar', inpath, b'-o', tmppath]
            status = subprocess.Popen(cmd).wait()
            if status == 0:
                f = open(tmppath, 'rb')
                try:
                    data = f.read()
                except IOError:
                    f.close()
                    # Swallow error
        try:
            os.remove(tmppath)
        except IOError:
            pass
        if callback:
            callback(uri, data)
        return data


# vi: et sts=4 sw=4 ts=4 tw=99
