# mpris2 - Support MPRIS 2 in Exaile
# Copyright (C) 2015-2016  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
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


from gi.repository import Gio

from . import dbushelper
from . import mprisobject


# MPRIS 2.2 partial introspection data.
# This contains some Exaile-specific optimizations, e.g. Rate is marked as
# const because Exaile cannot change playback rate.
# The order of interfaces is important; later we refer to them by index.
MPRIS_INTROSPECTION = '''\
<node>
  <interface name='org.mpris.MediaPlayer2'>
    <method name='Raise' />
    <method name='Quit'>
      <annotation name='org.freedesktop.DBus.Method.NoReply' value='true' />
    </method>
    <property name='CanQuit' type='b' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='FullScreen' type='b' access='readwrite' />
    <property name='CanSetFullScreen' type='b' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='CanRaise' type='b' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='HasTrackList' type='b' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='Identity' type='s' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='DesktopEntry' type='s' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='SupportedUriSchemes' type='as' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='SupportedMimeTypes' type='as' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
  </interface>
  <interface name='org.mpris.MediaPlayer2.Player'>
    <method name='Next' />
    <method name='Previous' />
    <method name='Pause' />
    <method name='PlayPause' />
    <method name='Stop' />
    <method name='Play' />
    <method name='Seek'>
      <arg name='Offset' type='x' direction='in' />
    </method>
    <method name='SetPosition'>
      <arg name='TrackId' type='o' direction='in' />
      <arg name='Position' type='x' direction='in' />
    </method>
    <method name='OpenUri'>
      <arg name='Uri' type='s' direction='in' />
    </method>
    <signal name='Seeked'>
      <arg name='Position' type='x' />
    </signal>
    <property name='PlaybackStatus' type='s' access='read' />
    <property name='LoopStatus' type='s' access='readwrite' />
    <property name='Rate' type='d' access='readwrite'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='Shuffle' type='b' access='readwrite' />
    <property name='Metadata' type='a{sv}' access='read' />
    <property name='Volume' type='d' access='readwrite' />
    <property name='Position' type='x' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='false' />
    </property>
    <property name='MinimumRate' type='d' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='MaximumRate' type='d' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
    <property name='CanGoNext' type='b' access='read' />
    <property name='CanGoPrevious' type='b' access='read' />
    <property name='CanPlay' type='b' access='read' />
    <property name='CanPause' type='b' access='read' />
    <property name='CanSeek' type='b' access='read' />
    <property name='CanControl' type='b' access='read'>
      <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='const' />
    </property>
  </interface>
</node>
'''


class MprisPlugin:
    def enable(self, exaile):
        self.handler = MprisHandler(exaile)

    def disable(self, exaile):
        self.handler.disconnect()
        del self.handler

    def teardown(self, exaile):
        self.handler.teardown()


plugin_class = MprisPlugin


class MprisHandler:
    root_interface = player_interface = None

    def __init__(self, exaile):
        if not self.root_interface:
            nodeinfo = Gio.DBusNodeInfo.new_for_xml(MPRIS_INTROSPECTION)
            self.root_interface = nodeinfo.interfaces[0]
            self.player_interface = nodeinfo.interfaces[1]
        self.exaile = exaile
        self.connection = None
        self.object = None
        self.registrations = []
        Gio.bus_own_name(
            Gio.BusType.SESSION,
            'org.mpris.MediaPlayer2.exaile',
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            None,
            None,
        )

    def _on_bus_acquired(self, connection, name):
        self.connection = connection
        self.object = obj = mprisobject.MprisObject(self.exaile, connection)
        helper = dbushelper.DBusHelper(obj)
        self.registrations.append(
            connection.register_object(
                '/org/mpris/MediaPlayer2',
                self.root_interface,
                helper.method_call,
                helper.get_property,
                helper.set_property,
            )
        )
        self.registrations.append(
            connection.register_object(
                '/org/mpris/MediaPlayer2',
                self.player_interface,
                helper.method_call,
                helper.get_property,
                helper.set_property,
            )
        )

    def disconnect(self):
        # XXX: Should probably cancel bus_own_name if it's still running.
        # FIXME: disable+enable doesn't work
        connection, self.connection = self.connection, None
        registrations = self.registrations
        while registrations:
            connection.unregister_object(registrations.pop())
        if connection:
            connection.close_sync()

    def teardown(self):
        obj = self.object
        if obj:
            obj.teardown()

    def __del__(self):
        self.disconnect()
