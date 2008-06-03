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

from xl import common, collection, playlist, player, settings
from xl import xdg, path, manager

import os

import xlgui

from optparse import OptionParser

def get_options():
    """
        Get the options for exaile
    """
    usage = "Usage: %prog [option...|uri]"
    p = OptionParser(usage=usage)
    
    # Playback options
    p.add_option("-n", "--next", dest="next", action="store_true",
        default=False, help="Play the next track")
    p.add_option("-p", "--prev", dest="prev", action="store_true",
        default=False,   help="Play the previous track")
    p.add_option("-s", "--stop", dest="stop", action="store_true",
        default=False, help="Stop playback")
    p.add_option("-a", "--play", dest="play", action="store_true",
        default=False, help="Play")
    p.add_option("-t", "--play-pause", dest="play_pause", action="store_true",
        default=False, help="Toggle Play or Pause")

    # Current song options
    p.add_option("-q", "--query", dest="query", action="store_true",
        default=False, help="Query player")
    p.add_option("--gui-query", dest="guiquery", action="store_true",
        default=False, help="Show a popup of the currently playing track")
    p.add_option("--get-title", dest="get_title", action="store_true",
        default=False, help="Print the title of current track")
    p.add_option("--get-album", dest="get_album", action="store_true",
        default=False, help="Print the album of current track")
    p.add_option("--get-artist", dest="get_artist", action="store_true",
        default=False, help="Print the artist of current track")
    p.add_option("--get-length", dest="get_length", action="store_true",
        default=False, help="Print the length of current track")
    p.add_option('--set-rating', dest='rating', help='Set rating for current '
        'song')
    p.add_option('--get-rating', dest='get_rating', help='Get rating for '
        'current song', default=False, action='store_true')
    p.add_option("--current-position", dest="current_position", action="store_true",
        default=False, help="Print the position inside the current track as a percentage")

    # Volume options
    p.add_option("-i","--increase_vol", dest="inc_vol",action="store", 
        type="int",metavar="VOL",help="Increases the volume by VOL")
    p.add_option("-l","--decrease_vol", dest="dec_vol",action="store",
        type="int",metavar="VOL",help="Decreases the volume by VOL")
    p.add_option("--get-volume", dest="get_volume", action="store_true",
        default=False, help="Print the current volume")

    # Other options
    p.add_option("--new", dest="new", action="store_true",
        default=False, help="Start new instance")
    p.add_option("--version", dest="show_version", action="store_true")
    p.add_option("--start-minimized", dest="minim", action="store_true",
        default=False, help="Start Exaile minimized to tray, if possible")

    return p


class Exaile:
    
    def __init__(self):
        """
            Initializes Exaile.
        """
        #parse args
        self.options, self.args = get_options().parse_args()

        #initialize DbusManager
        #self.dbus = dbus.DbusManager(self.options, self.args)

        #initialize SettingsManager
        self.settings = settings.SettingsManager( os.path.join(
                xdg.get_config_dir(), "settings.ini" ) )

        #show splash screen if enabled
        #xlgui.show_splash(show=True)

        #Set up the player itself.
        self.player = player.get_default_player()()

        #Set up the playback Queue
        self.queue = player.PlayQueue(self.player)

        #initialize CollectionsManager
        self.collections = manager.SimpleManager('collections')
        self.collections.add( collection.Collection("Collection", 
            location='testdb') )

        # temporary until we get a proper CollectionsManager
        # self.collection = collection.Collection(location='testdb')

        #initalize PlaylistsManager
        self.playlists = manager.SimpleManager('playlists')

        #initialize CoverManager
        #self.covers = ???

        #initialize LyricManager
        #self.lyrics = ???

        #initialize PluginManager
        #self.plugins = ???

        #setup GUI
        #self.gui = xlgui.Main()

