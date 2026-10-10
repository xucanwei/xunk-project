#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>
#include <stdint.h>
#include <stdlib.h>

#include "gd32f10x_rcu.h"
#include "gd32f10x_gpio.h"

/* ------------------ 串口配置定义 ------------------ */
#define K230_UART_NAME                       "uart2" /* PB10/PB11 对应 uart2 */
#define ASR_UART_NAME                        "uart1" /* PA2/PA3 对应 uart1 */

/* ------------------ 机械手与舵机协议定义 ------------------ */
#define APP_FW_VERSION_MAJOR                 1U
#define APP_FW_VERSION_MINOR                 0U
#define APP_FW_VERSION_PATCH                 0U

#define HOST_SOF                             0xAAU
#define HOST_ID                              0x5AU

#define APP_CMD_READ_FW_VERSION              0x01U
#define APP_CMD_SET_SERVO_ANGLE              0x10U
#define APP_CMD_SET_SERVO_ANGLES             0x11U
#define APP_CMD_ESTOP_ALL                    0x15U
#define APP_CMD_RESTORE_DEFAULT_POSE         0x16U
#define APP_CMD_PLAY_VOICE                   0x20U

#define APP_ERR_OK                           0x00U
#define APP_ERR_FRAME                        0x01U
#define APP_ERR_CHECKSUM                     0x02U
#define APP_ERR_RANGE                        0x03U
#define APP_ERR_CHANNEL                      0x04U
#define APP_ERR_BUSY                         0x05U
#define APP_ERR_HW_INIT                      0x06U
#define APP_ERR_I2C                          0x07U
#define APP_ERR_ESTOP                        0x08U
#define APP_ERR_UNSUPPORTED                  0x09U

#define APP_SERVO_COUNT                      6U
#define APP_SERVO_PWM_FREQ_HZ                50U     /* S90 舵机工作在 50Hz (20ms 周期) */
#define APP_SERVO_SMOOTH_INTERVAL_MS         10U
#define APP_SERVO_SMOOTH_STEP_DEG_X10        150U    /* 每次步进角度，单位 0.1 度 */

#define APP_SERVO_MIN_ANGLE_DEG_X10          0U
#define APP_SERVO_MAX_ANGLE_DEG_X10          1800U
#define APP_SERVO_SAFE_MIN_ANGLE_DEG_X10     50U     /* 安全下限 5 度 */
#define APP_SERVO_SAFE_MAX_ANGLE_DEG_X10     1750U    /* 安全上限 175 度 */

#define APP_SERVO_MIN_PULSE_US               500U    /* 0度脉宽：0.5ms */
#define APP_SERVO_MAX_PULSE_US               2500U   /* 180度脉宽：2.5ms */

#define APP_SERVO_I2C_ADDR                   0x40U    /* PCA9685 I2C 地址 */

/* 6路舵机对应的 PCA9685 通道映射：LED10 ~ LED15 */
static const uint8_t gcu8ServoPcaChannelMap[APP_SERVO_COUNT] = {10, 11, 12, 13, 14, 15};

/* ------------------ 软件 I2C 引脚及延时 ------------------ */
#define PIN_PCA_SCL_PORT                     GPIOB
#define PIN_PCA_SCL                          GPIO_PIN_6
#define PIN_PCA_SDA_PORT                     GPIOB
#define PIN_PCA_SDA                          GPIO_PIN_7
#define PIN_PCA_OE_PORT                      GPIOB
#define PIN_PCA_OE                           GPIO_PIN_5

#define I2C_DELAY_TICKS                      16U

/* ------------------ 模块内部全局变量 ------------------ */
static rt_device_t k230_dev = RT_NULL;
static rt_device_t asr_dev = RT_NULL;
static struct rt_semaphore rx_sem_k230;
static struct rt_semaphore rx_sem_asr;

static uint8_t gu8ServoEstop = 0;
static uint8_t gu8ServoReady = 0;
static uint16_t gu16ServoCurrentAngleX10[APP_SERVO_COUNT];
static uint16_t gu16ServoTargetAngleX10[APP_SERVO_COUNT];
static uint32_t gu32ServoSmoothTickMs;

/* ------------------ 软件 I2C 驱动实现 ------------------ */
static void i2c_delay(void)
{
    volatile uint16_t u16Delay;
    for (u16Delay = 0U; u16Delay < I2C_DELAY_TICKS; u16Delay++) {}
}

static void i2c_scl_set(uint8_t u8High)
{
    if (u8High != 0U) {
        gpio_bit_set(PIN_PCA_SCL_PORT, PIN_PCA_SCL);
    } else {
        gpio_bit_reset(PIN_PCA_SCL_PORT, PIN_PCA_SCL);
    }
}

