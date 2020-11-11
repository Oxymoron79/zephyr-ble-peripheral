# Adapted from https://github.com/elsampsa/btdemo/blob/master/bt_studio.py
# Documentation of the Bluetooth Service DBus API: https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/gatt-api.txt

from pprint import *
import json
import ble
from ble_helper import *

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
    
    stateCharacteristicId = ble.getCharacteristicIdFromUuid("00000101-f5bf-58d5-9d17-172177d1316a")
    print("ID of State Characteristic: %s" % stateCharacteristicId)

    print("Reading State Characteristic:")
    data = ble.readCharacteristic(stateCharacteristicId)
    print("State: %s" % data)

    js = json.dumps({'foo': 1, 'bar': 'baz'})
    data = bytes(js, 'utf-8')
    print("Writing State Characteristic:", js)
    ble.writeCharacteristic(stateCharacteristicId, data)

#     js = json.dumps([{'foo': 1}, {'foo': 2}])
#     data = bytes(js, 'utf-8')
#     print("Update State Characteristic:", js)
#     ble.writeCharacteristic(stateCharacteristicId, data)

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
