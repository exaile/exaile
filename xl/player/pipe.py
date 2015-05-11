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


import copy
import logging
import os.path
import sys
import threading

import pygst
pygst.require('0.10')
import gst

import glib

from xl.nls import gettext as _
from xl import event, common, settings
from xl.providers import ProviderHandler

logger = logging.getLogger(__name__)

class MainBin(gst.Bin):
    """
        The main bin - handles processing and output of audio after it
        is decoded by the engine.
    """
    def __init__(self, player, pre_elems=[]):
        gst.Bin.__init__(self, name='mainbin-%s' % player._name)
        
        self.__player = player
        self._elements = pre_elems[:]

        self.pp = Postprocessing(player)
        self._elements.append(self.pp)

        self.tee = gst.element_factory_make("tee")
        self._elements.append(self.tee)

        #self.queue = gst.element_factory_make("queue")
        #self._elements.append(self.queue)

        self.add(*self._elements)
        gst.element_link_many(*self._elements)
        
        self.audio_sink = None
        self.__audio_sink_lock = threading.Lock()
        self.setup_audiosink()
        
        self.sinkpad = self._elements[0].get_static_pad("sink")
        self.add_pad(gst.GhostPad('sink', self.sinkpad))

        self.sinkqueue = gst.element_factory_make("queue")
        self.sinkhandler = SinkHandler(player, 'playback_audio_sink')
        self.add(self.sinkhandler)
        self.add(self.sinkqueue)
        gst.element_link_many(self.tee, self.sinkqueue, self.sinkhandler)

    def get_volume(self):
        return self.audio_sink.get_volume()

    def set_volume(self, vol):
        self.audio_sink.set_volume(vol)

    def setup_audiosink(self):
        
        # don't try to switch more than one source at a time
        self.__audio_sink_lock.acquire()
        
        audio_sink = None
        sinkname = settings.get_option("%s/audiosink" % self.__player._name)
        
        # Only attempt to autoselect if the user has never specified a 
        # setting manually. Otherwise, they may be confused when it switches
        # to a new output. For example, if they specified a USB device, and
        # it is removed -- when restarting the program, they would not expect
        # to automatically start playing on the builtin sound.
        if sinkname is not None:
            audio_sink = sink_from_preset(self.__player, sinkname)
            
        if not audio_sink:
            if sinkname is not None:
                logger.warning("Could not enable %s sink for %s, "
                               "attempting to autoselect.", sinkname, self.__player._name)
            audio_sink = sink_from_preset(self.__player, "auto")
        
        # If this is the first time we added a sink, just add it to
        # the pipeline and we're done.
        
        if not self.audio_sink:
        
            self._add_audiosink(audio_sink, None)
            self.__audio_sink_lock.release()
            return
        
        old_audio_sink = self.audio_sink
        
        
        # Ok, time to replace the old sink. If it's not in a playing state,
        # then this isn't so bad.
        
        # if we don't use the timeout, when we set it to READY, it may be performing
        # an async wait for PAUSE, so we use the timeout here.
        
        state = old_audio_sink.get_state(timeout=50*gst.MSECOND)[1]
        
        if state != gst.STATE_PLAYING:
            
            buffer_position = None
            
            if state != gst.STATE_NULL:
                try:
                    buffer_position = old_audio_sink.query_position(gst.FORMAT_DEFAULT)
                except:
                    pass
            
            self.remove(old_audio_sink)
            
            # Now that the old sink is removed, we have to flush it out
            if old_audio_sink.get_state(timeout=50*gst.MSECOND)[1] == gst.STATE_PAUSED:
                self._clear_old_sink(old_audio_sink)
            else:
                old_audio_sink.set_state(gst.STATE_NULL)
        
            # Then add the new sink    
            self._add_audiosink(audio_sink, buffer_position)
            
            self.__audio_sink_lock.release()
            return
         
        #  
        # Otherwise, disconnecting the old device is a bit complex. Code is
        # derived from algorithm/code described at the following link:
        #
        # http://gstreamer.freedesktop.org/data/doc/gstreamer/head/manual/html/section-dynamic-pipelines.html
        #
        
        # TODO: Rapid output switching causes problems
        
        # Start off by blocking the src pad of the prior element
        spad = old_audio_sink.get_static_pad('sink').get_peer()
        spad.set_blocked_async(True, self._pad_blocked_cb, audio_sink)
        
    def _pad_blocked_cb(self, pad, info, new_audio_sink):
                
        old_audio_sink = self.audio_sink
        buffer_position = old_audio_sink.query_position(gst.FORMAT_DEFAULT)
        
        # No data is flowing at this point. Unlink the element, add the new one
        self.remove(old_audio_sink)
        
        self._add_audiosink(new_audio_sink, buffer_position)
        
        # GST is holding a lock, so unblock the pad on the main thread so
        # that data continues to flow
        
        def unblock_pad():
            pad.set_blocked(False)
        
        glib.idle_add(unblock_pad)
        self.__audio_sink_lock.release()
       
        # Start flushing the old sink
        self._clear_old_sink(old_audio_sink)
    
    def _clear_old_sink(self, old_audio_sink):
        
        # push EOS into the element, which will be fired once all the
        # data has left the sink
          
        sinkpad = old_audio_sink.get_static_pad('sink')
        self._pad_event_probe_id = sinkpad.add_event_probe(self._event_probe_cb, old_audio_sink)
        
        sinkpad.send_event(gst.event_new_eos())
        
        return False
    
    def _event_probe_cb(self, pad, info, audio_sink):
        
        # wait for end of stream marker
        if info.type != gst.EVENT_EOS:
            return True
        
        pad.remove_event_probe(self._pad_event_probe_id)
        self._pad_event_probe_id = None
        
        # Get rid of the old sink
        audio_sink.set_state(gst.STATE_NULL)
        
        return False
    
    def _add_audiosink(self, audio_sink, buffer_position):
        '''Sets up the new audiosink and syncs it'''
        
        self.add(audio_sink)
        audio_sink.sync_state_with_parent()
        gst.element_link_many(self._elements[-1], audio_sink)

        if buffer_position is not None:
            
            # buffer position is the output from get_position. If set, we
            # seek to that position.
            
            # TODO: this actually seems to skip ahead a tiny bit. why?
            
            # Note! this is super important in paused mode too, because when
            #       we switch the sinks around the new sink never goes into
            #       the paused state because there's no buffer. This forces
            #       a resync of the buffer, so things still work.
            
            seek_event = gst.event_new_seek(1.0, gst.FORMAT_DEFAULT,
                gst.SEEK_FLAG_FLUSH, gst.SEEK_TYPE_SET,
                buffer_position[0],
                gst.SEEK_TYPE_NONE, 0)
            
            self.send_event(seek_event)
        
        self.audio_sink = audio_sink        


