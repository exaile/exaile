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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

import pygst
pygst.require('0.10')
import gst

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
        gst.Bin.__init__(self)
        self._elements = pre_elems[:]

        self.pp = Postprocessing(player)
        self._elements.append(self.pp)

        self.tee = gst.element_factory_make("tee")
        self._elements.append(self.tee)

        #self.queue = gst.element_factory_make("queue")
        #self._elements.append(self.queue)

        sinkname = settings.get_option("%s/audiosink" % player._name, "auto")
        self.audio_sink = sink_from_preset(player, sinkname)
        if not self.audio_sink:
            logger.warning("Could not enable %s sink for %s, "
                    "attempting to autoselect." % (sinkname, player._name) )
            self.audio_sink = sink_from_preset(player, "auto")
        self._elements.append(self.audio_sink)

        self.add(*self._elements)
        gst.element_link_many(*self._elements)

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

    # TODO: add audio sink switching


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
    # TODO: allow duplicate #s
    def __init__(self, player, servicename, name=None):
        """
            :param servicename: the Provider name to listen for
        """
        ElementBin.__init__(self, player, name=name)
        ProviderHandler.__init__(self, servicename)

        self.reset_providers()
        self.setup_elements()

    def reset_providers(self):
        self.elements = {}
        for provider in self.get_providers():
            try:
                self.elements[provider.index] = provider(self.player)
            except:
                logger.warning("Could not create %s element for %s." % \
                        (provider, self.get_name()) )
                common.log_exception(log=logger)
        #self.setup_elements()

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
        }
}

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
        return sink
    except:
        common.log_exception(log=logger,
                message="Could not enable audiosink %s for %s." % (preset, player._name))
        return None
        
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
        return None

    # check to see if we can probe for a device
    if 'device' not in [prop.name for prop in tmpsink.probe_get_properties()]:
        return None

    # do the probe
    tmpsink.probe_property_name('device')
    devices = tmpsink.probe_get_values_name('device')

    if not devices:
        return None

    ret = [('', 'Auto')]

    for device in devices:
        tmpsink.set_property('device', device)
        devname = tmpsink.get_property('device-name')
        if not devname:
            devname = device

        ret.append((device, devname))

    return ret


class AudioSink(gst.Bin):
    def __init__(self, name, pipeline, player):
        gst.Bin.__init__(self)
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

