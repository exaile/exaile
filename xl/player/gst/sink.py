# Copyright (C) 2008-2010 Adam Olsen
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

from gi.repository import Gst

from xl import settings
from xl.nls import gettext as _

from . import gst_utils

import sys

import logging
logger = logging.getLogger(__name__)


__all__ = ['SINK_PRESETS', 'create_device', 'get_devices']


SINK_PRESETS = {
    "auto"  : {
        "name"      : _("Automatic")
    },
    "alsa"  : {
        "name"      : "ALSA",
        "pipe"      : "alsasink"
    },
    "oss"   : {
        "name"      : "OSS",
        "pipe"      : "osssink"
    },
    "pulse" : {
        "name"      : "PulseAudio",
        "pipe"      : "pulsesink"
    },
    "jack" : {
        "name"      : "JACK",
        "pipe"      : "jackaudiosink"
    },
    "custom" : {
        "name"      : _("Custom")
    }
}


def _gst_device_autodetect():
    dm = Gst.DeviceMonitor.new()
    dm.add_filter('Audio/Sink', Gst.Caps.new_empty_simple('audio/x-raw'))
    dm.start()
    
    try:
        for device in dm.get_devices():
            yield (device.get_display_name(),
                   device.props.internal_name,
                   device.create_element)
    finally:
        dm.stop()

_autodetect_devices = [
    _gst_device_autodetect
]


def get_devices():
    '''
        Generator that yields (display_name, internal_name, fn(name)) where
        fn is a function that will create the audiosink when called
    '''
    
    yield (_('Automatic'), 'auto', lambda name: Gst.ElementFactory.make('autoaudiosink', name))
    
    for fn in _autodetect_devices:
        for info in fn():
            yield info
    

def create_device(player_name, return_errorsink=True):
    '''
        Creates an audiosink based on the current settings. This will always
        return an audiosink, but sometimes it will return an audiosink that
        only sends error messages to the bus.
        
        ..note:: Only attempts to autoselect if the user has never specified a 
                 setting manually. Otherwise, they may be confused when it
                 switches to a new output. For example, if they specified a USB
                 device, and it is removed -- when restarting the program, they
                 would not expect to automatically start playing on the builtin
                 sound.
    '''
    
    sink_type = settings.get_option('%s/audiosink' % player_name, 'auto')
    name = '%s-audiosink' % player_name
    sink = None
    errmsg = None
    
    if sink_type == 'auto':
        
        specified_device = settings.get_option('%s/audiosink_device' % player_name, 'auto')
        
        for _unused, device_id, create in get_devices():
            if specified_device == device_id:
                sink = create(name)
                break
        
        if sink is None:
            errmsg = _("Could not create audiosink (device: %s, type: %s)")
            errmsg = errmsg % (specified_device, sink_type)
    
    elif sink_type == 'custom':
        
        pipeline = settings.get_option("%s/custom_sink_pipe" % player_name, "")
        if not pipeline:
            errmsg = _("No custom pipeline specified!")
        else:
            try:
                sink = CustomAudioSink(pipeline, name)
            except:
                errmsg = _("Error creating custom audiosink '%s'") % pipeline
                logger.exception(errmsg)
    
    else:
        preset = SINK_PRESETS.get(sink_type, None)
        if preset is None:
            errmsg = _("Invalid sink type '%s' specified") % sink_type
        else:
            sink = Gst.ElementFactory.make(preset['pipe'], name)
            if sink is None:
                errmsg = _("Could not create sink type '%s'") % preset['pipe']
    
    if errmsg is not None:
        logger.error(errmsg)
        if return_errorsink:
            sink = _get_error_audiosink(errmsg)
           
    return sink


def _get_error_audiosink(msg):
        
    sink = Gst.ElementFactory.make('fakesink')
    
    def handoff(s, b, p):
        s.message_full(Gst.MessageType.ERROR,
                       Gst.stream_error_quark(), Gst.StreamError.FAILED,
                       msg, msg,
                       "", "", 0)
    
    sink.props.signal_handoffs = True
    sink.props.sync = True
    sink.connect('handoff', handoff)
    return sink

class CustomAudioSink(Gst.Bin):
    """
        A bin that holds the audio output sink element(s) for a custom
        defined sink
    """
    
    def __init__(self, pipeline, name):
        Gst.Bin.__init__(self, name='%s-audiosink' % name)
        
        elems = [Gst.parse_launch(elem.strip()) for elem in pipeline.split('!')]
        
        for e in elems:
            self.add(e)
            
        gst_utils.element_link_many(*elems)
        
        # GhostPad allows the bin to pretend to be an audio sink
        ghost = Gst.GhostPad.new("sink",
                                 elems[0].get_static_pad("sink"))
        self.add_pad(ghost)

#
# Custom per-platform sink stuff where GStreamer doesn't currently support
# autodetection of output devices
#

if sys.platform == 'darwin':
    import sink_osx
    dev_fn = sink_osx.load_osxaudiosink(SINK_PRESETS)
    _autodetect_devices.append(dev_fn)
    
elif sys.platform == 'win32':
    import sink_windows
    dev_fn = sink_windows.load_directsoundsink(SINK_PRESETS)
    _autodetect_devices.append(dev_fn)

