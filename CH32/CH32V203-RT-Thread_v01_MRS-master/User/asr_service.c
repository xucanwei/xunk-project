/*********************************************************************
 * File Name          : asr_service.c
 * Description        : ASR PRO Voice Module Bridge Implementation
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 *********************************************************************/
#include "asr_service.h"
#include "bsp_ch32v203.h"
#include "servo_service.h"

/* 串口转发与帧解析缓冲区 */
static uint8_t g_k230_rx_buf[64];
static uint16_t g_k230_rx_idx = 0;

static uint8_t g_asr_rx_buf[64];
static uint16_t g_asr_rx_idx = 0;

/* USART3 (K230: PB10/PB11) 接收任务：解析舵机角度帧 (0xAA) 或 语音播放转发 */
static void k230_rx_task_entry(void *parameter)
{
    while (1) {
        if (USART_GetFlagStatus(K230_USART_DEV, USART_FLAG_RXNE) != RESET) {
            uint8_t ch = (uint8_t)USART_ReceiveData(K230_USART_DEV);
            
            if (g_k230_rx_idx < sizeof(g_k230_rx_buf)) {
                g_k230_rx_buf[g_k230_rx_idx++] = ch;
            } else {
                g_k230_rx_idx = 0;
            }

            /* 检测 0xAA 帧头引导的舵机/语音指令 */
            if (g_k230_rx_buf[0] == 0xAA) {
                if (g_k230_rx_idx >= 17 && g_k230_rx_buf[2] == 0x11) {
                    /* 6 轴舵机角度包，交给 servo_service 解析 */
                    servo_parse_k230_frame(g_k230_rx_buf, g_k230_rx_idx);
                    g_k230_rx_idx = 0;
                } else if (g_k230_rx_idx >= 6 && g_k230_rx_buf[2] == 0x20) {
                    /* K230 发送给 ASR PRO 的语音播放包 (0xAA 0x5A 0x20 0x01 <voice_id> <cs>)，直接透传转发给 ASR PRO */
                    asr_uart_send_data(g_k230_rx_buf, g_k230_rx_idx);
                    g_k230_rx_idx = 0;
                }
            } else {
                /* 非 0xAA 开头，清空 */
                g_k230_rx_idx = 0;
            }
        }
        rt_thread_mdelay(2);
    }
}

/* USART2 (ASR PRO: PA2/PA3) 接收任务：接收 CMD: 语音识别口令并转发给 K230 */
static void asr_rx_task_entry(void *parameter)
{
    while (1) {
        if (USART_GetFlagStatus(ASR_USART_DEV, USART_FLAG_RXNE) != RESET) {
            uint8_t ch = (uint8_t)USART_ReceiveData(ASR_USART_DEV);
            
            if (ch == '\n' || ch == '\r') {
                if (g_asr_rx_idx > 0) {
                    g_asr_rx_buf[g_asr_rx_idx] = '\0';
                    /* 增加换行符并转发给 K230 */
                    k230_uart_send_string((const char *)g_asr_rx_buf);
                    k230_uart_send_string("\n");
                    g_asr_rx_idx = 0;
                }
            } else {
                if (g_asr_rx_idx < sizeof(g_asr_rx_buf) - 1) {
                    g_asr_rx_buf[g_asr_rx_idx++] = ch;
                } else {
                    g_asr_rx_idx = 0;
                }
            }
        }
        rt_thread_mdelay(2);
    }
}

void asr_service_init(void)
{
    rt_thread_t tid1 = rt_thread_create("k230_rx",
                                        k230_rx_task_entry,
                                        RT_NULL,
                                        1024,
                                        9,
                                        10);
    if (tid1 != RT_NULL) {
        rt_thread_startup(tid1);
    }

    rt_thread_t tid2 = rt_thread_create("asr_rx",
                                        asr_rx_task_entry,
                                        RT_NULL,
                                        1024,
                                        9,
                                        10);
    if (tid2 != RT_NULL) {
        rt_thread_startup(tid2);
    }

    rt_kprintf("[ASR] ASR PRO Voice Bridge Tasks Initialized.\n");
}
