# Zephyr BLE Throughput

## Zephyr BLE Peripheral

Bluetooth LE 5 Peripheral Firmware for the [Nordic nRF52840 Dongle](https://docs.zephyrproject.org/latest/boards/arm/nrf52840dongle_nrf52840/doc/index.html)
using the [Zephyr RTOS](https://zephyrproject.org).

### Setup for Eclipse

#### Create Eclipse Project

```
$ source zephyr/zephyr-env.sh
$ cd zephyr-ble-peripheral
$ cmake -G"Eclipse CDT4 - Ninja" -DBOARD=nrf52840dongle_nrf52840 -B ../zephyr-ble-peripheral-cdt -S .
```

Import the Project in Eclipse from the `zephyr-ble-peripheral-cdt` directory.

#### Configure the Zephyr Kernel

Build the `guiconfig` target from the Build Target of the project.

#### Build the Application

Build the `all` target from the Build Target of the project.

The binary will be stored in `zephyr-ble-peripheral-cdt/zephyr/zephyr.hex`.

### Flash the Application

```
$ cd zephyr-ble-peripheral-cdt
# Package the application for the bootloader:
$ nrfutil pkg generate --hw-version 52 --sd-req=0x00 --application zephyr/zephyr.hex --application-version 1 peripheral.zip
# Flash it onto the board
$ nrfutil dfu usb-serial -pkg peripheral.zip -p /dev/ttyACM0
```

### Connect to Zephyr Console

```
$ minicom -D /dev/ttyACM0
```

## Zephyr BLE Dongle

The `hci_usb` folder is a copy of the `zephyr/samples/bluetooth/hci_usb` sample with some adjustments to the
`prj.conf` file.

### Build the application

```
$ source zephyr/zephyr-env.sh
$ cd zephyr-ble-peripheral/hci_usb
$ mkdir build
$ cd build
$ cmake -G"Ninja" -DBOARD=nrf52840dongle_nrf52840 ..
$ ninja
```

The binary will be stored in `zephyr-ble-peripheral/hci_usb/build/zephyr/zephyr.hex`.

### Flash the Application

```
$ cd zephyr-ble-peripheral/hci_usb/build
# Package the application for the bootloader:
$ nrfutil pkg generate --hw-version 52 --sd-req=0x00 --application zephyr/zephyr.hex --application-version 1 dongle.zip
# Flash it onto the board
$ nrfutil dfu usb-serial -pkg dongle.zip -p /dev/ttyACM0
```

### Enable 2MBit PHY support in BlueZ

```
$ sudo btmgmt phy LE1MTX LE1MRX LE2MTX LE2MRX
```

