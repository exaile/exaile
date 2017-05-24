# adopted from http://stackp.online.fr/?p=35

__all__ = ["Zeroconf"]

import select
import logging

logger = logging.getLogger(__name__)


class Zeroconf(object):
    """A simple class to publish a network service with zeroconf using
    avahi or pybonjour, preferring pybonjour.
    """

    class Helper(object):

        def __init__(self, name, port, **kwargs):
            self.name = name
            self.port = port
            self.stype = kwargs.get('stype', "_http._tcp")
            self.domain = kwargs.get('domain', '')
            self.host = kwargs.get('host', '')
            self.text = kwargs.get('text', '')

    class Pybonjour(Helper):

        def publish(self):
            import pybonjour
            # records as in mt-daapd
            txtRecord = pybonjour.TXTRecord()
            txtRecord['txtvers']            = '1'
            txtRecord['iTSh Version']       = '131073'  #'196609'
            txtRecord['Machine Name']       = self.name
            txtRecord['Password']           = '0'  # 'False' ?
            #txtRecord['Database ID']        = '' # 16 hex digits
            #txtRecord['Version']            = '196616'
            #txtRecord['iTSh Version']       =
            #txtRecord['Machine ID']         = '' # 12 hex digits
            #txtRecord['Media Kinds Shared'] = '0'
            #txtRecord['OSsi']               = '0x1F6' #?
            #txtRecord['MID']                = '0x3AA6175DD7155BA7', = database id - 2 ?
            #txtRecord['dmv']                = '131077'

            def register_callback(sdRef, flags, errorCode, name, regtype, domain):
                pass

            self.sdRef = pybonjour.DNSServiceRegister(name=self.name,
                                                      regtype="_daap._tcp",
                                                      port=self.port,
                                                      callBack=register_callback,
                                                      txtRecord=txtRecord)

            while True:
                ready = select.select([self.sdRef], [], [])
                if self.sdRef in ready[0]:
                    pybonjour.DNSServiceProcessResult(self.sdRef)
                    break

        def unpublish(self):
            self.sdRef.close()

    class Avahi(Helper):

        def publish(self, ipv4=True, ipv6=True):
            import dbus
            import avahi
            bus = dbus.SystemBus()
            server = dbus.Interface(
                bus.get_object(
                    avahi.DBUS_NAME,
                    avahi.DBUS_PATH_SERVER),
                avahi.DBUS_INTERFACE_SERVER)

            self.group = dbus.Interface(
                bus.get_object(avahi.DBUS_NAME,
                               server.EntryGroupNew()),
                avahi.DBUS_INTERFACE_ENTRY_GROUP)

            if ipv4 and ipv6:
                prot = avahi.PROTO_UNSPEC
            elif ipv6:
                proto = avahi.PROTO_INET6
            else:  # we don't let them both be false
                proto = avahi.PROTO_INET

            self.group.AddService(avahi.IF_UNSPEC, proto,
                                  dbus.UInt32(0), self.name, self.stype, self.domain,
                                  self.host, dbus.UInt16(self.port), self.text)
            self.group.Commit()

        def unpublish(self):
            self.group.Reset()

    def __init__(self, *args, **kwargs):
        try:
            import pybonjour
            self.helper = Zeroconf.Pybonjour(*args, **kwargs)
        except ImportError:
            logger.info('pybonjour not found, using avahi')
            try:
                import avahi
                import dbus
                self.helper = Zeroconf.Avahi(*args, **kwargs)
            except ImportError:
                logger.warning('pybonjour nor avahi found, cannot announce presence')
                self.helper = None

    def publish(self, *args, **kwargs):
        if self.helper is not None:
            self.helper.publish(*args, **kwargs)

    def unpublish(self):
        if self.helper is not None:
            self.helper.unpublish()
