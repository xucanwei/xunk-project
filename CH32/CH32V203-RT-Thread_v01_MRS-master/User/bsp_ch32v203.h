/*********************************************************************
 * File Name          : bsp_ch32v203.h
 * Description        : BSP Hardware Pin Definitions & Driver Prototypes for CH32V203C8T6
 * Target MCU         : CH32V203C8T6
 * OS                 : RT-Thread
 *********************************************************************/
#ifndef __BSP_CH32V203_H__
#define __BSP_CH32V203_H__

#include "ch32v20x.h"
#include <rtthread.h>
#include <rtdevice.h>

#ifdef __cplusplus
extern "C" {
#endif

void Delay_Us(uint32_t us);
void Delay_Ms(uint32_t ms);

/* ------------------ 引脚定义 ------------------ */

/* 1. 语音串口 (USART2: PA2_TX, PA3_RX) */
#define ASR_USART_DEV                     USART2
#define ASR_USART_GPIO_PORT               GPIOA
#define ASR_USART_TX_PIN                  GPIO_Pin_2
#define ASR_USART_RX_PIN                  GPIO_Pin_3
#define ASR_USART_CLK                     RCC_APB1Periph_USART2
#define ASR_USART_GPIO_CLK                RCC_APB2Periph_GPIOA

/* 2. K230 通讯串口 (USART3: PB10_TX, PB11_RX) */
#define K230_USART_DEV                    USART3
#define K230_USART_GPIO_PORT              GPIOB
#define K230_USART_TX_PIN                 GPIO_Pin_10
#define K230_USART_RX_PIN                 GPIO_Pin_11
#define K230_USART_CLK                    RCC_APB1Periph_USART3
#define K230_USART_GPIO_CLK               RCC_APB2Periph_GPIOB

/* 3. MSH 调试串口 (USART1: PA9_TX, PA10_RX) */
#define MSH_USART_DEV                     USART1
#define MSH_USART_GPIO_PORT               GPIOA
#define MSH_USART_TX_PIN                  GPIO_Pin_9
#define MSH_USART_RX_PIN                  GPIO_Pin_10
#define MSH_USART_CLK                     RCC_APB2Periph_USART1
#define MSH_USART_GPIO_CLK                RCC_APB2Periph_GPIOA

/* 4. PCA9685 舵机驱动器软件 I2C (PB8_SCL, PB9_SDA, PB5_OE) */
#define PIN_PCA_SCL_PORT                  GPIOB
#define PIN_PCA_SCL_PIN                   GPIO_Pin_8
#define PIN_PCA_SDA_PORT                  GPIOB
#define PIN_PCA_SDA_PIN                   GPIO_Pin_9
#define PIN_PCA_OE_PORT                   GPIOB
#define PIN_PCA_OE_PIN                    GPIO_Pin_5
#define PCA_I2C_GPIO_CLK                  RCC_APB2Periph_GPIOB

/* 5. USB3 CC 分压电压检测 ADC (PA4: CC1_ADC_IN4, PA5: CC2_ADC_IN5) */
#define ADC_CC1_PORT                      GPIOA
#define ADC_CC1_PIN                       GPIO_Pin_4
#define ADC_CC1_CHANNEL                   ADC_Channel_4

#define ADC_CC2_PORT                      GPIOA
#define ADC_CC2_PIN                       GPIO_Pin_5
#define ADC_CC2_CHANNEL                   ADC_Channel_5

/* 6. CH217A 电源分配开关控制 (PB12: PWREN1/EN#, PB13: OVCUR1/FLAG#) */
#define PIN_PWREN1_PORT                   GPIOB
#define PIN_PWREN1_PIN                    GPIO_Pin_12
#define PIN_OVCUR1_PORT                   GPIOB
#define PIN_OVCUR1_PIN                    GPIO_Pin_13

/* 7. USB Host HDMI Touch 引脚 (PB6: USB_DM / USB2_DM, PB7: USB_DP / USB2_DP) */
#define USB_HOST_PORT                     GPIOB
#define USB_HOST_DM_PIN                   GPIO_Pin_6
#define USB_HOST_DP_PIN                   GPIO_Pin_7

/* ------------------ 函数原型声明 ------------------ */

void bsp_hardware_init(void);

/* PCA9685 I2C & Servo 函数 */
void pca9685_init(void);
void pca9685_set_pwm(uint8_t channel, uint16_t on, uint16_t off);
void pca9685_set_servo_angle(uint8_t channel, float angle_deg);
void pca9685_oe_enable(uint8_t enable);

/* ADC 电压采样函数 */
uint16_t bsp_adc_read_channel(uint8_t channel);
float bsp_get_cc1_voltage(void);
float bsp_get_cc2_voltage(void);

/* 电源与故障检测函数 */
void bsp_power_enable(uint8_t enable);
uint8_t bsp_is_overcurrent(void);

/* 串口通信发送工具函数 */
void k230_uart_send_data(const uint8_t *data, uint16_t len);
void k230_uart_send_string(const char *str);
void asr_uart_send_data(const uint8_t *data, uint16_t len);

#ifdef __cplusplus
}
#endif

#endif /* __BSP_CH32V203_H__ */
