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
    an output device via the property probe mechanism. For plugins
    like the Preview Device, this is critical. 
    
    This should be removed once GST has proper support in mainline.
'''

import logging
import os.path
import platform
from gi.repository import GLib
from gi.repository import Gst

from xl import settings
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

def get_devices():
    return []

def load_exaile_directsound_plugin(presets):
    return get_devices

    # TODO: fix these

    try:
        if platform.architecture()[0] == "32bit":
            plugin_path = os.path.abspath(os.path.join(__file__, '../../../tools/win-installer/libgstexailedirectsoundsink.dll'))
        else:
            plugin_path = os.path.abspath(os.path.join(__file__, '../../../tools/win-installer/libgstexailedirectsoundsink64.dll'))
            
        plugin = Gst.plugin_load_file(plugin_path)
        Gst.registry_get_default().add_plugin(plugin)
        
    except GLib.GError, e:
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
