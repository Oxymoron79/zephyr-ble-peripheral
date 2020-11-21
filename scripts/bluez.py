import logging
import threading
import time
from gi.repository import Gio, GLib

__logger__ = logging.getLogger('bluez')

DBUS_OBJECT_MANAGER_INTERFACE = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'

BLUEZ_BUS_NAME = 'org.bluez'
BLUEZ_ADAPTER_INTERFACE = BLUEZ_BUS_NAME + '.Adapter1'
BLUEZ_DEVICE_INTERFACE = BLUEZ_BUS_NAME + '.Device1'

class _BaseObject:
    def __init__(self, bluez, object_path, interface_name):
        self._bluez = bluez
        self._proxy = bluez._om.get_interface(object_path, interface_name)
        self.__wait_condition = {}
        self._proxy.connect('g-properties-changed', self.__properties_changed_log)
    
    def __repr__(self):
        return '{}({}, {}, {})'.format(self.__class__.__name__,
                                       repr('Bluez()'),
                                       repr(self._proxy.get_object_path()),
                                       repr(self._proxy.get_interface_name()))
    
    def __str__(self):
        return '{} ({}, {})'.format(self.__class__.__name__,
                                    self._proxy.get_object_path(),
                                    self._proxy.get_interface_name())
    
    def __properties_changed_log(self, proxy, changed, invalidated):
        __logger__.debug('%s: Properties changed: %s', proxy.get_object_path(), changed.print_(True))
    
    def __wait_property_changed(self, proxy, changed, invalidated):
        for k in changed.keys():
            if k in self.__wait_condition.keys() and self.__wait_condition[k]['value'] == changed.lookup_value(k).unpack():
                cv = self.__wait_condition[k]['cv']
                with cv:
                    cv.notifyAll()
    
    def __wait_property_timeout(self, property):
        if property in self.__wait_condition.keys():
            self.__wait_condition[property]['timeout'] = True
            cv = self.__wait_condition[property]['cv']
            with cv:
                cv.notifyAll()
        return False
    
    def _wait_property_change(self, property, value, timeout_ms=10000):
        cv = threading.Condition()
        self.__wait_condition[property] = {'cv': cv, 'timeout': False, 'value': value}
        pc = self._proxy.connect('g-properties-changed', self.__wait_property_changed)
        tmo = GLib.timeout_add(timeout_ms, self.__wait_property_timeout, property)
        with cv:
            cv.wait()
        self._proxy.disconnect(pc)
        timeout = self.__wait_condition[property]['timeout']
        self.__wait_condition.pop(property, None)
        if timeout:
            raise Exception('Timeout')
        GLib.source_remove(tmo)
    
    def _get_property(self, name):
        return self._proxy.get_cached_property(name)

class Device(_BaseObject):
    def __init__(self, bluez, object_path, interface_name):
        super().__init__(bluez, object_path, interface_name)

    @property
    def Address(self):
        return self._get_property('Address').unpack()
     
    @property
    def Name(self):
        return self._get_property('Name').unpack()
     
    @property
    def RSSI(self):
        return self._get_property('RSSI').unpack()
     
    @property
    def Connected(self):
        return self._get_property('Connected').unpack()
     
    @property
    def UUIDs(self):
        return self._get_property('UUIDs').unpack()
     
    @property
    def ServicesResolved(self):
        return self._get_property('ServicesResolved')
     
    def connect(self, wait_for_services=True, timeout_ms=10000):
        if self.Connected:
            __logger__.info('%s: Already connected.', self._proxy.get_object_path())
            return
        self._proxy.Connect()
        if wait_for_services:
            self._wait_property_change('ServicesResolved', True, timeout_ms)
        else:
            self._wait_property_change('Connected', True, timeout_ms)
     
    def disconnect(self, timeout_ms=10000):
        if not self.Connected:
            __logger__.info('%s: Not connected.', self._proxy.get_object_path())
            return
        self._proxy.Disconnect()
        self._wait_property_change('Connected', False, timeout_ms)

