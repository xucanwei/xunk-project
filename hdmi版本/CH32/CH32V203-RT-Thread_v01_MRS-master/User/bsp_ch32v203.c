/*********************************************************************
 * File Name          : bsp_ch32v203.c
 * Description        : BSP Hardware Drivers & Pin Init for CH32V203C8T6
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 *********************************************************************/
#include "bsp_ch32v203.h"
#include <string.h>

void Delay_Us(uint32_t us)
{
    volatile uint32_t i;
    uint32_t count = us * (SystemCoreClock / 8000000);
    for (i = 0; i < count; i++) {
        __asm__ volatile ("nop");
    }
}

void Delay_Ms(uint32_t ms)
{
    rt_thread_mdelay(ms);
}

#define PCA9685_I2C_ADDR                  0x80  /* 8位写地址: 0x40 << 1 */
#define I2C_DELAY_TICKS                   12U
#define PCA9685_MODE2_REG                 0x01U
#define PCA9685_MODE2_OUTDRV              0x04U
#define PCA9685_MODE2_INVRT               0x10U

/* ------------------ 软件 I2C 驱动部分 (PB8_SCL, PB9_SDA) ------------------ */

static void i2c_delay(void)
{
    volatile uint16_t i;
    for (i = 0; i < I2C_DELAY_TICKS; i++) {}
}

static void i2c_scl_set(uint8_t high)
{
    if (high) {
        GPIO_SetBits(PIN_PCA_SCL_PORT, PIN_PCA_SCL_PIN);
    } else {
        GPIO_ResetBits(PIN_PCA_SCL_PORT, PIN_PCA_SCL_PIN);
    }
}

static void i2c_sda_set(uint8_t high)
{
    if (high) {
        GPIO_SetBits(PIN_PCA_SDA_PORT, PIN_PCA_SDA_PIN);
    } else {
        GPIO_ResetBits(PIN_PCA_SDA_PORT, PIN_PCA_SDA_PIN);
    }
}

static uint8_t i2c_sda_read(void)
{
    return (GPIO_ReadInputDataBit(PIN_PCA_SDA_PORT, PIN_PCA_SDA_PIN) != Bit_RESET) ? 1 : 0;
}

static void i2c_sda_mode(GPIOMode_TypeDef mode)
{
    GPIO_InitTypeDef GPIO_InitStructure = {0};
    GPIO_InitStructure.GPIO_Pin = PIN_PCA_SDA_PIN;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = mode;
    GPIO_Init(PIN_PCA_SDA_PORT, &GPIO_InitStructure);
}

static void i2c_start(void)
{
    i2c_sda_mode(GPIO_Mode_Out_OD);
    i2c_sda_set(1);
    i2c_scl_set(1);
    i2c_delay();
    i2c_sda_set(0);
    i2c_delay();
    i2c_scl_set(0);
}

static void i2c_stop(void)
{
    i2c_sda_mode(GPIO_Mode_Out_OD);
    i2c_sda_set(0);
    i2c_delay();
    i2c_scl_set(1);
    i2c_delay();
    i2c_sda_set(1);
    i2c_delay();
}

static uint8_t i2c_write_byte(uint8_t data)
{
    uint8_t i, ack;
    i2c_sda_mode(GPIO_Mode_Out_OD);
    for (i = 0; i < 8; i++) {
        i2c_sda_set((data & 0x80) ? 1 : 0);
        i2c_delay();
        i2c_scl_set(1);
        i2c_delay();
        i2c_scl_set(0);
        data <<= 1;
    }
    i2c_sda_mode(GPIO_Mode_IPU);
    i2c_sda_set(1);
    i2c_delay();
    i2c_scl_set(1);
    i2c_delay();
    ack = i2c_sda_read();
    i2c_scl_set(0);
    return (ack == 0) ? 1 : 0;
}

static uint8_t pca9685_write_reg(uint8_t reg, uint8_t value)
{
    rt_enter_critical();
    i2c_start();
    if (!i2c_write_byte(PCA9685_I2C_ADDR)) { i2c_stop(); rt_exit_critical(); return 0; }
    if (!i2c_write_byte(reg)) { i2c_stop(); rt_exit_critical(); return 0; }
    if (!i2c_write_byte(value)) { i2c_stop(); rt_exit_critical(); return 0; }
    i2c_stop();
    rt_exit_critical();
    return 1;
}

