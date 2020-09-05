# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

"""
Provides a signals-like system for sending and listening for 'events'


Events are kind of like signals, except they may be listened for on a
global scale, rather than connected on a per-object basis like signals
are. This means that ANY object can emit ANY event, and these events may
be listened for by ANY object.

Events should be emitted AFTER the given event has taken place. Often the
most appropriate spot is immediately before a return statement.
"""

from inspect import ismethod
import logging
import re
import threading
import time
import types
import weakref
from gi.repository import GLib

# define this here so the interpreter doesn't complain
EVENT_MANAGER = None

logger = logging.getLogger(__name__)


class Nothing:
    pass


_NONE = Nothing()  # used by event for a safe None replacement

# Assumes that this module was imported on main thread
_UiThread = threading.current_thread()


def log_event(evty, obj, data):
    """
    Sends an event.

    :param evty: the *type* or *name* of the event.
    :type evty: string
    :param obj: the object sending the event.
    :type obj: object
    :param data: some data about the event, None if not required
    :type data: object
    """
    global EVENT_MANAGER
    e = Event(evty, obj, data)
    EVENT_MANAGER.emit(e)


def add_callback(function, evty=None, obj=None, *args, **kwargs):
    """
    Adds a callback to an event

    You should ALWAYS specify one of the two options on what to listen
    for. While not forbidden to listen to all events, doing so will
    cause your callback to be called very frequently, and possibly may
    cause slowness within the player itself.

    :param function: the function to call when the event happens
    :type function: callable
    :param evty: the *type* or *name* of the event to listen for, eg
            `tracks_added`, `cover_changed`. Defaults to any event if
            not specified.
    :type evty: string
    :param obj: the object to listen to events from, e.g. `exaile.collection`
            or `xl.covers.MANAGER`. Defaults to any object if not
            specified.
    :type obj: object
    :param destroy_with: (keyword arg only) If specified, this event will be
                         detached when the specified Gtk widget is destroyed

    Any additional parameters will be passed to the callback.

    :returns: a convenience function that you can call to remove the callback.
    """
    global EVENT_MANAGER
    return EVENT_MANAGER.add_callback(function, evty, obj, args, kwargs)


def add_ui_callback(function, evty=None, obj=None, *args, **kwargs):
    """
    Adds a callback to an event. The callback is guaranteed to
    always be called on the UI thread.

    You should ALWAYS specify one of the two options on what to listen
    for. While not forbidden to listen to all events, doing so will
    cause your callback to be called very frequently, and possibly may
    cause slowness within the player itself.

    :param function: the function to call when the event happens
    :type function: callable
    :param evty: the *type* or *name* of the event to listen for, eg
            `tracks_added`, `cover_changed`. Defaults to any event if
            not specified.
    :type evty: string
    :param obj: the object to listen to events from, e.g. `exaile.collection`
            or `xl.covers.MANAGER`. Defaults to any object if not
            specified.
    :type obj: object
    :param destroy_with: (keyword arg only) If specified, this event will be
                         detached when the specified Gtk widget is destroyed

    Any additional parameters will be passed to the callback.

    :returns: a convenience function that you can call to remove the callback.
    """
    global EVENT_MANAGER
    return EVENT_MANAGER.add_callback(function, evty, obj, args, kwargs, ui=True)


def remove_callback(function, evty=None, obj=None):
    """
    Removes a callback. Can remove both ui and non-ui callbacks.

    The parameters passed should match those that were passed when adding
    the callback
    """
    global EVENT_MANAGER
    EVENT_MANAGER.remove_callback(function, evty, obj)


class Event:
    """
    Represents an Event
    """

    __slots__ = ['type', 'object', 'data']

    def __init__(self, evty, obj, data):
        """
        evty: the 'type' or 'name' for this Event [string]
        obj: the object emitting the Event [object]
        data: some piece of data relevant to the Event [object]
        """
        self.type = evty
        self.object = obj
        self.data = data