class Adapter(_BaseObject):
    def __init__(self, bluez, object_path, interface_name):
        super().__init__(bluez, object_path, interface_name)
    
    @property
    def Address(self):
        return self._get_property('Address').unpack()
     
    @property
    def Name(self):
        return self._get_property('Name').unpack()
     
    @property
    def Discovering(self):
        return self._get_property('Discovering').unpack()
    
    def start_discovery(self):
        """Start device discovery.
        
        :Returns: `None`
        """
        if self.Discovering:
            __logger__.info('%s: Already discovering.', self._proxy.get_object_path())
            return
        try:
            self._proxy.StartDiscovery()
            self._wait_property_change('Discovering', True)
        except BaseException as e:
            __logger__.error('%s: StartDiscovery failed: %s', self._proxy.get_object_path(), e)
    
    def stop_discovery(self):
        """Stop device discovery.
         
        :Returns: `None`
        """
        if not self.Discovering:
            __logger__.info('%s: Not discovering.', self._proxy.get_object_path())
            return
        try:
            self._proxy.StopDiscovery()
            self._wait_property_change('Discovering', False)
        except BaseException as e:
            __logger__.error('%s: StopDiscovery failed: %s', self._proxy.get_object_path(), e)
    
    def get_devices(self, serviceUUID=None):
        """Get all devices associated with the adapter.
         
        :Returns: `[ bluez.Device ]`
        """
        devices = [Device(self._bluez, path, BLUEZ_DEVICE_INTERFACE) for path, ifaces in self._bluez._objects.items()
                   if path.startswith(self._proxy.get_object_path()) and BLUEZ_DEVICE_INTERFACE in ifaces]
        if not serviceUUID:
            return devices
        return [d for d in devices if serviceUUID in d.UUIDs]

class Manager:
    class _MainLoop(threading.Thread):
        def __init__(self):
            super().__init__()
            self.loop = GLib.MainLoop()
        
        def run(self):
            self.loop.run()
        
        def stop(self):
            self.loop.quit()

    def __init__(self):
        self._mainloop = self._MainLoop()
        self._mainloop.daemon = True
        self._mainloop.start()
        # https://lazka.github.io/pgi-docs/Gio-2.0/classes/DBusObjectManager.html
        self._om = Gio.DBusObjectManagerClient.new_for_bus_sync(bus_type=Gio.BusType.SYSTEM,
                                                                flags=Gio.DBusProxyFlags.NONE,
                                                                name=BLUEZ_BUS_NAME,
                                                                object_path='/',
                                                                get_proxy_type_func=None,
                                                                get_proxy_type_user_data=None,
                                                                cancellable=None)
        self._om.connect('object-added', self.__object_added)
        self._om.connect('object-removed', self.__object_removed)
        self._objects = {}
        for o in self._om.get_objects():
            self._objects[o.get_object_path()] = [i.get_interface_name() for i in o.get_interfaces()]
    
    def __object_added(self, om, object):
        p = object.get_object_path()
        ifs = [i.get_interface_name() for i in object.get_interfaces()]
        self._objects[p] = ifs
        __logger__.debug('Object added: %s: %s', p, str(ifs))
    
    def __object_removed(self, om,  object):
        p = object.get_object_path()
        self._objects.pop(p, None)
        __logger__.debug('Object removed: %s', p)
    
    def get_adapter(self, pattern=None):
        """Returns the first bluetooth adapter found.
        
        :Parameters:
            `pattern` : str
                A adapter name (e.g. hci0) or address (XX:XX:XX:XX:XX:XX)
        
        :Returns: a `bluez.Adapter`
        :Raises `Exception`: if there are no bluetooth adapters available or none matched the `pattern`
        """
        for path, ifaces in self._objects.items():
            if BLUEZ_ADAPTER_INTERFACE not in ifaces:
                continue
            adapter = Adapter(self, path, BLUEZ_ADAPTER_INTERFACE)
            if not pattern or path.endswith(pattern) or pattern == adapter.Address:
                return adapter
        raise Exception("No bluetooth adapter found")

if __name__ == "__main__":
    from pprint import pprint
    logging.basicConfig(level=logging.INFO)
    try:
        mgr = Manager();
        print(len(mgr._objects), 'objects: ', repr(mgr._objects))
        a = mgr.get_adapter('hci0')
        print('Adapter', a.Name, a.Address)
        
        if not a.Discovering:
            print('Start discovery')
            a.start_discovery()
            
            print('Sleep for 2 sec.')
            time.sleep(2)
            
            print('Stop discovery')
            a.stop_discovery()
        
        devices = a.get_devices(serviceUUID='12345678-1234-5678-1234-56789abcdef0')
        print('Discovered devices:', repr(devices))
        
        if len(devices) > 0:
            d = devices[0]
            print('Connect to', d)
            d.connect()
            print('Done.')
            
            print('Disconnect', d)
            d.disconnect()
            print('Done.')
    except BaseException as e:
        print('Caught exception: {}'.format(e))
    print('Exit')
