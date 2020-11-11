from pprint import *


def parseData2(notification):
    seq = notification[-1] # Last byte is Sequence Number
    channelSettings = notification[-2] # 2nd last byte is Channel Settings

    # Parse Measurment Data Blocks
    measDataBlocksCount = (len(notification) - 2) / (4 * 2) # 4 * int16
    if measDataBlocksCount - int(measDataBlocksCount) != 0.0:
        raise Exception("The notification does not have full number of measurement Data Blocks! Should be integer number but is %f" % measDataBlocksCount)
    measDataBlocksCount = int(measDataBlocksCount)

    # Split to scans
    scans = []
    for j in range(0, measDataBlocksCount):# for each meas data block
        fx = notification[j * 2 * 4]     + 256 * notification[j * 2 * 4 + 1]
        fy = notification[j * 2 * 4 + 2] + 256 * notification[j * 2 * 4 + 3]
        fz = notification[j * 2 * 4 + 4] + 256 * notification[j * 2 * 4 + 5]
        mz = notification[j * 2 * 4 + 6] + 256 * notification[j * 2 * 4 + 7]

        # Swap big to little endianess and convert to sign value
        fx = convertToSigned(swap2bytes(fx))
        fy = convertToSigned(swap2bytes(fy))
        fz = convertToSigned(swap2bytes(fz))
        mz = convertToSigned(swap2bytes(mz))

#         print(j, mz, fx, fy, fz)
        scans.append([fx, fy, fz, mz])

    return (scans, channelSettings, seq)


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


# TODO refactor me
class DataParser():
    seqNumbers = []
    channelSettings = []
    data = []
    timestamps = []


    def __init__(self):
        self.seqNumbers = []
        self.channelSettings = []
        self.data = []
        self.timestamps = []


    """
    Parse data, validate it and fill it into our internal store
    Checks for:
     - Sequence Numbers ascending
     - Notification size
    """
    def parseData(self, rawData, timestamps):
        print("%d packets" % len(rawData))
        packetLen = len(rawData[0])
        print("Packet Length: %d bytes" % packetLen)

        if len(rawData) != len(timestamps):
            raise Exception("Length mismatch between data (%d) and timestamps array (%d)!" % (len(rawData), len(timestamps)))

        lastSeq = 0
        lastTimestamp = 0
        for i in range(0, len(rawData)):
            seq = rawData[i][-1] # Last byte is Sequence Number
            channelSettings = rawData[i][-2] # 2nd last byte is Channel Settings

            # Test for ascending seq number without a gap
#             print("Packet: %d, Sequence Numbers: %d" % (i, seq))
            if i > 0:
                if seq != lastSeq + 1:
                    lastSeq = seq
                    if lastSeq == 255: # Byte Overflow
                        lastSeq = -1

                    print("Sequence numbers: ", end="")
                    for i in range(0, len(rawData)):
                        seq = rawData[i][-1] # Last byte is Sequence Number
                        print(seq, end=", ")
                    print("")
                    raise Exception("Sequence Numbers not ascending! We expected %d on packet %d but got %d!" % ((lastSeq + 1) % 256, i, seq))

            lastSeq = seq
            if lastSeq == 255: # Byte Overflow
                lastSeq = -1

                # Test for ascending timestamps
                if timestamps[i] <= lastTimestamp:
                    raise Exception("Timestamp not ascending! We expected %d > %d!" % (timestamps[i], lastTimestamp))

                lastTimestamp = timestamps[i]

            # Add data to internal store
            self.seqNumbers.append(seq)
            self.channelSettings.append(channelSettings)

            # Parse Measurment Data Blocks
            measDataBlocksCount = (packetLen - 2) / (4 * 2) # 4 * int16
            if measDataBlocksCount - int(measDataBlocksCount) != 0.0:
                raise Exception("Packet does not have full number of measurement Data Blocks! Should be integer number but is %f" % measDataBlocksCount)
            measDataBlocksCount = int(measDataBlocksCount)

            # Split to scans
            data = []
            for j in range(0, measDataBlocksCount):# for each meas data block
                fx = rawData[i][j * 2 * 4]     + 256 * rawData[i][j * 2 * 4 + 1]
                fy = rawData[i][j * 2 * 4 + 2] + 256 * rawData[i][j * 2 * 4 + 3]
                fz = rawData[i][j * 2 * 4 + 4] + 256 * rawData[i][j * 2 * 4 + 5]
                mz = rawData[i][j * 2 * 4 + 6] + 256 * rawData[i][j * 2 * 4 + 7]

                # Swap big to little endianess and convert to sign value
                fx = convertToSigned(swap2bytes(fx))
                fy = convertToSigned(swap2bytes(fy))
                fz = convertToSigned(swap2bytes(fz))
                mz = convertToSigned(swap2bytes(mz))

#                 print(j, mz, fx, fy, fz)
                data.append([fx, fy, fz, mz])
            self.data.append(data)

#         pprint(self.data)

        self.timestamps = timestamps


    def getData(self):
        return self.timestamps, self.data, self.seqNumbers


    def showData(self):
        if self.data == []:
            raise Exception("Please first parse the data!")

        print("%d packets with %d Measurement Data Blocks each:" % (len(self.data), len(self.data[0])))
        print("Timestamp   Fx      Fy     Fz     Mz")
        for i in range(0, len(self.data)): # for each packet
            for j in range(0, len(self.data[0])): # for each meas data block
                print("%6.3f (%2d): %6d %6d %6d %6d" % (self.timestamps[i]*1000, j, self.data[i][j][0], self.data[i][j][1], self.data[i][j][2], self.data[i][j][3]))
