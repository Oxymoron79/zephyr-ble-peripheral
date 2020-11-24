
import unittest
import time
import struct
import sys, os

#sys.path.insert(0, os.path.abspath('.'))
import bluez
from unittest.case import skip

class TestCase01_BluezModule(unittest.TestCase):
    def test_01_Exports(self):
        # When
        manager = bluez.Manager()
        l = len(manager._objects)
        a = manager.get_adapter()
        
        # Then
        self.assertGreater(l, 0)

class TestCase02_AdapterClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = bluez.Manager()
    
    def test_01_GetFirst(self):
        self.manager.get_adapter()
    
    def test_02_GetByName(self):
        self.manager.get_adapter('hci0')
    
    def test_03_GetException(self):
        with self.assertRaises(Exception):
            self.manager.get_adapter('Invalid')
    
    def test_04_DiscoverAll(self):
        # Given
        duration = 2
        a = self.manager.get_adapter()
          
        # When
        a.start_discovery();
        time.sleep(duration)
        d = a.get_devices()
          
        # Then
        self.assertTrue(a.Discovering)
        self.assertGreater(len(d), 0, 'No devices discovered within {} seconds.'.format(duration))
          
        # When
        a.stop_discovery();
          
        # Then
        self.assertFalse(a.Discovering)
    
    def test_05_DiscoverAdvertisedUUID(self):
        # Given
        a = self.manager.get_adapter()
        timeout = 5000
        service_uuid = '00000100-f5bf-58d5-9d17-172177d1316a'
        def check(device):
            uuids = device.UUIDs
            return service_uuid in uuids
        
        # When
        device = a.discover_device(check, timeout)
        
        # Then
        self.assertTrue(device is not None, 'No devices advertising UUID {} discovered within {} milliseconds.'.format(service_uuid, timeout))
        self.assertFalse(a.Discovering)
    
    def test_06_DiscoverAdvertisedUUIDTimeout(self):
        # Given
        a = self.manager.get_adapter()
        timeout = 2000
        service_uuid = '12345678-1234-5678-1234-56789abcdef0'
        def check(device):
            uuids = device.UUIDs
            return service_uuid in uuids
        
        # When
        device = a.discover_device(check, timeout)
        
        # Then
        self.assertTrue(device is None, 'Devices advertising UUID {} discovered within {} milliseconds.'.format(service_uuid, timeout))
        self.assertFalse(a.Discovering)

class TestCase03_DeviceClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = bluez.Manager()
        cls.adapter = cls.manager.get_adapter()
    
    def test_01_GetAll(self):
        # Given
        duration = 2
        uuid = '00000100-f5bf-58d5-9d17-172177d1316a'
        uuid = '12345678-1234-5678-1234-56789abcdef0'
        
        # When
        self.adapter.start_discovery()
        time.sleep(duration)
        d = self.adapter.get_devices()
        self.adapter.stop_discovery();
        
        # Then
        self.assertGreater(len(d), 0, 'No devices discovered within {} seconds.'.format(duration))
    
    def test_01_GetByServiceUUID(self):
        # Given
        duration = 2
        service_uuid = '00000100-f5bf-58d5-9d17-172177d1316a'
        service_uuid = '12345678-1234-5678-1234-56789abcdef0'
        
        # When
        self.adapter.start_discovery()
        time.sleep(duration)
        d = self.adapter.get_devices(service_uuid)
        self.adapter.stop_discovery();
        
        # Then
        self.assertGreater(len(d), 0, 'No devices discovered within {} seconds.'.format(duration))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main(verbosity=2)
