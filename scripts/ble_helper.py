import threading
import os
import dbus
import dbus.service
import ast
import time
import numpy as np
import csv
from data_parser import *

from gi.repository import GObject, GLib   # now a main loop instance has been constructed .. ?
from dbus.mainloop.glib import DBusGMainLoop


from ble_characteristics import *
from ble_characteristics_wrcd import *



def deleteAllCachedBluetoothServiceData():
    print("Deleting all cached data of the Bluetooth service...")
    os.system("sudo rm -rf /var/lib/bluetooth/*")


"""
Restarts the Bluetooth Service (Linux Host, bluez)
Sometines we have isuses that bluez is unable to disconnect.
To make sure we have a clean test start, we can restart the service
"""
def restartBluetoothService():
    print("Restarting the Bluetooth service...")
    os.system("sudo systemctl restart bluetooth")


def enable2MbPhy():
    print("Enabling the 2MB PHY...")
    os.system("sudo btmgmt phy LE1MTX LE1MRX LE2MTX LE2MRX")


def scanAndWaitForDevice(ble, name, timeout=10):
    print("Scanning Bluetooth up to %d seconds or until we find a device names \"%s\" or \"%s-sim\"..." % (timeout, name, name))
    startTime = time.time()
    while True:
        if time.time() > (startTime + timeout):
                raise Exception("No matching device for \"%s\" or \"%s-sim\" found within %d seconds!", name, name, timeout)

        try:
            ble.scan(1)
        except Exception as e:
            if "org.bluez.Error.InProgress" in str(e):
                print("Scan already in progress, and we somehow can not stop it and it doesnt stop either, so lets restart the service once more")
                restartBluetoothService()
                continue
            elif "org.bluez.Error.NotReady" in str(e):
                print("Bluetooth Service not ready yet, waiting...")
                time.sleep(1)
                continue
            raise Exception("Unable to scan: %s" % e)

        dictOfDevices = ble.getListOfDevices()
#         print("Devices:")
#         pprint(dictOfDevices)

        # Try to find a device with that name.
        # If it fails, try to find a device wich has -sim" appended to its name
        # The correct way would be to use the type aparameter, but pytest does not support this on module level where we call this function
        try:
            address = ble.getAddressByName(dictOfDevices, name)
            return address # We found the device
        except:
            try:
                address = ble.getAddressByName(dictOfDevices, name + "-sim")
                return address # We found the device
            except: # not found yet, try again
                print("No matching device for \"%s\" found yet, trying again...!" % name)

"""
Looks up the UUID of the service in tables characteristicsNameByUuid and wrcdCharacteristicsNameByUuid
and returns the name.
If it does not get found, it returns the given UUID
"""
def getCharacteristicNameFromUuid(uuid):
    uuid = str(uuid)
    if uuid in characteristicsNameByUuid:
        return characteristicsNameByUuid[uuid]
    elif uuid in wrcdCharacteristicsNameByUuid:
        return wrcdCharacteristicsNameByUuid[uuid]
    else:
        raise Exception("Unknown UUID: %s" % uuid)


"""
Looks up the name of the service in tables characteristicsNameByUuid and wrcdCharacteristicsNameByUuid
and returns the UUID.
If it does not get found, it returns the given UUID
"""
def getCharacteristicUuidFromName(name):
    for key in characteristicsNameByUuid:
        if characteristicsNameByUuid[key] == name:
            return key

    for key in wrcdCharacteristicsNameByUuid:
        if wrcdCharacteristicsNameByUuid[key] == name:
            return key

    raise Exception("Unknown name: %s" % name)


"""
Converts a list of int to a string
 Eg. [65, 66, 67] => "ABC"
"""
def list2String(value):
    string = ""
    for ch in value:
        string +=(chr(ch))
    return string


