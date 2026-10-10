/*********************************************************************
 * File Name          : asr_service.h
 * Description        : ASR PRO Voice Module Bridge Service
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 * Pins               : PA2 (ASR_TX), PA3 (ASR_RX)
 *********************************************************************/
#ifndef __ASR_SERVICE_H__
#define __ASR_SERVICE_H__

#include <rtthread.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void asr_service_init(void);

#ifdef __cplusplus
}
#endif

#endif /* __ASR_SERVICE_H__ */
