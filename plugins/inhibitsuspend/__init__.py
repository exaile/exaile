"""
    This plugin will make an IPC call to prevent the computer from suspending
    during music playback

    TODO: use Gtk.Application.inhibit() for less error prone inhibition.
"""

try:
    import _thread
except ImportError:
    import _dummy_thread as _thread
import logging
import os

import dbus
import subprocess

from xl.player import adapters, PLAYER

SUSPEND_PLUGIN = None
logger = logging.getLogger(__name__)


def enable(exaile):
    """
    Called when the plugin is enabled
    """
    global SUSPEND_PLUGIN

    if SUSPEND_PLUGIN is None:
        try:
            SUSPEND_PLUGIN = SuspendInhibit()
        except EnvironmentError:
            logger.error('Failed to Acquire Suspend Bus')
            raise
        except NotImplementedError:
            logger.error('Desktop Session not implemented')
            raise

        # allow plugin to finished enabling so that if user returns
        # to gnome plugin will not have to be re-enabled

    logger.info('Suspend Inhibitor Enabled')


def disable(exaile):
    """
    Called when the plugin is disabled
    """
    global SUSPEND_PLUGIN

    if SUSPEND_PLUGIN is not None:
        SUSPEND_PLUGIN.destroy()
        SUSPEND_PLUGIN = None

    logger.info('Suspend Inhibitor Disabled')


class SuspendInhibit:
    """
    Attempt to detect desktop session and initialize appropriate adapter
    """

    def __init__(self):
        # Attempt to detect Desktop Session Type
        session = os.getenv('DESKTOP_SESSION', '').lower()
        # see https://askubuntu.com/questions/72549/how-to-determine-which-window-manager-is-running
        xdg_session = os.getenv('XDG_CURRENT_DESKTOP', '').lower()

        # Attempt to find an adaptor that works
        if 'gnome' in session or 'gnome' in xdg_session:
            self.adapter = GnomeAdapter()
        elif 'kde' in session or 'kde' in xdg_session:
            try:
                self.adapter = PowerManagerAdapter()
            except EnvironmentError:
                # Fall back to powerdevil
                self.adapter = KdeAdapter()
        elif 'xfce' in session or 'xfce' in xdg_session:
            self.adapter = XfceAdapter()
        elif 'sway' in session or 'sway' in xdg_session:
            self.adapter = SwayAdapter()
        # TODO implement for LXDE, X-Cinnamon, Unity; systemd-inhibit
        elif session == '' and xdg_session == '':
            logger.warning(
                'Could not detect Desktop Session, will try default \
                    Power Manager then Gnome'
            )
            try:
                self.adapter = PowerManagerAdapter()
            except EnvironmentError:
                # Fall back to Gnome power manager
                self.adapter = GnomeAdapter()
        else:
            raise NotImplementedError(xdg_session)

    def destroy(self):
        self.adapter.destroy()


class SuspendAdapter(adapters.PlaybackAdapter):
    """
    Base class for Desktop Session suspend inhibitors

    Subclasses will have to override the DBus call methods

    Thread safe
    """

    PROGRAM = 'exaile'
    ACTIVITY = 'playing-music'

    def __init__(self):
        self.inhibited = False
        self.lock = _thread.allocate_lock()

        # Initialize parent object
        super().__init__(PLAYER)

        # Inhibit if player currently playing
        if PLAYER.is_playing():
            self.inhibit()

    def inhibit(self):
        """
        Inhibit user session suspension.

        Make DBus call to inhibit session suspension if
        session suspension not already inhibited.

        If suspending already inhibited call does nothing.
        """

        with self.lock:
            if not self.inhibited:
                self._inhibit_call()
                self.inhibited = True
                logger.info('Inhibited Suspend')

    def uninhibit(self):
        """
        Uninhibit user session suspension.

        If suspending already uninhibited call does nothing.
        """

        with self.lock:
            if self.inhibited:
                self._uninhibit_call()
                self.inhibited = False
                logger.info('Uninhibited Suspend')

    def is_inhibited(self):
        """Inhibit Status"""
        return self.inhibited

    def destroy(self):
        """Cleanup"""
        # Make sure to uninhibit when exiting
        self.uninhibit()
        adapters.PlaybackAdapter.destroy(self)
        logger.debug('Adapter Destroyed')

    """
        Playback Adapter Callbacks
    """

    def on_playback_track_start(self, event, player, track):
        self.inhibit()

    def on_playback_player_end(self, event, player, track):
        self.uninhibit()

    def on_playback_toggle_pause(self, event, player, track):
        if player.is_playing():
            self.inhibit()
        else:
            self.uninhibit()

    def _inhibit_call(self):
        """
        Override, overriding method must set self.inhibited value
        Must not block
        """
        raise NotImplementedError('Method not Overridden')

    def _uninhibit_call(self):
        """
        Override, overriding method must set self.inhibited value
        Must not block
        """
        raise NotImplementedError('Method not Overridden')