static void i2c_sda_set(uint8_t u8High)
{
    if (u8High != 0U) {
        gpio_bit_set(PIN_PCA_SDA_PORT, PIN_PCA_SDA);
    } else {
        gpio_bit_reset(PIN_PCA_SDA_PORT, PIN_PCA_SDA);
    }
}

static uint8_t i2c_sda_read(void)
{
    return (gpio_input_bit_get(PIN_PCA_SDA_PORT, PIN_PCA_SDA) != RESET) ? 1U : 0U;
}

static void i2c_sda_input_mode(void)
{
    gpio_init(PIN_PCA_SDA_PORT, GPIO_MODE_IPU, GPIO_OSPEED_50MHZ, PIN_PCA_SDA);
}

static void i2c_sda_output_mode(void)
{
    gpio_init(PIN_PCA_SDA_PORT, GPIO_MODE_OUT_OD, GPIO_OSPEED_50MHZ, PIN_PCA_SDA);
}

static void i2c_start(void)
{
    i2c_sda_output_mode();
    i2c_sda_set(1U);
    i2c_scl_set(1U);
    i2c_delay();
    i2c_sda_set(0U);
    i2c_delay();
    i2c_scl_set(0U);
}

static void i2c_stop(void)
{
    i2c_sda_output_mode();
    i2c_sda_set(0U);
    i2c_delay();
    i2c_scl_set(1U);
    i2c_delay();
    i2c_sda_set(1U);
    i2c_delay();
}

static uint8_t i2c_write_byte(uint8_t u8Data)
{
    uint8_t u8Bit;
    uint8_t u8Ack;

    i2c_sda_output_mode();
    for (u8Bit = 0U; u8Bit < 8U; u8Bit++) {
        i2c_sda_set((u8Data & 0x80U) != 0U ? 1U : 0U);
        i2c_delay();
        i2c_scl_set(1U);
        i2c_delay();
        i2c_scl_set(0U);
        u8Data <<= 1;
    }

    i2c_sda_input_mode();
    i2c_delay();
    i2c_scl_set(1U);
    i2c_delay();
    u8Ack = (uint8_t)(i2c_sda_read() == 0U ? 1U : 0U);
    i2c_scl_set(0U);
    i2c_sda_output_mode();
    return u8Ack;
}

static uint8_t i2c_read_byte(void)
{
    uint8_t u8Bit;
    uint8_t u8Data;

    u8Data = 0U;
    i2c_sda_input_mode();
    for (u8Bit = 0U; u8Bit < 8U; u8Bit++) {
        u8Data <<= 1;
        i2c_scl_set(1U);
        i2c_delay();
        if (i2c_sda_read() != 0U) {
            u8Data |= 0x01U;
        }
        i2c_scl_set(0U);
        i2c_delay();
    }

    i2c_sda_output_mode();
    i2c_sda_set(1U);
    i2c_delay();
    i2c_scl_set(1U);
    i2c_delay();
    i2c_scl_set(0U);
    i2c_delay();
    return u8Data;
}

static void i2c_soft_init(void)
{
    i2c_sda_output_mode();
    i2c_sda_set(1U);
    i2c_scl_set(1U);
}

static uint8_t i2c_soft_write_reg(uint8_t u8Addr, uint8_t u8Reg, uint8_t u8Value)
{
    i2c_start();
    if (!i2c_write_byte((uint8_t)(u8Addr << 1))) {
        i2c_stop();
        return 0U;
    }
    if (!i2c_write_byte(u8Reg)) {
        i2c_stop();
        return 0U;
    }
    if (!i2c_write_byte(u8Value)) {
        i2c_stop();
        return 0U;
    }
    i2c_stop();
    return 1U;
}

static uint8_t i2c_soft_read_reg(uint8_t u8Addr, uint8_t u8Reg, uint8_t *pu8Value)
{
    if (pu8Value == 0) {
        return 0U;
    }
    i2c_start();
    if (!i2c_write_byte((uint8_t)(u8Addr << 1))) {
        i2c_stop();
        return 0U;
    }
    if (!i2c_write_byte(u8Reg)) {
        i2c_stop();
        return 0U;
    }
    i2c_stop();
    i2c_delay();
    i2c_start();
    if (!i2c_write_byte((uint8_t)((u8Addr << 1) | 0x01U))) {
        i2c_stop();
        return 0U;
    }
    *pu8Value = i2c_read_byte();
    i2c_stop();
    return 1U;
}

/* ------------------ PCA9685 驱动实现 ------------------ */
#define PCA9685_REG_MODE1         0x00U
#define PCA9685_REG_MODE2         0x01U
#define PCA9685_REG_LED0_ON_L     0x06U
#define PCA9685_REG_PRESCALE      0xFEU

