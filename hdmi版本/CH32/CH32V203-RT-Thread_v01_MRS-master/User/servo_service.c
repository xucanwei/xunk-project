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

/* 居中/闭合基准角度 (第一人称视角: 0:110°居中, 1:85°居中, 2:100°闭合, 3:60°闭合, 4:60°闭合, 5:110°闭合) */
static const uint16_t g_closed_angles_x10[APP_SERVO_COUNT] = {1100, 850, 1000, 600, 600, 1100};

static uint16_t g_current_angles_x10[APP_SERVO_COUNT] = {1100, 850, 1000, 600, 600, 1100};
static uint16_t g_target_angles_x10[APP_SERVO_COUNT]  = {1100, 850, 1000, 600, 600, 1100};
static uint16_t g_applied_angles_x10[APP_SERVO_COUNT] = {0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF};
/* 为避免测试命令被 20 ms 的舵机刷新覆盖，手动电平测试时暂停该刷新。 */
static volatile rt_bool_t g_pca_level_test_active = RT_FALSE;

static uint8_t checksum_calculate(const uint8_t *data, uint16_t len)
{
    uint8_t c = 0;
    uint16_t i;
    for (i = 0; i < len; i++) {
        c ^= data[i];
    }
    return c;
}

uint8_t servo_parse_k230_frame(const uint8_t *frame_data, uint16_t len)
{
    if (len < 17) return 0; /* 0xAA + DeviceID(0x5A) + Cmd(0x11) + Len(12) + 6*2bytes + Checksum */

    if (frame_data[0] != HOST_SOF) return 0;
    if (frame_data[1] != HOST_ID) return 0;
    if (frame_data[2] != APP_CMD_SET_SERVO_ANGLES) return 0;

    uint8_t payload_len = frame_data[3];
    if (payload_len != 12) return 0;

    /* 校验和计算 */
    uint8_t calc_cs = checksum_calculate(&frame_data[1], 15);
    if (calc_cs != frame_data[16]) return 0;

    /* 解析 6 通道新目标角度 (x10)，直接写入，完全透明输出，不作任何防堵转过滤 */
    uint8_t i;
    for (i = 0; i < APP_SERVO_COUNT; i++) {
        uint16_t angle_x10 = frame_data[4 + i * 2] | (frame_data[5 + i * 2] << 8);
        if (angle_x10 > 1800) angle_x10 = 1800;
        g_target_angles_x10[i] = angle_x10;
        g_current_angles_x10[i] = angle_x10;
    }
    return 1;
}

/* 舵机硬件刷新定时线程 (20ms 50Hz 刷新周期) */
static void servo_thread_entry(void *parameter)
{
    uint8_t i;
    uint16_t heartbeat_cnt = 0;

    while (1) {
        if (g_pca_level_test_active) {
            rt_thread_mdelay(20);
            continue;
        }

        /* 检查是否有任何通道角度发生变化，或到达 1000ms 心跳同步周期 */
        rt_bool_t need_update = RT_FALSE;
        if (++heartbeat_cnt >= 50) { /* 50 * 20ms = 1000ms 心跳容错 */
            heartbeat_cnt = 0;
            need_update = RT_TRUE;
        }

        for (i = 0; i < APP_SERVO_COUNT; i++) {
            if (g_current_angles_x10[i] != g_applied_angles_x10[i]) {
                need_update = RT_TRUE;
                break;
            }
        }

        /* 仅在角度有变化或心跳到达时才进行 I2C 写入，彻底消除长时间静止时每秒 1200 次 I2C 狂刷导致的临界区死锁与总线假死 */
        if (need_update) {
            for (i = 0; i < APP_SERVO_COUNT; i++) {
                if (g_current_angles_x10[i] != g_applied_angles_x10[i] || heartbeat_cnt == 0) {
                    float angle_deg = g_current_angles_x10[i] / 10.0f;
                    pca9685_set_servo_angle(g_servo_channel_map[i], angle_deg);
                    g_applied_angles_x10[i] = g_current_angles_x10[i];
                }
            }
        }

        rt_thread_mdelay(20);
    }
}

