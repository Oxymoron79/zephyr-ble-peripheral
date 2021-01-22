#!/usr/bin/env python
import logging
import struct

from bluez import Manager

logging.basicConfig(level=logging.INFO) # Set to DEBUG for debug logs of bluez module

log = logging.getLogger('Throughput')
log.setLevel(logging.INFO) # Set to DEBUG for debug logs of this script

try:
    mgr = Manager();
    a = mgr.get_adapter('hci0')
    print('Using', a)
    
    serviceUUID = '00000100-f5bf-58d5-9d17-172177d1316a'
    print('Discover device hosting the throughput service', serviceUUID, 'for 10 seconds')
    def check(device):
        uuids = device.UUIDs
        log.debug('Check UUIDs: %s', uuids)
        return serviceUUID in uuids
    device = a.discover_device(check)
    if device:
        print('Found.')
        print('Connect to', device)
        device.connect()
        print('Done.')
        
        services = device.get_gattservices();
        log.debug('GATT services: %s', services)
        print('Check for throughput service', serviceUUID)
        if serviceUUID in services.keys():
            service = services[serviceUUID]
            print('Found.')
            
            chars = service.get_gattcharacteristics()
            log.debug('GATT characteristics: %s', repr(chars))
            configCharUUID = '00000101-f5bf-58d5-9d17-172177d1316a'
            configChar = chars[configCharUUID]
            if configChar:
                configFormat = 'HB'
                print('Read config characteristic', configCharUUID, 'parameters:')
                data = configChar.ReadValue()
                log.debug('-> %s', data)
                interval, data_len = struct.unpack(configFormat, data)
                print('- interval:', interval, 'ms')
                print('- data_len:', data_len, 'bytes')
                
                interval = 100
                data_len = 20
                print('Set config characteristic', configCharUUID, 'parameters:')
                print('- interval:', interval, 'ms')
                print('- data_len:', data_len, 'bytes')
                data = struct.pack(configFormat, interval, data_len)
                log.debug('Write to %s: %s', configCharUUID, data)
                ret = configChar.WriteValue(data)
                log.debug('-> %s', ret)
            
            dataCharUUID = '00000102-f5bf-58d5-9d17-172177d1316a'
            dataChar = chars[dataCharUUID]
            if dataChar:
                with dataChar.fd_notify() as q:
                    numNotifications = 10
                    print('Receive', numNotifications, 'notifications from data characteristic', dataCharUUID)
                    for i in range(numNotifications):
                        n = q.get()
                        print('Notification', i+1, ':', len(n), 'bytes')
        else:
            print('Throughput service', serviceUUID, 'not found on', device)
        print('Disconnect', device)
        device.disconnect()
        print('Done.')
    else:
        print('Not found.')
except BaseException as e:
    print('Caught exception: {}'.format(e))
    raise e
print('Exit')
