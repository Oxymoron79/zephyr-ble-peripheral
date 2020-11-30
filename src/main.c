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
 * Test Service UUID
 * 00000100-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static struct bt_uuid_128 service_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x00, 0x01, 0x00, 0x00);

/*******************************************************************************
 * Test Service Characteristics
 * Config    : 00000101-f5bf-58d5-9d17-172177d1316a
 * Data      : 00000102-f5bf-58d5-9d17-172177d1316a
 * Statistics: 00000103-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static const struct bt_uuid_128 config_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x01, 0x01, 0x00, 0x00);

static const struct bt_uuid_128 data_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x02, 0x01, 0x00, 0x00);

static const struct bt_uuid_128 statistics_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x03, 0x01, 0x00, 0x00);

/**
 * @brief Callback triggered when the "Config" Characteristic gets read through BLE
 * @param conn Connection object.
 * @param attr Attribute to read.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t config_read(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf, uint16_t len,
                           uint16_t offset)
{
    return len;
}

/**
 * @brief Callback triggered when the "Config" Characteristic gets written through BLE
 * @param conn Connection object.
 * @param attr Attribute to write.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @param flags Write flags.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t config_write(struct bt_conn *conn, const struct bt_gatt_attr *attr, const void *buf, uint16_t len,
                         uint16_t offset,
                         uint8_t flags)
{
    return len;
}

/**
 * @brief Callback triggered when the "Statistics" Characteristic gets read through BLE
 * @param conn Connection object.
 * @param attr Attribute to read.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t statistics_read(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf, uint16_t len,
                              uint16_t offset)
{
    return len;
}

/**
 * @brief Callback triggered when the "Statistics" Characteristic Notifications get enabled/disabled through BLE
 * @param attr
 * @param value
 */
static void statistics_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
    if (value == 1)
    {
        printk("\"Statistics\" Characteristic Notifications got enabled\n");
    }
    else
    {
        printk("\"Statistics\" Characteristic Notifications got disabled\n");
    }
}

/**
 * @brief Callback triggered when the "Data" Characteristic Notifications get enabled/disabled through BLE
 * @param attr
 * @param value
 */
static void data_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
    if (value == 1)
    {
        printk("\"Data\" Characteristic Notifications got enabled\n");
    }
    else
    {
        printk("\"Data\" Characteristic Notifications got disabled\n");
    }
}

BT_GATT_SERVICE_DEFINE(
    service,
    BT_GATT_PRIMARY_SERVICE(&service_uuid),

    /* Config Characteristic */
    BT_GATT_CHARACTERISTIC(&config_uuid.uuid, BT_GATT_CHRC_READ | BT_GATT_CHRC_WRITE, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE, config_read, config_write, 0),

    /* Data Characteristic */
    BT_GATT_CHARACTERISTIC(&data_uuid.uuid, BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE, NULL, NULL, 0),
    BT_GATT_CCC(data_ccc_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

    /* Statistics Characteristic */
    BT_GATT_CHARACTERISTIC(&statistics_uuid.uuid, BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_READ, statistics_read, NULL, 0),
    BT_GATT_CCC(statistics_ccc_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE)
    );

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA(BT_DATA_UUID128_ALL, service_uuid.val, sizeof(service_uuid.val))
};

static void connected(struct bt_conn *conn, uint8_t err)
{
    if (err)
    {
        printk("Connection failed (err 0x%02x)\n", err);
    }
    else
    {
        printk("Connected\n");
    }
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
    printk("Disconnected (reason 0x%02x)\n", reason);
}

static bool le_param_req(struct bt_conn *conn, struct bt_le_conn_param *param)
{
    printk("Connection parameters update requested:\n"
           "interval min/max: %d/%d, latency: %d, timeout: %d\n",
           param->interval_min, param->interval_max, param->latency, param->timeout);
    return true;
}

static void le_param_updated(struct bt_conn *conn, uint16_t interval, uint16_t latency, uint16_t timeout)
{
    printk("Connection parameters updated: interval: %d, latency: %d, timeout: %d\n", interval, latency, timeout);
}

#if defined(CONFIG_BT_USER_PHY_UPDATE)
void le_phy_updated(struct bt_conn *conn, struct bt_conn_le_phy_info *param)
{
    printk("PHY updated: RX: 0x%02X, TX: 0x%02X\n", param->rx_phy, param->tx_phy);
}
#endif

static struct bt_conn_cb conn_callbacks = {
    .connected = connected,
    .disconnected = disconnected,
    .le_param_req = le_param_req,
    .le_param_updated = le_param_updated
#if defined(CONFIG_BT_USER_PHY_UPDATE)
    .le_phy_updated = le_phy_updated;
#endif
};

void main(void)
{
    const struct device *dev = device_get_binding(CONFIG_UART_CONSOLE_ON_DEV_NAME);
    uint32_t dtr = 0;
    int err;

    if (usb_enable(NULL))
    {
        return;
    }

    /* Poll if the DTR flag was set, optional */
    while (!dtr)
    {
        uart_line_ctrl_get(dev, UART_LINE_CTRL_DTR, &dtr);
    }

    if (strlen(CONFIG_UART_CONSOLE_ON_DEV_NAME) != strlen("CDC_ACM_0")
        || strncmp(CONFIG_UART_CONSOLE_ON_DEV_NAME, "CDC_ACM_0", strlen(CONFIG_UART_CONSOLE_ON_DEV_NAME)))
    {
        printk("Error: Console device name is not USB ACM\n");
        return;
    }

    /* Setup Bluetooth */
    bt_conn_cb_register(&conn_callbacks);

    err = bt_enable(NULL);
    if (err)
    {
        printk("Bluetooth init failed (err %d)\n", err);
        return;
    }
    printk("Bluetooth initialized\n");

    err = bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
    if (err)
    {
        printk("Advertising failed to start (err %d)\n", err);
        return;
    }
    printk("Advertising successfully started\n");
}
