# Adapted from https://github.com/elsampsa/btdemo/blob/master/bt_studio.py
# Documentation of the Bluetooth Service DBus API: https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/gatt-api.txt

from pprint import *
import json
import ble
from ble_helper import *
import struct
import unittest

class Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._devname = 'Rsc'
        cls._ble = ble.BLE()
        cls._ble.init()
        address = scanAndWaitForDevice(cls._ble, cls._devname, timeout=5)
        cls._ble.selectDevice(address)
        cls._ble.connect()
        cls._ble.getServicesDict()

    @classmethod
    def tearDownClass(cls):
        cls._ble.disconnect()
        
    def testSpec(self):
        specCharacteristicId = self._ble.getCharacteristicIdFromUuid("00000101-f5bf-58d5-9d17-172177d1316a")
        
        # Read spec Characteristic:")
        orig = bytearray(self._ble.readCharacteristic(specCharacteristicId))
        #print("Read %d bytes: %s" % (len(orig), orig))
        #print("  unpack: ", struct.unpack('<' + 4*'8s8sb8I', orig))
        
        # Modify spec Characteristic:", mod)
        mod = struct.pack('<' + 4*'8s8sb8I',
            b'Mz     \x00', b'Nm     \x00', 4, 2*110, 2*1100, 2*120, 2*1200, 2*130, 2*1300, 2*140, 2*1400,
            b'Fx     \x00', b'N      \x00', 4, 2*210, 2*2100, 2*220, 2*2200, 2*230, 2*2300, 2*240, 2*2400,
            b'Fy     \x00', b'N      \x00', 4, 2*310, 2*3100, 2*320, 2*3200, 2*330, 2*3300, 2*340, 2*3400,
            b'Fz     \x00', b'N      \x00', 4, 2*410, 2*4100, 2*420, 2*4200, 2*430, 2*4300, 2*440, 2*4400
        )
        self._ble.writeCharacteristic(specCharacteristicId, mod)
        
        # Read back Spec Characteristic
        check = bytearray(self._ble.readCharacteristic(specCharacteristicId))
        #print("Read %d bytes: %s" % (len(check), check))
        #print("  unpack: ", struct.unpack('<' + 4*'8s8sb8I', check))
        
        self.assertEqual(mod, check)
        
        # Write back original spec Characteristic
        self._ble.writeCharacteristic(specCharacteristicId, orig)
        
    def testCalib(self):
        calibCharacteristicId = self._ble.getCharacteristicIdFromUuid("00000102-f5bf-58d5-9d17-172177d1316a")
        
        # Read calib Characteristic
        orig = bytearray(self._ble.readCharacteristic(calibCharacteristicId))
        #print("Read %d bytes: %s" % (len(orig), orig))
        #print("  unpack: ", struct.unpack('<' + 4*'b4d', orig))
        
        # Modify calib Characteristic
        mod = struct.pack('<' + 4*'b4d',
                           4, 2*1.1, 2*2.1, 2*3.1, 2*4.1,
                           4, 2*1.2, 2*2.2, 2*3.2, 2*4.2,
                           4, 2*1.3, 2*2.3, 2*3.3, 2*4.3,
                           4, 2*1.4, 2*2.4, 2*3.4, 2*4.4
                           )
        self._ble.writeCharacteristic(calibCharacteristicId, mod)
        
        # Read back calib Characteristic
        check = bytearray(self._ble.readCharacteristic(calibCharacteristicId))
        #print("Read %d bytes: %s" % (len(check), check))
        #print("  unpack: ", struct.unpack('<' + 4*'b4d', check))
        
        self.assertEqual(mod, check)
        
        # Write back original calib Characteristic
        self._ble.writeCharacteristic(calibCharacteristicId, orig)

if __name__ == "__main__":
    unittest.main()
