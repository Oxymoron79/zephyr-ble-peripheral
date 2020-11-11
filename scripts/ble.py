# Adapted from https://github.com/elsampsa/btdemo/blob/master/bt_studio.py
# Documentation of the Bluetooth Service DBus API: https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/gatt-api.txt

from pprint import *
import re
import dbus
import dbus.service
import time

from gi.repository import GObject, GLib   # now a main loop instance has been constructed .. ?
from ble_helper import *


class BLE():
    managed_objects = None # dict: deep nested dictionary structure
    devices_by_adr = None # dict: key: device id, value: info about the device
    agent = None # instance of "Agent", see below
    agent_manager = None
    bus = None
    device = None
    servicesDict = None


    def __init__(self):
        DBusGMainLoop(set_as_default=True)  # now dbus.service.Object.__init__ can find it

        print("Connecting to Bluez D-Bus...")
        agent_path = "/org/bluez/my_bluetooth_agent"
        self.bus = dbus.SystemBus()


    def get_objects(self):
        """Some dbus interfaces implement a "manager":

        https://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces
        You can check if we have one for "org.bluez" like this:
        ::

            gdbus introspect --system --dest org.bluez --object-path /
        Let's get one
        """

        self.managed_objects = {}

        proxy_object = self.bus.get_object("org.bluez","/")
        manager = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager")
        self.managed_objects = manager.GetManagedObjects()
#         print("Got %d managed objects" % len(self.managed_objects))

        """That nested dictionary looks like this:

        /org/bluez/hci0 : 
                org.freedesktop.DBus.Introspectable : 
                org.bluez.Adapter1 : 
                    Address : 
                        9C:B6:D0:8C:5D:D6
                    AddressType : 
                        public
                    Name : 
                        sampsa-xps13
                    ...
                    ...
                ...
                ...

        /org/bluez/hci0/dev_58_C9_35_2F_A1_EF : 
                org.freedesktop.DBus.Introspectable : 
                org.bluez.Device1 : 
                    Address : 
                        58:C9:35:2F:A1:EF
                    AddressType : 
                        public
                    Name : 
                        Nokia 5
                    Alias : 
                        Nokia 5
                    Class : 
                        5898764
                    Icon : 
                        phone
                    Paired : 
                        1
                    Trusted : 
                        0
                    Blocked : 
                        0
                    ...
                    ...
        [any other devices follow]
            """


    def get_devices(self):
        """Populates the devices_by_adr dictionary
        """        
        self.devices_by_adr = {}

        r = re.compile("\\/org\\/bluez\\/hci\\d*\\/dev\\_(.*)")
        # e.g., match a string like this:
        # /org/bluez/hci0/dev_58_C9_35_2F_A1_EF

        for key, value in self.managed_objects.items():
            m = r.match(key)
            if m is not None:
                dev_str = m.group(1) # we have a device string (but maybe its not the root object of the device!)!
#                 print("dev_str=", dev_str)
                # let's flatten that dict a bit
                if "org.bluez.Device1" in value: # Only return the root objects (not the services and characteristics)
                    self.devices_by_adr[dev_str] = value["org.bluez.Device1"]

#         print("Got %d devices" % len(self.devices_by_adr))


    def clear_all_devices(self):
        """Clears all found bt devices from  .. a cache?

        After this, you have to run discovery again
        """
        adapter = self.get_adapter()
        for key in self.devices_by_adr.keys():
            device = self.get_device(key)
            print("Removing %s..." % device)
            try:
                adapter.RemoveDevice(device)
            except dbus.DBusException:
                print("could not remove", device)


    def get_adapter(self):
        """Adapter API:

        https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt

        Returns an object with all those methods, say StartDiscovery, etc.
        """
        # use [Service] and [Object path]:
        device_proxy_object = self.bus.get_object("org.bluez","/org/bluez/hci0")
        # use [Interface]:
        adapter = dbus.Interface(device_proxy_object,"org.bluez.Adapter1")
        return adapter


    def get_device(self, dev_str):
        """Device API:

        https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/device-api.txt

        Returns an object with all those methods, say Connect, Disconnect, Pair, etc
        """
        # use [Service] and [Object path]:
        device_proxy_object = self.bus.get_object("org.bluez","/org/bluez/hci0/dev_"+dev_str)
        # use [Interface]:
        device1 = dbus.Interface(device_proxy_object,"org.bluez.Device1")
        return device1


    def init(self):
        self.get_objects()
        self.get_devices()
#         print("Removing all devices...")
#         try:
#         self.clear_all_devices()
#         except:
#             print("Failed to remove devices!")


    def scan(self, timeout=10):
        print("Scanning for %d seconds..." % timeout)
        adapter = self.get_adapter()

        print("  Start discovery")
        startTime = time.time()
        while True:
            if time.time() > (startTime + timeout):
                raise Exception("Unable to start Discovery in time!")

            try:
                adapter.StartDiscovery() # discovery the device again
            except Exception as e:
                if "org.bluez.Error.InProgress" in str(e):
                    print("  Discovery already in progress")
