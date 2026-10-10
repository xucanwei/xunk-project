/*
 * Copyright (c) 2006-2026, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-05-21     Antigravity  First implementation for N20 Motor & Encoder with 20kHz PWM Speed Control
 */

#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>
#include <stdlib.h>

/* 引入 GD32 固件库外设头文件 */
#include "gd32f10x_rcu.h"
#include "gd32f10x_gpio.h"
#include "gd32f10x_timer.h"

/* 编码器输入引脚定义 */
#define ENCODER_A_PIN    GET_PIN(B, 13)
#define ENCODER_B_PIN    GET_PIN(B, 12)

/* 编码器计数变量 */
static volatile long encoder_count = 0;
static rt_bool_t monitor_enabled = RT_FALSE;
static rt_thread_t monitor_tid = RT_NULL;

/**
 * @brief 编码器 A 通道中断服务程序
 */
static void encoder_a_isr(void *args)
{
    /* A通道触发上升沿中断，读取B通道电平确定方向 */
    int b_val = rt_pin_read(ENCODER_B_PIN);
    
    if (b_val == PIN_LOW)
    {
        encoder_count++;
    }
    else
    {
        encoder_count--;
    }
}

/**
 * @brief 电机动作与转速控制函数
 * @param action 动作类型: 'f'正转, 'r'反转, 's'停止, 'b'刹车
 * @param speed  速度百分比: 0 到 100
 */
void motor_ctrl_set(char action, int speed)
{
    if (speed < 0) speed = 0;
    if (speed > 100) speed = 100;
    
    switch (action)
    {
    case 'f': /* 正转 */
        TIMER_CH0CV(TIMER2) = speed;
        TIMER_CH1CV(TIMER2) = 0;
        rt_kprintf("Motor control: Forward, Speed = %d%%\n", speed);
        break;
    case 'r': /* 反转 */
        TIMER_CH0CV(TIMER2) = 0;
        TIMER_CH1CV(TIMER2) = speed;
        rt_kprintf("Motor control: Reverse, Speed = %d%%\n", speed);
        break;
    case 'b': /* 刹车 */
        TIMER_CH0CV(TIMER2) = 100;
        TIMER_CH1CV(TIMER2) = 100;
        rt_kprintf("Motor control: Brake\n");
        break;
    case 's': /* 停止 */
    default:
        TIMER_CH0CV(TIMER2) = 0;
        TIMER_CH1CV(TIMER2) = 0;
        rt_kprintf("Motor control: Stop\n");
        break;
    }
}

/**
 * @brief 编码器速度监控后台线程入口
 */
static void motor_monitor_entry(void *parameter)
{
    long prev_count = 0;
    long curr_count = 0;
    long speed_pps = 0; /* 脉冲数/秒 */
    
    rt_kprintf("Motor Speed Monitor started.\n");
    
    while (1)
    {
        if (monitor_enabled)
        {
            curr_count = encoder_count;
            /* 100ms 刷新一次，乘以 10 转换为每秒脉冲数 (Pulse Per Second) */
            speed_pps = (curr_count - prev_count) * 10;
            prev_count = curr_count;
            
            rt_kprintf("[Motor Monitor] Count: %10ld | Speed: %6ld pps\n", curr_count, speed_pps);
        }
        else
        {
            /* 挂起前同步一下计数器 */
            prev_count = encoder_count;
        }
        
        rt_thread_mdelay(100);
    }
}

/**
 * @brief 驱动初始化函数，系统自动注册
 */
