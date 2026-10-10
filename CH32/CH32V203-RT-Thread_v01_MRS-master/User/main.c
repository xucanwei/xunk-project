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

int main(void)
{
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

    /* 5. 主循环：监控 USB3 CC 插入检测及 CH217A 过流保护 */
    while (1) {
        float cc1_v = bsp_get_cc1_voltage();
        float cc2_v = bsp_get_cc2_voltage();
        (void)cc1_v;
        (void)cc2_v;

        if (bsp_is_overcurrent()) {
            rt_kprintf("[WARN] CH217A Power Overcurrent Fault Detected (PB13/FLAG# LOW)!\n");
        }

        rt_thread_mdelay(2000);
    }

    return 0;
}
