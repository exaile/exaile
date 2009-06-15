# Copyright (C) 2008-2009 Adam Olsen 
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

from xl.nls import gettext as _

import pygst
pygst.require('0.10')
import gst

import threading, logging, copy
logger = logging.getLogger(__name__)

from xl import event, common, settings
from xl.providers import ProviderHandler


class MainBin(gst.Bin):
    """
        The main bin - handles processing and output of audio after it
        is decoded by the engine.
    """
    def __init__(self):
        gst.Bin.__init__(self)
        self._elements = []

        self.pp = Postprocessing()
        self._elements.append(self.pp)

        self.tee = gst.element_factory_make("tee")
        self._elements.append(self.tee)

        sinkname = settings.get_option("player/audiosink", "auto")
        self.audio_sink = sink_from_preset(sinkname)
        if not self.audio_sink:
            logger.warning("Could not enable %s sink, "
                    "attempting to autoselect." % sinkname)
            self.audio_sink = sink_from_preset("auto")
        self._elements.append(self.audio_sink)

        self.add(*self._elements)
        gst.element_link_many(*self._elements)

        self.sinkpad = self._elements[0].get_static_pad("sink")
        self.add_pad(gst.GhostPad('sink', self.sinkpad))

    def get_volume(self):
        return self.audio_sink.get_volume()

    def set_volume(self, vol):
        self.audio_sink.set_volume(vol)

    # TODO: add audio sink switching
    # TODO: support for multiple sinks
    # TODO: visualizations



class ProviderBin(gst.Bin, ProviderHandler):
    """
        A ProviderBin is a gst.Bin that adds and removes elements from itself
        using the providers system. Providers should be a subclass of 
        gst.Element and provide the following attributes:
            name  - name to use for this element
            index - priority within the pipeline. range [0-100] integer.
                    lower numbers are higher priority, elements having the
                    same index are ordered arbitrarily.
    """
    def __init__(self, servicename, name=None):
        """
            :param servicename: the Provider name to listen for
        """
        if name:
            gst.Bin.__init__(self, name)
        else:
            gst.Bin.__init__(self)
        ProviderHandler.__init__(self, servicename)
        self.elements = {}  # FIXME: needs to initialize itself from the 
                            # provider system, in case things are already 
                            # registered.
        self.added_elems = []
        self.srcpad = None
        self.sinkpad = None
        self.src = None
        self.sink = None
        self.setup_elements()

    def setup_elements(self):
        state = self.get_state()[1]

        if len(self.added_elems) > 0:
            self.remove(*self.added_elems)
        
        elems = list(self.elements.iteritems())
        elems.sort()
        if len(elems) == 0:
            elems.append(gst.element_factory_make('identity'))
        self.add(*elems)
        if len(elems) > 1:
            gst.element_link_many(*elems)

        self.srcpad = elems[-1].get_static_pad("src")
        if self.src:
            self.src.set_target(self.srcpad)
        else:
            self.src = gst.GhostPad('src', self.srcpad)
        self.add_pad(self.src)
        self.sinkpad = elems[0].get_static_pad("sink")
        if self.sink:
            self.sink.set_target(self.sinkpad)
        else:
            self.sink = gst.GhostPad('sink', self.sinkpad)
        self.add_pad(self.sink)

        self.added_elems = elems
        self.set_state(state)

    def on_new_provider(self, provider):
        self.elements[provider.index] = \
                self.elements.get(provider.index, []) + [provider]
        self.setup_elements()

    def on_del_provider(self, provider):
        try:
            self.elements[provider.index].remove(provider)
        except:
            pass
        self.setup_elements()


class Postprocessing(ProviderBin):
    def __init__(self):
        ProviderBin.__init__(self, 'postprocessing_element', 
                name="Postprocessing")

class BaseSink(gst.Bin):
    pass


SINK_PRESETS = {
        "auto"  : {
            "name"      : _("Automatic"), 
            "elem"      : "autoaudiosink", 
            "options"   : {},
            },
        "alsa"  : {
            "name"      : _("Alsa"),
            "elem"      : "alsasink",
            "options"   : {},
            },
        "oss"   : {
            "name"      : _("Oss"),
            "elem"      : "osssink",
            "options"   : {},
            },
        "pulse" : {
            "name"      : _("Pulseaudio"),
            "elem"      : "pulsesink",
            "options"   : {},
            },
        }

def sink_from_preset(preset):
    try:
        d = SINK_PRESETS[preset]
        sink = AudioSink(d['name'], d['elem'], d['options'])
        return sink
    except:
        common.log_exception(log=logger, 
                message="Could not enable audiosink %s"%preset)
        return None

class AudioSink(BaseSink):
    def __init__(self, name, elem, options, *args, **kwargs):
        BaseSink.__init__(self, *args, **kwargs)
        self.name = name
        self.sink_elem = elem
        self.options = options
        self.provided = ProviderBin('sink_element')
        self.vol = gst.element_factory_make("volume")
        self.sink = gst.element_factory_make(self.sink_elem)
        elems = [self.provided, self.vol, self.sink]
        self.add(*elems)
        gst.element_link_many(*elems)
        self.sinkghost = gst.GhostPad("sink", 
                self.provided.get_static_pad("sink"))
        self.add_pad(self.sinkghost)
        self.load_options()

    def load_options(self):
        # TODO: make this reset any non-explicitly set options to default
        # this setting is a list of strings of the form "param=value"
        options = settings.get_option("player/%s_sink_options"%self.name, [])
        optdict = copy.copy(self.options)
        optdict.update(dict([v.split("=") for v in options]))
        for param, value in optdict.iteritems():
            try:
                self.sink.set_property(param, value)
            except:
                common.log_exception(log=logger)
                logger.warning(_("Could not set parameter %s for %s") % 
                        (param, self.sink_elem))

    def set_volume(self, vol):
        self.vol.set_property("volume", vol)

    def get_volume(self):
        return self.vol.get_property("volume")


# vim: et sts=4 sw=4