#define PCA9685_MODE1_AI          0x20U
#define PCA9685_MODE1_SLEEP       0x10U
#define PCA9685_MODE1_RESTART     0x80U
#define PCA9685_MODE2_INVRT       0x10U
#define PCA9685_MODE2_OUTDRV      0x04U

static uint8_t pca_write_reg(uint8_t u8Reg, uint8_t u8Value)
{
    uint8_t u8Retry;
    for (u8Retry = 0U; u8Retry < 3; u8Retry++) {
        if (i2c_soft_write_reg(APP_SERVO_I2C_ADDR, u8Reg, u8Value)) {
            return 1U;
        }
    }
    return 0U;
}

static uint8_t pca_read_reg(uint8_t u8Reg, uint8_t *pu8Value)
{
    uint8_t u8Retry;
    for (u8Retry = 0U; u8Retry < 3; u8Retry++) {
        if (i2c_soft_read_reg(APP_SERVO_I2C_ADDR, u8Reg, pu8Value)) {
            return 1U;
        }
    }
    return 0U;
}

static uint8_t pca9685_init(uint16_t u16PwmFreqHz)
{
    uint8_t u8OldMode;
    uint8_t u8NewMode;
    uint8_t u8ActiveMode;
    uint8_t u8Prescale;

    /* 预计算 S90 舵机在 50Hz 下的 prescale 值为 124，避免引入浮点数库，节省大量 Flash 空间 */
    if (u16PwmFreqHz == 50U) {
        u8Prescale = 124U;
    } else {
        u8Prescale = (uint8_t)((25000000UL / 4096UL) / (uint32_t)u16PwmFreqHz - 1UL);
    }

    if (!pca_read_reg(PCA9685_REG_MODE1, &u8OldMode)) {
        return 0U;
    }
    u8ActiveMode = (uint8_t)((u8OldMode & (uint8_t)(~PCA9685_MODE1_SLEEP)) | PCA9685_MODE1_AI);
    u8NewMode = (uint8_t)((u8OldMode & 0x7FU) | PCA9685_MODE1_SLEEP);

    if (!pca_write_reg(PCA9685_REG_MODE1, u8NewMode)) {
        return 0U;
    }
    if (!pca_write_reg(PCA9685_REG_PRESCALE, u8Prescale)) {
        return 0U;
    }
    if (!pca_write_reg(PCA9685_REG_MODE2, (uint8_t)(PCA9685_MODE2_OUTDRV | PCA9685_MODE2_INVRT))) {
        return 0U;
    }
    if (!pca_write_reg(PCA9685_REG_MODE1, u8ActiveMode)) {
        return 0U;
    }

    rt_thread_mdelay(5);

    if (!pca_write_reg(PCA9685_REG_MODE1, (uint8_t)(u8ActiveMode | PCA9685_MODE1_RESTART))) {
        return 0U;
    }
    return 1U;
}

static uint8_t pca9685_set_pulse_us(uint8_t u8Channel, uint16_t u16PulseUs)
{
    uint8_t u8BaseReg;
    uint32_t u32OffCount;

    if (u8Channel >= 16U) {
        return 0U;
    }

    u32OffCount = ((uint32_t)u16PulseUs * (uint32_t)APP_SERVO_PWM_FREQ_HZ * 4096UL) / 1000000UL;
    if (u32OffCount > 4095UL) {
        u32OffCount = 4095UL;
    }

    u8BaseReg = (uint8_t)(PCA9685_REG_LED0_ON_L + (u8Channel * 4U));
    if (!pca_write_reg(u8BaseReg + 0U, 0U)) return 0U;
    if (!pca_write_reg(u8BaseReg + 1U, 0U)) return 0U;
    if (!pca_write_reg(u8BaseReg + 2U, (uint8_t)(u32OffCount & 0xFFUL))) return 0U;
    if (!pca_write_reg(u8BaseReg + 3U, (uint8_t)((u32OffCount >> 8) & 0x0FUL))) return 0U;

    return 1U;
}

/* ------------------ 舵机角度换算与平滑控制 ------------------ */
static uint16_t servo_board_angle_to_pulse_us(uint16_t u16AngleX10)
{
    uint32_t u32PulseRange = APP_SERVO_MAX_PULSE_US - APP_SERVO_MIN_PULSE_US;
    uint32_t u32AngleRange = APP_SERVO_MAX_ANGLE_DEG_X10 - APP_SERVO_MIN_ANGLE_DEG_X10;
    uint32_t u32PulseUs = APP_SERVO_MIN_PULSE_US +
                 ((((uint32_t)(u16AngleX10 - APP_SERVO_MIN_ANGLE_DEG_X10)) * u32PulseRange) / u32AngleRange);
    return (uint16_t)u32PulseUs;
}

