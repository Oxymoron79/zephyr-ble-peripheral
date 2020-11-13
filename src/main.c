/*
 * Copyright (c) 2016 Intel Corporation.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <bluetooth/bluetooth.h>
#include <bluetooth/conn.h>
#include <bluetooth/gatt.h>
#include <bluetooth/hci.h>
#include <bluetooth/uuid.h>
#include <drivers/uart.h>
#include <string.h>
#include <sys/printk.h>
#include <sys/util.h>
#include <usb/usb_device.h>
#include <zephyr.h>

/*******************************************************************************
 * WRCD Service
 * See https://wiki.kistler.com/x/lAZWPw
 * 00000100-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static struct bt_uuid_128 service = BT_UUID_INIT_128(
        0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
        0xd5, 0x58, 0xbf, 0xf5, 0x00, 0x01, 0x00, 0x00);


/*******************************************************************************
 * WRCD Service Characteristics
 * See https://wiki.kistler.com/x/lAZWPw
 * Channel Spec      (0x01): 00000101-f5bf-58d5-9d17-172177d1316a
 * Calibration       (0x02): 00000102-f5bf-58d5-9d17-172177d1316a
 * Status Message    (0x03): 00000103-f5bf-58d5-9d17-172177d1316a
 * Data              (0x04): 00000104-f5bf-58d5-9d17-172177d1316a
 * Calibration       (0x05): 00000105-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static const struct bt_uuid_128 specCharacteristic = BT_UUID_INIT_128(
        0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
        0xd5, 0x58, 0xbf, 0xf5, 0x01, 0x01, 0x00, 0x00);

static const struct bt_uuid_128 calibCharacteristic = BT_UUID_INIT_128(
        0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
        0xd5, 0x58, 0xbf, 0xf5, 0x02, 0x01, 0x00, 0x00);

static const struct bt_uuid_128 dataCharacteristic = BT_UUID_INIT_128(
        0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
        0xd5, 0x58, 0xbf, 0xf5, 0x04, 0x01, 0x00, 0x00);

/*******************************************************************************
 * Meta data
 ******************************************************************************/
struct range_s {
    uint32_t physicalRange;
    uint16_t adcRange;
    double calibrationFactor;
};

#define NUM_RANGES 4
struct channel_s {
    char name[8];
    char unit[8];
    struct range_s ranges[NUM_RANGES];
};

#define NUM_CHANNELS 4
struct sensor_s {
    char name[8];
    int sn;
    struct channel_s channels[NUM_CHANNELS];
};

static struct sensor_s sensor = {
		.name = "Test",
		.sn = 1234,
		.channels = {
				{
						.name = "Ch1",
						.unit = "N1",
						.ranges = {
								{ .physicalRange = 110, .adcRange = 1100, .calibrationFactor = 1.1 },
								{ .physicalRange = 120, .adcRange = 1200, .calibrationFactor = 1.2 },
								{ .physicalRange = 130, .adcRange = 1300, .calibrationFactor = 1.3 },
								{ .physicalRange = 140, .adcRange = 1400, .calibrationFactor = 1.4 }
						}
				},
				{
						.name = "Ch2",
						.unit = "N2",
						.ranges = {
								{ .physicalRange = 210, .adcRange = 2100, .calibrationFactor = 2.1 },
								{ .physicalRange = 220, .adcRange = 2200, .calibrationFactor = 2.2 },
								{ .physicalRange = 230, .adcRange = 2300, .calibrationFactor = 2.3 },
								{ .physicalRange = 240, .adcRange = 2400, .calibrationFactor = 2.4 }
						}
				},
				{
						.name = "Ch3",
						.unit = "N3",
						.ranges = {
								{ .physicalRange = 310, .adcRange = 3100, .calibrationFactor = 3.1 },
								{ .physicalRange = 320, .adcRange = 3200, .calibrationFactor = 3.2 },
								{ .physicalRange = 330, .adcRange = 3300, .calibrationFactor = 3.3 },
								{ .physicalRange = 340, .adcRange = 3400, .calibrationFactor = 3.4 }
						}
				},
				{
						.name = "Ch4",
						.unit = "N4",
						.ranges = {
								{ .physicalRange = 410, .adcRange = 4100, .calibrationFactor = 4.1 },
								{ .physicalRange = 420, .adcRange = 4200, .calibrationFactor = 4.2 },
								{ .physicalRange = 430, .adcRange = 4300, .calibrationFactor = 4.3 },
								{ .physicalRange = 440, .adcRange = 4400, .calibrationFactor = 4.4 }
						}
				},
		}
};

