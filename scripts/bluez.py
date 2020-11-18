__all__ = ('objects', 'start', 'stop', 'get_adapter')
__docformat__ = 'reStructuredText'
import logging
import threading
import time
from gi.repository import GLib
import dbus
from dbus.mainloop.glib import DBusGMainLoop, threads_init

__logger__ = logging.getLogger('bluez')
__mainloop__ = None
__bus__ = None

DBUS_OBJECT_MANAGER_INTERFACE = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'

BLUEZ_BUS_NAME = 'org.bluez'
BLUEZ_ADAPTER_INTERFACE = BLUEZ_BUS_NAME + '.Adapter1'
BLUEZ_DEVICE_INTERFACE = BLUEZ_BUS_NAME + '.Device1'

objects = {}

class _MainLoop(threading.Thread):
    def __init__(self):
        super().__init__()
        self.loop = GLib.MainLoop()

    def run(self):
        self.loop.run()

    def stop(self):
        self.loop.quit()

def __interfaces_added__(object_path, interfaces):
    global objects
    __logger__.debug('Interfaces added on %s: %s', object_path, repr([k for k in interfaces]))
    objects[object_path] = interfaces

def __interfaces_removed__(object_path, interfaces):
    global objects
    __logger__.debug('Interfaces removed from %s: %s', object_path, repr([k for k in interfaces]))
    objects.pop(object_path, None)

class _BaseObject:
    def __init__(self, object_path, interfaces):
        self._path = object_path
        self._object = __bus__.get_object(BLUEZ_BUS_NAME, self._path)
        self._ifaces = {}
        self._block_condition = {}
        if DBUS_PROPERTIES_INTERFACE in interfaces:
            self.__add_interface__(DBUS_PROPERTIES_INTERFACE)
            __bus__.add_signal_receiver(handler_function=self.__properties_changed__, signal_name='PropertiesChanged',
                            dbus_interface=DBUS_PROPERTIES_INTERFACE, bus_name=BLUEZ_BUS_NAME, 
                            path=object_path)
    
    def __repr__(self):
        return '{} ({}, {})'.format(self.__class__.__name__, repr(str(self._path)), repr([k for k in self._ifaces.keys()]))
    
    def __add_interface__(self, interface):
        self._ifaces[interface] = dbus.Interface(self._object, interface)
    
    def __properties_changed__(self, interface, changed, invalidated):
        __logger__.debug('%s: Properties changed: %s', self._path, repr(changed))
        if self._path not in objects.keys():
            __logger__.error('%s: Removed.', self._path)
            return
        for property, value in changed.items():
            objects[self._path][interface][property] = value
        for property in invalidated:
            objects[self._path][interface][property] = None
    
    def __block_until__(self, interface, property, value, timeout=10):
        duration = 0
        while duration < timeout and self._path in objects.keys() and objects[self._path][interface][property] != value:
            time.sleep(0.1)
            duration += 0.1
        if duration >= timeout:
            raise Exception('Timeout')
        if self._path not in objects.keys():
            __logger__.error('%s: Removed.', self._path)
            raise Exception('Removed')
    
    def __get_interface__(self, interface):
        if interface not in self._ifaces:
            raise Exception('Interface not available: {}'.format(interface))
        return self._ifaces[interface]
    
    def __get_property__(self, interface, name):
        return self.__get_interface__(DBUS_PROPERTIES_INTERFACE).Get(interface, name)

class Device(_BaseObject):
    def __init__(self, object_path, interfaces):
        super().__init__(object_path, interfaces)
        self.__add_interface__(BLUEZ_DEVICE_INTERFACE)
    
    def __str__(self):
        d = objects[self._path][BLUEZ_DEVICE_INTERFACE]
        return '{}({})'.format(d['Name'],  d['Address'])
    
    @property
    def Address(self):
        return self.__get_property__(BLUEZ_DEVICE_INTERFACE, 'Address')
    
    @property
    def Name(self):
        return self.__get_property__(BLUEZ_DEVICE_INTERFACE, 'Name')
    
    @property
    def RSSI(self):
        return self.__get_property__(BLUEZ_DEVICE_INTERFACE, 'RSSI')
    
    @property
    def Connected(self):
        return self.__get_property__(BLUEZ_DEVICE_INTERFACE, 'Connected')
    
    @property
    def UUIDs(self):
        return self.__get_property__(BLUEZ_DEVICE_INTERFACE, 'UUIDs')
    
    @property
    def ServicesResolved(self):
        return self.__get_property__(BLUEZ_DEVICE_INTERFACE, 'ServicesResolved')
    
    def connect(self, wait_for_services=True, timeout=10):
        if self.Connected:
            __logger__.debug('%s: Already connected.', self._path)
            return
        self.__get_interface__(BLUEZ_DEVICE_INTERFACE).Connect()
        if wait_for_services:
            self.__block_until__(BLUEZ_DEVICE_INTERFACE, 'ServicesResolved', True, timeout)
        else:
            self.__block_until__(BLUEZ_DEVICE_INTERFACE, 'Connected', True, timeout)
    
    def disconnect(self, timeout=10):
        if not self.Connected:
            __logger__.debug('%s: Not connected.', self._path)
            return
        self.__get_interface__(BLUEZ_DEVICE_INTERFACE).Disconnect()
        self.__block_until__(BLUEZ_DEVICE_INTERFACE, 'Connected', False, timeout)

