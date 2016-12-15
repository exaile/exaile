#!/usr/bin/env python2

"""Launcher for Exaile on Windows"""

from __future__ import division, print_function, unicode_literals

# Make file handles not inheritable, that way we can restart on the fly
# -> From http://www.virtualroadside.com/blog/index.php/2013/02/06/problems-with-file-descriptors-being-inherited-by-default-in-python/
import __builtin__
import msvcrt
import sys
from ctypes import windll


__builtin__open = __builtins__.open


def __open_inheritance_hack(*args, **kwargs):
    result = __builtin__open(*args, **kwargs)
    handle = msvcrt.get_osfhandle(result.fileno())
    windll.kernel32.SetHandleInformation(handle, 1, 0)
    return result

__builtin__.open = __open_inheritance_hack


def error(message1, message2=None, die=True):

    import logging

    """Show error message and exit.

    If two message arguments are supplied, the first one will be used as title.
    If `die` is true, exit after showing the message.
    """
    logging.error(message1 + (('\r\n\r\n' + message2) if message2 else ''))
    if sys.stdout.isatty():
        if die:
            print("\r\n[Press Enter to exit.]", file=sys.stderr)
            raw_input()
    else:
        import ctypes
        if not message2:
            message1, message2 = message2, message1
        ctypes.windll.user32.MessageBoxW(None, message2, message1, 0x10)
    if die:
        sys.exit(1)


def main():

    import logging
    logging.basicConfig(level=logging.INFO, datefmt="%H:%M:%S",
                        format="%(levelname)-8s: %(message)s")

    aio_message = "\r\n\r\nPlease run the 'All-In-One PyGI/PyGObject for " + \
        "Windows Installer' and ensure that the following are selected:" + \
                  "\r\n\r\n" + \
                  "* GTK+ 3.x\r\n" + \
                  "* GStreamer 1.x and the gst-plugins package(s)\r\n" + \
                  "\r\n" + \
                  "The 'All-In-One PyGI/PyGObject for Windows Installer' " + \
                  "can be downloaded at\r\n" + \
                  "http://sourceforge.net/projects/pygobjectwin32/\r\n\r\n" + \
                  "See README.Windows for more information."

    try:
        import gi
    except Exception:
        error("PyGObject not found",
              "PyGObject could not be imported. " + aio_message)
    else:
        logging.info("PyGObject works")
    try:
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
    except Exception:
        error("GTK+ not found",
              "GTK+ could not be imported. " + aio_message)
    else:
        logging.info("GTK+ works")

    try:
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
    except Exception:
        error("GStreamer not found",
              "GStreamer could not be imported. " + aio_message)
    else:
        logging.info("GStreamer works")

    try:
        import mutagen
    except Exception:
        error("Mutagen not found",
              "The Python module Mutagen could not be imported. It can be " +
              "downloaded from http://code.google.com/p/mutagen\r\n\r\n" +
              "See README.Windows for more information.")
    else:
        logging.info("Mutagen works")

    # disable the logging before starting exaile.. otherwise it gets
    # configured twice and we get double the log messages!
    logging = None
    del sys.modules['logging']

    try:
        sys.argv[1:1] = ['--startgui', '--no-dbus', '--no-hal']
        import exaile
        exaile.main()
    except Exception:
        import traceback
        traceback.print_exc()
        raw_input()

if __name__ == '__main__':
    main()

# vi: et sts=4 sw=4 ts=4