void printSensor() {
	printk("sensor.name: %s\n", sensor.name);
	printk("sensor.sn: %d\n", sensor.sn);
	for (int i = 0; i < NUM_CHANNELS; i++)
	{
		printk("sensor.channels[%d].name: %s\n", i, sensor.channels[i].name);
		printk("sensor.channels[%d].unit: %s\n", i, sensor.channels[i].unit);
		for (int j = 0; j < NUM_RANGES; j++)
		{
			printk("sensor.channels[%d].ranges[%d].physicalRange: %d\n", i, j, sensor.channels[i].ranges[j].physicalRange);
			printk("sensor.channels[%d].ranges[%d].adcRange: %d\n", i, j, sensor.channels[i].ranges[j].adcRange);
			printk("sensor.channels[%d].ranges[%d].calibrationFactor: %d\n", i, j, (int)(sensor.channels[i].ranges[j].calibrationFactor*1000));
		}
	}
}

/**
 * @brief Callback triggered when the "Spec" Characteristic gets read through BLE
 * @param conn Connection object.
 * @param attr Attribute to read.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t readSpec(struct bt_conn *conn, const struct bt_gatt_attr *attr,
        void *buf, uint16_t len, uint16_t offset) {
	uint8_t* wr8 = buf;
	uint32_t* wr32;
	ssize_t count = 0;
	printk("readSpec\n");
	for(int i = 0; i < NUM_CHANNELS; i++)
	{
		memcpy(wr8, sensor.channels[i].name, sizeof(sensor.channels[i].name));
		wr8 += sizeof(sensor.channels[i].name);
		memcpy(wr8, sensor.channels[i].unit, sizeof(sensor.channels[i].unit));
		wr8 += sizeof(sensor.channels[i].unit);
		*wr8++ = NUM_RANGES;
		wr32 = (uint32_t*)wr8;
		for (int j = 0; j < NUM_RANGES; j++)
		{
			*wr32++ = sensor.channels[i].ranges[j].physicalRange;
			*wr32++ = sensor.channels[i].ranges[j].adcRange;
		}
		wr8 = (uint8_t*)wr32;
	}
	count = wr8 - ((uint8_t*)buf);
	printk("readSpec: Wrote %d bytes.\n", count);
	return count;
}


/**
 * @brief Callback triggered when the "Spec" Characteristic gets written through BLE
 * @param conn Connection object.
 * @param attr Attribute to write.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @param flags Write flags.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t writeSpec(struct bt_conn *conn, const struct bt_gatt_attr *attr,
        const void *buf, uint16_t len, uint16_t offset, uint8_t flags) {
	const uint8_t* rd8 = buf;
	uint32_t* rd32;
	uint8_t numRanges;
	ssize_t count = 0;
	if (flags & BT_GATT_WRITE_FLAG_PREPARE) {
		return 0;
	}
	printk("writeSpec\n");
	for(int i = 0; i < NUM_CHANNELS; i++)
	{
		memcpy(sensor.channels[i].name, rd8, sizeof(sensor.channels[i].name));
		sensor.channels[i].name[sizeof(sensor.channels[i].name) - 1] = 0x00;
		rd8 += sizeof(sensor.channels[i].name);
		memcpy(sensor.channels[i].unit, rd8, sizeof(sensor.channels[i].unit));
		sensor.channels[i].unit[sizeof(sensor.channels[i].unit) - 1] = 0x00;
		rd8 += sizeof(sensor.channels[i].unit);
		numRanges = *rd8++;
		rd32 = (uint32_t*)rd8;
		for (int j = 0; j < numRanges; j++)
		{
			sensor.channels[i].ranges[j].physicalRange = *rd32++;
			sensor.channels[i].ranges[j].adcRange = *rd32++;
		}
		rd8 = (uint8_t*)rd32;
	}
	count = rd8 - ((uint8_t*)buf);
	printk("writeSpec: Read %d bytes.\n", count);
	printSensor();
	return len;
}

/**
 * @brief Callback triggered when the "Spec" Characteristic Notifications get enabled/disabled through BLE
 * @param attr
 * @param value
 */
static void spec_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    if (value == 1) {
        printk("\"Spec\" Characteristic Notifications got enabled\n");
    }
    else {
        printk("\"Spec\" Characteristic Notifications got disabled\n");
    }
}

