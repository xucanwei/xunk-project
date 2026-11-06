/*********************************************************************
 * File Name          : main.c
 * Description        : Main Application Entry for CH32V203C8T6 Bionic Eye Controller
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 *********************************************************************/
#include "bsp_ch32v203.h"
#include "servo_service.h"
#include "usb_touch_host.h"
#include "asr_service.h"

static void check_reset_reason(void)
{
    rt_kprintf("[BOOT] Reset Cause: ");
    uint8_t flags_found = 0;
    if (RCC_GetFlagStatus(RCC_FLAG_PORRST) != RESET) {
        rt_kprintf("[POR/BOR: Power-on or Brown-out Reset (供电跌落/上电复位)] ");
        flags_found = 1;
    }
    if (RCC_GetFlagStatus(RCC_FLAG_PINRST) != RESET) {
        rt_kprintf("[PIN: External Pin Reset (NRST引脚复位)] ");
        flags_found = 1;
    }
    if (RCC_GetFlagStatus(RCC_FLAG_SFTRST) != RESET) {
        rt_kprintf("[SFT: Software Reset (软件复位)] ");
        flags_found = 1;
    }
    if (RCC_GetFlagStatus(RCC_FLAG_IWDGRST) != RESET) {
        rt_kprintf("[IWDG: Watchdog Reset (独立看门狗复位)] ");
        flags_found = 1;
    }
    if (RCC_GetFlagStatus(RCC_FLAG_WWDGRST) != RESET) {
        rt_kprintf("[WWDG: Window Watchdog Reset] ");
        flags_found = 1;
    }
    if (RCC_GetFlagStatus(RCC_FLAG_LPWRRST) != RESET) {
        rt_kprintf("[LPWR: Low Power Reset] ");
        flags_found = 1;
    }
    if (!flags_found) {
        rt_kprintf("[Normal Boot / Unknown]");
    }
    rt_kprintf("\r\n");

    /* 清除复位标志位，确保下次复位能准确捕获最新原因 */
    RCC_ClearFlag();
}

int main(void)
{
    check_reset_reason();

    rt_kprintf("\r\n==================================================\r\n");
    rt_kprintf("   CH32V203C8T6 Bionic Eye Interactive System     \r\n");
    rt_kprintf("   RT-Thread OS Version %d.%d.%d                  \r\n", RT_VERSION_MAJOR, RT_VERSION_MINOR, RT_VERSION_PATCH);
    rt_kprintf("   System Core Clock: %d Hz                       \r\n", SystemCoreClock);
    rt_kprintf("==================================================\r\n");

    /* 1. 初始化板级引脚与外设驱动 (USART1/2/3, I2C, ADC, GPIO) */
    bsp_hardware_init();

    /* 2. 启动 6 轴眼球舵机控制服务 */
    servo_service_init();

    /* 3. 启动 USB Host HDMI 触摸数据解析与 UART 转发服务 */
    usb_touch_host_init();

    /* 4. 启动 ASR PRO 离线语音双向透传桥接服务 */
    asr_service_init();

    /* 5. 主循环：监控 USB3 CC 插入检测及 CH217A 过流保护与健康心跳 */
    uint32_t alive_ticks = 0;
    while (1) {
        float cc1_v = bsp_get_cc1_voltage();
        float cc2_v = bsp_get_cc2_voltage();
        (void)cc1_v;
        (void)cc2_v;

        if (bsp_is_overcurrent()) {
            rt_kprintf("[WARN] CH217A Power Overcurrent Fault Detected (PB13/FLAG# LOW)!\n");
        }

        /* 每隔 30 秒打印一次系统健康存活状态与运行时间，方便诊断 */
        if (++alive_ticks >= 15) {
            alive_ticks = 0;
            uint32_t cur_tick = (uint32_t)rt_tick_get();
            uint32_t uptime_s = cur_tick / RT_TICK_PER_SECOND;
            rt_kprintf("[SYS] System Alive: uptime=%u s, tick=%u\r\n", uptime_s, cur_tick);
        }

        rt_thread_mdelay(2000);
    }

    return 0;
}
