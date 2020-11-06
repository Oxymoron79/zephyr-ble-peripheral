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

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, 0xf0, 0xde, 0xbc, 0x9a, 0x78, 0x56, 0x34,
                  0x12, 0x78, 0x56, 0x34, 0x12, 0x78, 0x56, 0x34, 0x12),
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
