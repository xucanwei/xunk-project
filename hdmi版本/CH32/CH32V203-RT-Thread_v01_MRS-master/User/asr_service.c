/*********************************************************************
 * File Name          : asr_service.c
 * Description        : ASR PRO Voice Module Bridge Implementation (IRQ RingBuffer)
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 *********************************************************************/
#include "asr_service.h"
#include "bsp_ch32v203.h"
#include "servo_service.h"
#include "board.h"
#include <string.h>
#include <stdlib.h>

/* 硬件中断环形缓冲区大小 (必须为 2 的幂) */
#define UART_RB_SIZE                         256U
#define UART_RB_MASK                         (UART_RB_SIZE - 1U)

/* USART3 (K230 -> CH32) 接收环形缓冲区 */
static volatile uint8_t  g_k230_rb[UART_RB_SIZE];
static volatile uint16_t g_k230_rb_head = 0;
static volatile uint16_t g_k230_rb_tail = 0;

/* USART2 (ASR PRO -> CH32) 接收环形缓冲区 */
static volatile uint8_t  g_asr_rb[UART_RB_SIZE];
static volatile uint16_t g_asr_rb_head = 0;
static volatile uint16_t g_asr_rb_tail = 0;

/* 协议帧组装缓冲区 */
static uint8_t  g_k230_rx_buf[64];
static uint16_t g_k230_rx_idx = 0;

static char     g_asr_rx_buf[64];
static uint16_t g_asr_rx_idx = 0;

/* ------------------ 硬件串口接收中断服务函数 ------------------ */

#if defined(SOC_RISCV_SERIES_CH32V2)
void USART2_IRQHandler(void) __attribute__((interrupt()));
#else
void USART2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
#endif
void USART2_IRQHandler(void)
{
    GET_INT_SP();
    rt_interrupt_enter();

    if (USART_GetITStatus(ASR_USART_DEV, USART_IT_RXNE) != RESET) {
        uint8_t ch = (uint8_t)USART_ReceiveData(ASR_USART_DEV);
        uint16_t next = (g_asr_rb_head + 1U) & UART_RB_MASK;
        if (next != g_asr_rb_tail) {
            g_asr_rb[g_asr_rb_head] = ch;
            g_asr_rb_head = next;
        }
    }
    /* 清除可能出现的硬件溢出错误标志 (ORE)，防止串口锁死 */
    if (USART_GetFlagStatus(ASR_USART_DEV, USART_FLAG_ORE) != RESET) {
        (void)USART_ReceiveData(ASR_USART_DEV);
    }

    rt_interrupt_leave();
    FREE_INT_SP();
}

#if defined(SOC_RISCV_SERIES_CH32V2)
void USART3_IRQHandler(void) __attribute__((interrupt()));
#else
void USART3_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
#endif
void USART3_IRQHandler(void)
{
    GET_INT_SP();
    rt_interrupt_enter();

    if (USART_GetITStatus(K230_USART_DEV, USART_IT_RXNE) != RESET) {
        uint8_t ch = (uint8_t)USART_ReceiveData(K230_USART_DEV);
        uint16_t next = (g_k230_rb_head + 1U) & UART_RB_MASK;
        if (next != g_k230_rb_tail) {
            g_k230_rb[g_k230_rb_head] = ch;
            g_k230_rb_head = next;
        }
    }
    /* 清除可能出现的硬件溢出错误标志 (ORE)，防止串口锁死 */
    if (USART_GetFlagStatus(K230_USART_DEV, USART_FLAG_ORE) != RESET) {
        (void)USART_ReceiveData(K230_USART_DEV);
    }

    rt_interrupt_leave();
    FREE_INT_SP();
}

/* ------------------ K230 接收解析任务 (USART3: PB11 RX) ------------------ */
static void k230_rx_task_entry(void *parameter)
{
    (void)parameter;
    while (1) {
        while (g_k230_rb_tail != g_k230_rb_head) {
            uint8_t ch = g_k230_rb[g_k230_rb_tail];
            g_k230_rb_tail = (g_k230_rb_tail + 1U) & UART_RB_MASK;

            /* 寻找帧头 0xAA */
            if (g_k230_rx_idx == 0) {
                if (ch == 0xAA) {
                    g_k230_rx_buf[g_k230_rx_idx++] = ch;
                }
                continue;
            }

            g_k230_rx_buf[g_k230_rx_idx++] = ch;

            /* 校验第 2 字节设备 ID (0x5A) */
            if (g_k230_rx_idx == 2 && g_k230_rx_buf[1] != 0x5A) {
                /* 若当前字节本身就是新帧头 0xAA，则保留为首字节 */
                if (ch == 0xAA) {
                    g_k230_rx_buf[0] = 0xAA;
                    g_k230_rx_idx = 1;
                } else {
                    g_k230_rx_idx = 0;
                }
                continue;
            }

            /* 校验第 3 字节功能码：仅支持 0x11 (舵机角度) 和 0x20 (语音播报) */
            if (g_k230_rx_idx == 3) {
                uint8_t cmd = g_k230_rx_buf[2];
                if (cmd != 0x11 && cmd != 0x20) {
                    if (ch == 0xAA) {
                        g_k230_rx_buf[0] = 0xAA;
                        g_k230_rx_idx = 1;
                    } else {
                        g_k230_rx_idx = 0;
                    }
                    continue;
                }
            }

            /* 分支 1：0x11 舵机控制帧 (固定 17 字节) */
            if (g_k230_rx_buf[2] == 0x11 && g_k230_rx_idx >= 17) {
                if (!servo_parse_k230_frame(g_k230_rx_buf, 17)) {
                    /* 校验失败：发生滑字节错位，向前滑窗寻找下一个 0xAA 快速重同步，彻底杜绝顿挫卡死！ */
                    uint16_t shift_idx = 0;
                    uint16_t si;
                    for (si = 1; si < 17; si++) {
                        if (g_k230_rx_buf[si] == 0xAA) {
                            shift_idx = si;
                            break;
                        }
                    }
                    if (shift_idx > 0) {
                        uint16_t rem = 17 - shift_idx;
                        memmove(g_k230_rx_buf, (const void *)&g_k230_rx_buf[shift_idx], rem);
                        g_k230_rx_idx = rem;
                    } else {
                        g_k230_rx_idx = 0;
                    }
                } else {
                    g_k230_rx_idx = 0;
                }
            }
            /* 分支 2：0x20 语音播放请求帧 (固定 6 字节: AA 5A 20 01 <id> <cs>) */
            else if (g_k230_rx_buf[2] == 0x20 && g_k230_rx_idx >= 6) {
                uint8_t cs = g_k230_rx_buf[1] ^ g_k230_rx_buf[2] ^ g_k230_rx_buf[3] ^ g_k230_rx_buf[4];
                if (cs == g_k230_rx_buf[5]) {
                    uint8_t voice_id = g_k230_rx_buf[4];
                    char play_cmd[24];
                    rt_snprintf(play_cmd, sizeof(play_cmd), "PLAY:%d\r\n", 10000 + voice_id);
                    rt_kprintf("[K230 -> ASR] Play voice ID: %d -> %s", voice_id, play_cmd);
                    asr_uart_send_data((const uint8_t *)play_cmd, strlen(play_cmd));
                } else {
                    rt_kprintf("[K230 -> ASR] Voice frame checksum mismatch!\n");
                }
                g_k230_rx_idx = 0;
            }
            /* 防溢出保护 */
            else if (g_k230_rx_idx >= sizeof(g_k230_rx_buf)) {
                g_k230_rx_idx = 0;
            }
        }
        rt_thread_mdelay(2);
    }
}

