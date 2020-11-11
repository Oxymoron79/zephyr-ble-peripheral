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
#include <data/json.h>
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
 * State             (0x01): 00000101-f5bf-58d5-9d17-172177d1316a
 * Channel Settings  (0x02): 00000102-f5bf-58d5-9d17-172177d1316a
 * Status Message    (0x03): 00000103-f5bf-58d5-9d17-172177d1316a
 * Data              (0x04): 00000104-f5bf-58d5-9d17-172177d1316a
 * Calibration       (0x05): 00000105-f5bf-58d5-9d17-172177d1316a
 ******************************************************************************/
static const struct bt_uuid_128 stateCharacteristic = BT_UUID_INIT_128(
        0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
        0xd5, 0x58, 0xbf, 0xf5, 0x01, 0x01, 0x00, 0x00);

static const struct bt_uuid_128 dataCharacteristic = BT_UUID_INIT_128(
        0x6a, 0x31, 0xd1, 0x77, 0x21, 0x17, 0x17, 0x9d,
        0xd5, 0x58, 0xbf, 0xf5, 0x04, 0x01, 0x00, 0x00);

/*******************************************************************************
 * JSON
 ******************************************************************************/
struct state_s { int foo; char *bar; };
static struct json_obj_descr state_descr[] = {
    JSON_OBJ_DESCR_PRIM(struct state_s, foo, JSON_TOK_NUMBER),
    JSON_OBJ_DESCR_PRIM(struct state_s, bar, JSON_TOK_STRING),
};
struct state_s state = { .foo = 1, .bar = "bar" };
#define JSON_SIZE 1024
static char json[JSON_SIZE];
static ssize_t json_len = 0;

/**
 * @brief Callback triggered when the "State" Characteristic gets read through BLE
 * @param conn Connection object.
 * @param attr Attribute to read.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t readState(struct bt_conn *conn, const struct bt_gatt_attr *attr,
        void *buf, uint16_t len, uint16_t offset) {
    int err = 0;
    /* Clear json buffer */
    memset(json, 0, JSON_SIZE);
    /* Calculate the length of the encoded JSON string */
    json_len = json_calc_encoded_len(state_descr, 2, &state);
    printk("json calc len returned: %d\n", json_len);
    if (json_len > JSON_SIZE)
    {
        printk("Encoded JSON is too long for the buffer\n");
        return -1;
    }
    /* Encode state struct to json buffer */
    err = json_obj_encode_buf(state_descr, 2, &state, json, JSON_SIZE);
    if (err < 0)
    {
        printk("JSON encode failed: %d\n", err);
        return -2;
    }
    printk("\"State\" Characteristic Value: %s\n", json);
    return bt_gatt_attr_read(conn, attr, buf, len, offset, json, json_len);
}


/**
 * @brief Callback triggered when the "State" Characteristic gets written through BLE
 * @param conn Connection object.
 * @param attr Attribute to write.
 * @param buf Buffer to store the value.
 * @param len Buffer length.
 * @param offset Start offset.
 * @param flags Write flags.
 * @return number of bytes read in case of success or negative values in case of error.
 */
static ssize_t writeState(struct bt_conn *conn, const struct bt_gatt_attr *attr,
        const void *buf, uint16_t len, uint16_t offset, uint8_t flags) {
    int err = 0;
    if (flags & BT_GATT_WRITE_FLAG_PREPARE) {
        return 0;
    }
    memset(json, 0, JSON_SIZE);
    memcpy(json, buf, len);
    printk("New \"State\" Characteristic Value: %s\n", json);
    err = json_obj_parse(json, len, state_descr, 2,&state);
    if (err <0)
    {
        printk("Failed to parse JSON: %d\n", err);
        return -1;
    }
    printk("state.foo: %d\n", state.foo);
    printk("state.bar: %s\n", state.bar);
    return len;
}

/**
 * @brief Callback triggered when the "State" Characteristic Notifications get enabled/disabled through BLE
 * @param attr
 * @param value
 */
static void state_ccc_cfg_changed(const struct bt_gatt_attr *attr, uint16_t value) {
    if (value == 1) {
        printk("\"State\" Characteristic Notifications got enabled\n");
    }
    else {
        printk("\"State\" Characteristic Notifications got disabled\n");
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

        /* State Characteristic */
        BT_GATT_CHARACTERISTIC(
               &stateCharacteristic.uuid,
               BT_GATT_CHRC_READ | BT_GATT_CHRC_WRITE | BT_GATT_CHRC_NOTIFY,
               BT_GATT_PERM_READ | BT_GATT_PERM_WRITE,
               readState, writeState, 0),
        BT_GATT_CCC(state_ccc_cfg_changed, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),

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
}
