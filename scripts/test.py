# Adapted from https://github.com/elsampsa/btdemo/blob/master/bt_studio.py
# Documentation of the Bluetooth Service DBus API: https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/gatt-api.txt

from pprint import *
import json
import ble
from ble_helper import *
import struct

if __name__ == "__main__":
    name = "Rsc"
#     name = "RCD_SIM"

    ble = ble.BLE()
    ble.init()

    address = scanAndWaitForDevice(ble, name, timeout=5)
    print("Address of \"%s\": %s" % (name, address))
    
    ble.selectDevice(address)
 
    print("Connecting...")
    ble.connect()

    print("Services:")
    servicesDict = ble.getServicesDict()

    for service in servicesDict:
        print("  UUID: %s, ID: %s, Name: %s" % (service['uuid'], service['id'], service['name']))


    print("Characteristics:")
    servicesDict = ble.getServicesDict()
    for service in servicesDict:
        print("%s (%s)" % (getCharacteristicNameFromUuid(service['uuid']), service['uuid']))
        characteristicsDict = ble.getCharacteristicsDict(service['id'])
        for characteristic in characteristicsDict:
            print("  UUID: %s, ID: %s, Name: %s" % (characteristic['uuid'], characteristic['id'], characteristic['name']))

    print("-----------")
    wrcdServiceId = ble.getServiceIdFromUuid("00000100-f5bf-58d5-9d17-172177d1316a")
    print("ID of WRCD Service: %s" % wrcdServiceId)

    specCharacteristicId = ble.getCharacteristicIdFromUuid("00000101-f5bf-58d5-9d17-172177d1316a")
    print("ID of spec Characteristic: %s" % specCharacteristicId)

    print("Reading spec Characteristic:")
    data = bytearray(ble.readCharacteristic(specCharacteristicId))
    print("Read %d bytes: %s" % (len(data), data))
    print("  unpack: ", struct.unpack('<' + 4*'8s8sb8I', data))

    data = struct.pack('<' + 4*'8s8sb8I',
                       b'Mz     \x00', b'Nm     \x00', 4, 2*110, 2*1100, 2*120, 2*1200, 2*130, 2*1300, 2*140, 2*1400,
                       b'Fx     \x00', b'N      \x00', 4, 2*210, 2*2100, 2*220, 2*2200, 2*230, 2*2300, 2*240, 2*2400,
                       b'Fy     \x00', b'N      \x00', 4, 2*310, 2*3100, 2*320, 2*3200, 2*330, 2*3300, 2*340, 2*3400,
                       b'Fz     \x00', b'N      \x00', 4, 2*410, 2*4100, 2*420, 2*4200, 2*430, 2*4300, 2*440, 2*4400
                       )
    print("Writing Spec Characteristic:", data)
    ble.writeCharacteristic(specCharacteristicId, data)

    print("Reading back Spec Characteristic:")
    data = bytearray(ble.readCharacteristic(specCharacteristicId))
    print("Read %d bytes: %s" % (len(data), data))
    print("  unpack: ", struct.unpack('<' + 4*'8s8sb8I', data))

    print("-----------")
    calibCharacteristicId = ble.getCharacteristicIdFromUuid("00000102-f5bf-58d5-9d17-172177d1316a")
    print("ID of calib Characteristic: %s" % calibCharacteristicId)

    print("Reading calib Characteristic:")
    data = bytearray(ble.readCharacteristic(calibCharacteristicId))
    print("Read %d bytes: %s" % (len(data), data))
    print("  unpack: ", struct.unpack('<' + 4*'b4d', data))

    data = struct.pack('<' + 4*'b4d',
                       4, 2*1.1, 2*2.1, 2*3.1, 2*4.1,
                       4, 2*1.2, 2*2.2, 2*3.2, 2*4.2,
                       4, 2*1.3, 2*2.3, 2*3.3, 2*4.3,
                       4, 2*1.4, 2*2.4, 2*3.4, 2*4.4
                       )
    print("Writing calib Characteristic:", data)
    ble.writeCharacteristic(calibCharacteristicId, data)

    print("Reading back calib Characteristic:")
    data = bytearray(ble.readCharacteristic(calibCharacteristicId))
    print("Read %d bytes: %s" % (len(data), data))
    print("  unpack: ", struct.unpack('<' + 4*'b4d', data))

    print("Disconnecting...")
    ble.disconnect()
    exit(0)
    print("-----------")
    wrcdServiceId = ble.getServiceIdFromUuid("00000100-f5bf-58d5-9d17-172177d1316a")
    stateCharacteristicId = ble.getCharacteristicIdFromUuid("00000101-f5bf-58d5-9d17-172177d1316a")
     
    print("Reading State Characteristic:")
    data = ble.readCharacteristic(stateCharacteristicId)
    print("State:  0x%02x" % data[0])
 
 
    print("-----------")
    print("Listening to a WRCD Status Message Characteristic notification...")

    print("Triggering Channel Settings Characteristic Notification:")
    wrcdServiceId = ble.getServiceIdFromUuid("00000100-f5bf-58d5-9d17-172177d1316a")
    testingCharacteristicId = ble.getCharacteristicIdFromUuid("0000010f-f5bf-58d5-9d17-172177d1316a")

    ble.EnableNotify("00000101-f5bf-58d5-9d17-172177d1316a")
    ble.EnableNotify("00000102-f5bf-58d5-9d17-172177d1316a")
    ble.EnableNotify("00000103-f5bf-58d5-9d17-172177d1316a")

    notificationConsumer = SlowNotificationConsumer()
    notificationConsumer.start()
    
    startTime = time.time()
    duration = 5
    while True:
        time.sleep(1)
        print("+ ", end="", flush=True)
#         ble.writeCharacteristic(testingCharacteristicId, [0x43, 0xBB])

        if time.time() > (startTime + duration):
            break

    notificationConsumer.stop()

    ble.DisableNotify("00000101-f5bf-58d5-9d17-172177d1316a")
    ble.DisableNotify("00000102-f5bf-58d5-9d17-172177d1316a")
    ble.DisableNotify("00000103-f5bf-58d5-9d17-172177d1316a")

    notifications = notificationConsumer.getReceivedNotifications()
    print("Received %d notifications:" % len(notifications))
#     pprint(notifications)
    for notification in notifications:
        characteristicUuid = ble.getCharacteristicUuidFromNameFromId(notification['id'])
        print("  %s (%s, %s):" % (characteristicUuid, notification['id'], getCharacteristicNameFromUuid(characteristicUuid)))
        for key in notification:
            if key != 'id':
                print("    %s = %s" % (key, notification[key]))


    print("Disconnecting...")
    ble.disconnect()