class Callback:
    """
    Represents a callback
    """

    __slots__ = ['wfunction', 'time', 'args', 'kwargs']

    def __init__(self, function, time, args, kwargs):
        """
        @param function: the function to call
        @param time: the time this callback was added
        """
        self.wfunction = _getWeakRef(function)
        self.time = time
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return '<Callback %s>' % self.wfunction()


class _WeakMethod:
    """Represent a weak bound method, i.e. a method doesn't keep alive the
    object that it is bound to. It uses WeakRef which, used on its own,
    produces weak methods that are dead on creation, not very useful.
    Typically, you will use the getRef() function instead of using
    this class directly."""

    def __init__(self, method, notifyDead=None):
        """
        The method must be bound. notifyDead will be called when
        object that method is bound to dies.
        """
        assert ismethod(method)
        if method.__self__ is None:
            raise ValueError("We need a bound method!")
        if notifyDead is None:
            self.objRef = weakref.ref(method.__self__)
        else:
            self.objRef = weakref.ref(method.__self__, notifyDead)
        self.fun = method.__func__

    def __call__(self):
        objref = self.objRef()
        if objref is not None:
            return types.MethodType(self.fun, objref)

    def __eq__(self, method2):
        if not isinstance(method2, _WeakMethod):
            return False
        return (
            self.fun is method2.fun
            and self.objRef() is method2.objRef()
            and self.objRef() is not None
        )

    def __hash__(self):
        return hash(self.fun)

    def __repr__(self):
        dead = ''
        if self.objRef() is None:
            dead = '; DEAD'
        obj = '<%s at %s%s>' % (self.__class__, id(self), dead)
        return obj

    def refs(self, weakRef):
        """Return true if we are storing same object referred to by weakRef."""
        return self.objRef == weakRef


def _getWeakRef(obj, notifyDead=None):
    """
    Get a weak reference to obj. If obj is a bound method, a _WeakMethod
    object, that behaves like a WeakRef, is returned, if it is
    anything else a WeakRef is returned. If obj is an unbound method,
    a ValueError will be raised.
    """
    if ismethod(obj):
        createRef = _WeakMethod
    else:
        createRef = weakref.ref

    if notifyDead is None:
        return createRef(obj)
    else:
        return createRef(obj, notifyDead)


