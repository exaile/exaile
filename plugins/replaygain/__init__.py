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



from xl import providers, event, settings
from xl.player.pipe import ElementBin

import gst


def enable(exaile):
    providers.register("postprocessing_element", ReplaygainVolume)
    providers.register("postprocessing_element", ReplaygainLimiter)

def disable(exaile):
    providers.unregister("postprocessing_element", ReplaygainVolume)
    providers.unregister("postprocessing_element", ReplaygainLimiter)


class ReplaygainVolume(ElementBin):
    """
        Handles replaygain volume adjustment and pre-amp. 

        Placed at 20 in the pipeline, since most elements should do their 
        processing after it.
    """
    index = 20
    name = "rgvolume"
    def __init__(self):
        ElementBin.__init__(self, name=self.name)
        self.audioconvert = gst.element_factory_make("audioconvert")
        self.elements[40] = self.audioconvert
        self.rgvol = gst.element_factory_make("rgvolume")
        self.elements[50] = self.rgvol
        self.setup_elements()

        event.add_callback(self._on_setting_change, "option_set")

    def _on_setting_change(self, name, object, data):
        if data == "replaygain/album-mode":
            self.rgvol.set_property("album-mode", 
                    settings.get_option("replaygain/album-mode", True))
        elif data == "replaygain/pre-amp":
            self.rgvol.set_property("pre-amp",
                    settings.get_option("replaygain/pre-amp", 6))
        elif data == "replaygain/fallback-gain":
            self.rgvol.set_property("fallback-gain",
                    settings.get_option("replaygain/fallback-gain", 0))


class ReplaygainLimiter(ElementBin):
    """
        Implements clipping protection. 
        
        Placed at 80 in the pipeline so that other elements can come 
        before it if necessary.
    """
    index = 80
    name = "rglimiter"
    def __init__(self):
        ElementBin.__init__(self, name=self.name)
        self.rglimit = gst.element_factory_make("rglimiter")
        self.elements[50] = self.rglimit
        self.audioconvert = gst.element_factory_make("audioconvert")
        self.elements[60] = self.audioconvert
        self.setup_elements()

        event.add_callback(self._on_setting_change, "option_set")

    def _on_setting_change(self, name, object, data):
        if data == "replaygain/clipping-protection":
            self.rgvol.set_property("enabled", 
                    settings.get_option("replaygain/clipping-protection", 
                        True))