class Adapter(_BaseObject):
    def __init__(self, object_path, interfaces):
        super().__init__(object_path, interfaces)
        self.__add_interface__(BLUEZ_ADAPTER_INTERFACE)
    
    @property
    def Address(self):
        return self.__get_property__(BLUEZ_ADAPTER_INTERFACE, 'Address')
    
    @property
    def Name(self):
        return self.__get_property__(BLUEZ_ADAPTER_INTERFACE, 'Name')
    
    @property
    def Discovering(self):
        return bool(self.__get_property__(BLUEZ_ADAPTER_INTERFACE, 'Discovering'))
    
    def start_discovery(self, filter=None):
        """Start device discovery with an optional discovery filter.
        
        :Parameters:
            `filter` : dict
                Parameters that may be set in the filter dictionary
                include the following:
                
                array{string} UUIDs
                    Filter by service UUIDs, empty means match
                    _any_ UUID.
                    
                    When a remote device is found that advertises
                    any UUID from UUIDs, it will be reported if:
                    - Pathloss and RSSI are both empty.
                    - only Pathloss param is set, device advertise
                      TX pwer, and computed pathloss is less than
                      Pathloss param.
                    - only RSSI param is set, and received RSSI is
                      higher than RSSI param.
                
                int16 RSSI
                    RSSI threshold value.
                    
                    PropertiesChanged signals will be emitted
                    for already existing Device objects, with
                    updated RSSI value. If one or more discovery
                    filters have been set, the RSSI delta-threshold,
                    that is imposed by StartDiscovery by default,
                    will not be applied.
                
                uint16 Pathloss
                    Pathloss threshold value.
                    
                    PropertiesChanged signals will be emitted
                    for already existing Device objects, with
                    updated Pathloss value.
                
                string Transport (Default "auto")
                    Transport parameter determines the type of
                    scan.
                    Possible values:
                        "auto"    - interleaved scan
                        "bredr"    - BR/EDR inquiry
                        "le"    - LE scan only
                    
                    If "le" or "bredr" Transport is requested,
                    and the controller doesn't support it,
                    org.bluez.Error.Failed error will be returned.
                    If "auto" transport is requested, scan will use
                    LE, BREDR, or both, depending on what's
                    currently enabled on the controller.
                    
                bool DuplicateData (Default: true)
                    Disables duplicate detection of advertisement
                    data.
                    
                    When enabled PropertiesChanged signals will be
                    generated for either ManufacturerData and
                    ServiceData everytime they are discovered.
                
                bool Discoverable (Default: false)
                    Make adapter discoverable while discovering,
                    if the adapter is already discoverable setting
                    this filter won't do anything.

                string Pattern (Default: none)
                    Discover devices where the pattern matches
                    either the prefix of the address or
                    device name which is convenient way to limited
                    the number of device objects created during a
                    discovery.
                    
                    When set disregards device discoverable flags.
                    
                    Note: The pattern matching is ignored if there
                    are other client that don't set any pattern as
                    it work as a logical OR, also setting empty
                    string "" pattern will match any device found.
                    
                When discovery filter is set, Device objects will be
                created as new devices with matching criteria are
                discovered regardless of they are connectable or
                discoverable which enables listening to
                non-connectable and non-discoverable devices.
        
        :Returns: a `bluez.Adapter`
        :Raises `org.bluez.Error.InvalidArguments`: if the filter contains an invalid key.
                `org.bluez.Error.NotReady`,
                `org.bluez.Error.NotSupported`
                `org.bluez.Error.Failed`
        """
        adapter_iface = self.__get_interface__(BLUEZ_ADAPTER_INTERFACE)
        if filter:
            adapter_iface.SetDiscoveryFilter(filter)
        if self.Discovering:
            __logger__.debug('%s: Already discovering.', self._path)
            return
        adapter_iface.StartDiscovery()
        self.__block_until__(BLUEZ_ADAPTER_INTERFACE, 'Discovering', True)
    
    def stop_discovery(self):
        """Stop device discovery and clear the discovery filter.
        
        :Returns: None
        """
        adapter_iface = self.__get_interface__(BLUEZ_ADAPTER_INTERFACE)
        if not self.Discovering:
            __logger__.debug('%s: Not discovering.', self._path)
        else:
            try:
                adapter_iface.StopDiscovery()
                self.__block_until__(BLUEZ_ADAPTER_INTERFACE, 'Discovering', True)
            except BaseException as e:
                __logger__.error('StopDiscovery failed: %s', e)
        try:
            adapter_iface.SetDiscoveryFilter({})
        except BaseException as e:
            __logger__.error('SetDiscoveryFilter failed: %s', e)
    
    def get_devices(self):
        """Get all devices associated with the adapter.
        
        :Returns: `[ bluez.Device ]`
        """
        return [Device(path, ifaces.keys()) for path, ifaces in objects.items()
                if path.startswith(self._path) and BLUEZ_DEVICE_INTERFACE in ifaces.keys()]

