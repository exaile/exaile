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

from xl.common import threaded

EVENT_MANAGER = None

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

    @threaded
    def emit_async(self, event):
        self.emit(event)

    def add_callback(self, function, type=None, object=None):
        if not self.callbacks.has_key(type):
            self.callbacks[type] = {}
        if not self.callbacks[type].has_key(object):
            self.callbacks[type][object] = []
        self.callbacks[type][object].append(function)

    def remove_callback(self, function, type=None, object=None):
        self.callbacks[type][object].remove(function)

EVENT_MANAGER = EventManager()
