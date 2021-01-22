#!/usr/bin/env python
import logging
from bluez import Manager
from pprint import pprint
import struct

logging.basicConfig(level=logging.INFO)
try:
    mgr = Manager();
    print(len(mgr._objects), 'objects: ', repr(mgr._objects))
    a = mgr.get_adapter('hci0')
    print('Adapter', a.Name, a.Address)
    
    serviceUUID = '00000100-f5bf-58d5-9d17-172177d1316a'
    def check(device):
        uuids = device.UUIDs
        print('Check UUIDs:', uuids)
        return serviceUUID in uuids
    device = a.discover_device(check)
    if device:
        print('Connect to', device)
        device.connect()
        print('Done.')
        
        services = device.get_gattservices();
        print('GATT services:', services)
        if serviceUUID in services.keys():
            service = services[serviceUUID]
            
            chars = service.get_gattcharacteristics()
            print('GATT characteristics:', repr(chars))
            configCharUUID = '00000101-f5bf-58d5-9d17-172177d1316a'
            configChar = chars[configCharUUID]
            if configChar:
                configFormat = 'HB'
                print('Read', configCharUUID)
                data = configChar.ReadValue()
                print('-> ', data)
                interval, data_len = struct.unpack(configFormat, data)
                print('interval:', interval)
                print('data_len:', data_len)
                
                interval = 100
                data_len = 20
                data = struct.pack(configFormat, interval, data_len)
                print('Write to', configCharUUID, data)
                ret = configChar.WriteValue(data)
                print('->', ret)
            
            dataCharUUID = '00000102-f5bf-58d5-9d17-172177d1316a'
            dataChar = chars[dataCharUUID]
            if dataChar:
                with dataChar.fd_notify() as q:
                    for i in range(5):
                        n = q.get()
                        print('Notification', i+1, ':', len(n), 'bytes')
        
        print('Disconnect', device)
        device.disconnect()
        print('Done.')
except BaseException as e:
    print('Caught exception: {}'.format(e))
    raise e
print('Exit')