# def dbus_to_python(data):
#     '''
#         convert dbus data types to python native data types
#     '''
#     if isinstance(data, dbus.String):
#         data = str(data)
#     elif isinstance(data, dbus.Boolean):
#         data = bool(data)
#     elif isinstance(data, dbus.Int64):
#         data = int(data)
#     elif isinstance(data, dbus.Double):
#         data = float(data)
#     elif isinstance(data, dbus.Array):
#         data = [dbus_to_python(value) for value in data]
#     elif isinstance(data, dbus.Dictionary):
#         new_data = dict()
#         for key in data.keys():
#             new_data[key] = dbus_to_python(data[key])
#         data = new_data
#     return data


# # convert byte array to string
# def dbus2str(db):
#     if type(db)==dbus.Struct:
#         return str(tuple(dbus2str(i) for i in db))
#     if type(db)==dbus.Array:
#         return "".join([dbus2str(i) for i in db])
#     if type(db)==dbus.Dictionary:
#         return dict((dbus2str(k), dbus2str(v)) for k, v in db.items())
#     if type(db)==dbus.String:
#         return db+''
#     if type(db)==dbus.UInt32:
#         return str(db+0)
#     if type(db)==dbus.Byte:
#         return chr(db)
#     if type(db)==dbus.Boolean:
#         return db==True
#     if type(db)==dict:
#         return dict((dbus2str(k), dbus2str(v)) for k, v in db.items())
#     return "(%s:%s)" % (type(db), db)


def dbus2python(dbusString):
    # Nasty parser (there must be a better way...)
    # dbus.Dictionary({dbus.String('Value'): dbus.Array([dbus.Byte(170), dbus.Byte(187), dbus.Byte(204)], signature=dbus.Signature('y'), variant_level=1)}, signature=dbus.Signature('sv'))
    # dbus.Dictionary({dbus.String('Percentage'): dbus.Byte(78, variant_level=1)}, signature=dbus.Signature('sv'))
    data = str(dbusString).split(", signature")[0]
    data = data.replace("dbus.Dictionary(", "")
    data = data.replace("dbus.Array(", "")
    data = data.replace("dbus.String", "")
    data = data.replace("dbus.Byte", "")
    data = data.replace(", variant_level=1", "")
    if data[-1] != '}':
        data += '}'
#     print("Cleaned data: %s" % data)
    data = ast.literal_eval(data)
    return data


"""
Use the Simulation Service characteristic to update the Connection Parameters
minInterval in N * 1.25 ms (N = 6..3200)
maxInterval in N * 1.25 ms (N = 6..3200)
latency in 0..((Timeout / Interval Max) - 1)
timeout in N * 10 ms (N = 10..3200)
"""
def setConnectionParameters(ble, minInterval, maxInterval, latency, timeout):
    data = minInterval.to_bytes(2, 'little') + maxInterval.to_bytes(2, 'little') + latency.to_bytes(2, 'little') + timeout.to_bytes(2, 'little')
    print(data)
    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("Sim Connection Parameters")),
                            data)


"""
Tell the sensor to use the set throughput
throughput in Mbit/s
"""
def setThroughput(ble, throughput, scansPerDataNotification):
    samplingFrequency = (throughput / 8 * 1024 * 1024) / (scansPerDataNotification * 8 + 2) * scansPerDataNotification
    realSamplingFrequency = setSimulatorSamplingFrequency(ble, samplingFrequency) # Hz
    realThroughput = realSamplingFrequency / scansPerDataNotification * (scansPerDataNotification * 8 + 2) * 8 / 1024 / 1024
    print("Set throughput to %0.3f Mbit/s (requested: %0.3f Mbit/s) with %d scans/Notification" % (realThroughput, throughput, scansPerDataNotification))
    setScansPerDataNotification(ble, scansPerDataNotification)


def setScansPerDataNotification(ble, scansPerDataNotification):
    print("Set Notifications to use %d scans" % scansPerDataNotification)
    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("Sim Scans per Data Notification")), scansPerDataNotification.to_bytes(1, 'little'))


