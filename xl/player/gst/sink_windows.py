# Copyright (C) 2013-2015 Dustin Spicuzza
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


'''
    The default GST DirectSound plugin does not support Gst DeviceMonitor.
    For plugins like the Preview Device, this is critical.
'''

import logging

import ctypes.wintypes as cwin
import ctypes

from gi.repository import Gst

logger = logging.getLogger(__name__)


class _SinkSettings:
    sink = 'directsoundsink'
    can_set_device = False

    def __init__(self):
        sink = Gst.ElementFactory.make(self.sink)
        if hasattr(sink.props, 'device'):
            self.can_set_device = True

_sink_settings = _SinkSettings()

if _sink_settings.can_set_device:
    _dsound_dll = ctypes.windll.LoadLibrary("dsound.dll")
    _DirectSoundEnumerateW = _dsound_dll.DirectSoundEnumerateW

    _LPDSENUMCALLBACK = ctypes.WINFUNCTYPE(cwin.BOOL,
                                           cwin.LPVOID,
                                           cwin.LPCWSTR,
                                           cwin.LPCWSTR,
                                           cwin.LPCVOID)

    _ole32_dll = ctypes.oledll.ole32
    _StringFromGUID2 = _ole32_dll.StringFromGUID2

    def get_create_fn(device_id):
        def _create_fn(name):
            e = Gst.ElementFactory.make(_sink_settings.sink, name)
            e.props.device = device_id
            return e

        return _create_fn

    def get_devices():

        devices = []

        def cb_enum(lpGUID, lpszDesc, lpszDrvName, _unused):
            dev = ""
            if lpGUID is not None:
                buf = ctypes.create_unicode_buffer(200)
                if _StringFromGUID2(lpGUID, ctypes.byref(buf), 200):
                    dev = buf.value

            devices.append((lpszDesc, dev))
            return True

        _DirectSoundEnumerateW(_LPDSENUMCALLBACK(cb_enum), None)

        for name, devid in devices:
            yield (name, devid, get_create_fn(devid))

else:
    def get_devices():
        return []


def load_directsoundsink(presets):

    preset = {
        "name": "DirectSound",
        "pipe": "directsoundsink"
    }

    presets['directsoundsink'] = preset

    return get_devices


def get_priority_booster():
    '''
        This hack allows us to boost the priority of GStreamer task threads on
        Windows. See https://github.com/exaile/exaile/issues/76 and
        https://bugzilla.gnome.org/show_bug.cgi?id=781998
    '''
    avrt_dll = ctypes.windll.LoadLibrary("avrt.dll")
    AvSetMmThreadCharacteristics = avrt_dll.AvSetMmThreadCharacteristicsW
    AvSetMmThreadCharacteristics.argtypes = [cwin.LPCWSTR, ctypes.POINTER(cwin.DWORD)]
    AvSetMmThreadCharacteristics.restype = cwin.HANDLE

    AvRevertMmThreadCharacteristics = avrt_dll.AvRevertMmThreadCharacteristics
    AvRevertMmThreadCharacteristics.argtypes = [cwin.HANDLE]
    AvRevertMmThreadCharacteristics.restype = cwin.BOOL

    def on_stream_status(bus, message):
        '''
            Called synchronously from GStreamer processing threads -- do what
            we need to do and then get out ASAP
        '''
        status = message.parse_stream_status()

        # A gstreamer thread starts
        if status.type == Gst.StreamStatusType.ENTER:
            obj = message.get_stream_status_object()

            # note that we use "Pro Audio" because it gives a higher priority, and
            # that's what Chrome does anyways...
            unused = cwin.DWORD()
            obj.task_handle = AvSetMmThreadCharacteristics("Pro Audio", ctypes.byref(unused))

        # A gstreamer thread ends
        elif status.type == Gst.StreamStatusType.LEAVE:
            obj = message.get_stream_status_object()
            task_handle = getattr(obj, 'task_handle', None)
            if task_handle:
                AvRevertMmThreadCharacteristics(task_handle)

    def attach_priority_hook(player):
        bus = player.get_bus()
        bus.connect('sync-message::stream-status', on_stream_status)
        bus.enable_sync_message_emission()

    return attach_priority_hook
