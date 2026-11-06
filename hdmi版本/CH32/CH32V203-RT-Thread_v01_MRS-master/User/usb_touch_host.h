/*********************************************************************
 * File Name          : usb_touch_host.h
 * Description        : USB Host HID Touch Controller & Coordinate Forwarder
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 * Pins               : PB6 (USB_DM / USB2_DM), PB7 (USB_DP / USB2_DP)
 *********************************************************************/
#ifndef __USB_TOUCH_HOST_H__
#define __USB_TOUCH_HOST_H__

#include <rtthread.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TOUCH_EVENT_NONE = 0,
    TOUCH_EVENT_UP,
    TOUCH_EVENT_DOWN,
    TOUCH_EVENT_MOVE
} touch_event_t;

void usb_touch_host_init(void);
void usb_touch_send_to_k230(uint16_t x, uint16_t y, touch_event_t event);
void usb_touch_process_hid_report(const uint8_t *buf, uint16_t len);

#ifdef __cplusplus
}
#endif

#endif /* __USB_TOUCH_HOST_H__ */
