#!/usr/bin/env python
import logging
import struct
import time

from bluez import Manager

logging.basicConfig(level=logging.INFO) # Set to DEBUG for debug logs of bluez module

log = logging.getLogger('Throughput')
log.setLevel(logging.INFO) # Set to DEBUG for debug logs of this script

# Test parameters
configInterval = 100 # Notification interval in milliseconds
configDataLen = 200 # Notification data size in bytes
numDataNotifications = 10 # Number of notifications to receive from the data characteristic

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
                
                print('Set config characteristic', configCharUUID, 'parameters:')
                print('- interval:', configInterval, 'ms')
                print('- data_len:', configDataLen, 'bytes')
                data = struct.pack(configFormat, configInterval, configDataLen)
                log.debug('Write to %s: %s', configCharUUID, data)
                ret = configChar.WriteValue(data)
                log.debug('-> %s', ret)
                print('Done.')
            
            dataCharUUID = '00000102-f5bf-58d5-9d17-172177d1316a'
            dataChar = chars[dataCharUUID]
            if dataChar:
                with dataChar.fd_notify() as q:
                    print('Receive', numDataNotifications, 'notifications from data characteristic', dataCharUUID)
                    startTs = time.time()
                    for i in range(numDataNotifications):
                        n = q.get()
                        NotificationTs = time.time()
                        print(f'Notification {i+1:4}: {len(n):3} bytes, timestamp: {(NotificationTs - startTs):{1}.{3}}s')
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
