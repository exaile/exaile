

import dbus

from xl import devices, common



class HAL(object):
    """
        HAL interface
    """
    def __init__(self, devicemanager):
        self.devicemanager = devicemanager
        
        self.bus = None
        self.hal = None

        self.hal_devices = {}

        self.connect()

    def connect(self):
        try:
            self.bus = dbus.SystemBus()

            hal_obj = self.bus.get_object('org.freedesktop.Hal', 
                '/org/freedesktop/Hal/Manager')

            self.hal = dbus.Interface(hal_obj, 'org.freedesktop.Hal.Manager')
        
            self.initial_device_setup()
        except:
            common.log_exception()

    @common.threaded
    def initial_device_setup(self):
        self.setup_cds_initial()
        self.setup_device_events()

    def setup_cds_initial(self):
        udis = self.hal.FindDeviceByCapability("volume.disc")

        for udi in udis:
            self.add_cd_device(udi)


    def add_cd_device(self, udi):
        cd_obj = self.bus.get_object("org.freedesktop.Hal", udi)
        cd = dbus.Interface(cd_obj, "org.freedesktop.Hal.Device")
        if not cd.GetProperty("volume.disc.has_audio"):
            return #not CD-Audio
            #TODO: implement mp3 cd support
        device = str(cd.GetProperty("block.device"))

        cddev = devices.CDDevice( dev=device)

        cddev.connect()
        
        self.devicemanager.add_device(cddev)
        self.hal_devices[udi] = cddev


    def handle_device_added(self, device_udi):
        dev_obj = self.bus.get_object("org.freedesktop.Hal", device_udi)
        device = dbus.Interface(dev_obj, "org.freedesktop.Hal.Device")
        capabilities = device.GetProperty("info.capabilities")
        if "volume.disc" in capabilities:
            self.add_cd_device(device_udi)


    def handle_device_removed(self, device_udi):
        try:
            self.devicemanager.remove_device(self.hal_devices[device_udi])
            del self.hal_devices[device_udi]
        except KeyError:
            pass

    def setup_device_events(self):
        self.bus.add_signal_receiver(self.handle_device_added,
                "DeviceAdded")
        self.bus.add_signal_receiver(self.handle_device_removed,
                "DeviceRemoved")



