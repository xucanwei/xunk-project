/*********************************************************************
 * File Name          : servo_service.h
 * Description        : 6-Axis Bionic Eye Servo Controller Service
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 *********************************************************************/
#ifndef __SERVO_SERVICE_H__
#define __SERVO_SERVICE_H__

#include <rtthread.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define APP_SERVO_COUNT                      6U

void servo_service_init(void);
void servo_parse_k230_frame(const uint8_t *frame_data, uint16_t len);

#ifdef __cplusplus
}
#endif

#endif /* __SERVO_SERVICE_H__ */
