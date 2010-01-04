# adopted from http://stackp.online.fr/?p=35

__all__ = ["Zeroconf"]

import select, sys, traceback

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
            #records as in mt-daapd
            txtRecord=pybonjour.TXTRecord()
            txtRecord['txtvers']            = '1'
            txtRecord['iTSh Version']       = '131073' #'196609'
            txtRecord['Machine Name']       = self.name
            txtRecord['Password']           = '0' # 'False' ?
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

            self.sdRef = pybonjour.DNSServiceRegister(name = self.name,
                                                      regtype = "_daap._tcp",
                                                      port = self.port,
                                                      callBack = register_callback,
                                                      txtRecord=txtRecord)
            
            while True:
                ready = select.select([self.sdRef], [], [])
                if self.sdRef in ready[0]:
                    pybonjour.DNSServiceProcessResult(self.sdRef)
                    break

        def unpublish(self):
            self.sdRef.close()

    class Avahi(Helper):
        def publish(self):
            import dbus, avahi
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
            
            self.group.AddService(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC,dbus.UInt32(0),
                         self.name, self.stype, self.domain, self.host,
                         dbus.UInt16(self.port), self.text)
            self.group.Commit()

        def unpublish(self):
            self.group.Reset()

    def __init__(self, *args, **kwargs):
        try:
            import pybonjour
            self.helper = Zeroconf.Pybonjour(*args, **kwargs)
        except:
            traceback.print_exc(file=sys.stdout)
            try:
                import avahi, dbus
                self.helper = Zeroconf.Avahi(*args, **kwargs)
            except:
                traceback.print_exc(file=sys.stdout)
                self.helper = None
                
    def publish(self):
        if self.helper != None:
            self.helper.publish()

    def unpublish(self):
        if self.helper != None:
            self.helper.unpublish()