/* ------------------ ASR PRO 接收转发任务 (USART2: PA3 RX) ------------------ */
static void asr_rx_task_entry(void *parameter)
{
    (void)parameter;
    while (1) {
        while (g_asr_rb_tail != g_asr_rb_head) {
            uint8_t ch = g_asr_rb[g_asr_rb_tail];
            g_asr_rb_tail = (g_asr_rb_tail + 1U) & UART_RB_MASK;

            if (ch == '\n' || ch == '\r') {
                if (g_asr_rx_idx > 0) {
                    g_asr_rx_buf[g_asr_rx_idx] = '\0';

                    /* 查找有效 CMD: 起始位置，自动跳过可能存在的上电杂波字符 */
                    char *cmd_ptr = strstr(g_asr_rx_buf, "CMD:");
                    const char *send_ptr = (cmd_ptr != RT_NULL) ? cmd_ptr : g_asr_rx_buf;

                    char tx_line[72];
                    rt_snprintf(tx_line, sizeof(tx_line), "%s\n", send_ptr);
                    k230_uart_send_string(tx_line);
                    rt_kprintf("[ASR -> K230] RX: \"%s\" -> Forwarded: %s", g_asr_rx_buf, tx_line);

                    g_asr_rx_idx = 0;
                }
            } else if (ch >= 0x20 && ch <= 0x7E) {
                /* 仅接收可见 ASCII 字符，过滤上电毛刺 0x00/0xFF */
                if (g_asr_rx_idx < sizeof(g_asr_rx_buf) - 1) {
                    g_asr_rx_buf[g_asr_rx_idx++] = (char)ch;
                } else {
                    g_asr_rx_idx = 0;
                }
            }
        }
        rt_thread_mdelay(2);
    }
}

/* ------------------ MSH 调试命令 (支持直接从串口测试语音与指令) ------------------ */
static void asr_play(int argc, char **argv)
{
    int voice_id = 11;
    if (argc >= 2) {
        voice_id = atoi(argv[1]);
    }
    char play_cmd[24];
    int target_id = (voice_id < 1000) ? (10000 + voice_id) : voice_id;
    rt_snprintf(play_cmd, sizeof(play_cmd), "PLAY:%d\r\n", target_id);
    asr_uart_send_data((const uint8_t *)play_cmd, strlen(play_cmd));
    rt_kprintf("[MSH -> ASR] Sent to PA2 (USART2): %s", play_cmd);
}
MSH_CMD_EXPORT(asr_play, Test sending PLAY:100xx to ASR PRO e.g. asr_play 11);

static void asr_cmd(int argc, char **argv)
{
    const char *cmd = "CMD:FOLLOW";
    if (argc >= 2) {
        cmd = argv[1];
    }
    char tx_line[64];
    rt_snprintf(tx_line, sizeof(tx_line), "%s\n", cmd);
    k230_uart_send_string(tx_line);
    rt_kprintf("[MSH -> K230] Sent to PB10 (USART3): %s", tx_line);
}
MSH_CMD_EXPORT(asr_cmd, Test forwarding CMD:xxx to K230 e.g. asr_cmd CMD:FOLLOW);

void asr_service_init(void)
{
    rt_thread_t tid1 = rt_thread_create("k230_rx",
                                        k230_rx_task_entry,
                                        RT_NULL,
                                        1536,
                                        7,
                                        10);
    if (tid1 != RT_NULL) {
        rt_thread_startup(tid1);
    }

    rt_thread_t tid2 = rt_thread_create("asr_rx",
                                        asr_rx_task_entry,
                                        RT_NULL,
                                        1536,
                                        7,
                                        10);
    if (tid2 != RT_NULL) {
        rt_thread_startup(tid2);
    }

    rt_kprintf("[ASR] ASR PRO & K230 IRQ RingBuffer Bridge Initialized.\n");
}
