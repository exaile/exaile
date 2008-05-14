# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import threading


EVENT_MANAGER = None
IDLE_MANAGER  = None

def log_event(type, object, data, async=True):
    global EVENT_MANAGER
    e = Event(type, object, data)
    if async:
        EVENT_MANAGER.emit_async(e)
    else:
        EVENT_MANAGER.emit(e)

def set_event_callback(function, type=None, object=None):
    global EVENT_MANAGER
    EVENT_MANAGER.add_callback(function, type, object)

def idle_add(func, *args):
    global IDLE_MANAGER
    IDLE_MANAGER.add(func, *args)

class Event:
    def __init__(self, type, object, data):
        self.type = type
        self.object = object
        self.data = data

class EventManager:
    callbacks = {}
    def __init__(self):
        pass

    def emit(self, event):
        callbacks = []
        for tcall in [None, event.type]:
            for ocall in [None, event.object]:
                try:
                    for call in self.callbacks[tcall][ocall]:
                        if call not in callbacks:
                            callbacks.append(call)
                except KeyError:
                    pass
        for call in callbacks:
            call.__call__(event.type, event.object, event.data)

    #FIXME: we probably shouldn't use the global idle_add for this
    def emit_async(self, event):
        idle_add(self.emit, event)

    def add_callback(self, function, type=None, object=None):
        if not self.callbacks.has_key(type):
            self.callbacks[type] = {}
        if not self.callbacks[type].has_key(object):
            self.callbacks[type][object] = []
        self.callbacks[type][object].append(function)

    def remove_callback(self, function, type=None, object=None):
        self.callbacks[type][object].remove(function)


class IdleManager(threading.Thread):
    queue = []
    event = threading.Event()

    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.start()

    def run(self):
        while True:
            while len(self.queue) == 0:
                self.event.wait()
            self.event.clear()
            func, args = self.queue[0]
            self.queue = self.queue[1:]
            
            try:
                func.__call__(*args)
            except:
                pass # TODO: handle this more smartly by logging errors

    def add(self, func, *args):
        self.queue.append((func, args))
        self.event.set()


EVENT_MANAGER = EventManager()
IDLE_MANAGER  = IdleManager()