/* ------------------ PCA9685 初始化与控制 ------------------ */

void pca9685_oe_enable(uint8_t enable)
{
    if (enable) {
        GPIO_ResetBits(PIN_PCA_OE_PORT, PIN_PCA_OE_PIN); /* 低电平使能输出 */
    } else {
        GPIO_SetBits(PIN_PCA_OE_PORT, PIN_PCA_OE_PIN);   /* 高电平禁用输出 */
    }
}

void pca9685_set_pwm(uint8_t channel, uint16_t on, uint16_t off)
{
    if (channel >= 16U) {
        return;
    }

    uint8_t reg_base = 0x06 + 4 * channel;
    pca9685_write_reg(reg_base,     on & 0xFF);
    pca9685_write_reg(reg_base + 1, on >> 8);
    pca9685_write_reg(reg_base + 2, off & 0xFF);
    pca9685_write_reg(reg_base + 3, off >> 8);
}

/* PCA9685 的 LEDn_ON_H / LEDn_OFF_H 的 bit4 用于强制恒高 / 恒低输出。 */
void pca9685_set_output_level(uint8_t channel, uint8_t high)
{
    if (high) {
        pca9685_set_pwm(channel, 0x1000U, 0x0000U); /* Full ON: 恒高 */
    } else {
        pca9685_set_pwm(channel, 0x0000U, 0x1000U); /* Full OFF: 恒低 */
    }
}

void pca9685_set_servo_angle(uint8_t channel, float angle_deg)
{
    if (angle_deg < 0.0f) angle_deg = 0.0f;
    if (angle_deg > 180.0f) angle_deg = 180.0f;

    /* 50Hz (20ms 周期), 4096 计数. 0.5ms~2.5ms 对应 102~512 脉宽计数 */
    float pulse_us = 500.0f + (angle_deg / 180.0f) * 2000.0f;
    uint16_t off_count = (uint16_t)((pulse_us * 4096.0f) / 20000.0f);
    pca9685_set_pwm(channel, 0, off_count);
}

uint8_t pca9685_init(void)
{
    pca9685_oe_enable(0);
    
    /* 尝试向 MODE1 写入 0x10 (进入 Sleep 以配置预分频) */
    if (!pca9685_write_reg(0x00, 0x10)) {
        rt_kprintf("[ERROR] PCA9685 Init Failed! No ACK on I2C addr 0x%02X (PB8_SCL, PB9_SDA). Check wiring or power!\n", PCA9685_I2C_ADDR);
        return 0;
    }
    
    /* 25MHz 晶振, 50Hz 预分频值 PRESCALE = round(25MHz / (4096 * 50Hz)) - 1 = 121 (0x79) */
    if (!pca9685_write_reg(0xFE, 0x79)) {
        rt_kprintf("[ERROR] PCA9685 set PRESCALE failed!\n");
        return 0;
    }
    
    if (!pca9685_write_reg(0x00, 0x20)) { /* MODE1: Auto-Increment */
        rt_kprintf("[ERROR] PCA9685 set Auto-Increment failed!\n");
        return 0;
    }
    rt_thread_mdelay(5);
    
    if (!pca9685_write_reg(0x00, 0xA0)) { /* 退出 Sleep 模式 */
        rt_kprintf("[ERROR] PCA9685 wake up failed!\n");
        return 0;
    }
    rt_thread_mdelay(5);

    /*
     * PWM 输出经外部三极管反相。设置 PCA9685 的 INVRT 位后，软件中的
     * “高电平/PWM 脉冲”语义对应三极管后的实际输出，无需改动角度计算。
     */
    if (!pca9685_write_reg(PCA9685_MODE2_REG,
                           PCA9685_MODE2_OUTDRV | PCA9685_MODE2_INVRT)) {
        rt_kprintf("[ERROR] PCA9685 set output inversion failed!\n");
        return 0;
    }

    /*
     * 在使能 OE 输出前，预先将 6 轴舵机硬件寄存器配置为待机闭眼脉宽，
     * 确保上电从第一帧 PWM 起立即进入待机闭眼状态，无需等待 K230 发帧，彻底防止舵机抽动。
     */
    pca9685_set_servo_angle(10, 110.0f); /* Yaw: 110.0° 居中 */
    pca9685_set_servo_angle(11, 85.0f);  /* Pitch: 85.0° 居中 */
    pca9685_set_servo_angle(12, 100.0f); /* 左眼上眼皮: 100.0° 完全闭合 */
    pca9685_set_servo_angle(13, 60.0f);  /* 左眼下眼皮: 60.0° 完全闭合 */
    pca9685_set_servo_angle(14, 60.0f);  /* 右眼上眼皮: 60.0° 完全闭合 */
    pca9685_set_servo_angle(15, 110.0f); /* 右眼下眼皮: 110.0° 完全闭合 */

    pca9685_oe_enable(1);
    rt_kprintf("[SUCCESS] PCA9685PW Servo Driver Initialized OK (PB8_SCL, PB9_SDA, PB5_OE, Addr: 0x%02X, Output Inverted).\n", PCA9685_I2C_ADDR);
    return 1;
}

