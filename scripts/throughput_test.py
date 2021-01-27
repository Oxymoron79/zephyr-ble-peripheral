#!/usr/bin/env python
import logging
import struct
import time
import argparse

from bluez import Manager

# Setup logging
logging.basicConfig(level=logging.INFO) # Set to DEBUG for debug logs of bluez module
log = logging.getLogger('Throughput')
log.setLevel(logging.INFO) # Set to DEBUG for debug logs of this script

# Test parameters
configInterval = 100 # Notification interval in milliseconds
configDataLen = 200 # Notification data size in bytes
numDataNotifications = 10 # Number of notifications to receive from the data characteristic

# Command line arguments
parser = argparse.ArgumentParser(description='Throughput test.')
parser.add_argument('-i', '--interval', type=int, help = 'Notification interval in milliseconds')
parser.add_argument('-l', '--length', type=int, help = 'Notification data size in bytes')
parser.add_argument('-n', '--num', type=int, help = 'Number of notifications to receive')
args = parser.parse_args()
if args.interval:
    configInterval = args.interval
if args.length:
    configDataLen = args.length
if args.num:
    numDataNotifications = args.num

try:
    mgr = Manager();
    a = mgr.get_adapter('hci0')
    print(f'Using {a}')
    
    serviceUUID = 'abcdef00-f5bf-58d5-9d17-172177d1316a'
    print(f'Discover device hosting the throughput service {serviceUUID} for 10 seconds.')
    def check(device):
        uuids = device.UUIDs
        log.debug(f'Check UUIDs: {uuids}')
        return serviceUUID in uuids
    device = a.discover_device(check)
    if device:
        print('Found.')
        print(f'Connect to {device}')
        device.connect()
        print('Done.')
        
        services = device.get_gattservices();
        log.debug(f'GATT services: {services}')
        print(f'Check for throughput service {serviceUUID}')
        if serviceUUID in services.keys():
            service = services[serviceUUID]
            print('Found.')
            
            chars = service.get_gattcharacteristics()
            log.debug(f'GATT characteristics: {chars!r}')
            configCharUUID = 'abcdef01-f5bf-58d5-9d17-172177d1316a'
            configChar = chars[configCharUUID]
            if configChar:
                configFormat = 'HB'
                print(f'Read config characteristic {configCharUUID} parameters:')
                data = configChar.ReadValue()
                log.debug(f'-> {data}')
                interval, data_len = struct.unpack(configFormat, data)
                print(f'- interval: {interval} ms')
                print(f'- data_len: {data_len} bytes')
                
                print(f'Set config characteristic {configCharUUID} parameters:')
                print(f'- interval: {configInterval} ms')
                print(f'- data_len: {configDataLen} bytes')
                data = struct.pack(configFormat, configInterval, configDataLen)
                log.debug(f'Write to {configCharUUID}: {data}')
                ret = configChar.WriteValue(data)
                log.debug(f'-> {ret}')
                print('Done.')
            
            dataCharUUID = 'abcdef02-f5bf-58d5-9d17-172177d1316a'
            dataChar = chars[dataCharUUID]
            if dataChar:
                with dataChar.fd_notify() as q:
                    print(f'Receive {numDataNotifications} notifications from data characteristic {dataCharUUID}')
                    startTime = time.time()
                    lastNotificationTime = startTime
                    notificationCount = 0
                    dataSize = 0
                    for i in range(numDataNotifications):
                        n = q.get()
                        notificationTime = time.time()
                        notificationCount += 1
                        dataSize += len(n)
                        print(f'Notification {i+1:4}: {len(n):3} bytes, timestamp: {(notificationTime - startTime):{7}.{3}} s, '
                              f'dt: {(notificationTime - lastNotificationTime):{7}.{3}} s')
                        lastNotificationTime = notificationTime
                    endTime = time.time()
                    throughput = dataSize * 8 / (endTime - startTime) / 1000
                    print(f'Summary: Received {dataSize} bytes in {notificationCount} notificattions '
                          f'during {endTime - startTime:.{3}} seconds: '
                          f'{throughput:.3f} kbits/sec.')
        else:
            print(f'Throughput service {serviceUUID} not found on {device}')
        print(f'Disconnect {device}')
        device.disconnect()
        print('Done.')
    else:
        print('Not found.')
except BaseException as e:
    print(f'Caught exception: {e}')
    raise e
print('Exit')