int motor_encoder_init(void)
{
    /* 1. 开启 GPIOA 和 TIMER2 硬件时钟 */
    rcu_periph_clock_enable(RCU_GPIOA);
    rcu_periph_clock_enable(RCU_TIMER2);
    
    /* 2. 初始化 PA6 和 PA7 为复用推挽输出模式以配置为 TIMER2_CH0 & TIMER2_CH1 */
    gpio_init(GPIOA, GPIO_MODE_AF_PP, GPIO_OSPEED_50MHZ, GPIO_PIN_6 | GPIO_PIN_7);
    
    /* 3. 配置 TIMER2 产生 20kHz PWM */
    TIMER_CTL0(TIMER2) &= ~TIMER_CTL0_CEN;
    
    /* 
     * APB1的定时器时钟频率为 72MHz。
     * 预分频 PSC = 35，则计数器时钟频率为 72MHz / (35 + 1) = 2MHz。
     * 自动重装载值 CAR = 99，则 PWM 周期为 2MHz / (99 + 1) = 20kHz。
     */
    TIMER_PSC(TIMER2) = 35;
    TIMER_CAR(TIMER2) = 99;
    
    /* 配置通道 0 和通道 1 为输出比较 PWM0 模式，使能输出比较影子寄存器 */
    TIMER_CHCTL0(TIMER2) &= ~((3U << 0) | (7U << 4) | (3U << 8) | (7U << 12));
    TIMER_CHCTL0(TIMER2) |= ((6U << 4) | (1U << 3) | (6U << 12) | (1U << 11));
    
    /* 通道 0 和通道 1 极性设为高电平有效，并使能通道输出 */
    TIMER_CHCTL2(TIMER2) &= ~((1U << 1) | (1U << 5));
    TIMER_CHCTL2(TIMER2) |= ((1U << 0) | (1U << 4));
    
    /* 初始脉宽设为 0 (占空比 0%，停止) */
    TIMER_CH0CV(TIMER2) = 0;
    TIMER_CH1CV(TIMER2) = 0;
    
    /* 触发软件更新事件，以将 PSC 和 CAR 加载进活动寄存器 */
    TIMER_SWEVG(TIMER2) |= TIMER_SWEVG_UPG;
    
    /* 开启定时器计数器 */
    TIMER_CTL0(TIMER2) |= TIMER_CTL0_CEN;
    
    /* 4. 初始化编码器引脚，配置上拉输入 */
    rt_pin_mode(ENCODER_A_PIN, PIN_MODE_INPUT_PULLUP);
    rt_pin_mode(ENCODER_B_PIN, PIN_MODE_INPUT_PULLUP);
    
    /* 5. 绑定编码器A通道上升沿中断并使能 */
    rt_pin_attach_irq(ENCODER_A_PIN, PIN_IRQ_MODE_RISING, encoder_a_isr, RT_NULL);
    rt_pin_irq_enable(ENCODER_A_PIN, PIN_IRQ_ENABLE);
    
    /* 6. 创建后台定时监控线程 */
    monitor_tid = rt_thread_create("mot_mon", motor_monitor_entry, RT_NULL,
                                   1024, 22, 10);
    if (monitor_tid != RT_NULL)
    {
        rt_thread_startup(monitor_tid);
    }
    
    rt_kprintf("N20 Motor (20kHz PWM) & Encoder driver initialized successfully!\n");
    return RT_EOK;
}
/* 导出为板级初始化，在调度器运行后自动执行 */
INIT_APP_EXPORT(motor_encoder_init);


/* ================= MSH 调试指令实现 ================= */

/**
 * @brief 控制电机转动与转速指令
 */
static void motor_ctrl(int argc, char **argv)
{
    if (argc < 2)
    {
        rt_kprintf("Usage: motor_ctrl <action> [speed]\n");
        rt_kprintf("Actions:\n");
        rt_kprintf("  f  : Forward,  e.g., motor_ctrl f 50 (50%% speed)\n");
        rt_kprintf("  r  : Reverse,  e.g., motor_ctrl r 80 (80%% speed)\n");
        rt_kprintf("  s  : Stop (Coast)\n");
        rt_kprintf("  b  : Brake (Brake)\n");
        return;
    }
    
    char action = argv[1][0];
    int speed = 50; /* 默认 50% 转速 */
    
    if (argc >= 3)
    {
        speed = atoi(argv[2]);
    }
    
    motor_ctrl_set(action, speed);
}
MSH_CMD_EXPORT(motor_ctrl, control N20 motor: motor_ctrl [f|r|s|b] [speed_percent]);

/**
 * @brief 读取当前编码器脉冲计数值
 */
static void motor_read(void)
{
    rt_kprintf("Current Encoder Count: %ld\n", encoder_count);
}
MSH_CMD_EXPORT(motor_read, read current motor encoder count);

/**
 * @brief 编码器脉冲计数值清零
 */
static void motor_clear(void)
{
    encoder_count = 0;
    rt_kprintf("Encoder count cleared to 0.\n");
}
MSH_CMD_EXPORT(motor_clear, clear motor encoder count);

/**
 * @brief 启用/停用速度实时监控打印
 */
static void motor_monitor(int argc, char **argv)
{
    if (argc < 2)
    {
        rt_kprintf("Usage: motor_monitor <start|stop>\n");
        return;
    }
    
    if (rt_strcmp(argv[1], "start") == 0)
    {
        monitor_enabled = RT_TRUE;
        rt_kprintf("Motor real-time monitor enabled.\n");
    }
    else if (rt_strcmp(argv[1], "stop") == 0)
    {
        monitor_enabled = RT_FALSE;
        rt_kprintf("Motor real-time monitor disabled.\n");
    }
    else
    {
        rt_kprintf("Invalid parameter! Use 'start' or 'stop'.\n");
    }
}
MSH_CMD_EXPORT(motor_monitor, enable/disable encoder monitor: motor_monitor [start|stop]);