def setSimulatorSamplingFrequency(ble, samplingFrequency):
    samplingInterval = int(round(float(1e6)/samplingFrequency, 0)) # round to integer
    realSamplingFrequency = 1e6 / samplingInterval # calculate back to frequency

    print("Set Sampling Frequency to %0.3f Hz (%d us), requested: %0.3f Hz" % (realSamplingFrequency, 1e6/samplingFrequency, samplingFrequency))
    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("Sim Sampling Interval")), samplingInterval.to_bytes(2, 'little'))

    return samplingFrequency


def setSimulatorSignalAmplitudes(ble, fx, fy, fz, mz):
    print("Setting Simulator Amplitudes (Fx, Fy, Fz, Mz) to %d, %d, %d, %d" % (fx ,fy, fz, mz))
    data = mz.to_bytes(2, 'little') + fx.to_bytes(2, 'little') + fy.to_bytes(2, 'little') + fz.to_bytes(2, 'little')
    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("Sim Signal Amplitude")), data)


def setState(ble, state):
    print("Setting state: %d" % state)
    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("State")), state.to_bytes(1, 'little'))


def setSignalSource(ble, signalSource):
    print("Configure sensor so to use %s as Signal Source" % signalSource)
    if signalSource == "ADC":
        source = 0
    elif signalSource == "CONSTANT":
        source = 1
    elif signalSource == "SAWTOOTH":
        source = 2
    elif signalSource == "SINE":
        source = 3
    elif signalSource == "RECTANGLE":
        source = 4
    else:
        raise "Unknown signal Source \"%s\"" % signalSource

    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("Sim Channel Signal Source")), source.to_bytes(1, 'little'))


def setSimulatorSignalFrequency(ble, signalFrequency=1):
    print("Configure sensor so simulate a signal with a frequency of %0.3f Hz " % float(signalFrequency))
    ble.writeCharacteristic(ble.getCharacteristicIdFromUuid(getCharacteristicUuidFromName("Sim Signal Interval")), int(float(1) / signalFrequency * 1000).to_bytes(2, 'little')) # in ms


"""
The ADC Data is transmitted in the unsigned Big Endian Format
This function converts it to Little Endian
"""
def swap2bytes(value):
    return (value & 0xFF) * 256 + (value & 0xFF00) / 256


"""
Casts the unsigned to a signed value
"""
def convertToSigned(value):
    if value > 32767:
        return int(value) - 65535
    return int(value)


"""
Class used to receive slow notifications (all but data notifications)
"""
class SlowNotificationsConsumer(threading.Thread):
    notificationsBuffer = []
    loop = None
    receiver = None

    def __init__(self):
        threading.Thread.__init__(self)
        self.clearNotificationsBuffer()


    def run(self):
        dbusLoop = DBusGMainLoop(set_as_default=False)
        self.system_bus = dbus.SystemBus(mainloop=dbusLoop)
        self.receiver = self.system_bus.add_signal_receiver(self.dbusSignalCallback,
            sender_keyword='sender', destination_keyword='dest', interface_keyword='interface',
            member_keyword='member', path_keyword='path')

        print("Start listening...")
        self.loop = GLib.MainLoop()
        self.loop.run()
        print("Stopped listening")


    def stop(self):
        print("Stop listening...")
        self.loop.quit()
        self.system_bus.remove_signal_receiver(self.receiver)


    def clearNotificationsBuffer(self):
        self.notificationsBuffer = []


    def getReceivedNotifications(self):
        return self.notificationsBuffer


    def dbusSignalCallback(self, *args, **kwargs):
        object = args[0]
        try:
            if "org.bluez" in object: # we only are interested in Bluetooth signals
                print("\nReceived a signal:")
                characteristicId = str(kwargs['path'])
                dataDict = args[1]
                print("  object: %s (%s): " % (characteristicId, object))
                data = dbus2python(dataDict)
                dict = {'id': characteristicId}
                for key in data:
                    print("  key: %s, value: %s" % (key, data[key]))
                    dict[key] = data[key]
                self.notificationsBuffer.append(dict)
        except:
            pass