class EventManager:
    """
    Manages all Events
    """

    def __init__(self, use_logger=False, logger_filter=None, verbose=False):
        # sacrifice space for speed in emit
        self.all_callbacks = {}
        self.callbacks = {}
        self.ui_callbacks = {}
        self.use_logger = use_logger
        self.use_verbose_logger = verbose
        self.logger_filter = logger_filter

        # RLock is needed so that event callbacks can themselves send
        # synchronous events and add or remove callbacks
        self.lock = threading.RLock()

        self.pending_ui = []
        self.pending_ui_lock = threading.Lock()

    def emit(self, event):
        """
        Emits an Event, calling any registered callbacks.

        event: the Event to emit [Event]
        """

        emit_logmsg = self.use_logger and (
            not self.logger_filter or re.search(self.logger_filter, event.type)
        )
        emit_verbose = emit_logmsg and self.use_verbose_logger

        global _UiThread
        is_ui_thread = threading.current_thread() == _UiThread

        # note: a majority of the calls to emit are made on the
        #       UI thread

        if is_ui_thread:
            self._emit(event, self.all_callbacks, emit_logmsg, emit_verbose)
        else:
            # Don't issue the log message twice
            with self.pending_ui_lock:
                do_emit = not self.pending_ui
                self.pending_ui.append(
                    (event, self.ui_callbacks, emit_logmsg, emit_verbose)
                )

            if do_emit:
                GLib.idle_add(self._emit_pending)
            self._emit(event, self.callbacks, False, emit_verbose)

    def _emit_pending(self):

        with self.pending_ui_lock:
            events = self.pending_ui
            self.pending_ui = []

        for event in events:
            self._emit(*event)

    def _emit(self, event, exc_callbacks, emit_logmsg, emit_verbose):

        # Accumulate in this set to ensure callbacks only get called once
        callbacks = set()

        with self.lock:
            for tcall in [_NONE, event.type]:
                tcb = exc_callbacks.get(tcall)
                if tcb is not None:
                    for ocall in [_NONE, event.object]:
                        ocb = tcb.get(ocall)
                        if ocb is not None:
                            callbacks.update(ocb)

        # However, do not actually call the callbacks from within the lock
        # -> Otherwise non-ui threads could accidentally block the UI if
        #    they decide to run for too long

        for cb in callbacks:
            try:
                fn = cb.wfunction()
                if fn is None:
                    # Remove callbacks that have been garbage collected.. but
                    # really, should be using remove_callback to clean up after
                    # your event handler
                    with self.lock:
                        try:
                            exc_callbacks[event.type][event.object].remove(cb)
                        except (KeyError, ValueError):
                            pass
                else:
                    if emit_verbose:
                        logger.debug(
                            "Attempting to call "
                            "%(function)s in response "
                            "to %(event)s." % {'function': fn, 'event': event.type}
                        )
                    fn.__call__(
                        event.type, event.object, event.data, *cb.args, **cb.kwargs
                    )
                fn = None
            except Exception:
                # something went wrong inside the function we're calling
                logger.exception("Event callback exception caught!")

        if emit_logmsg:
            logger.debug(
                "Sent '%s' event from %r with data %r",
                event.type,
                event.object,
                event.data,
            )

    def emit_async(self, event):
        """
        Same as emit(), but does not block.
        """
        GLib.idle_add(self.emit, event)

    def add_callback(self, function, evty, obj, args, kwargs, ui=False):
        """
        Registers a callback.
        You should always specify at least one of event type or object.

        @param function: The function to call [function]
        @param evty: The 'type' or 'name' of event to listen for. Defaults
            to any. [string]
        @param obj: The object to listen to events from. Defaults
            to any. [string]

        Returns a convenience function that you can call to
        remove the callback.
        """

        if ui:
            all_cbs = [self.ui_callbacks, self.all_callbacks]
        else:
            all_cbs = [self.callbacks, self.all_callbacks]

        destroy_with = kwargs.pop('destroy_with', None)

        if evty is None:
            evty = _NONE
        if obj is None:
            obj = _NONE

        with self.lock:
            cb = Callback(function, time.time(), args, kwargs)

            # add the specified categories if needed.
            for cbs in all_cbs:
                if evty not in cbs:
                    cbs[evty] = weakref.WeakKeyDictionary()
                try:
                    callbacks = cbs[evty][obj]
                except KeyError:
                    callbacks = cbs[evty][obj] = []

                # add the actual callback
                callbacks.append(cb)

        if self.use_logger:
            if (
                not self.logger_filter
                or evty is _NONE
                or re.search(self.logger_filter, evty)
            ):
                logger.debug("Added callback %s for [%s, %s]" % (function, evty, obj))

        if destroy_with is not None:
            destroy_with.connect(
                'destroy', lambda w: self.remove_callback(function, evty, obj)
            )

        return lambda: self.remove_callback(function, evty, obj)

    def remove_callback(self, function, evty=None, obj=None):
        """
        Unsets a callback

        The parameters must match those given when the callback was
        registered. (minus any additional args)
        """
        if evty is None:
            evty = _NONE
        if obj is None:
            obj = _NONE

        with self.lock:
            for cbs in [self.callbacks, self.all_callbacks, self.ui_callbacks]:
                remove = []
                try:
                    callbacks = cbs[evty][obj]
                    for cb in callbacks:
                        if cb.wfunction() == function:
                            remove.append(cb)
                except KeyError:
                    continue
                except TypeError:
                    continue

                for cb in remove:
                    callbacks.remove(cb)

                if len(callbacks) == 0:
                    del cbs[evty][obj]
                    if len(cbs[evty]) == 0:
                        del cbs[evty]

        if self.use_logger:
            if (
                not self.logger_filter
                or evty is _NONE
                or re.search(self.logger_filter, evty)
            ):
                logger.debug("Removed callback %s for [%s, %s]" % (function, evty, obj))


EVENT_MANAGER = EventManager()

# vim: et sts=4 sw=4
