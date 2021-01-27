# Copyright (c) 2021 Martin Roesch
# SPDX-License-Identifier: Apache-2.0

import logging
import threading
import time
from contextlib import contextmanager
from queue import SimpleQueue
import os
import select
from gi.repository import Gio, GLib

__logger__ = logging.getLogger('bluez')

DBUS_OBJECT_MANAGER_INTERFACE = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'

BLUEZ_BUS_NAME = 'org.bluez'
BLUEZ_ADAPTER_INTERFACE = BLUEZ_BUS_NAME + '.Adapter1'
BLUEZ_DEVICE_INTERFACE = BLUEZ_BUS_NAME + '.Device1'
BLUEZ_GATTSERVICE_INTERFACE = BLUEZ_BUS_NAME + '.GattService1'
BLUEZ_GATTCHARACTERISTIC_INTERFACE = BLUEZ_BUS_NAME + '.GattCharacteristic1'

class _BaseObject:
    def __init__(self, bluez, object_path, interface_name):
        self._bluez = bluez
        self._proxy = bluez._om.get_interface(object_path, interface_name)
        self.__wait_condition = None
        self._proxy.connect('g-properties-changed', self.__properties_changed_log)
    
    def __repr__(self):
        return f'{self.__class__.__name__}(\'Bluez()\', {self._proxy.get_object_path()!r}, {self._proxy.get_interface_name()!r})'
    
    def __str__(self):
        return f'{self.__class__.__name__} ({self._proxy.get_object_path()}, {self._proxy.get_interface_name()})'
    
    def __properties_changed_log(self, proxy, changed, invalidated):
        __logger__.debug(f'{proxy.get_object_path()}: Properties changed: {changed.print_(True)}')
    
    def __wait_property_changed(self, proxy, changed, invalidated):
        if self.__wait_condition:
            if self.__wait_condition['check'](changed):
                cv = self.__wait_condition['cv']
                with cv:
                    cv.notifyAll()
    
    def __wait_property_timeout(self):
        if self.__wait_condition:
            self.__wait_condition['timeout'] = True
            cv = self.__wait_condition['cv']
            with cv:
                cv.notifyAll()
        return False
    
    def _wait_property_change(self, check_fn, timeout_ms=1000):
        cv = threading.Condition()
        assert self.__wait_condition is None
        self.__wait_condition = {'cv': cv, 'timeout': False, 'check': check_fn}
        pc = self._proxy.connect('g-properties-changed', self.__wait_property_changed)
        tmo = GLib.timeout_add(timeout_ms, self.__wait_property_timeout)
        with cv:
            cv.wait()
        self._proxy.disconnect(pc)
        timeout = self.__wait_condition['timeout']
        self.__wait_condition = None
        if timeout:
            raise Exception('Timeout')
        GLib.source_remove(tmo)
    
    def __wait_object_added(self, om, object):
        if self.__wait_condition:
            ifname = self.__wait_condition['interface']
            iface = None
            for i in object.get_interfaces():
                if i.get_interface_name() == ifname:
                    iface = i
            if iface and self.__wait_condition['check'](iface):
                cv = self.__wait_condition['cv']
                with cv:
                    cv.notifyAll()
    
    def __wait_object_timeout(self):
        if self.__wait_condition:
            self.__wait_condition['timeout'] = True
            cv = self.__wait_condition['cv']
            with cv:
                cv.notifyAll()
        return False
    
    def _wait_object_added(self, interface_name, check_fn, timeout_ms=10000):
        cv = threading.Condition()
        assert self.__wait_condition is None
        self.__wait_condition = {'cv': cv, 'timeout': False, 'interface': interface_name, 'check': check_fn}
        oa = self._bluez._om.connect('object-added', self.__wait_object_added)
        tmo = GLib.timeout_add(timeout_ms, self.__wait_object_timeout)
        with cv:
            cv.wait()
        self._bluez._om.disconnect(oa)
        timeout = self.__wait_condition['timeout']
        self.__wait_condition = None
        if timeout:
            raise Exception('Timeout')
        GLib.source_remove(tmo)
    
    def _get_property(self, name):
        return self._proxy.get_cached_property(name)

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
                                                                flags=Gio.DBusObjectManagerClientFlags.NONE,
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
        __logger__.debug(f'Object added: {p}: {ifs}')
    
    def __object_removed(self, om,  object):
        p = object.get_object_path()
        self._objects.pop(p, None)
        __logger__.debug(f'Object removed: {p}')
    
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
        raise Exception('No bluetooth adapter found')

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
            __logger__.info(f'{self._proxy.get_object_path()}: Already discovering.')
            return
        try:
            def check(properties):
                value = properties.lookup_value('Discovering')
                if value is None:
                    return False
                return value.get_boolean()
            self._proxy.StartDiscovery()
            self._wait_property_change(check)
        except BaseException as e:
            __logger__.error(f'{self._proxy.get_object_path()}: StartDiscovery failed: {e}')
    
    def stop_discovery(self):
        """Stop device discovery.
         
        :Returns: `None`
        """
        if not self.Discovering:
            __logger__.info(f'{self._proxy.get_object_path()}: Not discovering.')
            return
        try:
            def check(properties):
                value = properties.lookup_value('Discovering')
                if value is None:
                    return False
                return not value.get_boolean()
            self._proxy.StopDiscovery()
            self._wait_property_change(check)
        except BaseException as e:
            __logger__.error(f'{self._proxy.get_object_path()}: StopDiscovery failed: {e}')
    
    def get_devices(self, serviceUUID=None):
        """Get all devices associated with the adapter.
         
        :Returns: `[ bluez.Device ]`
        """
        devices = [Device(self._bluez, path, BLUEZ_DEVICE_INTERFACE) for path, ifaces in self._bluez._objects.items()
                   if path.startswith(self._proxy.get_object_path()) and BLUEZ_DEVICE_INTERFACE in ifaces]
        if not serviceUUID:
            return devices
        return [d for d in devices if serviceUUID in d.UUIDs]
    
    def discover_device(self, check_fn, timeout_ms=10000):
        for device in self.get_devices():
            if check_fn(device):
                return device
        __logger__.debug(f'{self._proxy.get_object_path()}: Start discovering.')
        self.start_discovery()
        try:
            def check_object(device):
                return check_fn(Device(self._bluez, device.get_object_path(), BLUEZ_DEVICE_INTERFACE))
            self._wait_object_added(BLUEZ_DEVICE_INTERFACE, check_object, timeout_ms)
        except BaseException as e:
            __logger__.debug(f'{self._proxy.get_object_path()}: discover_device: Caught exception: {e}')
            return None
        finally:
            __logger__.debug(f'{self._proxy.get_object_path()}: Stop discovering.')
            self.stop_discovery()
        for device in self.get_devices():
            if check_fn(device):
                return device
        return None

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
            __logger__.info(f'{self._proxy.get_object_path()}: Already connected.')
            return
        self._proxy.Connect()
        if self.Connected:
            if not wait_for_services:
                return
        def check(properties):
            value = None
            if wait_for_services:
                value = properties.lookup_value('ServicesResolved')
            else:
                value = properties.lookup_value('Connected')
            if value is None:
                return False
            return value.get_boolean()
        self._wait_property_change(check, timeout_ms)
     
    def disconnect(self, timeout_ms=10000):
        if not self.Connected:
            __logger__.info(f'{self._proxy.get_object_path()}: Not connected.')
            return
        def check(properties):
            value = properties.lookup_value('Connected')
            if value is None:
                return False
            return not value.get_boolean()
        self._proxy.Disconnect()
        self._wait_property_change(check, timeout_ms)
    
    def get_gattservices(self):
        """Get all GATT services associated with the device.
         
        :Returns: `{ str: bluez.GattService }`
        """
        services = [GattService(self._bluez, path, BLUEZ_GATTSERVICE_INTERFACE) for path, ifaces in self._bluez._objects.items()
                   if path.startswith(self._proxy.get_object_path()) and BLUEZ_GATTSERVICE_INTERFACE in ifaces]
        return {s.UUID: s for s in services}

