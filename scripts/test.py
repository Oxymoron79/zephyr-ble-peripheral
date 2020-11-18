
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
        bluez.start()
        l = len(bluez.objects)
        a = bluez.get_adapter()
        bluez.stop()
        
        # Then
        self.assertGreater(l, 0)

class TestCase02_AdapterClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bluez.start()
    
    @classmethod
    def tearDownClass(cls):
        bluez.stop()

    def test_01_GetFirst(self):
        bluez.get_adapter()
    
    def test_02_GetByName(self):
        bluez.get_adapter('hci0')
    
    def test_03_GetException(self):
        with self.assertRaises(Exception):
            bluez.get_adapter('Invalid')
    
    def test_04_Discovery(self):
        # Given
        duration = 2
        a = bluez.get_adapter()
          
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
    
    def test_05_DiscoverByUUID(self):
        # Given
        duration = 2
        uuid = '00000100-f5bf-58d5-9d17-172177d1316a'
        uuid = '12345678-1234-5678-1234-56789abcdef0'
        a = bluez.get_adapter()
        
        # When
        a.start_discovery({'UUIDs': [uuid]});
        time.sleep(duration)
        d = a.get_devices()
        
        # Then
        self.assertTrue(a.Discovering)
        self.assertGreater(len(d), 0, 'No devices discovered within {} seconds.'.format(duration))
        self.assertTrue(uuid in d[0].UUIDs, 'Discovered device does not advertise {}. It advertised '.format(uuid, d[0].UUIDs))
        
        # When
        a.stop_discovery();
        
        # Then
        self.assertFalse(a.Discovering)

class TestCase03_DeviceClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bluez.start()
        cls.adapter = bluez.get_adapter()
    
    @classmethod
    def tearDownClass(cls):
        bluez.stop()

    def test_01_GetFirst(self):
        # Given
        duration = 2
        uuid = '00000100-f5bf-58d5-9d17-172177d1316a'
        uuid = '12345678-1234-5678-1234-56789abcdef0'
        
        # When
        self.adapter.start_discovery({'UUIDs': [uuid]});
        time.sleep(duration)
        d = self.adapter.get_devices()
        a.stop_discovery();
        
        # Then
        self.assertGreater(len(d), 0, 'No devices discovered within {} seconds.'.format(duration))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main(verbosity=2)
