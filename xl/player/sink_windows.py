'''
    The default GST DirectSound plugin does not support selecting
    an output device via the property probe mechanism. For plugins
    like the Preview Device, this is critical. 
    
    This should be removed once GST has proper support in mainline.
'''

import logging
import os.path
import glib
import gst

from xl import settings
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

def load_exaile_directsound_plugin(presets):
    
    try:
        plugin_path = os.path.abspath(os.path.join(__file__, '../../../tools/win-installer/libgstexailedirectsoundsink.dll'))
        plugin = gst.plugin_load_file(plugin_path)
        gst.registry_get_default().add_plugin(plugin)
        
    except glib.GError, e:
        logger.error("Error loading custom DirectSound plugin: %s" % str(e))
        
    else:
        # add to presets if successfully loaded
        preset = {
            "name"      : "DirectSound (Exaile %s)" % _('Custom'),
            "pipe"      : "exailedirectsoundsink"
        }
        
        presets["exailedirectsound"] = preset
        
        # make this default if there is no default
        if settings.get_option('player/audiosink', None) == None:
            settings.set_option('player/audiosink', 'exailedirectsound')