static uint16_t servo_board_clamp_safe_angle_x10(uint16_t u16AngleX10)
{
    if (u16AngleX10 < APP_SERVO_SAFE_MIN_ANGLE_DEG_X10) {
        return APP_SERVO_SAFE_MIN_ANGLE_DEG_X10;
    }
    if (u16AngleX10 > APP_SERVO_SAFE_MAX_ANGLE_DEG_X10) {
        return APP_SERVO_SAFE_MAX_ANGLE_DEG_X10;
    }
    return u16AngleX10;
}

static uint16_t servo_board_normalize_angle_x10(uint8_t u8Channel, uint16_t u16AngleX10)
{
    /* 移除机械手特定的大拇指非线性映射，所有眼球/眼睑通道全部使用1:1线性安全限幅映射 */
    return servo_board_clamp_safe_angle_x10(u16AngleX10);
}

static uint8_t servo_board_write_channel(uint8_t u8Channel, uint16_t u16AngleX10)
{
    uint8_t u8PcaChannel;
    uint16_t u16OutputAngleX10;
    uint16_t u16PulseUs;

    if (u8Channel >= APP_SERVO_COUNT) {
        return APP_ERR_CHANNEL;
    }

    u8PcaChannel = gcu8ServoPcaChannelMap[u8Channel];
    u16OutputAngleX10 = servo_board_normalize_angle_x10(u8Channel, u16AngleX10);
    u16PulseUs = servo_board_angle_to_pulse_us(u16OutputAngleX10);
    if (!pca9685_set_pulse_us(u8PcaChannel, u16PulseUs)) {
        return APP_ERR_I2C;
    }
    return APP_ERR_OK;
}

uint8_t ServoBoardInit(void)
{
    uint8_t u8Index;
    uint16_t u16DefaultAngleX10 = 900; /* 默认 90 度 */

    gu8ServoEstop = 0U;
    gu8ServoReady = 0U;

    i2c_soft_init();

    if (!pca9685_init(APP_SERVO_PWM_FREQ_HZ)) {
        return 0U;
    }

    /* 物理使能 PCA9685 输出：低电平拉低 PB5 */
    gpio_bit_reset(PIN_PCA_OE_PORT, PIN_PCA_OE);

    for (u8Index = 0U; u8Index < APP_SERVO_COUNT; u8Index++) {
        gu16ServoCurrentAngleX10[u8Index] = u16DefaultAngleX10;
        gu16ServoTargetAngleX10[u8Index] = u16DefaultAngleX10;
        (void)servo_board_write_channel(u8Index, u16DefaultAngleX10);
    }

    gu32ServoSmoothTickMs = rt_tick_get() * (1000 / RT_TICK_PER_SECOND);
    gu8ServoReady = 1U;
    return 1U;
}

void ServoBoardLoop(void)
{
    uint8_t u8Index;
    uint16_t u16CurrentAngleX10;
    uint16_t u16TargetAngleX10;
    uint16_t u16NextAngleX10;
    uint32_t u32NowMs = rt_tick_get() * (1000 / RT_TICK_PER_SECOND);

    if ((gu8ServoReady == 0U) || (gu8ServoEstop != 0U)) {
        return;
    }

    if ((u32NowMs - gu32ServoSmoothTickMs) < APP_SERVO_SMOOTH_INTERVAL_MS) {
        return;
    }
    gu32ServoSmoothTickMs = u32NowMs;

    for (u8Index = 0U; u8Index < APP_SERVO_COUNT; u8Index++) {
        u16CurrentAngleX10 = gu16ServoCurrentAngleX10[u8Index];
        u16TargetAngleX10 = gu16ServoTargetAngleX10[u8Index];
        if (u16CurrentAngleX10 == u16TargetAngleX10) {
            continue;
        }

        u16NextAngleX10 = u16CurrentAngleX10;
        if (u16CurrentAngleX10 < u16TargetAngleX10) {
            if ((uint16_t)(u16TargetAngleX10 - u16CurrentAngleX10) <= APP_SERVO_SMOOTH_STEP_DEG_X10) {
                u16NextAngleX10 = u16TargetAngleX10;
            } else {
                u16NextAngleX10 = (uint16_t)(u16CurrentAngleX10 + APP_SERVO_SMOOTH_STEP_DEG_X10);
            }
        } else {
            if ((uint16_t)(u16CurrentAngleX10 - u16TargetAngleX10) <= APP_SERVO_SMOOTH_STEP_DEG_X10) {
                u16NextAngleX10 = u16TargetAngleX10;
            } else {
                u16NextAngleX10 = (uint16_t)(u16CurrentAngleX10 - APP_SERVO_SMOOTH_STEP_DEG_X10);
            }
        }

        (void)servo_board_write_channel(u8Index, u16NextAngleX10);
        gu16ServoCurrentAngleX10[u8Index] = u16NextAngleX10;
    }
}

