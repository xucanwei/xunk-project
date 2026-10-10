#include <stdio.h>
#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>

/* 声明外部舵机控制与串口中转初始化函数 */
extern int servo_service_init(void);

/* 定义 LED 引脚 PA5 */
#define AIR_PIN GET_PIN(A, 5)

int main(void)
{
    int count = 1;

    /* 在主线程入口显式调用舵机及串口服务初始化 */
    servo_service_init();

    /* 设置引脚模式为输出 */
    rt_pin_mode(AIR_PIN, PIN_MODE_OUTPUT);

    rt_kprintf("\n============================================\n");
    rt_kprintf("=== GD32F103C8T6 RT-Thread System Online ===\n");
    rt_kprintf("=== Console: %s, Baudrate: 115200 ===\n", RT_CONSOLE_DEVICE_NAME);
    rt_kprintf("============================================\n");

    return RT_EOK;
}
