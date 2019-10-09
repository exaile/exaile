#
# Allows GTK 3 python applications to exit when CTRL-C is raised
# From https://bugzilla.gnome.org/show_bug.cgi?id=622084
#
# Author: Simon Feltman
# License: Presume same as pygobject
#


import sys
import signal
from typing import ClassVar, List

from gi.repository import GLib


class InterruptibleLoopContext:
    """
    Context Manager for GLib/Gtk based loops.

    Usage of this context manager will install a single GLib unix signal handler
    and allow for multiple context managers to be nested using this single handler.
    """

    #: Global stack context loops. This is added to per InterruptibleLoopContext
    #: instance and allows for context nesting using the same GLib signal handler.
    _loop_contexts: ClassVar[List['InterruptibleLoopContext']] = []

    #: Single source id for the unix signal handler.
    _signal_source_id = None

    @classmethod
    def _glib_sigint_handler(cls, user_data):
        context = cls._loop_contexts[-1]
        context._quit_by_sigint = True
        context._loop_exit_func()

        # keep the handler around until we explicitly remove it
        return True

    def __init__(self, loop_exit_func):
        self._loop_exit_func = loop_exit_func
        self._quit_by_sigint = False

    def __enter__(self):
        # Only use unix_signal_add if this is not win32 and there has
        # not already been one.
        if sys.platform != 'win32' and not InterruptibleLoopContext._loop_contexts:
            # Add a glib signal handler
            source_id = GLib.unix_signal_add(
                GLib.PRIORITY_DEFAULT, signal.SIGINT, self._glib_sigint_handler, None
            )
            InterruptibleLoopContext._signal_source_id = source_id

        InterruptibleLoopContext._loop_contexts.append(self)

    def __exit__(self, exc_type, exc_value, traceback):
        context = InterruptibleLoopContext._loop_contexts.pop()
        assert self == context

        # if the context stack is empty and we have a GLib signal source,
        # remove the source from GLib and clear out the variable.
        if (
            not InterruptibleLoopContext._loop_contexts
            and InterruptibleLoopContext._signal_source_id is not None
        ):
            GLib.source_remove(InterruptibleLoopContext._signal_source_id)
            InterruptibleLoopContext._signal_source_id = None

        if self._quit_by_sigint:
            # caught by _glib_sigint_handler()
            raise KeyboardInterrupt