uint8_t ServoBoardSetAngleX10(uint8_t u8Channel, uint16_t u16AngleX10)
{
    if (gu8ServoReady == 0U) return APP_ERR_HW_INIT;
    if (gu8ServoEstop != 0U) return APP_ERR_ESTOP;
    if (u8Channel >= APP_SERVO_COUNT) return APP_ERR_CHANNEL;
    if (u16AngleX10 > APP_SERVO_MAX_ANGLE_DEG_X10) return APP_ERR_RANGE;

    gu16ServoTargetAngleX10[u8Channel] = servo_board_clamp_safe_angle_x10(u16AngleX10);
    return APP_ERR_OK;
}

uint8_t ServoBoardSetAnglesX10(const uint16_t *pu16AnglesX10, uint8_t u8Count)
{
    uint8_t u8Index;

    if (gu8ServoReady == 0U) return APP_ERR_HW_INIT;
    if (gu8ServoEstop != 0U) return APP_ERR_ESTOP;
    if ((pu16AnglesX10 == 0) || (u8Count != APP_SERVO_COUNT)) return APP_ERR_FRAME;

    for (u8Index = 0U; u8Index < u8Count; u8Index++) {
        if (pu16AnglesX10[u8Index] > APP_SERVO_MAX_ANGLE_DEG_X10) return APP_ERR_RANGE;
    }

    for (u8Index = 0U; u8Index < u8Count; u8Index++) {
        gu16ServoTargetAngleX10[u8Index] = servo_board_clamp_safe_angle_x10(pu16AnglesX10[u8Index]);
    }
    return APP_ERR_OK;
}

uint8_t ServoBoardRestoreDefaultPose(void)
{
    uint8_t u8Index;
    uint16_t u16DefaultAngleX10 = 900; /* 默认 90 度 */

    if (gu8ServoReady == 0U) return APP_ERR_HW_INIT;

    gu8ServoEstop = 0U;
    gpio_bit_reset(PIN_PCA_OE_PORT, PIN_PCA_OE);

    for (u8Index = 0U; u8Index < APP_SERVO_COUNT; u8Index++) {
        gu16ServoCurrentAngleX10[u8Index] = u16DefaultAngleX10;
        gu16ServoTargetAngleX10[u8Index] = u16DefaultAngleX10;
        (void)servo_board_write_channel(u8Index, u16DefaultAngleX10);
    }
    return APP_ERR_OK;
}

uint8_t ServoBoardEmergencyStop(void)
{
    if (gu8ServoReady == 0U) return APP_ERR_HW_INIT;

    gu8ServoEstop = 1U;
    /* 禁用输出：拉高 PB5 */
    gpio_bit_set(PIN_PCA_OE_PORT, PIN_PCA_OE);
    return APP_ERR_OK;
}

/* ------------------ RT-Thread 串口与逻辑处理任务 ------------------ */

static uint8_t calc_checksum(uint8_t id, uint8_t cmd, uint8_t len, const uint8_t *data, uint8_t data_len)
{
    uint8_t chk = id ^ cmd ^ len;
    for (uint8_t i = 0; i < data_len; i++) {
        chk ^= data[i];
    }
    return chk;
}

static void send_host_reply(uint8_t cmd, uint8_t err, const uint8_t *data, uint8_t data_len)
{
    uint8_t tx_buf[40];
    tx_buf[0] = HOST_SOF;
    tx_buf[1] = HOST_ID;
    tx_buf[2] = cmd;
    tx_buf[3] = data_len + 1; /* 错误码 + 数据 */
    tx_buf[4] = err;
    for (uint8_t i = 0; i < data_len; i++) {
        tx_buf[5 + i] = data[i];
    }
    uint8_t checksum = calc_checksum(HOST_ID, cmd, data_len + 1, &tx_buf[4], data_len + 1);
    tx_buf[5 + data_len] = checksum;
    if (k230_dev != RT_NULL) {
        rt_device_write(k230_dev, 0, tx_buf, 6 + data_len);
    }
}