#                     print("  Discovery already in progress, waiting (%s)..." % e)
#                     adapter.StopDiscovery()
#                     time.sleep(1)
#                     continue
                else:
                    raise
            break

        print("  Waiting %d seconds..." % timeout)
        time.sleep(timeout)
        print("  Stopping discovery...")
        try:
            adapter.StopDiscovery()
        except Exception as e:
            print("WARNING: Failed to stop discovery! (%s)" % e)
        
        print("  Get list of objects...")
        self.get_objects()
        self.get_devices()


    """
    Returns a dict with address=MAC, name=NAME
    """
    def getListOfDevices(self):
        dictOfDevices = {}

        for key in self.devices_by_adr:
            if 'Name' in self.devices_by_adr[key]:
                deviceName = str(self.devices_by_adr[key]['Name'])
            else: # Device has no name
                deviceName = ""

            if 'Address' in self.devices_by_adr[key]:
                address = str(self.devices_by_adr[key]['Address'])
                dictOfDevices[address] = deviceName
            else: # Device has no address
                raise Exception("Device has no address!")

        return dictOfDevices


    def getAddressByName(self, dictOfDevices, name):
        for key in dictOfDevices.keys():
            if name == dictOfDevices[key]:
                return key

        raise Exception("No device matching \"%s\"!" % name)


    def selectDevice(self, address):
        print("Selecting device with %s..." % address)
        dev_key = address.replace(':', '_')
        # TODO handle if no device is there...
        self.device = self.get_device(dev_key)


    """
    Connect to the selected device
    """
    def connect(self):
        print("Connecting to selected device...")
        if self.device == None:
            raise Exception("No device selected!")
        
        try:
            self.device.Connect()
        except Exception as e:
            if "org.freedesktop.DBus.Error.NoReply" in str(e):
                raise Exception("Bluetooth service did not respond to dbus call in time (%s)!" % e)
            else:
                raise

        self.get_objects()


    """
    Disconnect to the selected device
    """
    def disconnect(self):
        print("\nDisconnecting selected device...", flush=True)
        if self.device == None:
            raise Exception("No device selected!")
        
        try:
            self.device.Disconnect()
        except Exception as e:
            if "org.freedesktop.DBus.Error.NoReply" in str(e):
                print("WARNING: Bluetooth service did not respond to dbus call in time (%s)!" % e)
                # TODO Investigate why we sometimes fail to disconnect
            else:
                raise

        self.get_objects()


    """
    Returns a service list of dicts with (UUID, ID, NAME)
    Eg. [{'id': '/org/bluez/hci0/dev_78_31_C1_AC_2A_8A/service0021', 'uuid': '00000100-f5bf-58d5-9d17-172177d1316a', 'name': 'WRCD'}]
    Without being connected, Bluez shows some wrong service UUIDs!
    Only after connecting we get the right list.
    How ever it takes a moment after connecting, so if we get no or unexpected UUIDs, we should wait a bit and try again
    """
    def getServicesDict(self):
        servicesDict = []
        retries = 5
        self.servicesDict = None # Clear list
        print("Feching list of services...")
        while True:
            retries -= 1
            if retries == 0:
                raise Exception("Failed to get valid list of services!")

            self.get_objects()

            try:
                # iterate through all objects, and find the service ID
                servicesDict = []
                for object in self.managed_objects:
                    for interface in self.managed_objects[object]:
                        if str(interface) == 'org.bluez.GattService1':
                            uuid = str(self.managed_objects[object]['org.bluez.GattService1']['UUID'])
                            name = getCharacteristicNameFromUuid(uuid)
                            servicesDict.append({'id': str(object), 'uuid': uuid, 'name': name})

#                 pprint(servicesDict)
#                 print(len(servicesDict))
                if len(servicesDict) > 0: # we got some services
                    break
                else:
                    print("  No services listed yet, try again...")

            except Exception as e:
                print("We got an odd services UUID (%s), maybe the list is not up to date, wait a bit and try again..." % e)

            time.sleep(1)

#         print("We got %d services" % len(servicesDict))
        self.servicesDict = servicesDict
        return servicesDict


    def getServiceIdFromUuid(self, serviceUuid):
        if self.servicesDict == None:
            self.servicesDict = self.getServicesDict()
        for serviceId in self.servicesDict:
            if serviceId['uuid'] == serviceUuid:
                return serviceId['id']
            
        raise Exception("No matching service for UUID %s found!" % serviceUuid)


    """
    Returns a list of characteristics in a service
    """
    def getCharacteristicsDict(self, serviceId):
        # iterate through all objects, and find the service ID
#         print("serviceId:", serviceId)
        
        characteristicIds = []
        for object in self.managed_objects:
#             print(object)
            if serviceId in object: # Object is the service or a characteristic in the service
#                 print("Service or Characteristics:", object)
#                 pprint(self.managed_objects[object])
                for interface in self.managed_objects[object]:
                    if str(interface) == 'org.bluez.GattCharacteristic1': # only the characteristics
