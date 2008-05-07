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

import common, event, collection, playlist, player, media

import time

class Exaile:
    
    def __init__(self, options, args):
        """
            initializes Exaile, expects the commandline args as input
            (parsed via optparse)
        """
        self.options = options
        self.args = args

        #handle DBUS stuff here

        #show spash screen
        print "Pretend this is a splash screen"

        #initialize settings manager

        self.player = player.get_default_player()()

        self.collection = collection.Collection(location='testdb')

        lib = collection.Library('/home/reacocard/music/library', self.collection)
        lib.rescan()

        print "Scan complete"

        self.player.play(self.collection.search('')[0])

        print self.collection.search('')[0]['title']

        time.sleep(3600)
