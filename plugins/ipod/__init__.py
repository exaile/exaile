# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

# Exaile plugin for iPod support, with autodetection


import sys
from xl.devices import Device
from xl.collection import Collection
from xl.track import Track, is_valid_track
from xl import event, providers
from xl.hal import Handler
import gpod
import dbus

# iPod device class
class iPod( Device ):

    def __init__( self, volume ):
        self.volume = volume
        self.name = self.volume.GetProperty( "volume.label" )
        if not self.name: # This ipod has not yet been given a name
            self.name = "Apple iPod Music Player"
        Device.__init__( self, self.name )
        self.db = None
        self.connected  = volume.GetProperty( "volume.is_mounted" )
        self.mountpoint = None
        self.collection = Collection( "Master" )
        if self.connected:
            self.mountpoint = str( volume.GetProperty( "volume.mount_point" ) )
            self.open_db()
            self.populate_collection()  

    def open_db( self ):
        if self.db:
            return
        else:
            self.db = gpod.Database( mountpoint=self.mountpoint )

    def populate_collection( self ):
        for track in self.db.get_master():
           track_path = self.mountpoint + track["ipod_path"].replace(":", "/")
           if is_valid_track( track_path ):
               track_object = Track( track_path )
               if track_object:
                   self.collection.add( track_object )

    def disconnect( self ):
        """
        Disconnect (or in this case 'unmount' the ipod)
        """
        self.connected = False
        self.db = None

    def connect( self ):
        """
        Connect (or in this case 'mount' the ipod)
        """
        self.connected = True
        self.mountpoint = self.volume.GetProperty( "volume.mount_point" )
        self.open_db()
        self.populate_collection()

# iPod provider handled
class iPodHandler( Handler ):

    name="ipod"

    def __init__(self):
        Handler.__init__( self)
        self.bus = None

    def get_udis(self, hal):
        # Based on the code from: https://bugs.launchpad.net/exaile/+bug/135915
        self.bus = hal.bus # BAD
        ret = []
        dev_udi_list = hal.hal.FindDeviceStringMatch ('portable_audio_player.type', 'ipod')
        for udi in dev_udi_list:
            vol_udi_list = hal.hal.FindDeviceStringMatch ('info.parent', udi)
            for vol_udi in vol_udi_list:
                vol_obj = hal.bus.get_object ('org.freedesktop.Hal', vol_udi)
                vol = dbus.Interface (vol_obj, 'org.freedesktop.Hal.Device')
                # The first partition contains ipod firmware,  which cannot be mounted
                if int( vol.GetProperty('volume.partition.number') ) != 1:
                    ret.append( vol_udi )
        return ret

    def is_type( self, device, capabilities ):
        parent_udi = device.GetProperty( "info.parent" )
        parent_proxy = self.bus.get_object( "org.freedesktop.Hal", parent_udi )
        parent_iface = dbus.Interface( parent_proxy, 'org.freedesktop.Hal.Device' )
        parent_protocols = parent_iface.GetProperty( "portable_audio_player.access_method.protocols" )
        return ( "ipod" in parent_protocols )

    def device_from_udi( self, hal, udi ):
        device_proxy = hal.bus.get_object( "org.freedesktop.Hal", udi )
        device_iface = dbus.Interface( device_proxy, 'org.freedesktop.Hal.Device' )
        return iPod( device_iface )

ipod_provider = None

def enable( exaile ):
    global ipod_provider
    ipod_provider = iPodHandler()
    providers.register( "hal", ipod_provider )

def disable( exaile ):
    global ipod_provider
    providers.unregister( "hal", ipod_provider )
    ipod_provider = None