#                         print("Characteristics:", object)
#                         pprint(self.managed_objects[object])
                        uuid = str(self.managed_objects[object]['org.bluez.GattCharacteristic1']['UUID'])  
                        try:
                            name = getCharacteristicNameFromUuid(uuid)
                        except:
                            name = ""
                        characteristicIds.append({'id': str(object), 'uuid': uuid, 'name': name})

        return characteristicIds


    def getCharacteristicIdFromUuid(self, characteristicUuid):
        if self.servicesDict == None:
            self.servicesDict = self.getServicesDict()
        for service in self.servicesDict:
            characteristicDict = self.getCharacteristicsDict(service['id'])
            for characteristic in characteristicDict:
                if characteristic['uuid'] == characteristicUuid:
                    return characteristic['id']
            
        raise Exception("No matching characteristic for UUID %s found!" % characteristicUuid)


    def getCharacteristicUuidFromNameFromId(self, characteristicId):
        try:
            uuid = str(self.managed_objects[characteristicId]['org.bluez.GattCharacteristic1']['UUID'])
            return uuid
        except:
            raise Exception("Unable to find UUID for %s!" % characteristicId)


    def readCharacteristic(self, characteristicId):
        retries = 5
        retry = 0
        while True:
            print("Reading \"%s\" Characteristic (%s)..." % (getCharacteristicNameFromUuid(self.getCharacteristicUuidFromNameFromId(characteristicId)), characteristicId))
            retry += 1
            try:
                object = self.bus.get_object("org.bluez", characteristicId)
                interface = dbus.Interface(object, dbus_interface='org.bluez.GattCharacteristic1')
                data = interface.ReadValue({})
            except Exception as e:
                print("Failed to read Characteristic (%d/%d) %s" % (retry, retries, e))
                if retry == retries:
                    raise Exception("Failed to read Characteristic: %s" % e)
                continue
            break # No error occured
        data2 = []
        for i in range(0, len(data)):
            data2.append(int(data[i]))
            # TODO why int?
        return data2


    def writeCharacteristic(self, characteristicId, value):
        object = self.bus.get_object("org.bluez", characteristicId)
        interface = dbus.Interface(object, dbus_interface='org.bluez.GattCharacteristic1')
        retries = 5
        retry = 0
        while True:
            print("Writing %s to \"%s\" Characteristic (%s)..." % (value, getCharacteristicNameFromUuid(self.getCharacteristicUuidFromNameFromId(characteristicId)), characteristicId))
            retry += 1
            try:
                interface.WriteValue(value, {'type': 'request'})
            except Exception as e:
                print("Failed to write Characteristic (%d/%d) %s" % (retry, retries, e))
                if retry == retries:
                    raise Exception("Failed to write Characteristic: %s" % e)
                continue
            break # No error occured


    def EnableNotify(self, characteristicUuid):
        characteristicId = self.getCharacteristicIdFromUuid(characteristicUuid)
        retries = 5
        retry = 0
        while True:
            print("Enable Notify for \"%s\" Characteristic (%s)..." % (getCharacteristicNameFromUuid(characteristicUuid), characteristicId))
            retry += 1
            try:
                object = self.bus.get_object("org.bluez", characteristicId)
                interface = dbus.Interface(object, dbus_interface='org.bluez.GattCharacteristic1')
                interface.StartNotify()
            except Exception as e:
                print("Failed to enable Notify (%d/%d) %s" % (retry, retries, e))
                if retry == retries:
                    raise Exception("Failed to enable Notify: %s" % e)
                continue
            break # No error occured


    def DisableNotify(self, characteristicUuid):
        characteristicId = self.getCharacteristicIdFromUuid(characteristicUuid)
        retries = 5
        retry = 0
        while True:
            print("Disable Notify for \"%s\" Characteristic (%s)..." % (getCharacteristicNameFromUuid(characteristicUuid), characteristicId))
            retry += 1
            try:
                object = self.bus.get_object("org.bluez", characteristicId)
                interface = dbus.Interface(object, dbus_interface='org.bluez.GattCharacteristic1')
                interface.StopNotify()
            except Exception as e:
                print("Failed to disable Notify (%d/%d) %s" % (retry, retries, e))
                if retry == retries:
                    raise Exception("Failed to disable Notify: %s" % e)
                continue
            break # No error occured


if __name__ == "__main__":
    name = "9170B SN0"
#     name = "RCD_SIM"

    ble = BLE()
    ble.init()

    address = ble.waitForDevice(name, timeout=5)
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
    
    statusMessageCharacteristicId = ble.getCharacteristicIdFromUuid("00000103-f5bf-58d5-9d17-172177d1316a")
    print("ID of Status Message Characteristic: %s" % statusMessageCharacteristicId)

    print("Reading Status Message Characteristic:")
    data = ble.readCharacteristic(statusMessageCharacteristicId)
    print("Status Message: %s" % data)


    print("-----------")
    print("Writing State Characteristic:")
    wrcdServiceId = ble.getServiceIdFromUuid("00000100-f5bf-58d5-9d17-172177d1316a")
    stateCharacteristicId = ble.getCharacteristicIdFromUuid("00000101-f5bf-58d5-9d17-172177d1316a")
    ble.writeCharacteristic(stateCharacteristicId, [9])
     
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