/* ------------------ ADC1 采集 (PA4 CC1, PA5 CC2) ------------------ */

uint16_t bsp_adc_read_channel(uint8_t channel)
{
    uint32_t timeout = 10000;
    ADC_RegularChannelConfig(ADC1, channel, 1, ADC_SampleTime_55Cycles5);
    ADC_SoftwareStartConvCmd(ADC1, ENABLE);
    while (!ADC_GetFlagStatus(ADC1, ADC_FLAG_EOC) && --timeout);
    if (timeout == 0) {
        return 0; /* 超时退出，严防死循环霸占 CPU */
    }
    return ADC_GetConversionValue(ADC1);
}

float bsp_get_cc1_voltage(void)
{
    uint16_t val = bsp_adc_read_channel(ADC_CC1_CHANNEL);
    return (val * 3.3f) / 4095.0f;
}

float bsp_get_cc2_voltage(void)
{
    uint16_t val = bsp_adc_read_channel(ADC_CC2_CHANNEL);
    return (val * 3.3f) / 4095.0f;
}

/* ------------------ 电源控制与过流故障检测 ------------------ */

void bsp_power_enable(uint8_t enable)
{
    if (enable) {
        GPIO_ResetBits(PIN_PWREN1_PORT, PIN_PWREN1_PIN); /* CH217A EN# 低电平使能 */
    } else {
        GPIO_SetBits(PIN_PWREN1_PORT, PIN_PWREN1_PIN);   /* 高电平关闭 */
    }
}

uint8_t bsp_is_overcurrent(void)
{
    /* CH217A FLAG# 引脚低电平代表故障/过流 */
    return (GPIO_ReadInputDataBit(PIN_OVCUR1_PORT, PIN_OVCUR1_PIN) == Bit_RESET) ? 1 : 0;
}

/* ------------------ 串口工具函数 ------------------ */

void k230_uart_send_data(const uint8_t *data, uint16_t len)
{
    uint16_t i;
    rt_enter_critical();
    for (i = 0; i < len; i++) {
        while (USART_GetFlagStatus(K230_USART_DEV, USART_FLAG_TXE) == RESET);
        USART_SendData(K230_USART_DEV, data[i]);
    }
    while (USART_GetFlagStatus(K230_USART_DEV, USART_FLAG_TC) == RESET);
    rt_exit_critical();
}

void k230_uart_send_string(const char *str)
{
    k230_uart_send_data((const uint8_t *)str, strlen(str));
}

void asr_uart_send_data(const uint8_t *data, uint16_t len)
{
    uint16_t i;
    rt_enter_critical();
    for (i = 0; i < len; i++) {
        while (USART_GetFlagStatus(ASR_USART_DEV, USART_FLAG_TXE) == RESET);
        USART_SendData(ASR_USART_DEV, data[i]);
    }
    while (USART_GetFlagStatus(ASR_USART_DEV, USART_FLAG_TC) == RESET);
    rt_exit_critical();
}

/* ------------------ 板级整体硬件初始化 ------------------ */