class GattService(_BaseObject):
    def __init__(self, bluez, object_path, interface_name):
        super().__init__(bluez, object_path, interface_name)
    
    @property
    def Primary(self):
        return self._get_property('Primary').unpack()
    
    @property
    def UUID(self):
        return self._get_property('UUID').unpack()
    
    def get_gattcharacteristics(self):
        """Get all GATT characteristics associated with the gatt service.
         
        :Returns: `{ str: bluez.GattCharacteristic }`
        """
        characteristics = [GattCharacteristic(self._bluez, path, BLUEZ_GATTCHARACTERISTIC_INTERFACE) for path, ifaces in self._bluez._objects.items()
                           if path.startswith(self._proxy.get_object_path()) and BLUEZ_GATTCHARACTERISTIC_INTERFACE in ifaces]
        return {c.UUID: c for c in characteristics}

class GattCharacteristic(_BaseObject):
    OPTION_REQUEST = GLib.Variant.parse(None, "{'type': <'request'>}")
    def __init__(self, bluez, object_path, interface_name):
        super().__init__(bluez, object_path, interface_name)
    
    @property
    def UUID(self):
        return self._get_property('UUID').unpack()
    
    @property
    def Flags(self):
        return self._get_property('Flags').unpack()
    
    @property
    def Notifying(self):
        return self._get_property('Notifying').unpack()
    
    @property
    def NotifyAcquired(self):
        return self._get_property('NotifyAcquired').unpack()
    
    @property
    def WriteAcquired(self):
        return self._get_property('WriteAcquired').unpack()
    
    @property
    def Value(self):
        return self._get_property('Value').unpack()
    
    def StartNotify(self):
        return self._proxy.StartNotify()
    
    def StopNotify(self):
        return self._proxy.StopNotify()
    
    def AcquireNotify(self):
        fdl = Gio.UnixFDList()
        v, fdl = self._proxy.call_with_unix_fd_list_sync('AcquireNotify', GLib.Variant.new_tuple(self.OPTION_REQUEST), Gio.DBusCallFlags.NONE, -1, fdl, None)
        fdl_index, mtu = v.unpack()
        fd = fdl.get(fdl_index)
        return (fd, mtu)
    
    def ReadValue(self):
        value = self._proxy.call_sync('ReadValue', GLib.Variant.new_tuple(self.OPTION_REQUEST), Gio.DBusCallFlags.NONE, -1, None)
        return bytearray(value[0])
    
    def WriteValue(self, data):
        v = GLib.Variant('ay', bytearray(data))
        return self._proxy.call_sync('WriteValue', GLib.Variant.new_tuple(v, self.OPTION_REQUEST), Gio.DBusCallFlags.NONE, -1, None)
    
    @contextmanager
    def dbus_signal_notify(self):
        """Get a context manager to receive notifications through a `queue.SimpleQueue` as `bytearray` items.
        Uses the PropertiesChanged DBus signal to receive the notifications.
        The contextmanager takes care of starting and stopping the notification emission.
        
        Example:
        with gatt_char.dbus_signal_notify() as q:
            # Receive 5 notifications
            for i in range(5):
                n = q.get()
                print('Notification', i+1, ':', n)
        """
        sq = SimpleQueue()
        def value_changed(proxy, changed, invalidated):
            key = 'Value'
            if key in changed.keys():
                sq.put(bytearray(changed[key]))
        hid = self._proxy.connect('g-properties-changed', value_changed)
        self.StartNotify()
        yield sq
        self.StopNotify()
        self._proxy.disconnect(hid)
    
    @contextmanager
    def fd_notify(self):
        """Get a context manager to receive notifications through a `queue.SimpleQueue` as `bytearray` items.
        Uses the file descriptor returned by AcquireNotify to receive the notifications.
        The contextmanager takes care of acquiring and closing the file descriptor.
        
        Example:
        with gatt_char.fd_notify() as q:
            # Receive 5 notifications
            for i in range(5):
                n = q.get()
                print('Notification', i+1, ':', n)
        """
        sq = SimpleQueue()
        fd, mtu = self.AcquireNotify()
        class ReadFd(threading.Thread):
            def __init__(self):
                super().__init__()
                self._run = True
            
            def run(self):
                with select.epoll() as ep:
                    ep.register(fd, select.EPOLLIN)
                    while self._run:
                        events = ep.poll(timeout=0.1, maxevents=10)
                        for pollfd, _ in events:
                            if pollfd == fd:
                                n = os.read(fd, mtu)
                                sq.put(n)
            
            def stop(self):
                self._run = False
        rdt = ReadFd()
        rdt.start()
        yield sq
        rdt.stop()
        rdt.join()
        os.close(fd)
