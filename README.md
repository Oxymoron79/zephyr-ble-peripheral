# Zephyr BLE Throughput

This project aims to maximize the data throughput of a Bluetooth LE 5 Peripheral to a Bluetooth Dongle connected to a
Linux host using two [Nordic nRF52840 Dongles](https://docs.zephyrproject.org/latest/boards/arm/nrf52840dongle_nrf52840/doc/index.html).

The Firmware of the Bluetooth LE 5 Peripheral and the Dongle are built with the [Zephyr RTOS](https://zephyrproject.org).

# Zephyr BLE Peripheral

Bluetooth LE 5 Peripheral Firmware for the [Nordic nRF52840 Dongle](https://docs.zephyrproject.org/latest/boards/arm/nrf52840dongle_nrf52840/doc/index.html)
using the [Zephyr RTOS](https://zephyrproject.org).

The Peripheral hosts a GATT service (UUID: `abcdef00-f5bf-58d5-9d17-172177d1316a`) that contains the following
GATT characteristics:

Configuration (UUID: abcdef01-f5bf-58d5-9d17-172177d1316a, R/W):
* `interval_ms` (`uint16_t`): The interval in milliseconds at which notifications are sent on the Data characteristic.
* `data_length` (`uint8_t`): The size in bytes of each notification.

Data (UUID: abcdef02-f5bf-58d5-9d17-172177d1316a, R/N): The notifications of this characteristic are used to transfer
the data. For simple verification, each notification data is just a byte array with incrementing values:
`[0x00, 0x01, ... data_length-1]`.  
When notifications are enabled, a [Kernel Timer](https://docs.zephyrproject.org/latest/reference/kernel/timing/timers.html)
is started with the `timeout` and `interval` parameters set to `interval_ms`.

## Setup for Eclipse

### Create Eclipse Project

```
$ source zephyr/zephyr-env.sh
$ cd zephyr-ble-peripheral
$ cmake -G"Eclipse CDT4 - Ninja" -DBOARD=nrf52840dongle_nrf52840 -B ../zephyr-ble-peripheral-cdt -S .
```

Import the Project in Eclipse from the `zephyr-ble-peripheral-cdt` directory.

### Configure the Zephyr Kernel

Build the `guiconfig` target from the Build Target of the project.

### Build the Application

Build the `all` target from the Build Target of the project.

The binary will be stored in `zephyr-ble-peripheral-cdt/zephyr/zephyr.hex`.

## Flash the Application

```
$ cd zephyr-ble-peripheral-cdt
# Package the application for the bootloader:
$ nrfutil pkg generate --hw-version 52 --sd-req=0x00 --application zephyr/zephyr.hex --application-version 1 peripheral.zip
# Flash it onto the board
$ nrfutil dfu usb-serial -pkg peripheral.zip -p /dev/ttyACM0
```

## (Optional) Connect to Zephyr Console

The firmware has the USB console enabled (based of `samples/subsys/usb/console`) for kernel and application logs.
The bluetooth stack is configured to log debug messages.

When running the peripheral, the USB console can be accessed with a serial port program, e.g.:

```
$ minicom -D /dev/ttyACM0
```

# Zephyr BLE Dongle

The `hci_usb` folder is a copy of the `zephyr/samples/bluetooth/hci_usb` sample with some adjustments to the
`prj.conf` file.

## Build the Application

```
$ source zephyr/zephyr-env.sh
$ cd zephyr-ble-peripheral/hci_usb
$ mkdir build
$ cd build
$ cmake -G"Ninja" -DBOARD=nrf52840dongle_nrf52840 ..
$ ninja
```

The binary will be stored in `zephyr-ble-peripheral/hci_usb/build/zephyr/zephyr.hex`.

## Flash the Application

```
$ cd zephyr-ble-peripheral/hci_usb/build
# Package the application for the bootloader:
$ nrfutil pkg generate --hw-version 52 --sd-req=0x00 --application zephyr/zephyr.hex --application-version 1 dongle.zip
# Flash it onto the board
$ nrfutil dfu usb-serial -pkg dongle.zip -p /dev/ttyACM0
```

## Enable 2MBit PHY support in BlueZ

Since BlueZ version 5.51 support for the 2MBit PHY can be enabled with the `btmgmt` tool:

```
$ sudo btmgmt phy LE1MTX LE1MRX LE2MTX LE2MRX
```

# BLE Throughput Test

The `scripts` folder contains the Python script for the throughput test:

```
$ cd zephyr-ble-peripheral/scripts
$ ./throughput_test.py
```

Before running the script make sure that 2MBit PHY support is enabled in BlueZ.

The script
1. discovers a peripheral that advertises the Throughput GATT service
1. connects to it
1. writes the given `interval_ms` and `data_length` parameters to the Configuration characteristic
1. enables notifications on the Data characteristic
1. receives a given number of notifications
1. disables notifications on the Data characteristic again

For notification reception, the script uses the `AcquireNotify` method of the BlueZ
[GATT DBus API](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/gatt-api.txt) to avoid the usage of
DBus signals.
