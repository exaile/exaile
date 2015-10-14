from __future__ import division, print_function, unicode_literals

import os
import sys


if sys.platform == 'win32':
    import string
    invalid_chars = b'*/:<>?\\'
    TRANS = string.maketrans(invalid_chars, b'-' * len(invalid_chars))


class MoodbarCache:
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
    def __init__(self, location):
        self.loc = location

    def get(self, uri):
        with open(self._get_cache_path(uri), 'rb') as f:
            return f.read()

    def put(self, uri, data):
        if data is None:
            return
        with open(self._get_cache_path(uri), 'wb') as f:
            f.write(data)

    def _get_cache_path(self, uri):
        """
        :type uri: bytes
        :rtype: bytes
        """
        assert isinstance(uri, bytes)
        if uri.startswith(b'file://'):
            uri = uri[7:]
        uri = uri.replace(b"'", b"")
        if sys.platform == 'win32':
            uri = string.replace(b'"', b'').translate(uri, TRANS)
        else:
            uri = uri.replace(b'/', b'-')
        return os.path.join(self.loc, uri + b'.mood')


# vi: et sts=4 sw=4 ts=4 tw=99
