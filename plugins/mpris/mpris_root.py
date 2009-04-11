import dbus
import dbus.service

from xl.nls import gettext as _

INTERFACE_NAME = 'org.freedesktop.MediaPlayer'

class ExaileMprisRoot(dbus.service.Object):

    """
        / (Root) object methods
    """

    def __init__(self, exaile, bus):
        dbus.service.Object.__init__(self, bus, '/')
        self.exaile = exaile

    @dbus.service.method(INTERFACE_NAME, out_signature="s")
    def Identity(self):
        """
            Identify the "media player"
        """
        return _("Exaile %(version)s") % {'version': self.exaile.get_version()}

    @dbus.service.method(INTERFACE_NAME)
    def Quit(self):
        """
            Makes the "Media Player" exit.
        """
        self.exaile.quit()

    @dbus.service.method(INTERFACE_NAME, out_signature="(qq)")
    def MprisVersion(self):
        """
            Makes the "Media Player" exit.
        """
        return (1, 0)

