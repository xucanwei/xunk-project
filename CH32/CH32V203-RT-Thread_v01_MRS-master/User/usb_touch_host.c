/*********************************************************************
 * File Name          : usb_touch_host.c
 * Description        : USB Host HID Touch Controller Implementation
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 * Pins               : PA11 (USB_DM), PA12 (USB_DP) / PB6, PB7
 *********************************************************************/
#include "usb_touch_host.h"
#include "bsp_ch32v203.h"
#include "usb_host_config.h"
#include <stdio.h>
#include <stdbool.h>

/* Touch state tracking variables */
static bool g_last_touch_state = false;
static uint16_t g_last_x = 0;
static uint16_t g_last_y = 0;

void usb_touch_send_to_k230(uint16_t x, uint16_t y, touch_event_t event)
{
    char buf[48];
    const char *ev_str = "UP";
    if (event == TOUCH_EVENT_DOWN) ev_str = "DOWN";
    else if (event == TOUCH_EVENT_MOVE) ev_str = "MOVE";

    snprintf(buf, sizeof(buf), "TOUCH:%u,%u,%s\n", x, y, ev_str);
    k230_uart_send_string(buf);
}

/* Parse USB HID Input Report for Touch Screen & Mouse Packets */
void usb_touch_process_hid_report(const uint8_t *buf, uint16_t len)
{
    if (!buf || len < 3) return;

    bool is_down = false;
    uint16_t x = g_last_x;
    uint16_t y = g_last_y;

    if (len >= 5) {
        /* Absolute Coordinate HID Digitizer / Touch Report (5+ Bytes) */
        is_down = (buf[0] & 0x01) != 0;
        x = (uint16_t)(buf[1] | (buf[2] << 8));
        y = (uint16_t)(buf[3] | (buf[4] << 8));

        /* Normalize if raw coordinate range is 0~4095 to 1024x600 screen */
        if (x > 1024 && x <= 4095) x = (uint32_t)x * 1024 / 4095;
        if (y > 600  && y <= 4095) y = (uint32_t)y * 600 / 4095;
    } else if (len >= 3) {
        /* Relative Coordinate HID Mouse Report (3-4 Bytes) */
        is_down = (buf[0] & 0x01) != 0;
        int8_t dx = (int8_t)buf[1];
        int8_t dy = (int8_t)buf[2];

        int32_t new_x = (int32_t)g_last_x + dx;
        int32_t new_y = (int32_t)g_last_y + dy;
        if (new_x < 0) new_x = 0;
        if (new_x > 1024) new_x = 1024;
        if (new_y < 0) new_y = 0;
        if (new_y > 600) new_y = 600;
        x = (uint16_t)new_x;
        y = (uint16_t)new_y;
    }

    touch_event_t event = TOUCH_EVENT_NONE;
    if (is_down && !g_last_touch_state) {
        event = TOUCH_EVENT_DOWN;
    } else if (is_down && g_last_touch_state) {
        if (x != g_last_x || y != g_last_y) {
            event = TOUCH_EVENT_MOVE;
        }
    } else if (!is_down && g_last_touch_state) {
        event = TOUCH_EVENT_UP;
    }

    g_last_touch_state = is_down;
    g_last_x = x;
    g_last_y = y;

    if (event != TOUCH_EVENT_NONE) {
        usb_touch_send_to_k230(x, y, event);
    }
}

/* USB Host HID Touch polling task entry */
static void usb_touch_thread_entry(void *parameter)
{
    (void)parameter;
    rt_kprintf("[USB_TOUCH] USB Host Task Thread Running...\n");

    while (1) {
        /* Run USB Host state machine: connection detection, enumeration, and endpoint polling */
        USBH_MainDeal();

        /* Update endpoint time count ticks for USB Host HID endpoint interval timing */
        if (RootHubDev.bStatus >= ROOT_DEV_SUCCESS) {
            uint8_t index = RootHubDev.DeviceIndex;
            if (RootHubDev.bType == USB_DEV_CLASS_HID) {
                for (uint8_t intf_num = 0; intf_num < HostCtl[index].InterfaceNum; intf_num++) {
                    for (uint8_t in_num = 0; in_num < HostCtl[index].Interface[intf_num].InEndpNum; in_num++) {
                        HostCtl[index].Interface[intf_num].InEndpTimeCount[in_num]++;
                    }
                }
            }
        }

        rt_thread_mdelay(10);
    }
}

void usb_touch_host_init(void)
{
    /* Initialize USB Host SIE & Clock */
    USBFS_RCC_Init();
    USBFS_Host_Init(ENABLE);

    memset(&RootHubDev.bStatus, 0, sizeof(struct _ROOT_HUB_DEVICE));
    memset(&HostCtl[DEF_USBFS_PORT_INDEX * DEF_ONE_USB_SUP_DEV_TOTAL].InterfaceNum, 0, DEF_ONE_USB_SUP_DEV_TOTAL * sizeof(struct __HOST_CTL));

    rt_thread_t tid = rt_thread_create("usb_touch",
                                       usb_touch_thread_entry,
                                       RT_NULL,
                                       2048,
                                       8,
                                       10);
    if (tid != RT_NULL) {
        rt_thread_startup(tid);
        rt_kprintf("[USB_TOUCH] USB Host Touch Controller Service Initialized.\n");
    }
}
