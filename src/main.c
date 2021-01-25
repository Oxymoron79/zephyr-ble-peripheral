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

/* Configure the Connection Parameters
 * See https://www.novelbits.io/ble-connection-intervals
 */
#define CONNECTION_INTERVAL_MIN       6 // N * 1.25ms => 7.5ms (7.5ms..4000ms)
#define CONNECTION_INTERVAL_MAX     320 // N * 1.25ms => 400ms (7.5ms..4000ms)
#define CONNECTION_LATENCY            0 //
#define CONNECTION_TIMEOUT           40 // N * 10 ms => 400ms (100ms..32s)

/*******************************************************************************
 * Test Service UUID
 * abcdef00-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static struct bt_uuid_128 service_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x00, 0xef, 0xcd, 0xab);

/*******************************************************************************
 * Test Service Characteristics
 * Config    : ABCDEF01-f5bf-58d5-9d17-172177d1316a
 * Data      : ABCDEF02-f5bf-58d5-9d17-172177d1316a
 * Statistics: ABCDEF03-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static const struct bt_uuid_128 config_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x01, 0xef, 0xcd, 0xab);

static const struct bt_uuid_128 data_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x02, 0xef, 0xcd, 0xab);

static const struct bt_uuid_128 statistics_uuid = BT_UUID_INIT_128(
    0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
    0xd5, 0x58, 0xbf, 0xf5, 0x03, 0xef, 0xcd, 0xab);

typedef struct {
    uint16_t interval_ms;
    uint8_t data_length;
} __attribute__((packed)) config_t; // Pack it so it is byte aligned!;

static config_t config = {
    .interval_ms = 100,
    .data_length = 10
};

static uint8_t data[256];

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
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &config, sizeof(config));
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
    config_t *cfg = (config_t *)buf;

    if (flags & BT_GATT_WRITE_FLAG_PREPARE) {
        return 0;
    }

    if (offset + len > sizeof(config_t)) {
        return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
    }
    config = *cfg;
    printk("Wrote config:\n"
           "- interval_ms: %u\n"
           "- data_length: %u\n",
           config.interval_ms,
           config.data_length);
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

static void data_work_handler(struct k_work *work);

K_WORK_DEFINE(data_work, data_work_handler);

static void data_timer_handler(struct k_timer *dummy)
{
    k_work_submit(&data_work);
}

K_TIMER_DEFINE(data_timer, data_timer_handler, NULL);

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
        /* start periodic timer that expires once every second */
        k_timer_start(&data_timer, K_MSEC(config.interval_ms), K_MSEC(config.interval_ms));
    }
    else
    {
        printk("\"Data\" Characteristic Notifications got disabled\n");
        /* stop periodic timer */
        k_timer_stop(&data_timer);
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

static void data_work_handler(struct k_work *work)
{
    int err = 0;
    err = bt_gatt_notify(NULL, &service.attrs[3], data, config.data_length);
    if (err != 0)
        printk("data_work_handler: bt_gatt_notify returned: %i\n", err);
}

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA(BT_DATA_UUID128_ALL, service_uuid.val, sizeof(service_uuid.val))
};

/**
 * Requests an update of the Connection Parameters
 * @param conn
 * @param minInterval
 * @param maxInterval
 * @param latency
 * @param timeout
 * @return success
 */
static int update_le_conn_param(struct bt_conn *conn, uint16_t minInterval, uint16_t maxInterval, uint16_t latency, uint16_t timeout) {
    int err;
    printk("Setting the Connection Parameters: Interval min: %dms, Interval max: %dms, Latency: %d, timout: %dms.\n",
            (uint32_t)((float)minInterval * 1.25), (uint32_t)((float)maxInterval * 1.25),
            latency, timeout * 10);
    struct bt_le_conn_param le_conn_param = BT_LE_CONN_PARAM_INIT( minInterval, maxInterval, latency, timeout);
    err = bt_conn_le_param_update(conn, &le_conn_param);
    if (err) {
        printk("Failed to update connection parameters: %d\n", err);
        return err;
    }
    return 0;
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


static void connected(struct bt_conn *conn, uint8_t err)
{
    if (err)
    {
        printk("Connection failed (err 0x%02x)\n", err);
    }
    else
    {
        printk("Connected\n");
        /* Update the Data Length
         * See https://punchthrough.com/maximizing-ble-throughput-part-3-data-length-extension-dle-2
         * A max TX Length of 251 is the maximum we can get.
         * The max TX Time is calculated out of it:
         *   (251 + 14 bytes) * 8 bits  * 1 μs = 2120 μs */
        printk("Setting the Data Length\n");
        struct bt_conn_le_data_len_param conn_le_data_len_param;
        conn_le_data_len_param.tx_max_len = 251;
        conn_le_data_len_param.tx_max_time = 2120;
        err = bt_conn_le_data_len_update(conn, &conn_le_data_len_param);
        if (err) {
            printk("Failed to Update Data Length: %d!\n", err);
        }

        update_le_conn_param(conn, CONNECTION_INTERVAL_MIN, CONNECTION_INTERVAL_MAX, CONNECTION_LATENCY, CONNECTION_TIMEOUT);
    }
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
    printk("Disconnected (reason 0x%02x)\n", reason);
}

#if defined(CONFIG_BT_USER_PHY_UPDATE)
void le_phy_updated(struct bt_conn *conn, struct bt_conn_le_phy_info *param)
{
    printk("PHY updated: RX: 0x%02X, TX: 0x%02X\n", param->rx_phy, param->tx_phy);
}
#endif

#if defined(CONFIG_BT_USER_DATA_LEN_UPDATE)
void le_data_len_updated(struct bt_conn *conn, struct bt_conn_le_data_len_info *info)
{
  printk("Data length updated: TX: max_len: %d, max_time: %d - RX: max_len: %d, max_time: %d\n",
         info->tx_max_len, info->tx_max_time, info->rx_max_len, info->rx_max_time);
}
#endif

static struct bt_conn_cb conn_callbacks = {
    .connected = connected,
    .disconnected = disconnected,
    .le_param_req = le_param_req,
    .le_param_updated = le_param_updated,
#if defined(CONFIG_BT_USER_PHY_UPDATE)
    .le_phy_updated = le_phy_updated,
#endif
#if defined(CONFIG_BT_USER_DATA_LEN_UPDATE)
    .le_data_len_updated = le_data_len_updated,
#endif
};

void main(void)
{
    const struct device *dev = device_get_binding(CONFIG_UART_CONSOLE_ON_DEV_NAME);
    uint32_t dtr = 0;
    int err;

    for(uint8_t i=0; i<0xFF; i++)
    {
        data[i] = i;
    }

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