static void process_valid_host_frame(uint8_t cmd, uint8_t len, const uint8_t *data)
{
    switch (cmd) {
        case APP_CMD_READ_FW_VERSION: {
            uint8_t reply[3] = {1, 0, 0};
            send_host_reply(cmd, APP_ERR_OK, reply, 3);
            break;
        }
        case APP_CMD_SET_SERVO_ANGLES: {
            if (len == 12 || len == 13) {
                uint16_t angles[APP_SERVO_COUNT];
                int offset = (len == 13) ? 1 : 0;
                for (int i = 0; i < APP_SERVO_COUNT; i++) {
                    angles[i] = (uint16_t)data[offset + i * 2] | ((uint16_t)data[offset + i * 2 + 1] << 8);
                }
                rt_kprintf("[K230 CMD] Set angles: %d, %d, %d, %d, %d, %d\n",
                           angles[0], angles[1], angles[2], angles[3], angles[4], angles[5]);
                uint8_t err = ServoBoardSetAnglesX10(angles, APP_SERVO_COUNT);
                send_host_reply(cmd, err, data, len);
            } else {
                send_host_reply(cmd, APP_ERR_FRAME, RT_NULL, 0);
            }
            break;
        }
        case APP_CMD_SET_SERVO_ANGLE: {
            if (len == 3) {
                uint8_t ch = data[0];
                uint16_t angle = (uint16_t)data[1] | ((uint16_t)data[2] << 8);
                rt_kprintf("[K230 CMD] Set angle logic_ch=%d, angle=%d\n", ch, angle);
                uint8_t err = ServoBoardSetAngleX10(ch, angle);
                send_host_reply(cmd, err, data, 3);
            } else {
                send_host_reply(cmd, APP_ERR_FRAME, RT_NULL, 0);
            }
            break;
        }
        case APP_CMD_PLAY_VOICE: {
            if (len == 1 || len == 2) {
                uint8_t voice_id = (len == 2) ? data[1] : data[0];
                rt_kprintf("[K230 CMD] Play voice ID: %d\n", voice_id);
                if (asr_dev != RT_NULL) {
                    char play_cmd[24];
                    rt_snprintf(play_cmd, sizeof(play_cmd), "PLAY:%d\r\n", 10000 + voice_id);
                    rt_device_write(asr_dev, 0, play_cmd, rt_strlen(play_cmd));
                }
                send_host_reply(cmd, APP_ERR_OK, data, len);
            } else {
                send_host_reply(cmd, APP_ERR_FRAME, RT_NULL, 0);
            }
            break;
        }
        case APP_CMD_ESTOP_ALL: {
            uint8_t err = ServoBoardEmergencyStop();
            send_host_reply(cmd, err, RT_NULL, 0);
            break;
        }
        case APP_CMD_RESTORE_DEFAULT_POSE: {
            uint8_t err = ServoBoardRestoreDefaultPose();
            send_host_reply(cmd, err, RT_NULL, 0);
            break;
        }
        default: {
            send_host_reply(cmd, APP_ERR_UNSUPPORTED, RT_NULL, 0);
            break;
        }
    }
}

static enum {
    STATE_SOF = 0,
    STATE_ID,
    STATE_CMD,
    STATE_LEN,
    STATE_DATA,
    STATE_CHKSUM
} parse_state = STATE_SOF;

static uint8_t rx_cmd;
static uint8_t rx_len;
static uint8_t rx_data[32];
static uint8_t rx_data_idx;
static uint8_t rx_chksum;

static void host_command_parse_char(uint8_t ch)
{
    switch (parse_state) {
        case STATE_SOF:
            if (ch == HOST_SOF) {
                parse_state = STATE_ID;
            }
            break;
        case STATE_ID:
            if (ch == HOST_ID) {
                parse_state = STATE_CMD;
            } else {
                parse_state = STATE_SOF;
            }
            break;
        case STATE_CMD:
            rx_cmd = ch;
            parse_state = STATE_LEN;
            break;
        case STATE_LEN:
            rx_len = ch;
            if (rx_len > 32) {
                parse_state = STATE_SOF;
            } else if (rx_len == 0) {
                parse_state = STATE_CHKSUM;
            } else {
                rx_data_idx = 0;
                parse_state = STATE_DATA;
            }
            break;
        case STATE_DATA:
            rx_data[rx_data_idx++] = ch;
            if (rx_data_idx >= rx_len) {
                parse_state = STATE_CHKSUM;
            }
            break;
        case STATE_CHKSUM:
            rx_chksum = ch;
            uint8_t expected = calc_checksum(HOST_ID, rx_cmd, rx_len, rx_data, rx_len);
            if (rx_chksum == expected) {
                process_valid_host_frame(rx_cmd, rx_len, rx_data);
            }
            parse_state = STATE_SOF;
            break;
    }
}

/* ------------------ RT-Thread 接收中断通知回调 ------------------ */

static rt_err_t k230_rx_ind(rt_device_t dev, rt_size_t size)
{
    rt_sem_release(&rx_sem_k230);
    return RT_EOK;
}