class DbusSuspendAdapter(SuspendAdapter):
    def __init__(self, bus_name, object_path, interface):
        try:
            bus = dbus.SessionBus()
            obj = bus.get_object(bus_name, object_path)
            self.iface = dbus.Interface(obj, interface)
            logger.info('Suspend Bus Acquired')
        except dbus.DBusException:
            raise EnvironmentError(bus_name + ' bus not available')

        super().__init__()

    def uninhibit(self):
        """
        Uninhibit user session suspension.

        Make DBus call to uninhibit session suspension if
        session suspension not already uninhibited.

        If suspending already uninhibited call does nothing.
        """

        with self.lock:
            if self.inhibited:
                if self.cookie is not None:
                    self._uninhibit_call()
                    self.cookie = None
                    self.inhibited = False
                    logger.info('Unihibited Suspend')
                else:
                    logger.error('Cannot Uninhibit Suspend without cookie')


class PowerManagerAdapter(DbusSuspendAdapter):
    """
    Default Adapter, implemented by most desktop sessions
    Adapter for org.freedesktop.PowerManagement.Inhibit Interface
    Some desktop sesssions use different bus names for this interface
    and have other small variances
    """

    def __init__(
        self,
        bus_name='org.freedesktop.PowerManagement',
        object_name='/org/freedesktop/PowerManagement/Inhibit',
        interface_name='org.freedesktop.PowerManagement.Inhibit',
    ):
        super().__init__(bus_name, object_name, interface_name)

    def _dbus_inhibit_call(self):
        self.cookie = self.iface.Inhibit(self.PROGRAM, self.ACTIVITY)

    def _dbus_uninhibit_call(self):
        self.iface.UnInhibit(self.cookie)


class GnomeAdapter(DbusSuspendAdapter):
    """
    Gnome uses a similar interface to org.freedesktop.PowerManagement
    but is has different bus name, object path and interface name
    The inhibit and uninhibit method signatures are also different
    """

    SUSPEND_FLAG = 8

    def __init__(self):
        super().__init__(
            'org.gnome.SessionManager',
            '/org/gnome/SessionManager',
            'org.gnome.SessionManager',
        )

    def _dbus_inhibit_call(self):
        """
        Gnome Interface has more paramters
        """
        self.cookie = self.iface.Inhibit(
            self.PROGRAM, 1, self.ACTIVITY, self.SUSPEND_FLAG
        )

    def _dbus_uninhibit_call(self):
        """
        Gnome Interface has different case
        """
        self.iface.Uninhibit(self.cookie)


class KdeAdapter(PowerManagerAdapter):
    """
    Adapter for when org.freedesktop.PowerManager interface
    located at bus org.kde.powerdevil
    """

    def __init__(self):
        try:
            super().__init__()
        except EnvironmentError:
            # Fall back to other bus name
            super().__init__(bus_name='org.kde.powerdevil')


class XfceAdapter(PowerManagerAdapter):
    """
    Adapter for org.freedesktop.PowerManagement interface at bus name
    org.xfce.PowerManager
    """

    def __init__(self):
        try:
            super().__init__()
        except EnvironmentError:
            # Fall back to other bus name
            super().__init__(bus_name='org.xfce.PowerManager')


class SwayAdapter(SuspendAdapter):
    """
    Adapter for sway's IPC protocol/tool.
    """

    def _sway_inhibit_idle(self, status):
        subprocess.run(['swaymsg', '[app_id="exaile"]', 'inhibit_idle', status])

    def _inhibit_call(self):
        self._sway_inhibit_idle('open')

    def _uninhibit_call(self):
        self._sway_inhibit_idle('none')
