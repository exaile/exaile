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
    The default GST DirectSound plugin does not support selecting
    an output device. For plugins like the Preview Device, this is
    critical.
'''


import os.path
import platform
from gi.repository import GLib
from gi.repository import Gst

from xl.nls import gettext as _

import logging
logger = logging.getLogger(__name__)

class _SinkSettings:
    sink = 'directsoundsink'
    can_set_device = False
    
_sink_settings = _SinkSettings()


def __setup_custom_plugin():
    '''Get rid of this once patch is in mainline'''
    
    sink = Gst.ElementFactory.make('directsoundsink')
    if hasattr(sink.props, 'device'):
        # Don't need custom plugin
        _sink_settings.can_set_device = True
        return
    
    try:
        if platform.architecture()[0] == "32bit":
            plugin_path = os.path.abspath(os.path.join(__file__, '../../../../tools/win-installer/libgstexailedirectsoundsink.dll'))
        else:
            plugin_path = os.path.abspath(os.path.join(__file__, '../../../../tools/win-installer/libgstexailedirectsoundsink64.dll'))
            
        plugin = Gst.Plugin.load_file(plugin_path)
        Gst.Registry.get().add_plugin(plugin)
        
    except GLib.GError, e:
        logger.error("Error loading custom DirectSound plugin: %s" % str(e))
    else:
        _sink_settings.sink = 'exailedirectsoundsink'
        _sink_settings.can_set_device = True

__setup_custom_plugin()


if _sink_settings.can_set_device:
    
    import ctypes.wintypes
    import ctypes as C
    
    _dsound_dll = C.windll.LoadLibrary("dsound.dll")
    _DirectSoundEnumerateW = _dsound_dll.DirectSoundEnumerateW
    
    
    
    _LPDSENUMCALLBACK = C.WINFUNCTYPE(C.wintypes.BOOL,
                                      C.wintypes.LPVOID,
                                      C.wintypes.LPCWSTR,
                                      C.wintypes.LPCWSTR,
                                      C.wintypes.LPCVOID)
    
    _ole32_dll = C.oledll.ole32
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
                buf = C.create_unicode_buffer(200)
                if _StringFromGUID2(lpGUID, C.byref(buf), 200):
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
        "name"      : "DirectSound",
        "pipe"      : "directsoundsink"
    }
    
    presets['directsoundsink'] = preset
        
    return get_devices
        