static rt_err_t asr_rx_ind(rt_device_t dev, rt_size_t size)
{
    rt_sem_release(&rx_sem_asr);
    return RT_EOK;
}

/* ------------------ RT-Thread 独立线程入口 ------------------ */

static void servo_thread_entry(void *parameter)
{
    rt_kprintf("[INFO] Servo board initialization...\n");
    if (ServoBoardInit()) {
        rt_kprintf("[INFO] Servo board initialization OK.\n");
    } else {
        rt_kprintf("[ERROR] Servo board initialization FAILED.\n");
    }

    while (1) {
        ServoBoardLoop();
        rt_thread_mdelay(10);
    }
}

static void k230_recv_entry(void *parameter)
{
    char ch;
    rt_kprintf("[INFO] K230 command thread started.\n");

    while (1) {
        while (rt_device_read(k230_dev, -1, &ch, 1) != 1) {
            rt_sem_take(&rx_sem_k230, RT_WAITING_FOREVER);
        }
        host_command_parse_char((uint8_t)ch);
    }
}

static void asr_recv_entry(void *parameter)
{
    char ch;
    static char asr_rx_buf[80];
    static int asr_rx_idx = 0;
    rt_kprintf("[INFO] ASR voice forwarder thread started.\n");

    while (1) {
        while (rt_device_read(asr_dev, -1, &ch, 1) != 1) {
            rt_sem_take(&rx_sem_asr, RT_WAITING_FOREVER);
        }
        /* 1. 直接无延迟透明转发接收到的字符到 K230 串口 */
        if (k230_dev != RT_NULL) {
            rt_device_write(k230_dev, 0, &ch, 1);
        }
        /* 2. 收集并打印到 MSH 调试口 */
        if (ch == '\n' || ch == '\r') {
            if (asr_rx_idx > 0) {
                asr_rx_buf[asr_rx_idx] = '\0';
                rt_kprintf("[ASR RXD] Line: %s\n", asr_rx_buf);
                asr_rx_idx = 0;
            }
        } else {
            if (asr_rx_idx < 79) {
                asr_rx_buf[asr_rx_idx++] = ch;
            } else {
                asr_rx_buf[asr_rx_idx] = '\0';
                rt_kprintf("[ASR RXD] Line: %s\n", asr_rx_buf);
                asr_rx_idx = 0;
                asr_rx_buf[asr_rx_idx++] = ch;
            }
        }
    }
}

/* ------------------ RT-Thread 自动初始化入口 ------------------ */

int servo_service_init(void)
{
    /* 1. 物理引脚时钟使能与 GPIOB 初始化（用于软件 I2C） */
    rcu_periph_clock_enable(RCU_GPIOB);
    
    gpio_init(PIN_PCA_OE_PORT, GPIO_MODE_OUT_PP, GPIO_OSPEED_50MHZ, PIN_PCA_OE);
    gpio_init(PIN_PCA_SCL_PORT, GPIO_MODE_OUT_OD, GPIO_OSPEED_50MHZ, PIN_PCA_SCL);
    gpio_init(PIN_PCA_SDA_PORT, GPIO_MODE_OUT_OD, GPIO_OSPEED_50MHZ, PIN_PCA_SDA);

    /* 2. 初始化接收信号量 */
    rt_sem_init(&rx_sem_k230, "rx_k230", 0, RT_IPC_FLAG_FIFO);
    rt_sem_init(&rx_sem_asr, "rx_asr", 0, RT_IPC_FLAG_FIFO);

    /* 3. 寻找并以 115200 速率初始化打开 K230 串口 uart2 */
    k230_dev = rt_device_find(K230_UART_NAME);
    if (k230_dev != RT_NULL) {
        struct serial_configure config = RT_SERIAL_CONFIG_DEFAULT;
        config.baud_rate = BAUD_RATE_115200;
        rt_device_control(k230_dev, RT_DEVICE_CTRL_CONFIG, &config);
        rt_device_open(k230_dev, RT_DEVICE_FLAG_RDWR | RT_DEVICE_FLAG_INT_RX);
        rt_device_set_rx_indicate(k230_dev, k230_rx_ind);
        rt_kprintf("[INFO] Opened K230 serial device %s successfully.\n", K230_UART_NAME);
    } else {
        rt_kprintf("[ERROR] Cannot find K230 serial device %s.\n", K230_UART_NAME);
    }

    /* 4. 寻找并以 115200 速率初始化打开天问串口 uart1 */
    asr_dev = rt_device_find(ASR_UART_NAME);
    if (asr_dev != RT_NULL) {
        struct serial_configure config = RT_SERIAL_CONFIG_DEFAULT;
        config.baud_rate = BAUD_RATE_115200;
        rt_device_control(asr_dev, RT_DEVICE_CTRL_CONFIG, &config);
        rt_device_open(asr_dev, RT_DEVICE_FLAG_RDWR | RT_DEVICE_FLAG_INT_RX);
        rt_device_set_rx_indicate(asr_dev, asr_rx_ind);
        rt_kprintf("[INFO] Opened ASR serial device %s successfully.\n", ASR_UART_NAME);
    } else {
        rt_kprintf("[ERROR] Cannot find ASR serial device %s.\n", ASR_UART_NAME);
    }

    /* 5. 创建平滑舵机刷新线程 */
    rt_thread_t th_servo = rt_thread_create("servo_ctrl",
                                            servo_thread_entry,
                                            RT_NULL,
                                            1024,
                                            15,
                                            10);
    if (th_servo != RT_NULL) {
        rt_thread_startup(th_servo);
    }

    /* 6. 创建 K230 接收处理线程 */
    if (k230_dev != RT_NULL) {
        rt_thread_t th_k230 = rt_thread_create("k230_rx",
                                               k230_recv_entry,
                                               RT_NULL,
                                               1024,
                                               16,
                                               10);
        if (th_k230 != RT_NULL) {
            rt_thread_startup(th_k230);
        }
    }

    /* 7. 创建天问透传中转线程 */
    if (asr_dev != RT_NULL && k230_dev != RT_NULL) {
        rt_thread_t th_asr = rt_thread_create("asr_rx",
                                              asr_recv_entry,
                                              RT_NULL,
                                              1024,
                                              17,
                                              10);
        if (th_asr != RT_NULL) {
            rt_thread_startup(th_asr);
        }
    }

    return 0;
}