class SinkHandler(gst.Bin, ProviderHandler):
    def __init__(self, player, servicename):
        gst.Bin.__init__(self, name=servicename)
        ProviderHandler.__init__(self, servicename)
        self.tee = gst.element_factory_make("tee", "sinkhandler-tee")
        self.add(self.tee)
        self.sinkpad = self.tee.get_static_pad("sink")
        self.sink = gst.GhostPad('sink', self.sinkpad)
        self.add_pad(self.sink)
        self.fake = gst.element_factory_make("fakesink", "sinkhandler-fake")
        self.fake.props.async = False
        self.add(self.fake)
        self.tee.link(self.fake)
        self.queuedict = {}

        self.sinks = {}
        self.added_sinks = []

        event.add_callback(self.on_reconfigure_bins, 'playback_reconfigure_bins', player)

    def reset_providers(self):
        self.sinks = {}
        for provider in self.get_providers():
            try:
                self.sinks[provider.name] = provider()
            except:
                logger.warning("Could not create %s element for %s." % \
                        (provider, self.get_name()) )
                common.log_exception(log=logger)

    def on_provider_added(self, provider):
        self.reset_providers()

    def on_provider_removed(self, provider):
        self.reset_providers()

    def on_reconfigure_bins(self, *args):
        self.setup_sinks()

    def setup_sinks(self):
        state = self.get_state()[1]
        if False: #self.srcpad is not None:
            self.sinkpad.set_blocked_async(True, self._setup_finish, state)
        else:
            self._setup_finish(None, True, state)

    def _setup_finish(self, elem, blocked, state):
        for sink in self.added_sinks:
            queue = self.queuedict[sink.name]
            pad = queue.get_static_pad("sink").get_peer()
            if pad:
                self.tee.release_request_pad(pad)
            try:
                self.remove(queue)
                queue.set_state(gst.STATE_NULL)
            except gst.RemoveError:
                pass
            try:
                self.remove(sink)
                sink.set_state(gst.STATE_NULL)
            except gst.RemoveError:
                pass
        self.added_sinks = []

        for name, sink in self.sinks.iteritems():
            self.add(sink)
            queue = gst.element_factory_make("queue")
            self.add(queue)
            self.queuedict[sink.name] = queue

            gst.element_link_many(self.tee, queue, sink)

            self.added_sinks.append(sink)

        self.set_state(state)
        if blocked:
            self.sinkpad.set_blocked_async(False, lambda *args: False, state)

    def set_state(self, state):
        if state == gst.STATE_PLAYING and \
                self.get_state() == gst.STATE_NULL:
            self.setup_elements()
        gst.Bin.set_state(self, state)