void bsp_hardware_init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure = {0};
    USART_InitTypeDef USART_InitStructure = {0};
    ADC_InitTypeDef ADC_InitStructure = {0};
    NVIC_InitTypeDef NVIC_InitStructure = {0};

    /* 开启 APB1 / APB2 外设时钟 */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB | RCC_APB2Periph_ADC1 | RCC_APB2Periph_USART1, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART2 | RCC_APB1Periph_USART3, ENABLE);

    /* 0. 全局配置中断优先级分组为 Group 0 (全部为响应优先级，无抢占优先级，彻底杜绝中断嵌套导致 mscratch 跑飞) */
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_0);

    /* 1. 配置 PA2/PA3 (USART2 ASR PRO) */
    GPIO_InitStructure.GPIO_Pin = ASR_USART_TX_PIN;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(ASR_USART_GPIO_PORT, &GPIO_InitStructure);

    GPIO_InitStructure.GPIO_Pin = ASR_USART_RX_PIN;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_Init(ASR_USART_GPIO_PORT, &GPIO_InitStructure);

    USART_InitStructure.USART_BaudRate = 115200;
    USART_InitStructure.USART_WordLength = USART_WordLength_8b;
    USART_InitStructure.USART_StopBits = USART_StopBits_1;
    USART_InitStructure.USART_Parity = USART_Parity_No;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(ASR_USART_DEV, &USART_InitStructure);

    USART_ITConfig(ASR_USART_DEV, USART_IT_RXNE, ENABLE);
    NVIC_InitStructure.NVIC_IRQChannel = USART2_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 1;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);

    USART_Cmd(ASR_USART_DEV, ENABLE);

    /* 2. 配置 PB10/PB11 (USART3 K230) */
    GPIO_InitStructure.GPIO_Pin = K230_USART_TX_PIN;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(K230_USART_GPIO_PORT, &GPIO_InitStructure);

    GPIO_InitStructure.GPIO_Pin = K230_USART_RX_PIN;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_Init(K230_USART_GPIO_PORT, &GPIO_InitStructure);

    USART_Init(K230_USART_DEV, &USART_InitStructure);

    USART_ITConfig(K230_USART_DEV, USART_IT_RXNE, ENABLE);
    NVIC_InitStructure.NVIC_IRQChannel = USART3_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 2;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);

    USART_Cmd(K230_USART_DEV, ENABLE);

    /* 配置 USART1 (MSH 控制台串口) 中断优先级，确保统一为无抢占优先级 */
    NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);

    /* 3. 配置 PB5 (PCA_OE), PB8 (PCA_SCL), PB9 (PCA_SDA) */
    GPIO_InitStructure.GPIO_Pin = PIN_PCA_OE_PIN;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(PIN_PCA_OE_PORT, &GPIO_InitStructure);

    GPIO_InitStructure.GPIO_Pin = PIN_PCA_SCL_PIN | PIN_PCA_SDA_PIN;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_OD;
    GPIO_Init(PIN_PCA_SCL_PORT, &GPIO_InitStructure);

    /* 4. 配置 PA4/PA5 (ADC_IN4/ADC_IN5 USB3 CC 检测) */
    GPIO_InitStructure.GPIO_Pin = ADC_CC1_PIN | ADC_CC2_PIN;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AIN;
    GPIO_Init(ADC_CC1_PORT, &GPIO_InitStructure);

    ADC_InitStructure.ADC_Mode = ADC_Mode_Independent;
    ADC_InitStructure.ADC_ScanConvMode = DISABLE;
    ADC_InitStructure.ADC_ContinuousConvMode = DISABLE;
    ADC_InitStructure.ADC_ExternalTrigConv = ADC_ExternalTrigConv_None;
    ADC_InitStructure.ADC_DataAlign = ADC_DataAlign_Right;
    ADC_InitStructure.ADC_NbrOfChannel = 1;
    ADC_Init(ADC1, &ADC_InitStructure);
    ADC_Cmd(ADC1, ENABLE);

    ADC_ResetCalibration(ADC1);
    while (ADC_GetResetCalibrationStatus(ADC1));
    ADC_StartCalibration(ADC1);
    while (ADC_GetCalibrationStatus(ADC1));

    /* 5. 配置 PB12 (PWREN1) 和 PB13 (OVCUR1) */
    GPIO_InitStructure.GPIO_Pin = PIN_PWREN1_PIN;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_Init(PIN_PWREN1_PORT, &GPIO_InitStructure);

    GPIO_InitStructure.GPIO_Pin = PIN_OVCUR1_PIN;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_Init(PIN_OVCUR1_PORT, &GPIO_InitStructure);

    bsp_power_enable(1); /* 默认使能 CH217A 电源 */

    /* 初始化 PCA9685PW 舵机控制芯片 */
    pca9685_init();

    rt_kprintf("[BSP] Hardware Initialization Completed Successfully.\n");
}