/* ------------------ MSH 调试与校准指令 ------------------ */

static int parse_angle_x10(const char *str)
{
    int integer_part = 0;
    int fractional_part = 0;
    int has_dot = 0;
    int fractional_digits = 0;
    
    while (*str)
    {
        if (*str == '.')
        {
            has_dot = 1;
            str++;
            continue;
        }
        if (*str >= '0' && *str <= '9')
        {
            if (!has_dot)
            {
                integer_part = integer_part * 10 + (*str - '0');
            }
            else if (fractional_digits < 1)
            {
                fractional_part = *str - '0';
                fractional_digits++;
            }
        }
        else
        {
            break;
        }
        str++;
    }
    return integer_part * 10 + fractional_part;
}

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
        rt_kprintf("Example: servo_set 4 120    (sets Left Eye Eyelid to 120.0 deg)\n");
        rt_kprintf("\nCurrent Servo Angles & Pin Mapping:\n");
        for (int i = 0; i < APP_SERVO_COUNT; i++)
        {
            rt_kprintf("  Channel %d [%s]: Current = %d.%d deg, Target = %d.%d deg\n",
                       i, g_servo_names[i],
                       gu16ServoCurrentAngleX10[i] / 10, gu16ServoCurrentAngleX10[i] % 10,
                       gu16ServoTargetAngleX10[i] / 10, gu16ServoTargetAngleX10[i] % 10);
        }
        return;
    }
    
    int ch = atoi(argv[1]);
    if (ch < 0 || ch >= APP_SERVO_COUNT)
    {
        rt_kprintf("Error: channel must be between 0 and %d\n", APP_SERVO_COUNT - 1);
        return;
    }
    
    int angle_x10 = parse_angle_x10(argv[2]);
    
    if (angle_x10 < APP_SERVO_MIN_ANGLE_DEG_X10 || angle_x10 > APP_SERVO_MAX_ANGLE_DEG_X10)
    {
        rt_kprintf("Error: angle must be between %d.%d and %d.%d degrees\n",
                   APP_SERVO_MIN_ANGLE_DEG_X10 / 10, APP_SERVO_MIN_ANGLE_DEG_X10 % 10,
                   APP_SERVO_MAX_ANGLE_DEG_X10 / 10, APP_SERVO_MAX_ANGLE_DEG_X10 % 10);
        return;
    }
    
    uint8_t err = ServoBoardSetAngleX10((uint8_t)ch, (uint16_t)angle_x10);
    if (err == APP_ERR_OK)
    {
        rt_kprintf("Success: Set channel %d [%s] to %d.%d degrees (%d)\n", ch, g_servo_names[ch], angle_x10 / 10, angle_x10 % 10, angle_x10);
    }
    else
    {
        rt_kprintf("Error: Failed to set angle, error code %d\n", err);
    }
}
MSH_CMD_EXPORT(servo_set, Set individual servo angle: servo_set <ch> <deg>);