class ElementBin(gst.Bin):
    """
        A bin for easily containing elements

        elements are added to the elements dictionary in the form of
            elements[position] = element
        where position is a value from 0-100 indicating its position
        in the resulting bin, and element is the gst.Element itself.

        changes made to elements do not apply until setup_elements()
        is called
    """
    def __init__(self, player, name=None):
        if name:
            gst.Bin.__init__(self, name)
        else:
            gst.Bin.__init__(self)
        self.player = player
        self.elements = {}
        self.added_elems = []
        self.srcpad = None
        self.sinkpad = None
        self.src = None
        self.sink = None

        event.add_callback(self.on_reconfigure_bins, 'playback_reconfigure_bins', self.player)

    def on_reconfigure_bins(self, *args):
        self.setup_elements()

    def setup_elements(self):
        state = self.get_state()[1]

        if False: #self.srcpad is not None:
            self.srcpad.set_blocked_async(True, self._setup_finish, state)
        else:
            self._setup_finish(None, True, state)


    def _setup_finish(self, elem, blocked, state):
        if not blocked:
            logger.warning("Could not block pipeline, skipping element "
                    "reconstruction.")
            return

        if len(self.added_elems) > 0:
            for elem in self.added_elems:
                try:
                    self.remove(elem)
                    elem.set_state(gst.STATE_NULL)
                except gst.RemoveError:
                    pass

        elems = list(self.elements.iteritems())
        elems.sort()
        if len(elems) == 0:
            elems.append(gst.element_factory_make('identity'))
        else:
            elems = [ x[1] for x in elems ]
        self.add(*elems)
        if len(elems) > 1:
            gst.element_link_many(*elems)

        self.srcpad = elems[-1].get_static_pad("src")
        if self.src is not None:
            self.src.set_target(self.srcpad)
        else:
            self.src = gst.GhostPad('src', self.srcpad)
            self.add_pad(self.src)
        self.sinkpad = elems[0].get_static_pad("sink")
        if self.sink is not None:
            self.sink.set_target(self.sinkpad)
        else:
            self.sink = gst.GhostPad('sink', self.sinkpad)
            self.add_pad(self.sink)

        self.added_elems = elems

        self.set_state(state)
        if blocked:
            self.srcpad.set_blocked_async(False, lambda *args: False, state)

    def set_state(self, state):
        if state == gst.STATE_PLAYING and \
                self.get_state() == gst.STATE_NULL:
            self.setup_elements()
        gst.Bin.set_state(self, state)


class ProviderBin(ElementBin, ProviderHandler):
    """
        A ProviderBin is a gst.Bin that adds and removes elements from itself
        using the providers system. Providers should be a subclass of
        gst.Element and provide the following attributes:
            name  - name to use for this element
            index - priority within the pipeline. range [0-100] integer.
                    lower numbers are higher priority. elements must
                    choose a unique number.
    """
    def __init__(self, player, servicename, name=None):
        """
            :param servicename: the Provider name to listen for
        """
        if name is None:
            name = servicename
        ElementBin.__init__(self, player, name=name)
        ProviderHandler.__init__(self, servicename)

        self.reset_providers()
        self.setup_elements()

    def reset_providers(self):
        self.elements = {}
        dups = {}
        for provider in self.get_providers():
            idx = provider.index
            if idx in self.elements:
                dup = dups.setdefault(idx, [self.elements[idx].name])
                dup.append(provider.name)
                while idx in self.elements:
                    idx += 1
            try:
                self.elements[idx] = provider(self.player)
            except:
                logger.warning("Could not create %s element for %s." % \
                        (provider, self.get_name()) )
                common.log_exception(log=logger)
        #self.setup_elements()
        
        for k, v in dups.iteritems():
            logger.warning("Audio plugins %s are sharing index %s (may have unpredictable output!)",
                            v, k)
        
    def on_provider_added(self, provider):
        self.reset_providers()

    def on_provider_removed(self, provider):
        self.reset_providers()