/**
 * @brief Callback triggered when the "Calib" Characteristic gets read through BLE
 * @param conn Connection object.
 * @param attr Attribute to read.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t readCalib(struct bt_conn *conn, const struct bt_gatt_attr *attr,
        void *buf, uint16_t len, uint16_t offset) {
	printk("readCalib\n");
	return len;
}


/**
 * @brief Callback triggered when the "Calib" Characteristic gets written through BLE
 * @param conn Connection object.
 * @param attr Attribute to write.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @param flags Write flags.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t writeCalib(struct bt_conn *conn, const struct bt_gatt_attr *attr,
        const void *buf, uint16_t len, uint16_t offset, uint8_t flags) {
	if (flags & BT_GATT_WRITE_FLAG_PREPARE) {
		return 0;
	}
	printk("writeCalib\n");
	return len;
}

/**
 * @brief Callback triggered when the "Calib" Characteristic Notifications get enabled/disabled through BLE
 * @param attr
 * @param value
 */
static void calib_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
	if (value == 1) {
		printk("\"Calib\" Characteristic Notifications got enabled\n");
	}
	else {
		printk("\"Calib\" Characteristic Notifications got disabled\n");
	}
}

/**
 * @brief Callback triggered when the "Data" Characteristic Notifications get enabled/disabled through BLE
 * @param attr
 * @param value
 */
static void data_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
	if (value == 1) {
		printk("\"Data\" Characteristic Notifications got enabled\n");
	}
	else {
		printk("\"Data\" Characteristic Notifications got disabled\n");
	}
}

BT_GATT_SERVICE_DEFINE(wrcdService,
        BT_GATT_PRIMARY_SERVICE(&service),

        /* Channel Spec Characteristic */
        BT_GATT_CHARACTERISTIC(
               &specCharacteristic.uuid,
               BT_GATT_CHRC_READ | BT_GATT_CHRC_WRITE,
               BT_GATT_PERM_READ | BT_GATT_PERM_WRITE,
               readSpec, writeSpec, 0),
        BT_GATT_CCC(spec_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

        /* Calibration Characteristic */
        BT_GATT_CHARACTERISTIC(
               &calibCharacteristic.uuid,
               BT_GATT_CHRC_READ | BT_GATT_CHRC_WRITE,
               BT_GATT_PERM_READ | BT_GATT_PERM_WRITE,
               readCalib, writeCalib, 0),
        BT_GATT_CCC(calib_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

        /* Data Characteristic */
        BT_GATT_CHARACTERISTIC(
               &dataCharacteristic.uuid,
               BT_GATT_CHRC_NOTIFY,
               BT_GATT_PERM_READ,
               NULL, NULL, 0),
        BT_GATT_CCC(data_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
);

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, 0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
            0xd5, 0x58, 0xbf, 0xf5, 0x00, 0x01, 0x00, 0x00),
};

static void connected(struct bt_conn *conn, uint8_t err) {
  if (err) {
    printk("Connection failed (err 0x%02x)\n", err);
  } else {
    printk("Connected\n");
  }
}

static void disconnected(struct bt_conn *conn, uint8_t reason) {
  printk("Disconnected (reason 0x%02x)\n", reason);
}

static bool le_param_req(struct bt_conn *conn, struct bt_le_conn_param *param) {
  printk("Connection parameters update requested\n");
  return true;
}

static void le_param_updated(struct bt_conn *conn, uint16_t interval,
                             uint16_t latency, uint16_t timeout) {
  printk(
      "Connection parameters updated: interval: %d, latency: %d, timeout: %d\n",
      interval, latency, timeout);
}

static struct bt_conn_cb conn_callbacks = {
    .connected = connected,
    .disconnected = disconnected,
    .le_param_req = le_param_req,
    .le_param_updated = le_param_updated,
};

void main(void) {
  const struct device *dev =
      device_get_binding(CONFIG_UART_CONSOLE_ON_DEV_NAME);
  uint32_t dtr = 0;
  int err;

  if (usb_enable(NULL)) {
    return;
  }

  /* Poll if the DTR flag was set, optional */
  while (!dtr) {
    uart_line_ctrl_get(dev, UART_LINE_CTRL_DTR, &dtr);
  }

  if (strlen(CONFIG_UART_CONSOLE_ON_DEV_NAME) != strlen("CDC_ACM_0") ||
      strncmp(CONFIG_UART_CONSOLE_ON_DEV_NAME, "CDC_ACM_0",
              strlen(CONFIG_UART_CONSOLE_ON_DEV_NAME))) {
    printk("Error: Console device name is not USB ACM\n");

    return;
  }

  /* Setup Bluetooth */
  bt_conn_cb_register(&conn_callbacks);

  err = bt_enable(NULL);
  if (err) {
    printk("Bluetooth init failed (err %d)\n", err);
    return;
  }
  printk("Bluetooth initialized\n");

  err = bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
  if (err) {
    printk("Advertising failed to start (err %d)\n", err);
    return;
  }
  printk("Advertising successfully started\n");


  printSensor();
}
