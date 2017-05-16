import sys


def get_default_encoding():
    """
        Returns the encoding to be used when dealing with file paths.  Do not
        use for other purposes.
    """
    # return 'utf-8'
    return sys.getfilesystemencoding() or sys.getdefaultencoding()