class Postprocessing(ProviderBin):
    def __init__(self, player):
        ProviderBin.__init__(self, player, 'postprocessing_element',
                name="Postprocessing")

SINK_PRESETS = {
        "auto"  : {
            "name"      : _("Automatic"),
            "pipe"      : "autoaudiosink"
            },
        "gconf" : {
            "name"      : "GNOME",
            "pipe"      : "gconfaudiosink",
            "pipeargs"  : "profile=music"
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
        "directsound" : {
            "name"      : "DirectSound",
            "pipe"      : "directsoundsink"
        },
        "custom" : {
            "name"      : _("Custom")
        }
}


#
# Custom sinks
#   
    
if sys.platform == 'win32':
    import sink_windows
    sink_windows.load_exaile_directsound_plugin(SINK_PRESETS)

elif sys.platform == 'darwin':
    import sink_osx
    sink_osx.load_osxaudiosink(SINK_PRESETS)

def sink_from_preset(player, preset):
    if preset == "custom":
        pipe = settings.get_option("%s/custom_sink_pipe" % player._name, "")
        if not pipe:
            logger.error("No custom sink pipe set for %s" % player._name)
            return None
        name = _("Custom")
    else:
        d = SINK_PRESETS.get(preset, "")
        if not d:
            logger.error("Could not find sink preset %s for %s." % (preset, player._name))
            return None

        name = d['name']
        pipe = d['pipe']
        if preset != 'auto':
            dname = settings.get_option('%s/audiosink_device' % player._name)
            if dname:
                pipe += ' device=' + dname
        if 'pipeargs' in d:
            pipe += ' ' + d['pipeargs']

    try:
        sink = AudioSink(name, pipe, player)
    except Exception:
        common.log_exception(log=logger,
                message="Could not enable audiosink %s for %s." % (preset, player._name))
        return None
    return sink
        
def sink_enumerate_devices(preset):
    '''
        Enumerate all availables devices for a particular sink type 
        in (device, device-name) pairs. Returns None if no devices
        can be enumerated for that preset type
    '''

    p = SINK_PRESETS[preset]

    # create a temporary sink, probe it
    try:
        tmpsink = gst.element_factory_make(p['pipe'], 'tmp')
    except Exception:
        # If we can't create an instance of the sink, probably doesn't exist... 
        return None
        
    # does it support the property probe interface? 
    if not hasattr(tmpsink, 'probe_get_properties'):
        
        # Maybe it supports a custom interface?
        if 'get_devices' in p:
            return p['get_devices']()
        
        return None

    # check to see if we can probe for a device
    if 'device' not in [prop.name for prop in tmpsink.probe_get_properties()]:
        return None

    # do the probe
    tmpsink.probe_property_name('device')
    devices = tmpsink.probe_get_values_name('device')

    if not devices:
        return None

    ret = [('', _('Auto'))]

    for device in devices:
        tmpsink.set_property('device', device)
        devname = tmpsink.get_property('device-name')
        if not devname:
            devname = device

        ret.append((device, devname))

    return ret


class AudioSink(gst.Bin):
    def __init__(self, name, pipeline, player):
        gst.Bin.__init__(self, name='audiosink-%s-%s' % (name, player._name))
        self.name = name
        self.sink = elems = [gst.parse_launch(elem) for elem in pipeline.split('!')]
        self.provided = ProviderBin(player, 'sink_element')
        self.vol = gst.element_factory_make("volume")
        elems = [self.provided, self.vol] + elems
        self.add(*elems)
        gst.element_link_many(*elems)
        self.sinkghost = gst.GhostPad("sink",
                self.provided.get_static_pad("sink"))
        self.add_pad(self.sinkghost)

    def set_volume(self, vol):
        self.vol.set_property("volume", vol)

    def get_volume(self):
        return self.vol.get_property("volume")


# vim: et sts=4 sw=4

