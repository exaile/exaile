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

# Here's where it all begins.....

import common, collection, playlist, player, settings

import os

class Exaile:
    
    def __init__(self, options, args):
        """
            initializes Exaile, expects the commandline args as input
            (parsed via optparse)
        """
        self.options = options
        self.args = args

        #initialize DbusManager
        #self.dbus = ???

        #initialize SettingsManager
        self.settings = settings.SettingsManager(
                os.path.join(common.get_config_dir(), 'settings.ini') )

        #initialize GUI (show splash screen if enabled)
        #self.gui = ???

        #Set up the player itself.
        self.player = player.get_default_player()()

        #Set up the playback Queue
        self.queue = player.PlayQueue(self.player)

        #initialize CollectionsManager
        #self.collections = ???
        # temporary until we get a proper CollectionsManager
        self.collection = collection.Collection(location='testdb')

        #initalize PlaylistsManager
        #self.playlists = ???

        #initialize CoverManager
        #self.covers = ???

        #initialize LyricManager
        #self.lyrics = ???

        #initialize PluginManager
        #self.plugins = ???

        #show GUI. also passes control to gtk.main() or similar.
        #self.gui.start()
