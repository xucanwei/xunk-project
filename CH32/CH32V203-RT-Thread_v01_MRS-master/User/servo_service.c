/*********************************************************************
 * File Name          : servo_service.c
 * Description        : 6-Axis Bionic Eye Servo Controller Service Implementation
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 * MSH Commands       : servo_set <ch> <deg>
 *********************************************************************/
#include "servo_service.h"
#include "bsp_ch32v203.h"
#include <stdlib.h>

#define HOST_SOF                             0xAAU
#define HOST_ID                              0x5AU
#define APP_CMD_SET_SERVO_ANGLES             0x11U

static const uint8_t g_servo_channel_map[APP_SERVO_COUNT] = {10, 11, 12, 13, 14, 15};

static uint16_t g_current_angles_x10[APP_SERVO_COUNT] = {1025, 800, 825, 1000, 950, 850};
static uint16_t g_target_angles_x10[APP_SERVO_COUNT]  = {1025, 800, 825, 1000, 950, 850};

static uint8_t checksum_calculate(const uint8_t *data, uint16_t len)
{
    uint8_t c = 0;
    uint16_t i;
    for (i = 0; i < len; i++) {
        c ^= data[i];
    }
    return c;
}

void servo_parse_k230_frame(const uint8_t *frame_data, uint16_t len)
{
    if (len < 17) return; /* 0xAA + DeviceID(0x5A) + Cmd(0x11) + Len(12) + 6*2bytes + Checksum */

    if (frame_data[0] != HOST_SOF) return;
    if (frame_data[1] != HOST_ID) return;
    if (frame_data[2] != APP_CMD_SET_SERVO_ANGLES) return;

    uint8_t payload_len = frame_data[3];
    if (payload_len != 12) return;

    /* 校验和计算 */
    uint8_t calc_cs = checksum_calculate(&frame_data[1], 15);
    if (calc_cs != frame_data[16]) return;

    /* 解析 6 通道角度 (x10) */
    uint8_t i;
    for (i = 0; i < APP_SERVO_COUNT; i++) {
        uint16_t angle_x10 = frame_data[4 + i * 2] | (frame_data[5 + i * 2] << 8);
        if (angle_x10 > 1800) angle_x10 = 1800;
        g_target_angles_x10[i] = angle_x10;
    }
}

/* 舵机平滑插值与硬件刷新定时线程 (20ms 50Hz 刷新周期) */
static void servo_thread_entry(void *parameter)
{
    uint8_t i;
    while (1) {
        for (i = 0; i < APP_SERVO_COUNT; i++) {
            if (g_current_angles_x10[i] != g_target_angles_x10[i]) {
                int16_t diff = (int16_t)g_target_angles_x10[i] - (int16_t)g_current_angles_x10[i];
                if (diff > 15) {
                    g_current_angles_x10[i] += 15;
                } else if (diff < -15) {
                    g_current_angles_x10[i] -= 15;
                } else {
                    g_current_angles_x10[i] = g_target_angles_x10[i];
                }
            }
            float angle_deg = g_current_angles_x10[i] / 10.0f;
            pca9685_set_servo_angle(g_servo_channel_map[i], angle_deg);
        }
        rt_thread_mdelay(20);
    }
}

void servo_service_init(void)
{
    rt_thread_t tid = rt_thread_create("servo_th",
                                       servo_thread_entry,
                                       RT_NULL,
                                       1024,
                                       10,
                                       10);
    if (tid != RT_NULL) {
        rt_thread_startup(tid);
        rt_kprintf("[SERVO] 6-Axis Servo Service Thread Started.\n");
    }
}

/* ------------------ MSH 串口调试与角度校准指令 ------------------ */

static const char *g_servo_names[APP_SERVO_COUNT] = {
    "Left Eye Yaw (LED 10)",
    "Left Eye Pitch (LED 11)",
    "Right Eye Yaw (LED 12)",
    "Right Eye Pitch (LED 13)",
    "Left Eye Eyelid (LED 14)",
    "Right Eye Eyelid (LED 15)"
};

void servo_set(int argc, char **argv)
{
    if (argc < 3)
    {
        rt_kprintf("Usage: servo_set <channel_0_to_5> <angle_in_degrees>\n");
        rt_kprintf("Example: servo_set 0 90.0   (sets Left Eye Yaw to 90.0 deg)\n");
        rt_kprintf("Example: servo_set 4 120    (sets Left Eye Eyelid to 120.0 deg)\n\n");
        rt_kprintf("Current Servo Angles:\n");
        for (int i = 0; i < APP_SERVO_COUNT; i++)
        {
            rt_kprintf("  Channel %d [%s]: Current = %d.%d deg, Target = %d.%d deg\n",
                       i, g_servo_names[i],
                       g_current_angles_x10[i] / 10, g_current_angles_x10[i] % 10,
                       g_target_angles_x10[i] / 10, g_target_angles_x10[i] % 10);
        }
        return;
    }

    int ch = atoi(argv[1]);
    if (ch < 0 || ch >= APP_SERVO_COUNT)
    {
        rt_kprintf("Error: channel must be between 0 and %d\n", APP_SERVO_COUNT - 1);
        return;
    }

    float angle_deg = (float)atof(argv[2]);
    if (angle_deg < 0.0f || angle_deg > 180.0f)
    {
        rt_kprintf("Error: angle must be between 0.0 and 180.0 degrees\n");
        return;
    }

    g_target_angles_x10[ch] = (uint16_t)(angle_deg * 10.0f);
    rt_kprintf("Success: Set channel %d [%s] to %.1f degrees\n", ch, g_servo_names[ch], angle_deg);
}
MSH_CMD_EXPORT(servo_set, Set individual servo angle: servo_set <ch> <deg>);