"""
Class used to receive data notifications
After stopping, the data gets automatically parsed and validated
"""
class DataNotificationsConsumer(threading.Thread):
    notificationsBuffer = []
    rxTimestamps = []
    loop = None
    receiver = None
    timeFirstNotification = 0
    timeLastNotification = 0
    timePreviousCallNotification = 0
    previousCallTotalCount = 0
    notificationSize = 0
    notificationsToBeIgnoredAtStart = 0
    notificationsToBeIgnoredAtEnd = 0
    dataParser = None
    userCallback = None


    def __init__(self, userCallback=None):
        threading.Thread.__init__(self)
        self.dataParser = DataParser()
        self.clearNotificationsBuffer()
        self.notificationsToBeIgnoredAtStart = 5 # In the first few notifications have a high interval time, leading to wrong throughput calculations. To avoid this, we drop them.
        self.notificationsToBeIgnoredAtEnd = 11
        self.userCallback = userCallback


    def run(self):
        dbusLoop = DBusGMainLoop(set_as_default=False)
        self.system_bus = dbus.SystemBus(mainloop=dbusLoop)
        self.receiver = self.system_bus.add_signal_receiver(self.dbusSignalCallback,
            sender_keyword='sender', destination_keyword='dest', interface_keyword='interface',
            member_keyword='member', path_keyword='path')

        print("Start listening...")
        self.loop = GLib.MainLoop()
        self.loop.run()
        print("Stopped listening, received %d bytes" % self.getTotalCount())


    def stop(self):
        print("Stop listening...")
        self.system_bus.remove_signal_receiver(self.receiver)
        self.loop.quit()

        if self.getTotalCount() == 0: # No data received
            print("WARNING: Received no data!")
            return

        # Workaround for the data hickup (see dbusSignalCallback()):
        # Drop the last x notifications
        self.rxTimestamps = self.rxTimestamps[:-1 * self.notificationsToBeIgnoredAtEnd]
        self.notificationsBuffer = self.notificationsBuffer[:-1 * self.notificationsToBeIgnoredAtEnd]

        # Convert the absolute timestamps to relative ones
        offset = self.rxTimestamps[0]
        self.rxTimestamps[0]
        for i in range(len(self.rxTimestamps)):
            self.rxTimestamps[i] -= offset

        # parse and validate
        self.dataParser.parseData(self.notificationsBuffer, self.rxTimestamps)
