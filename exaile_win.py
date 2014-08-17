#!/usr/bin/env python2

"""Launcher for Exaile on Windows"""

from __future__ import division, print_function, unicode_literals

# Make file handles not inheritable, that way we can restart on the fly
# -> From http://www.virtualroadside.com/blog/index.php/2013/02/06/problems-with-file-descriptors-being-inherited-by-default-in-python/
import __builtin__
import msvcrt, sys
from ctypes import windll

    
__builtin__open = __builtins__.open

def __open_inheritance_hack(*args, **kwargs):
    result = __builtin__open(*args, **kwargs)
    handle = msvcrt.get_osfhandle(result.fileno())
    windll.kernel32.SetHandleInformation(handle, 1, 0)
    return result
    
__builtin__.open = __open_inheritance_hack


import logging, os

exailedir = os.path.dirname(os.path.realpath(__file__))
logging.basicConfig(level=logging.INFO, datefmt="%H:%M:%S",
        format="%(levelname)-8s: %(message)s")

def error(message1, message2=None, die=True):
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
    # The first time GStreamer is imported, it hijacks standard args like
    # '--help'. To prevent this, we hide non-gst args and restore them later.
    argv = sys.argv
    sys.argv = [argv[0]]
    sys.argv.extend(a for a in argv if a == '--help-gst' or a.startswith('--gst-'))
    try:
        import pygst
        pygst.require('0.10')
        import gst
    except Exception:
        import struct
        is64bit = len(struct.pack(b'P', 0)) == 8
        logging.info("Python arch: %d-bit" % (64 if is64bit else 32))
        gstroot = os.environ.get('GSTREAMER_SDK_ROOT_X86_64', r'C:\gstreamer-sdk\0.10\x86_64') \
                if is64bit \
                else os.environ.get('GSTREAMER_SDK_ROOT_X86', r'C:\gstreamer-sdk\0.10\x86')
        if not os.path.exists(gstroot):
            error("GStreamer not found",
                    "GStreamer was not found. It can be downloaded from http://www.gstreamer.com/\r\n\r\n" +
                    "See README.Windows for more information.")
        os.environ['PATH'] = gstroot + r'\bin;' + os.environ['PATH']
        gstpypath = gstroot + r'\lib\python2.7\site-packages'
        sys.path.insert(1, gstpypath)
        os.environ['PYTHONPATH'] = gstpypath
        try:
            import pygst
            pygst.require('0.10')
            import gst
        except Exception:
            error("GStreamer Python bindings not found",
                    "The Python bindings for GStreamer could not be imported. Please re-run the GStreamer installer and ensure that \"GStreamer python bindings\" is selected for installation (it should be selected by default).\r\n\r\n" +
                    "GStreamer can be downloaded from http://www.gstreamer.com/\r\n\r\n" +
                    "See README.Windows for more information.")
        else:
            logging.info("GStreamer: %s" % gstroot)
    else:
        logging.info("GStreamer works out of the box")
    finally:
        sys.argv = argv

    try:
        import pygtk
        pygtk.require('2.0')
        import gtk
    except Exception:
        error("GTK/PyGTK not found",
                "PyGTK 2.x could not be imported. Please re-run the GStreamer installer and ensure that \"Gtk toolkit\" and \"Gtk python bindings\" are selected (they should be selected by default). Note that the PyGTK library from pygtk.org is NOT compatible with the GStreamer library from gstreamer.com.\r\n\r\n" +
                "GStreamer can be downloaded from http://www.gstreamer.com/\r\n\r\n" +
                "See README.Windows for more information.")
    else:
        logging.info("PyGTK works")

    try:
        import mutagen
    except Exception:
        error("Mutagen not found",
                "The Python module Mutagen could not be imported. It can be downloaded from http://code.google.com/p/mutagen\r\n\r\n" +
                "See README.Windows for more information.")
    else:
        logging.info("Mutagen works")

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