void servo_service_init(void)
{
    uint8_t i;
    /* 上电开机立即主动将 6 轴舵机设置并驱动至待机闭眼状态，无需等待 K230 发帧 */
    for (i = 0; i < APP_SERVO_COUNT; i++) {
        g_current_angles_x10[i] = g_closed_angles_x10[i];
        g_target_angles_x10[i] = g_closed_angles_x10[i];
        pca9685_set_servo_angle(g_servo_channel_map[i], g_closed_angles_x10[i] / 10.0f);
    }

    rt_thread_t tid = rt_thread_create("servo_th",
                                       servo_thread_entry,
                                       RT_NULL,
                                       1024,
                                       10,
                                       10);
    if (tid != RT_NULL) {
        rt_thread_startup(tid);
        rt_kprintf("[SERVO] 6-Axis Servo Service Thread Started (Standby Closed-Eye Mode Active).\n");
    }
}

/* ------------------ MSH 串口调试与角度校准指令 ------------------ */

static const char *g_servo_names[APP_SERVO_COUNT] = {
    "Yaw (LED 10)",
    "Pitch (LED 11)",
    "Left Upper Eyelid (LED 12)",
    "Left Lower Eyelid (LED 13)",
    "Right Upper Eyelid (LED 14)",
    "Right Lower Eyelid (LED 15)"
};

void servo_set(int argc, char **argv)
{
    if (argc < 3)
    {
        rt_kprintf("Usage: servo_set <channel_0_to_5> <angle_in_degrees>\n");
        rt_kprintf("  CH0: Yaw (110.0 center, 60.0 right, 160.0 left)\n");
        rt_kprintf("  CH1: Pitch (85.0 center, 100.0 up, 70.0 down)\n");
        rt_kprintf("  CH2: Left Upper Eyelid (60.0 open, 100.0 close)\n");
        rt_kprintf("  CH3: Left Lower Eyelid (100.0 open, 60.0 close)\n");
        rt_kprintf("  CH4: Right Upper Eyelid (110.0 open, 60.0 close)\n");
        rt_kprintf("  CH5: Right Lower Eyelid (80.0 open, 110.0 close)\n\n");
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
    g_current_angles_x10[ch] = g_target_angles_x10[ch];
    pca9685_set_servo_angle(g_servo_channel_map[ch], angle_deg);
    rt_kprintf("Success: Set channel %d [%s] to %d.%d degrees\n",
               ch, g_servo_names[ch], (int)angle_deg, (int)(angle_deg * 10.0f) % 10);
}
MSH_CMD_EXPORT(servo_set, Set individual servo angle: servo_set <ch> <deg>);

/*
 * 输出固定高/低电平，适合确认 PCA9685 的 PWM10~PWM15 引脚及连线。
 * pca_level 的电平是三极管后的最终电平；PCA9685 已在 MODE2 中硬件反相。
 */
static void pca_level(int argc, char **argv)
{
    uint8_t channel;
    uint8_t high;
    uint8_t i;

    if (argc != 3) {
        rt_kprintf("Usage: pca_level <pca_channel_10_to_15> <0|1>\n");
        rt_kprintf("Example: pca_level 10 1  (final output of PWM10 HIGH)\n");
        rt_kprintf("Example: pca_level 10 0  (final output of PWM10 LOW)\n");
        rt_kprintf("Note: this pauses servo PWM refresh; reset the board to resume servo control.\n");
        return;
    }

    channel = (uint8_t)atoi(argv[1]);
    high = (uint8_t)atoi(argv[2]);
    if (channel < 10U || channel > 15U || high > 1U) {
        rt_kprintf("Error: channel must be 10..15 and level must be 0 or 1.\n");
        return;
    }

    g_pca_level_test_active = RT_TRUE;
    for (i = 10U; i <= 15U; i++) {
        pca9685_set_output_level(i, 0U);
    }
    pca9685_set_output_level(channel, high);

    rt_kprintf("[PCA] PWM%u fixed %s; PWM10..PWM15 other channels fixed LOW.\n",
               channel, high ? "HIGH" : "LOW");
}
MSH_CMD_EXPORT(pca_level, Set PCA9685 PWM10-PWM15 fixed output level: pca_level <ch> <0|1>);

static void pca_test(int argc, char **argv)
{
    rt_kprintf("[TEST] Testing PCA9685 connection on PB8(SCL) / PB9(SDA) / PB5(OE)...\n");
    if (pca9685_init()) {
        rt_kprintf("[TEST] PCA9685 I2C communication OK! Address: 0x%02X\n", 0x80);
    } else {
        rt_kprintf("[TEST] PCA9685 communication FAILED! No ACK received.\n");
    }
}
MSH_CMD_EXPORT(pca_test, Test PCA9685 I2C communication: pca_test);

