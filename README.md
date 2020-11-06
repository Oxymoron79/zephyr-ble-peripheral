# Zephyr BLE Peripheral

Bluetooth LE 5 Peripheral Firmware for the [Nordic nRF52840 Dongle](https://docs.zephyrproject.org/latest/boards/arm/nrf52840dongle_nrf52840/doc/index.html)
using the [Zephyr RTOS](https://zephyrproject.org).

# Setup for Eclipse

## Create Eclipse Project

```
$ source zephyr/zephyr-env.sh
$ cd zephyr-ble-peripheral
$ cmake -G"Eclipse CDT4 - Ninja" -DBOARD=nrf52840dongle_nrf52840 -B ../zephyr-ble-peripheral-cdt -S .
```

Import the Project in Eclipse from the `zephyr-ble-peripheral-cdt` directory.

## Configure the Zephyr Kernel

Build the `guiconfig` target from the Build Target of the project.

## Build the Application

Build the `all` target from the Build Target of the project.

The binary will be stored in `zephyr-ble-peripheral-cdt/zephyr/zephyr.hex`.

# Flash the Application
```
$ cd zephyr-ble-peripheral-cdt
# Package the application for the bootloader:
$ nrfutil pkg generate --hw-version 52 --sd-req=0x00 --application zephyr/zephyr.hex --application-version 1 app.zip
# Flash it onto the board
$ nrfutil dfu usb-serial -pkg peripheral.zip -p /dev/ttyACM0
```

# Connect to Zephyr Console

```
$ minicom -D /dev/ttyACM0
```