def start():
    """Starts the event handling loop and initializes the connection to DBus.
    
    Needs to be called before any other methods in this module are used in the application.
    
    :Returns: None
    """
    global __bus__, __mainloop__, objects
    threads_init()
    DBusGMainLoop(set_as_default=True)
    __bus__ = dbus.SystemBus(private=True)
    __bus__.add_signal_receiver(handler_function=__interfaces_added__, signal_name='InterfacesAdded',
                                dbus_interface=DBUS_OBJECT_MANAGER_INTERFACE, bus_name=BLUEZ_BUS_NAME, 
                                path='/')
    __bus__.add_signal_receiver(handler_function=__interfaces_removed__, signal_name='InterfacesRemoved',
                                dbus_interface=DBUS_OBJECT_MANAGER_INTERFACE, bus_name=BLUEZ_BUS_NAME, 
                                path='/')
    om = dbus.Interface(__bus__.get_object(BLUEZ_BUS_NAME, '/'), DBUS_OBJECT_MANAGER_INTERFACE)
    __mainloop__ = _MainLoop()
    __mainloop__.start()
    objects = om.GetManagedObjects()

def stop():
    """Stops the event handling loop and close the connection to DBus.
    
    Needs to be called before the application exits.
    
    :Returns: None
    """
    global __bus__, __mainloop__, objects
    objects.clear()
    __bus__.remove_signal_receiver(__interfaces_added__, signal_name='InterfacesAdded',
                                   dbus_interface=DBUS_OBJECT_MANAGER_INTERFACE, bus_name=BLUEZ_BUS_NAME, path='/')
    __bus__.remove_signal_receiver(__interfaces_removed__, signal_name='InterfacesRemoved',
                                   dbus_interface=DBUS_OBJECT_MANAGER_INTERFACE, bus_name=BLUEZ_BUS_NAME, path='/')
    __bus__.flush()
    __bus__.close()
    del __bus__
    __mainloop__.stop()
    __mainloop__.join()
    del __mainloop__

def get_adapter(pattern=None):
    """Returns the first bluetooth adapter found.

    :Parameters:
        `pattern` : str
            A adapter name (e.g. hci0) or address (XX:XX:XX:XX:XX:XX)

    :Returns: a `bluez.Adapter`
    :Raises `Exception`: if there are no bluetooth adapters available or none matched the `pattern`
    """
    for path, ifaces in objects.items():
        adapter = ifaces.get(BLUEZ_ADAPTER_INTERFACE)
        if adapter is None:
            continue
        if not pattern or pattern == adapter["Address"] or path.endswith(pattern):
            return Adapter(path, ifaces.keys())
    raise Exception("No bluetooth adapter found")

if __name__ == "__main__":
    from pprint import pprint
    try:
        logging.basicConfig(level=logging.INFO)
        start();
        a = get_adapter('hci0')
        print('Start discovery')
        a.start_discovery({'UUIDs': ['00000100-f5bf-58d5-9d17-172177d1316a', '12345678-1234-5678-1234-56789abcdef0']})
        time.sleep(1)
        print('Stop discovery')
        a.stop_discovery()
        d = a.get_devices()[0]
        print('Connect to', d)
        d.connect()
        print('Done.')
        print('Disconnect', d)
        d.disconnect()
        print('Done.')
    except BaseException as e:
        print('Caught exception: {}'.format(e))
    print('End')
    stop()
    print('Exit')