#         self.dataParser.showData()



    def clearNotificationsBuffer(self):
        self.notificationsBuffer = []
        self.rxTimestamps = []


    """
    Return the received notification data
    Format: list of notifications. The notifications themselfs are byte lists, where the last byte is the sequence number
    """
    def getNotifications(self):
        return self.notificationsBuffer


    """
    Return the parsed data
    Format: list of timestamps, list of data [Mz, Fx, Fy, Fz]
    """
    def getParsedData(self):
        return self.dataParser.getData()


    def getDuration(self):
        return self.timeLastNotification - self.timeFirstNotification


    """
    Return the size of all (resp. the first) notification
    """
    def getNotificationSize(self):
        return self.notificationSize


    """
    Return the number of received notifications
    """
    def getNotificationsCount(self):
        return len(self.notificationsBuffer)


    """
    Return the number of received bytes
    """
    def getTotalCount(self):
        if len(self.notificationsBuffer) == 0:
            print("RX buffer is empty!")
            return 0

        try:
            return len(self.notificationsBuffer) * self.notificationSize
        except:
            print("Unable to get number of bytes!")
            return 0


    def showTiming(self):
        # Calculate time between notifications
        timestampDelta = self.rxTimestamps.copy()
        for i in range(len(timestampDelta), 1, -1): # traverse in reverse direction
            timestampDelta[i - 1] = timestampDelta[i - 1] - timestampDelta[i - 2]
        timestampDelta[0] = 0

        print("Timing Statistics:")
        print("  Average: %6.2f ms" % (np.average(timestampDelta[1:]) * 1000))
        print("  Min:     %6.2f ms" % (np.min(timestampDelta[1:]) * 1000))
        print("  Max:     %6.2f ms" % (np.max(timestampDelta[1:]) * 1000))


    def export(self, filenameData, filenameTimestamps):
        print("Exporting recorded data to %s..." % filenameData)
        with open(filenameData, 'w') as csvfile:
            scanSize = len(self.notificationsBuffer[0]) # 242
            writer = csv.writer(csvfile, delimiter=',')
            for i in range(0, len(self.notificationsBuffer)): # For each notification
                for scan in range(30): # for every scan
                    mz = self.notificationsBuffer[i][scan * 8 + 0] + self.notificationsBuffer[i][scan * 8 + 1] * 256
                    fx = self.notificationsBuffer[i][scan * 8 + 2] + self.notificationsBuffer[i][scan * 8 + 3] * 256
                    fz = self.notificationsBuffer[i][scan * 8 + 4] + self.notificationsBuffer[i][scan * 8 + 5] * 256
                    fy = self.notificationsBuffer[i][scan * 8 + 6] + self.notificationsBuffer[i][scan * 8 + 7] * 256

                    # Swap big to little endianess and convert to sign value
                    fx = convertToSigned(swap2bytes(fx))
                    fy = convertToSigned(swap2bytes(fy))
                    fz = convertToSigned(swap2bytes(fz))
                    mz = convertToSigned(swap2bytes(mz))

                    writer.writerow([fx, fy, fz, mz])

        print("Exporting timestamps (stamped by receiver) to %s..." % filenameTimestamps)
        with open(filenameTimestamps, 'w') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            for i in range(0, len(self.notificationsBuffer)): # For each notification
                writer.writerow([self.rxTimestamps[i]])
        print("Export completed")

    """
    Returns the total throughput in Mbit/s
    """
    def getThroughput(self):
        if (self.timeLastNotification - self.timeFirstNotification) == 0:
            return 0
        return float(self.getTotalCount()) * 8 / (self.timeLastNotification - self.timeFirstNotification) / 1024 / 1024


    """
    Returns the throughput since the last call in Mbit/s
    """
    def getThroughputSinceLastCall(self):
        if (self.timeLastNotification - self.timePreviousCallNotification) == 0:
            return 0
        throughput =  float(self.getTotalCount() - self.previousCallTotalCount) * 8 / (self.timeLastNotification - self.timePreviousCallNotification) / 1024 / 1024
        self.timePreviousCallNotification = self.timeLastNotification
        self.previousCallTotalCount = self.getTotalCount()

        return throughput


    def dbusSignalCallback(self, *args, **kwargs):
        object = args[0]
        try:
            if "org.bluez" in object: # we only are interested in Bluetooth signals
                if self.notificationsToBeIgnoredAtStart > 0: # Ignore first x notifications due to bad timeings
                    self.notificationsToBeIgnoredAtStart -= 1
                    return

                characteristicId = str(kwargs['path'])
                dataDict = args[1]

                try:
                    data = dbus2python(dataDict)
                    # Todo dbus2python() is not really efficient, improve performance

                    # Note for the workaround implemented in DataNotificationsConsumer.stop():
                    #   The data already is wrong here, but is still correct on air (proved by Wireshark trace).
                    #   It seems that it gets a hickup when the state gets changed ("Writing b'\x01' to "State" Characteristic...")

                    self.notificationsBuffer.append(data['Value'])
                    t = time.time()
                    self.rxTimestamps.append(t) # store current time
                    if self.timeFirstNotification == 0: # First notification
                        self.timeFirstNotification = time.time()
                        self.timePreviousCallNotification = self.timeFirstNotification
                        self.notificationSize = len(data['Value']) # We expect that all data notifications have the same size
                    self.timeLastNotification = time.time()

                    # Call user callback
                    if self.userCallback:
                        self.userCallback(data['Value'], t)

    #                 print(data['Value'])

                except Exception as e:
                    print("Warning: Failed to process notification: %s" % e)
        except:
            pass
