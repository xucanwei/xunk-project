'''
Demo: Bionic Eye Interactive Gaming System (YuNet based)
Platform: 01Studio CanMV K230 (Synchronized Menu UI, Eye Evasion Game & Debug Backdoor)
'''
import os, sys, ujson, gc, math, random, time, _thread

# 异常日志记录，以防板子启动闪退
try:
    # 1. 导入 display 模块
    import media.display

    # 2. 导入其余模块
    from libs.PipeLine import PipeLine
    from media.display import *
    from libs.AIBase import AIBase
    from libs.AI2D import Ai2d
    from libs.Utils import *
    from media.media import *
    import nncase_runtime as nn
    import ulab.numpy as np
    import image
    import aidemo
    from machine import FPIOA, UART
except Exception as e:
    with open("/sdcard/error.log", "w") as f:
        try:
            import traceback
            traceback.print_exception(e, f)
        except:
            f.write(repr(e))
    raise e

# ==============================================================================
# 【全局运行与显示配置参数】
USE_CANMV = False              # 是否启用 CanMV IDE 虚拟摄像头与显示屏测试 (True: 开启虚拟测试, False: 物理屏)

DISPLAY_ROTATION_MODE = 0      # 屏幕方向 (0: 正常横屏/HDMI, 1: 旋转180度, 2: 旋转90度, 3: 旋转270度)
DISPLAY_MIRROR_MODE = 0        # 屏幕镜像 (0: 无镜像, 1: 左右镜面翻转/水平镜像, 2: 上下镜面翻转/垂直镜像)
SENSOR_HMIRROR = True          # 摄像头水平镜像
SENSOR_VFLIP = False           # 摄像头垂直翻转

# OSD 绘图坐标镜像配置
OSD_MIRROR_X = True            # OSD 左右镜像 (HDMI 0度屏开启左右镜像，与水平镜像摄像头视频精准叠合)
OSD_MIRROR_Y = False           # OSD 上下镜像 (HDMI 0度屏关闭上下镜像，使往上框在上、往下框在下)

DISPLAY_WIDTH = 1024
DISPLAY_HEIGHT = 600
RGB888P_SIZE = [1024, 600]     # 摄像头给AI的采集分辨率
# ==============================================================================

# 【调试后门控制标志位】(若当前没有触摸屏，可通过在此处修改变量切换模式)
# 0: 主菜单 (正常启用屏幕触控交互)
# 1: 强行直接进入 - 瞄准跟随模式
# 2: 强行直接进入 - 对视挑战模式
# 3: 强行直接进入 - 视线躲避模式
BACKDOOR_MODE = 0
# ==============================================================================

# 【动态人脸距离/框大小分档追踪配置】
DIST_FAR_LIMIT = 120           # 远距离分界线
DIST_NEAR_LIMIT = 240          # 近距离分界线

GAIN_FAR = 0.6                 # 远档灵敏度增益乘数
GAIN_MEDIUM = 1.0              # 中档灵敏度增益乘数
GAIN_NEAR = 1.5                # 近档灵敏度增益乘数
# ==============================================================================

# 【游戏模式代号】
MODE_FOLLOW = 0                # 瞄准跟随模式
MODE_STARING = 1               # 对视持久战模式
MODE_GAZE = 2                  # 视线躲避战模式

# 【舵机与控制逻辑参数】
# Channel 0: 左眼水平偏转 (Left Eye Yaw)
# 各通道极限值与居中定义 (第一人称视角):
# Channel 0: 左右移动 (110° 正中间, 60° 看向最右边, 160° 看最左边)
# Channel 1: 上下移动 (85° 正中间, 100° 看最上面, 70° 看最下面)
# Channel 2: 左眼上眼皮 (60° 打开, 100° 闭合)
# Channel 3: 左眼下眼皮 (100° 打开, 60° 闭合)
# Channel 4: 右眼上眼皮 (110° 打开, 60° 闭合)
# Channel 5: 右眼下眼皮 (80° 打开, 110° 闭合)
SERVO_MIN_DEG = [60.0, 70.0, 60.0, 60.0, 60.0, 80.0]
SERVO_MAX_DEG = [160.0, 100.0, 100.0, 100.0, 110.0, 110.0]
SERVO_DEFAULT_DEG = [110.0, 85.0, 100.0, 60.0, 60.0, 110.0] # 闭合/居中基准
SERVO_OPEN_DEG = [110.0, 85.0, 60.0, 100.0, 110.0, 80.0]    # 全打开基准

# 舵机运动方向反向标志
YAW_REVERSE = False             # 水平偏转方向反向
PITCH_REVERSE = False           # 垂直偏转方向反向

# 水平偏置修正 (以 90° 为对称中位)
YAW_CENTER_OFFSET = 0.0

# 追踪灵敏度 (基础映射系数)
YAW_SENSITIVITY = 140.0        # 归一化偏差 [-0.5, 0.5] 乘以该系数映射为舵机偏转角
PITCH_SENSITIVITY = 110.0      # 垂直灵敏度

# 平滑滤波因子 (0.01 ~ 1.0, 越小动作越平滑平缓，防止舵机抖动)
TRACKING_ALPHA_YAW = 0.35
TRACKING_ALPHA_PITCH = 0.35

# 寻人待机扫视参数
SCAN_YAW_RANGE = 28            # 左右扫视角度范围
SCAN_SPEED = 2.0               # 扫视速度因子
# 自动随机眨眼时间间隔限制 (单位: 秒)
BLINK_INTERVAL_MIN = 3.0       # 眨眼最小间隔时间
BLINK_INTERVAL_MAX = 8.0       # 眨眼最大间隔时间
# ==============================================================================

# 【系统24小时定时自动软重启维护配置】
AUTO_REBOOT_ENABLE = True         # 是否启用定时自动软重启 (长期无人值守防内存碎片/硬件死锁)
AUTO_REBOOT_HOURS = 24            # 自动重启周期 (小时, 支持小数如 0.01 供快速测试)
AUTO_REBOOT_ONLY_IDLE = True      # 仅在主菜单/空闲状态下重启 (若处于游戏中，等待返回主菜单或连续 30 秒无人脸后重启；最多宽限 1 小时)
# ==============================================================================

# 【厂测老化模式配置】
FACTORY_MAX_REBOOTS = 1000           # 厂测老化总软重启次数 (默认 50 次)
FACTORY_GAME_DURATION_SEC = 20     # 每个游戏老化运行时间 (秒, 3个游戏一轮共约 60 秒后触发 1 次软重启)
FACTORY_TEST_FILE = "/sdcard/factory_test.json" # 厂测持久化状态记录文件
# ==============================================================================

# 串口与控制配置 (UART3 Pin28 TX, Pin29 RX 专用高速直连通道)
FOLLOW_UART_PORT = 3
FOLLOW_UART_BAUDRATE = 115200
FOLLOW_UART_SEND_INTERVAL_MS = 20
FOLLOW_UART_MIN_DELTA_DEG = 1
FOLLOW_UART_TX_PIN = 28
FOLLOW_UART_RX_PIN = 29

# 触摸板互斥锁
touch_lock = _thread.allocate_lock()


# ----------------------------------------------------------------------
# 【与机械手 100% 对应一致的 OSD 界面缩放渲染辅助工具函数】
def scale_x(value):
    return int(value * DISPLAY_WIDTH / 640)

def scale_y(value):
    return int(value * DISPLAY_HEIGHT / 480)

def scale_px(value):
    return int(value * DISPLAY_WIDTH / 640)

def scale_rect(rect):
    return (scale_x(rect[0]), scale_y(rect[1]), scale_x(rect[2]), scale_y(rect[3]))

def fill_rect(img, x, y, w, h, color, step=2):
    img.draw_rectangle(x, y, w, h, color=color, fill=True)

def draw_gradient_bg(img, x, y, w, h, col1, col2, step=6):
    r1, g1, b1 = col1[1], col1[2], col1[3]
    r2, g2, b2 = col2[1], col2[2], col2[3]
    for yy in range(y, y+h, step):
        t = (yy - y) / h
        r = int(r1 * (1.0 - t) + r2 * t)
        g = int(g1 * (1.0 - t) + g2 * t)
        b = int(b1 * (1.0 - t) + b2 * t)
        img.draw_line(x, yy, x+w, yy, color=(255, r, g, b), thickness=step)

def draw_bold_string(img, x, y, size, text, color):
    img.draw_string_advanced(x, y, size, text, color=color)
    img.draw_string_advanced(x + 1, y, size, text, color=color)
    img.draw_string_advanced(x, y + 1, size, text, color=color)
    img.draw_string_advanced(x + 1, y + 1, size, text, color=color)

def draw_panel(img, x, y, w, h, border=(255,90,90,90), bg=(255,20,20,20)):
    if bg[0] == 255:
        fill_rect(img, x+2, y+2, w, h, (255,8,8,8), 3)
    fill_rect(img, x, y, w, h, bg, 3)
    img.draw_rectangle(x, y, w, h, color=border, thickness=scale_px(2))

def draw_flat_panel(img, x, y, w, h, border=(255,90,90,90), bg=(255,20,20,20)):
    fill_rect(img, x, y, w, h, bg, 3)
    img.draw_rectangle(x, y, w, h, color=border, thickness=scale_px(1))

def draw_progress_bar(img, x, y, w, h, value, color):
    img.draw_rectangle(x, y, w, h, color=(255,85,85,85), thickness=scale_px(1))
    fill_w = int((w-4) * max(0.0, min(1.0, value)))
    if fill_w > 0:
        fill_rect(img, x+2, y+2, fill_w, h-4, color, 2)

def draw_countdown_meter(img, x, y, w, h, remain_ms, total_ms):
    if total_ms <= 0: return
    value = remain_ms / total_ms
    draw_progress_bar(img, x, y, w, h, value, (255, 255, 210, 40))
    sec = int((remain_ms + 999) // 1000)
    img.draw_string_advanced(x+w+scale_x(8), y-scale_y(6), scale_px(22), "%d" % sec, color=(255, 255, 210, 40))
# ----------------------------------------------------------------------


# 舵机角度平滑滤波器
class SmoothFilter:
    def __init__(self, alpha=0.15):
        self.alpha = alpha
        self.current_val = None

    def update(self, target_val):
        if self.current_val is None:
            self.current_val = target_val
        else:
            self.current_val = self.alpha * target_val + (1.0 - self.alpha) * self.current_val
        return self.current_val


# ----------------------------------------------------------------------
# 【6 通道舵机运动学平滑与防顿挫滤波器】
class ServoMotionFilter:
    """
    6 通道全局舵机平滑运动滤波器：
    以仿生平滑速率插值所有通道，彻底杜绝模式切换、开局、结算与眨眼时的任何阶跃与机械顿挫。
    """
    def __init__(self, init_angles=None):
        if init_angles is None:
            init_angles = SERVO_DEFAULT_DEG
        # 当前 6 通道实际输出角度 (预分配列表，零内存申请)
        self.current = [float(a) for a in init_angles]
        self.last_ms = time.ticks_ms()
        # 各通道角速度上限 (度/秒)
        # CH0 (Yaw 左右): 240°/s
        # CH1 (Pitch 上下): 180°/s
        # CH2~5 (眼皮开闭): 300°/s (确保 120ms 自然眨眼不失真，同时将 0ms 突变限制为优雅的 150~200ms 平滑开闭)
        self.max_speed = [240.0, 180.0, 300.0, 300.0, 300.0, 300.0]

    def reset_to(self, angles):
        for i in range(6):
            self.current[i] = float(angles[i])
        self.last_ms = time.ticks_ms()

    def update(self, target_angles):
        now = time.ticks_ms()
        dt_s = time.ticks_diff(now, self.last_ms) / 1000.0
        self.last_ms = now

        if dt_s <= 0.001:
            dt_s = 0.001
        elif dt_s > 0.05:
            dt_s = 0.05  # 限制单帧最大时间增量，防止系统 GC 或阻塞后瞬间大步跳跃

        for i in range(6):
            target = float(target_angles[i])
            diff = target - self.current[i]
            max_step = self.max_speed[i] * dt_s
            if abs(diff) <= max_step:
                self.current[i] = target
            elif diff > 0:
                self.current[i] += max_step
            else:
                self.current[i] -= max_step

        return self.current


# 自动随机眨眼控制器（非阻塞状态机）
class BlinkController:
    def __init__(self, close_angle=30, open_angle=90):
        self.state = 0  # 0: 正常睁眼, 1: 正在眨眼
        self.next_blink_time = time.ticks_ms() + random.randint(int(BLINK_INTERVAL_MIN * 1000), int(BLINK_INTERVAL_MAX * 1000))
        self.blink_start_time = 0
        self.blink_duration_ms = 260 # 眨眼总时长 260ms

    def reset(self):
        """重置眨眼状态至正常睁眼，确保新开局或模式切换时不出现突发眨眼"""
        self.state = 0
        self.next_blink_time = time.ticks_ms() + random.randint(int(BLINK_INTERVAL_MIN * 1000), int(BLINK_INTERVAL_MAX * 1000))

    def update(self):
        now = time.ticks_ms()
        if self.state == 0:
            if time.ticks_diff(now, self.next_blink_time) >= 0:
                self.state = 1
                self.blink_start_time = now
                self.next_blink_time = now + random.randint(int(BLINK_INTERVAL_MIN * 1000), int(BLINK_INTERVAL_MAX * 1000))
            else:
                return 1.0, 1.0  # 完全睁眼注视

        if self.state == 1:
            dt = time.ticks_diff(now, self.blink_start_time)
            if dt >= self.blink_duration_ms:
                self.state = 0
                return 1.0, 1.0
            # 拟人自然平滑眨眼曲线: 前 110ms 快速合拢 (1.0 -> 0.0), 后 150ms 平滑睁开 (0.0 -> 1.0)
            if dt < 110:
                ratio = 1.0 - (dt / 110.0)
            else:
                ratio = (dt - 110.0) / 150.0
            ratio = max(0.0, min(1.0, ratio))
            return ratio, ratio


# 仿生眼球专用串口控制器 (专一定向 Pin 28 TX / Pin 29 RX，全双工零内存抖动架构)
class EyeMechanismController:
    def __init__(self, enable=True, port=3, baudrate=115200, device_id=0x5A, cmd_set_angles=0x11, send_interval_ms=8, min_delta_deg=1, tx_pin=28, rx_pin=29):
        self.enable = enable
        self.port = port
        self.baudrate = baudrate
        self.device_id = device_id
        self.cmd_set_angles = cmd_set_angles
        self.send_interval_ms = send_interval_ms
        self.min_delta_deg = min_delta_deg
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        self.last_servo = [-1000] * 6
        self.last_send_ms = None
        self.uart = None
        self.tx_frames = 0
        self.ready = False
        self.rx_buffer = ""
        self.last_voice_play_ms = time.ticks_ms() - 3000
        self.last_voice_19_ms = time.ticks_ms() - 6000
        self.last_wake_ms = 0
        # 预分配 17 字节固定发送帧缓冲区，零内存申请，彻底杜绝 MicroPython GC 顿挫！
        self._frame_buf = bytearray(17)
        self._frame_buf[0] = 0xAA
        self._frame_buf[1] = self.device_id
        self._frame_buf[2] = self.cmd_set_angles
        self._frame_buf[3] = 12
        if self.enable:
            self._ensure_uart()

    def _init_uart(self):
        try:
            fpioa = FPIOA()
            fpioa.set_function(self.tx_pin, FPIOA.UART3_TXD)
            fpioa.set_function(self.rx_pin, FPIOA.UART3_RXD)
            u_id = getattr(UART, 'UART%d' % self.port) if hasattr(UART, 'UART%d' % self.port) else self.port
            self.uart = UART(u_id, self.baudrate)
            self.ready = True
            print("[INFO] EyeController: UART%d (Pin %d TX / Pin %d RX) 就绪" % (self.port, self.tx_pin, self.rx_pin))
        except Exception as e:
            print("[WARN] EyeController: UART%d init failed: %s" % (self.port, e))
            self.uart = None
            self.ready = False

    def _ensure_uart(self):
        if self.ready and self.uart is not None:
            return True
        self._init_uart()
        return self.ready

    def _ensure_uarts(self):
        return self._ensure_uart()

    def _checksum(self, data):
        cs = 0
        for b in data:
            cs ^= b
        return cs

    def update(self, servo_angles):
        if not self.enable:
            return
        if not self._ensure_uart():
            return

        now = time.ticks_ms()
        if self.last_send_ms is not None and time.ticks_diff(now, self.last_send_ms) < self.send_interval_ms:
            return

        buf = self._frame_buf
        cs = 0x5A ^ 0x11 ^ 12
        for channel in range(6):
            angle_x10 = int(round(servo_angles[channel] * 10))
            if angle_x10 < 0:
                angle_x10 = 0
            elif angle_x10 > 1800:
                angle_x10 = 1800
            idx = 4 + channel * 2
            low = angle_x10 & 0xFF
            high = (angle_x10 >> 8) & 0xFF
            buf[idx] = low
            buf[idx + 1] = high
            cs ^= low ^ high
        buf[16] = cs & 0xFF

        try:
            self.uart.write(buf)
            self.last_servo = [int(round(angle)) for angle in servo_angles]
            self.tx_frames += 1
            self.last_send_ms = now
        except Exception as e:
            pass

    def play_voice(self, voice_id):
        now = time.ticks_ms()

        # 针对语音 ID 19 (打卡成功) 设置 5 秒保护期，5 秒内最多播报 1 次
        if voice_id == 19:
            if hasattr(self, "last_voice_19_ms") and time.ticks_diff(now, self.last_voice_19_ms) < 5000:
                print("[VOICE] Success voice (19) suppressed (5s protection cooldown active)")
                return
            self.last_voice_19_ms = now

        # 用户操作指令/模式切换/主菜单/结算高优先级语音 (10:返回菜单, 11~13:模式, 21~22:结算, 90+:音量) 强制优先播报
        is_high_priority = (voice_id in (10, 11, 12, 13, 21, 22) or voice_id >= 90)

        # 当在“你好大眼”唤醒后的 8 秒指令等待窗口期内，拦截所有低优先级背景音 (14:没找到你, 15:找到了你)，确保用户的后续指令流畅识别不被顶掉
        if not is_high_priority:
            if hasattr(self, "last_wake_ms") and self.last_wake_ms > 0:
                if time.ticks_diff(now, self.last_wake_ms) < 8000:
                    print("[VOICE] Non-priority voice %d suppressed (8s wake window active)" % voice_id)
                    return

            if hasattr(self, "last_voice_play_ms") and time.ticks_diff(now, self.last_voice_play_ms) < 2000:
                print("[VOICE] Non-priority voice %d suppressed to prevent audio queue lag" % voice_id)
                return

        self.last_voice_play_ms = now

        if not self._ensure_uart():
            return
        payload = bytearray(5)
        payload[0] = self.device_id
        payload[1] = 0x20
        payload[2] = 1
        payload[3] = voice_id
        payload[4] = self._checksum(payload[:-1])

        frame = bytearray(6)
        frame[0] = 0xAA
        for i in range(5):
            frame[i+1] = payload[i]

        try:
            self.uart.write(bytes(frame))
            print("[VOICE] Sent play command for voice ID: %d" % voice_id)
        except Exception as e:
            pass

    def read_command(self, buttons=None):
        if not self._ensure_uart():
            return None

        # 1. 专一从 UART3 (Pin 29 RX) 硬件 FIFO 读取新数据
        try:
            if self.uart.any():
                data = self.uart.read()
                if data:
                    try:
                        decoded_str = data.decode('utf-8', 'ignore')
                    except:
                        decoded_str = str(data)

                    self.rx_buffer += decoded_str
                    self.rx_buffer = self.rx_buffer.replace('\r', '\n')
        except Exception as e:
            pass

        if not self.rx_buffer:
            return None

        # 2. 如果缓冲区无换行且超长，防溢出清空
        if '\n' not in self.rx_buffer:
            if len(self.rx_buffer) > 256:
                self.rx_buffer = ""
            return None

        # 3. 逐行提取完整协议数据包，未接收完毕的半行保留在缓冲区
        lines = self.rx_buffer.split('\n')
        self.rx_buffer = lines[-1]
        complete_lines = lines[:-1]

        voice_action = None
        for line in complete_lines:
            line_str = line.strip()
            if not line_str:
                continue
            line_upper = line_str.upper()

            # A. 触摸坐标数据包 (TOUCH:<x>,<y>,<event>)
            if line_upper.startswith("TOUCH:"):
                parts = line_str[6:].split(',')
                if len(parts) >= 3 and buttons is not None:
                    try:
                        tx = int(parts[0])
                        ty = int(parts[1])
                        tevent = parts[2].strip().upper()
                        with touch_lock:
                            buttons.pending_events.append(TouchPoint(tx, ty, tevent))
                    except Exception as e:
                        print("[WARN] Touch coordinate parse error:", e)

            # B. 语音指令数据包 (CMD:<action>)
            elif "CMD:" in line_upper:
                if any(k in line_upper for k in ("CMD:WAKE", "CMD: WAKE", "CMD:HI", "CMD: HI", "CMD:HELLO", "CMD: HELLO", "CMD:NIHAO", "CMD: NIHAO")):
                    voice_action = ("wake", None)
                    self.last_wake_ms = time.ticks_ms()
                elif "CMD:FOLLOW" in line_upper or "CMD: FOLLOW" in line_upper:
                    voice_action = ("mode", MODE_FOLLOW)
                elif "CMD:MIMIC" in line_upper or "CMD: MIMIC" in line_upper:
                    voice_action = ("mode", MODE_STARING)
                elif "CMD:RPS" in line_upper or "CMD: RPS" in line_upper:
                    voice_action = ("mode", MODE_GAZE)
                elif "CMD:MENU" in line_upper or "CMD: MENU" in line_upper:
                    voice_action = ("menu", None)
                elif "CMD:RESTART" in line_upper or "CMD: RESTART" in line_upper:
                    voice_action = ("restart", None)
                elif any(k in line_upper for k in ("CMD:FACTORY", "CMD: FACTORY", "CMD:AGING", "CMD: AGING", "CMD:BURNIN", "CMD: BURNIN")):
                    voice_action = ("factory_test", None)
                if voice_action is not None:
                    print("[UART RXD] Voice command matched:", voice_action)

        return voice_action


# 触摸点坐标定义
class TouchPoint:
    def __init__(self, x, y, event):
        self.x = x
        self.y = y
        self.event = event


# 触摸屏与UI菜单组件 (一行一行横条分布)
class TouchButtons:
    def __init__(self):
        self.enabled = True
        self.pending_events = []
        self.last_press_ms = 0

        # 3 个游戏模式长条卡片 (X, Y, W, H, mode, dummy, title_zh, dummy2, desc_zh)
        self.menu_cards = (
            (120, 200, 780, 75, MODE_FOLLOW, "", "视线跟随", "", "物理眼球实时跟随人脸注视与移动"),
            (120, 305, 780, 75, MODE_STARING, "", "木头人模式", "", "123木头人！红灯绝对静止，绿灯可以活动"),
            (120, 410, 780, 75, MODE_GAZE, "", "大眼躲避球", "", "移动人脸框躲避屏幕上运动的眼球")
        )

        # 底部返回与重启菜单按钮 (尺寸与位置完全同步机械手 100% 对齐)
        self.menu_button = (20, 535, 120, 45, "返回菜单")
        self.restart_button = (884, 535, 120, 45, "重新开始")

        # 音量控制状态 (范围 1~7)
        self.volume = 5
        self.vol_button = (844, 535, 160, 45)

        # 厂测模式长按进入状态追踪 (连续点击音量键3次，第3次长按超过5秒)
        self.vol_click_count = 0        # 连续点击次数
        self.vol_last_click_time = 0    # 上次点击抬起时间戳
        self.vol_press_down_time = 0    # 当前按下开始时间戳
        self.vol_is_down = False        # 手指当前是否正按在音量键上
        self.vol_triggered_factory = False # 本次长按是否已触发厂测

        # 尝试加载自定义菜单背景图片
        self.menu_bg_img = None
        paths_to_try = [
            "/sdcard/data/images/menu_bg_1024.bmp",
            "/sdcard/data/image/menu_bg_1024.bmp",
            "/sdcard/CanMV/data/images/menu_bg_1024.bmp",
            "/sdcard/CanMV/data/image/menu_bg_1024.bmp",
            "/sdcard/canmv/data/images/menu_bg_1024.bmp",
            "/sdcard/canmv/data/image/menu_bg_1024.bmp"
        ]
        for p in paths_to_try:
            try:
                self.menu_bg_img = image.Image(p)
                print("[SYSTEM] Custom menu background image loaded successfully from:", p)
                break
            except Exception as e:
                print("[DEBUG] Failed loading menu_bg from %s: %s" % (p, repr(e)))
        if self.menu_bg_img is None:
            print("[WARN] Failed to load custom menu background image from standard paths.")

    def _read_points(self):
        with touch_lock:
            events = []
            for pt in self.pending_events:
                if DISPLAY_ROTATION_MODE == 1:
                    rx = 1024 - 1 - pt.x
                    ry = 600 - 1 - pt.y
                else:
                    rx = pt.x
                    ry = pt.y
                events.append(TouchPoint(rx, ry, pt.event))
            self.pending_events.clear()
            return tuple(events)

    def read_action(self, in_menu):
        if not self.enabled:
            return None
        now = time.ticks_ms()

        # 1. 厂测模式持续长按检测 (即使无新触控坐标上报，手指按住时间到达 5 秒立即响应)
        if self.vol_is_down and not self.vol_triggered_factory:
            held_ms = time.ticks_diff(now, self.vol_press_down_time)
            # 连续点击满 2 次，且当前第 3 次（或以上）按住超过 5000 毫秒
            if self.vol_click_count >= 2:
                # 动态刷新音量按钮提示 "厂测: Xs/5s"
                if in_menu and self.menu_bg_img is not None:
                    held_s = held_ms // 1000
                    self.draw_volume_button(self.menu_bg_img, custom_text="厂测: %ds/5s" % min(5, held_s + 1))
                if held_ms >= 5000:
                    self.vol_triggered_factory = True
                    self.vol_click_count = 0
                    self.vol_is_down = False
                    if in_menu and self.menu_bg_img is not None:
                        self.draw_volume_button(self.menu_bg_img, custom_text="进入厂测!")
                    print("\n[FACTORY] ★★★ 连续点击音量键3次且长按超5秒！进入厂测老化模式 ★★★")
                    return ("factory_test", None)

        points = self._read_points()
        if not len(points):
            return None

        vx, vy, vw, vh = self.vol_button

        # 2. 检查触摸点对音量键的操作 (处理 DOWN, MOVE, UP)
        for p in points:
            in_vol = (p.x >= vx and p.x <= vx + vw and p.y >= vy and p.y <= vy + vh)
            if p.event == "DOWN":
                if in_vol:
                    self.vol_is_down = True
                    self.vol_press_down_time = now
                    self.vol_triggered_factory = False
                    # 若距离上次点击超过 1500ms，重置前序点击计数
                    if time.ticks_diff(now, self.vol_last_click_time) > 1500:
                        self.vol_click_count = 0
            elif p.event == "MOVE":
                if not in_vol and self.vol_is_down:
                    self.vol_is_down = False
                    if in_menu and self.menu_bg_img is not None:
                        self.draw_volume_button(self.menu_bg_img)
            elif p.event == "UP":
                if self.vol_is_down:
                    self.vol_is_down = False
                    press_duration = time.ticks_diff(now, self.vol_press_down_time)
                    if not self.vol_triggered_factory:
                        if press_duration < 800:
                            # 短促点击
                            self.vol_click_count += 1
                            self.vol_last_click_time = now
                            print("[VOL] 音量键短按点击，连续点击计数: %d (第3次长按5秒可进厂测)" % self.vol_click_count)
                            # 正常音量切换 (1, 3, 5, 7)
                            if in_menu:
                                self.last_press_ms = now
                                if self.volume == 1: self.volume = 3
                                elif self.volume == 3: self.volume = 5
                                elif self.volume == 5: self.volume = 7
                                else: self.volume = 1
                                if self.menu_bg_img is not None:
                                    self.draw_volume_button(self.menu_bg_img)
                                return ("volume", self.volume)
                        else:
                            # 超过800ms但不足5000ms松手，重置按钮显示
                            if in_menu and self.menu_bg_img is not None:
                                self.draw_volume_button(self.menu_bg_img)

        # 3. 常规按键防抖过滤
        if time.ticks_diff(now, self.last_press_ms) < 350:
            return None

        pt = None
        for p in points:
            if p.event in ("DOWN", "MOVE"):
                pt = p
                break
        if pt is None:
            return None

        if in_menu:
            for b in self.menu_cards:
                x, y, w, h, mode, _, _, _, _ = b
                if pt.x >= x and pt.x <= x+w and pt.y >= y and pt.y <= y+h:
                    self.last_press_ms = now
                    return ("mode", mode)
            return None

        # 在非菜单（游戏模式）下：
        # 1. 大幅扩充左下角“返回菜单”按键的触控响应热区 (X: 0 ~ 280, Y: 450 ~ 600)，极大提升触控返回灵敏度
        if pt.x <= 280 and pt.y >= 450:
            self.last_press_ms = now
            return ("menu", None)

        # 2. 大幅扩充右下角“重新开始”按键的触控响应热区 (X: 744 ~ 1024, Y: 450 ~ 600)
        if pt.x >= 744 and pt.y >= 450:
            self.last_press_ms = now
            return ("restart", None)

        return None

    def prepare_menu(self):
        if self.menu_bg_img is not None:
            # 1. 顶部主面板标题 (使用极富科技感的暗板灰色实色替代半透明，以确保 100% 稳定防死机)
            self.menu_bg_img.draw_rectangle(205, 25, 614, 75, color=(30, 34, 42), fill=True)
            self.menu_bg_img.draw_rectangle(205, 25, 614, 75, color=(100, 160, 220), thickness=1)
            self.menu_bg_img.draw_string_advanced(379, 43, 38, "AI互动眼球系统", color=(255, 255, 255))

            # 2. 中间提示引导字 (实色暗板灰 + 细线边框 + 炫酷橙黄文字)
            self.menu_bg_img.draw_rectangle(300, 142, 424, 40, color=(30, 34, 42), fill=True)
            self.menu_bg_img.draw_rectangle(300, 142, 424, 40, color=(100, 160, 220), thickness=1)
            self.menu_bg_img.draw_string_advanced(343, 150, 26, "请说出或点击想体验的模式吧", color=(255, 215, 0))

            # 3. 一行一行绘制长条卡片菜单 (实色衬底 + 细线边框 + 文字)
            for b in self.menu_cards:
                x, y, w, h, mode, _, title_zh, _, desc_zh = b

                if mode == MODE_FOLLOW:
                    border = (0, 180, 70)       # 3-tuple 绿色调
                elif mode == MODE_STARING:
                    border = (80, 160, 220)     # 3-tuple 蓝色调
                else:
                    border = (230, 150, 0)      # 3-tuple 橙色调

                # 绘制整条卡片的实色暗板灰衬底
                self.menu_bg_img.draw_rectangle(x, y, 780, h, color=(30, 34, 42), fill=True)
                # 绘制细线边框 (必须使用 3-tuple 颜色在 RGB565 画布上绘制，否则会抛出 TypeError)
                self.menu_bg_img.draw_rectangle(x, y, 780, h, color=border, thickness=1)

                # 绘制左侧的模式标题文字 (白色 3-tuple)
                draw_bold_string(self.menu_bg_img, x + 42, y + 25, 24, title_zh, color=(255, 255, 255))

                # 绘制右侧的长条模式描述文字 (浅灰蓝色 3-tuple)
                self.menu_bg_img.draw_string_advanced(x + 225, y + 28, 18, desc_zh, color=(210, 225, 235))

                # 右端提示箭头 (使用 border 3-tuple 颜色)
                self.menu_bg_img.draw_string_advanced(x + 745, y + 28, 18, ">", color=border)

            # 绘制右下角音量控制按钮 (实色)
            self.draw_volume_button(self.menu_bg_img)

    def draw_volume_button(self, img, custom_text=None):
        x, y, w, h = self.vol_button
        # 1. 绘制暗 slate-dark 的实色小块作为毛玻璃底色
        img.draw_rectangle(x, y, w, h, color=(25, 30, 38), fill=True)
        # 2. 绘制亮蓝色细边框 (使用 3-tuple 颜色在 RGB565 画布上绘制，否则会抛出 TypeError)
        border_col = (255, 140, 0) if custom_text else (80, 160, 220)
        img.draw_rectangle(x, y, w, h, color=border_col, thickness=1)
        # 3. 绘制当前音量状态文字 (居中，使用 3-tuple 颜色)
        vol_str = custom_text if custom_text else ("音量: %d" % self.volume)
        text_x = x + 15 if custom_text else (x + 35)
        text_col = (255, 200, 50) if custom_text else (255, 255, 255)
        img.draw_string_advanced(text_x, y + 10, 20, vol_str, color=text_col)

    def draw_menu(self, img):
        # 1. 绘制背景图或渐变色 (先填充不透明底色，防止无 Alpha 的 BMP 图像变为透明)
        fill_rect(img, 0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, (255, 0, 0, 0), 4)
        if self.menu_bg_img is not None:
            try:
                img.draw_image(self.menu_bg_img, 0, 0, x_scale=3.2, y_scale=3.2, alpha=255)
            except Exception as e:
                draw_gradient_bg(img, 0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, (255, 225, 240, 255), (255, 185, 215, 255), step=6)
        else:
            draw_gradient_bg(img, 0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, (255, 225, 240, 255), (255, 185, 215, 255), step=6)

        # 2. 顶部主面板标题
        draw_flat_panel(img, 205, 25, 614, 75, border=(255, 100, 160, 220), bg=(255, 255, 255, 255))
        img.draw_string_advanced(395, 43, 38, "AI互动眼球系统", color=(255, 20, 24, 30))

        # 3. 中间主菜单面板背景
        draw_flat_panel(img, 80, 125, 864, 440, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))

        # 4. 中间提示引导字
        img.draw_string_advanced(382, 150, 26, "请说出或点击想体验的模式吧", color=(255, 20, 24, 30))

        # 5. 一行一行绘制长条卡片菜单
        for b in self.menu_cards:
            x, y, w, h, mode, _, title_zh, _, desc_zh = b

            if mode == MODE_FOLLOW:
                border = (255, 0, 180, 70)       # 绿色调
                bg_left = border
                bg_right = (255, 235, 255, 240)
            elif mode == MODE_STARING:
                border = (255, 80, 160, 220)     # 蓝色调
                bg_left = border
                bg_right = (255, 230, 242, 255)
            else:
                border = (255, 230, 150, 0)      # 橙色调
                bg_left = border
                bg_right = (255, 255, 250, 235)

            # 绘制左侧的模式标题色块按钮
            draw_panel(img, x, y, 180, h, border=border, bg=bg_left)
            draw_bold_string(img, x + 42, y + 25, 24, title_zh, color=(255, 255, 255, 255))

            # 绘制右侧的长条模式描述背景块
            draw_panel(img, x + 200, y, 580, h, border=border, bg=bg_right)
            img.draw_string_advanced(x + 225, y + 28, 18, desc_zh, color=(255, 50, 60, 70))

            # 右端提示箭头
            img.draw_string_advanced(x + 745, y + 28, 18, ">", color=border)

    def draw_game_nav(self, img):
        # 绘制底部的“返回菜单”和“重新开始”小按钮
        mx, my, mw, mh, mtext = self.menu_button
        draw_flat_panel(img, mx, my, mw, mh, border=(255, 80, 160, 220), bg=(76, 255, 255, 255))
        img.draw_string_advanced(mx+22, my+12, 14, mtext, color=(255, 20, 24, 30))

        rx, ry, rw, rh, rtext = self.restart_button
        draw_flat_panel(img, rx, ry, rw, rh, border=(255, 220, 80, 40), bg=(76, 255, 255, 255))
        img.draw_string_advanced(rx+18, ry+12, 14, rtext, color=(255, 20, 24, 30))


# 游戏核心逻辑状态机
class GameState:
    def __init__(self):
        self.mode = MODE_FOLLOW
        self.score = 0
        self.high_score_staring = 0
        self.high_score_evasion = 0
        self.should_exit_to_menu = False
        self.game_over = False
        self.game_over_start_ms = 0
        self.message = "READY"

        # Staring mode variables (123木头人)
        self.staring_active = False
        self.staring_start_time = 0
        self.staring_hp = 100
        self.staring_state = 0  # 0: 绿灯, 1: 红灯
        self.staring_state_start_ms = 0
        self.staring_state_duration_ms = 3000
        self.staring_lock_cx = None
        self.staring_lock_cy = None
        self.staring_warn_flash_ms = 0
        self.staring_star_x = 0
        self.staring_star_y = 0
        self.staring_star_active = False

        # Follow/Alignment game variables
        self.follow_level = 1
        self.follow_rounds = 0
        self.follow_wins = 0
        self.follow_target_x = 462
        self.follow_target_y = 250
        self.follow_target_tx = 462
        self.follow_target_ty = 250
        self.follow_speed = 4
        self.follow_round_start_ms = 0
        self.follow_round_active = False
        self.follow_overlap_duration = 0
        self.follow_last_overlap_time = 0
        self.follow_last_collision_state = False

        # Evasion mode variables (躲避眼球视线)
        self.hp = 100
        self.eye_x = 462
        self.eye_y = 250
        self.target_x = 462
        self.target_y = 250
        self.speed = 5
        self.evade_start_ms = 0
        self.evade_active = False
        self.last_collision_state = False
        self.last_score_for_speedup = 0

    def reset(self):
        self.should_exit_to_menu = False
        self.game_over = False
        self.score = 0
        self.message = "READY"
        # Staring reset (123木头人)
        self.staring_active = False
        self.staring_start_time = 0
        self.staring_hp = 100
        self.staring_state = 0  # 0: 绿灯, 1: 红灯
        self.staring_state_start_ms = 0
        self.staring_state_duration_ms = 3000
        self.staring_lock_cx = None
        self.staring_lock_cy = None
        self.staring_warn_flash_ms = 0
        self.staring_star_x = 0
        self.staring_star_y = 0
        self.staring_star_active = False
        self.staring_star_cooldown_ms = 0

        # Follow reset
        self.follow_level = 1
        self.follow_rounds = 0
        self.follow_wins = 0
        self.follow_target_x = 462
        self.follow_target_y = 250
        self.follow_target_tx = random.randint(50, 850)
        self.follow_target_ty = random.randint(150, 450)
        self.follow_speed = 4
        self.follow_round_start_ms = 0
        self.follow_round_active = False
        self.follow_overlap_duration = 0
        self.follow_last_overlap_time = 0
        self.follow_last_collision_state = False

        # Evasion reset
        self.hp = 100
        self.eye_x = 462
        self.eye_y = 250
        self.target_x = random.randint(20, 900)
        self.target_y = random.randint(120, 480)
        self.speed = 5
        self.evade_active = False
        self.last_collision_state = False
        self.last_score_for_speedup = 0

    def set_mode(self, mode):
        self.mode = mode
        self.reset()
        if mode == MODE_FOLLOW:
            self.message = "视线跟随对齐挑战！准备！"
        elif mode == MODE_STARING:
            self.message = "123木头人挑战！准备！"
        elif mode == MODE_GAZE:
            self.message = "躲避移动的红色眼球！"

    def update(self, has_face, face_rect, display_size, eye_controller=None):
        now = time.ticks_ms()

        # 模式 1: 视线跟随模式 (物理眼球全程跟随人脸移动)
        if self.mode == MODE_FOLLOW:
            if self.game_over:
                if time.ticks_diff(now, self.game_over_start_ms) >= 2000:
                    self.should_exit_to_menu = True
                return

            if not self.follow_round_active:
                self.follow_round_active = True
                self.follow_round_start_ms = now
                self.score = 0

            self.last_has_face_state = has_face
            elapsed = time.ticks_diff(now, self.follow_round_start_ms) // 1000
            self.score = elapsed

            if has_face:
                self.message = "视线跟随中 | 已全程锁住人脸注视 %d 秒" % self.score
            else:
                self.message = "正在寻找人脸... 请站在摄像头前方"

        # 模式 2: 对视 123 木头人模式
        elif self.mode == MODE_STARING:
            if self.game_over:
                if time.ticks_diff(now, self.game_over_start_ms) >= 2000:
                    self.should_exit_to_menu = True
                return

            if not self.staring_active:
                self.staring_active = True
                self.staring_start_time = now
                self.staring_state = 0  # 0: 绿灯, 1: 红灯
                self.staring_state_start_ms = now
                self.staring_state_duration_ms = random.randint(4500, 6500)
                self.staring_lock_cx = None
                self.staring_lock_cy = None
                self.staring_hp = 100
                self.staring_warn_flash_ms = 0
                self.message = "绿灯亮起，可以活动！"

            # 计算剩余生存秒数 (生存上限 30 秒)
            remain_sec = 30 - (time.ticks_diff(now, self.staring_start_time) // 1000)
            if remain_sec <= 0:
                remain_sec = 0
                self.game_over = True
                self.game_over_start_ms = now
                self.message = "时间到！木头人挑战成功！"
                if eye_controller:
                    eye_controller.play_voice(21)
                return

            # 随机产生金星 (吃完后冷却 1.5 秒再刷新下一只，防止频繁打卡)
            if not self.staring_star_active:
                if self.staring_star_cooldown_ms == 0 or time.ticks_diff(now, self.staring_star_cooldown_ms) >= 1500:
                    self.staring_star_x = random.randint(100, 800)
                    self.staring_star_y = random.randint(150, 420)
                    self.staring_star_active = True

            # 金星碰撞检测 (玩家移动去吃星星，只有在绿灯或者活动时才安全)
            if self.staring_star_active and has_face and face_rect is not None:
                fx, fy, fw, fh = face_rect
                if not (fx + fw < self.staring_star_x or self.staring_star_x + 50 < fx or fy + fh < self.staring_star_y or self.staring_star_y + 50 < fy):
                    self.score += 1
                    if self.score > self.high_score_staring:
                        self.high_score_staring = self.score
                    if eye_controller:
                        eye_controller.play_voice(19)
                    self.staring_star_active = False  # 被吃掉，开启 1.5 秒冷却
                    self.staring_star_cooldown_ms = now

            # 红绿灯交替逻辑
            state_elapsed = time.ticks_diff(now, self.staring_state_start_ms)
            if state_elapsed >= self.staring_state_duration_ms:
                if self.staring_state == 0:
                    self.staring_state = 1
                    self.staring_state_start_ms = now
                    self.staring_state_duration_ms = random.randint(1500, 3000)
                    self.message = "红灯亮！绝对不许动！！！"
                    if has_face and face_rect is not None:
                        fx, fy, fw, fh = face_rect
                        self.staring_lock_cx = fx + fw // 2
                        self.staring_lock_cy = fy + fh // 2
                    else:
                        self.staring_lock_cx = None
                        self.staring_lock_cy = None
                else:
                    self.staring_state = 0
                    self.staring_state_start_ms = now
                    self.staring_state_duration_ms = random.randint(4500, 6500)
                    self.message = "绿灯亮！活动活动身骨~"
                    self.staring_lock_cx = None
                    self.staring_lock_cy = None

            # 红灯静止检测
            if self.staring_state == 1:
                if has_face and face_rect is not None:
                    fx, fy, fw, fh = face_rect
                    cx = fx + fw // 2
                    cy = fy + fh // 2
                    if self.staring_lock_cx is None or self.staring_lock_cy is None:
                        self.staring_hp -= 34
                        self.staring_warn_flash_ms = now
                        if self.staring_hp > 0 and eye_controller:
                            eye_controller.play_voice(20)
                        self.staring_lock_cx = cx
                        self.staring_lock_cy = cy
                    else:
                        dx = cx - self.staring_lock_cx
                        dy = cy - self.staring_lock_cy

                        # 根据人脸大小级别动态确定允许的抖动阈值量 (更远处人脸偏小，近处人脸偏大)
                        # 允许的活动幅度增大：系数提升至 0.40 倍人脸宽度，最小容差提升至 100 像素
                        dynamic_thresh = int(fw * 0.40)
                        if dynamic_thresh < 100:
                            dynamic_thresh = 100

                        if math.sqrt(dx*dx + dy*dy) > dynamic_thresh:
                            self.staring_hp -= 34
                            self.staring_warn_flash_ms = now
                            if self.staring_hp > 0 and eye_controller:
                                eye_controller.play_voice(20)
                            self.staring_lock_cx = cx
                            self.staring_lock_cy = cy
                else:
                    if self.staring_lock_cx is not None:
                        self.staring_hp -= 34
                        self.staring_warn_flash_ms = now
                        if self.staring_hp > 0 and eye_controller:
                            eye_controller.play_voice(20)
                        self.staring_lock_cx = None
                        self.staring_lock_cy = None

                if self.staring_hp <= 0:
                    self.staring_hp = 0
                    self.game_over = True
                    self.game_over_start_ms = now
                    self.message = "你动了！木头人挑战失败！"
                    if eye_controller:
                        eye_controller.play_voice(22)
                    return

        # 模式 3: 视线躲避战模式 (Evasion Game)
        elif self.mode == MODE_GAZE:
            if self.game_over:
                if time.ticks_diff(now, self.game_over_start_ms) >= 2000:
                    self.should_exit_to_menu = True
                return

            if not self.evade_active:
                self.evade_active = True
                self.evade_start_ms = now
                self.hp = 100

            # 计算生存得分 (存活秒数)
            elapsed_survive = time.ticks_diff(now, self.evade_start_ms)
            self.score = elapsed_survive // 1000
            if self.score > self.high_score_evasion:
                self.high_score_evasion = self.score

            # 计算到随机生成的目标坐标的方向和距离
            dx = self.target_x - self.eye_x
            dy = self.target_y - self.eye_y
            dist = math.sqrt(dx*dx + dy*dy)

            if dist < self.speed:
                # 已经到达目标位置，重新生成一个随机目标坐标 (避开顶部文字条和底部返回栏)
                self.target_x = random.randint(20, display_size[0] - 120)
                self.target_y = random.randint(120, display_size[1] - 120)
            else:
                # 往目标方向移动
                self.eye_x = int(self.eye_x + (dx / dist) * self.speed)
                self.eye_y = int(self.eye_y + (dy / dist) * self.speed)

            # 随着时间推移，眼球移动速度会缓慢增加，增加难度 (每一秒整型更新一次)
            if self.score > 0 and self.score % 8 == 0 and self.score != self.last_score_for_speedup:
                self.last_score_for_speedup = self.score
                if self.speed < 15:
                    self.speed += 1

            # 碰撞检测：检查人脸框是否接触/进入红色眼球方框
            collision = False
            if has_face and face_rect is not None:
                fx, fy, fw, fh = face_rect
                # 矩形相交判定
                if not (fx + fw < self.eye_x or self.eye_x + 100 < fx or fy + fh < self.eye_y or self.eye_y + 100 < fy):
                    collision = True

            self.last_collision_state = collision

            if collision:
                self.hp -= 2  # 发生碰撞，生命值迅速降低
                if self.hp <= 0:
                    self.hp = 0
                    self.game_over = True
                    self.game_over_start_ms = now
                    self.evade_active = False
                    self.message = "你被眼球接触到了！挑战失败"
                    if eye_controller:
                        if self.score >= 15:
                            eye_controller.play_voice(21)
                        else:
                            eye_controller.play_voice(22)
                else:
                    self.message = "警告！正在被眼球接触！HP: %d%%" % self.hp
            else:
                self.message = "生命值: %d%% | 存活时间: %d秒" % (self.hp, self.score)

    def quantize_grade(self, dev_deg, step1, step2, step3):
        # 0 级死区阈值：±3 度内认为居中，不移动
        if abs(dev_deg) < 4.0:
            return 0.0
        elif dev_deg > 0:
            if dev_deg < 14.0:
                return step1
            elif dev_deg < 24.0:
                return step2
            else:
                return step3
        else:
            if dev_deg > -14.0:
                return -step1
            elif dev_deg > -24.0:
                return -step2
            else:
                return -step3

    def map_eyes(self, yaw_dev, pitch_dev, blink_ratios):
        # 1. Channel 0: 左右移动 (110° 正中间，60° 第一视角最右，160° 第一视角最左)
        # 连续无级角度直接映射 (按照真实目标输出，不进行阶梯离散化/防堵转抑制)
        yaw = 110.0 + yaw_dev
        yaw = max(SERVO_MIN_DEG[0], min(SERVO_MAX_DEG[0], yaw))

        # 2. Channel 1: 上下移动 (85° 正中间，100° 第一视角最上，70° 第一视角最下)
        pitch = 85.0 + pitch_dev
        pitch = max(SERVO_MIN_DEG[1], min(SERVO_MAX_DEG[1], pitch))

        # 3. Channels 2~5: 左右眼上下眼皮 (0.0闭合 ~ 1.0打开)
        # 左眼: blink_ratios[0]
        #   Channel 2: 左眼上眼皮 (60° 打开, 100° 闭合)
        #   Channel 3: 左眼下眼皮 (100° 打开, 60° 闭合)
        # 右眼: blink_ratios[1]
        #   Channel 4: 右眼上眼皮 (110° 打开, 60° 闭合)
        #   Channel 5: 右眼下眼皮 (80° 打开, 110° 闭合)
        b_ratio_l = blink_ratios[0]
        b_ratio_r = blink_ratios[1] if len(blink_ratios) > 1 else blink_ratios[0]

        b_l = max(0.0, min(1.0, b_ratio_l))
        b_r = max(0.0, min(1.0, b_ratio_r))

        lu_eyelid = 100.0 - 40.0 * b_l
        ll_eyelid = 60.0 + 40.0 * b_l
        ru_eyelid = 60.0 + 50.0 * b_r
        rl_eyelid = 110.0 - 30.0 * b_r

        return [yaw, pitch, lu_eyelid, ll_eyelid, ru_eyelid, rl_eyelid]

    # 获得对应模式下的舵机目标角度
    def get_servo_angles(self, follow_yaw, follow_pitch, blink_ratios, display_size):
        if self.mode == MODE_FOLLOW:
            if self.game_over:
                return SERVO_DEFAULT_DEG # 闭眼 (全部闭合)

            # 第一个游戏 (视线跟随模式)：物理眼球直接跟随真实人脸移动，眼皮自然眨眼
            yaw_dev = follow_yaw - 110.0
            pitch_dev = follow_pitch - 85.0
            return self.map_eyes(yaw_dev, pitch_dev, blink_ratios)

        elif self.mode == MODE_STARING:
            if self.game_over:
                return SERVO_DEFAULT_DEG # 结算时闭眼
            if self.staring_state == 1:
                # 红灯：睁眼！盯着人脸看！
                yaw_dev = follow_yaw - 110.0
                pitch_dev = follow_pitch - 85.0
                return self.map_eyes(yaw_dev, pitch_dev, [1.0, 1.0])
            else:
                # 绿灯：闭眼！
                return self.map_eyes(0.0, -8.0, [0.0, 0.0])

        elif self.mode == MODE_GAZE:
            # 机器人眼球物理跟随屏幕上运动的小眼球方块
            if self.game_over:
                return SERVO_DEFAULT_DEG # 挑战失败闭眼

            # 计算小眼球方块的中心点坐标
            ecx = self.eye_x + 50
            ecy = self.eye_y + 50

            # 屏幕归一化偏差 (-1.0 ~ 1.0)
            err_x = (ecx - display_size[0] * 0.5) / (display_size[0] * 0.5)
            err_y = (ecy - display_size[1] * 0.5) / (display_size[1] * 0.5)

            yaw_dev = err_x * 40.0
            pitch_dev = -err_y * 15.0
            return self.map_eyes(yaw_dev, pitch_dev, blink_ratios)

        return SERVO_OPEN_DEG

    def draw_game_overlay(self, img, display_size):
        COLOR_GREEN = (255, 0, 255, 0)
        COLOR_RED = (255, 255, 0, 0)

        # 1. 顶部半透明背景条和信息文字
        draw_flat_panel(img, 200, 30, 624, 70, border=(255, 100, 160, 220), bg=(255, 255, 255, 255))

        text_color = COLOR_RED if (self.mode == MODE_GAZE and self.last_collision_state) else (255, 20, 24, 30)
        img.draw_string_advanced(230, 50, 24, self.message, color=text_color)

        # 2. 绘制模式特殊 UI 元素
        # 2. 绘制模式特殊 UI 元素
        if self.mode == MODE_FOLLOW:
            # 绘制视线跟随模式的即时状态记分板
            draw_flat_panel(img, 760, 125, 230, 120, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))
            img.draw_string_advanced(780, 150, 20, "模式: 视线跟随", color=(255, 20, 24, 30))
            img.draw_string_advanced(780, 182, 20, "跟随时长: %d 秒" % self.score, color=(255, 20, 24, 30))
            has_lock = getattr(self, 'last_has_face_state', False)
            status_text = "状态: 锁定注视中" if has_lock else "状态: 寻找人脸中"
            status_col = (255, 0, 160, 0) if has_lock else (255, 220, 140, 0)
            img.draw_string_advanced(780, 212, 20, status_text, color=status_col)

        elif self.mode == MODE_STARING:
            # 绘制 123 木头人模式记分板
            draw_flat_panel(img, 760, 125, 230, 120, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))
            img.draw_string_advanced(780, 150, 20, "模式: 123木头人", color=(255, 20, 24, 30))
            img.draw_string_advanced(780, 182, 20, "吃到星星: %d 个" % self.score, color=(255, 20, 24, 30))
            remain_sec = max(0, 30 - (time.ticks_diff(time.ticks_ms(), self.staring_start_time) // 1000)) if getattr(self, 'staring_active', False) else 30
            img.draw_string_advanced(780, 212, 20, "倒计时: %d 秒" % remain_sec, color=(255, 20, 24, 30))

            if self.staring_star_active:
                cx = self.staring_star_x + 25
                cy = self.staring_star_y + 25
                COLOR_YELLOW = (255, 255, 220, 0)
                img.draw_circle(cx, cy, 14, color=COLOR_YELLOW, thickness=1)
                img.draw_circle(cx, cy, 6, color=COLOR_YELLOW, thickness=1, fill=True)
                img.draw_line(cx, cy - 25, cx, cy - 10, color=COLOR_YELLOW, thickness=3)
                img.draw_line(cx, cy + 10, cx, cy + 25, color=COLOR_YELLOW, thickness=3)
                img.draw_line(cx - 25, cy, cx - 10, cy, color=COLOR_YELLOW, thickness=3)
                img.draw_line(cx + 10, cy, cx + 25, cy, color=COLOR_YELLOW, thickness=3)
                img.draw_line(cx - 15, cy - 15, cx - 6, cy - 6, color=COLOR_YELLOW, thickness=1)
                img.draw_line(cx + 6, cy + 6, cx + 15, cy + 15, color=COLOR_YELLOW, thickness=1)
                img.draw_line(cx + 6, cy - 6, cx + 15, cy - 15, color=COLOR_YELLOW, thickness=1)
                img.draw_line(cx - 15, cy + 15, cx - 6, cy + 6, color=COLOR_YELLOW, thickness=1)

            # 绘制红绿灯大指示器
            cx_light = 512
            cy_light = 150
            if self.staring_state == 0:
                img.draw_circle(cx_light, cy_light, 35, color=COLOR_GREEN, thickness=4, fill=True)
                img.draw_string_advanced(cx_light - 24, cy_light - 12, 24, "绿灯", color=(255, 255, 255, 255))
            else:
                is_bright = (time.ticks_ms() // 250) % 2 == 0
                red_color = COLOR_RED if is_bright else (255, 120, 0, 0)
                img.draw_circle(cx_light, cy_light, 35, color=red_color, thickness=4, fill=True)
                img.draw_string_advanced(cx_light - 24, cy_light - 12, 24, "红灯", color=(255, 255, 255, 255))

            # 被抓乱动，闪烁红框
            if self.staring_warn_flash_ms > 0 and time.ticks_diff(time.ticks_ms(), self.staring_warn_flash_ms) < 400:
                img.draw_rectangle(0, 0, display_size[0], display_size[1], color=COLOR_RED, thickness=15)
                img.draw_string_advanced(300, 250, 40, "警告：监测到移动！！！", color=COLOR_RED)

        elif self.mode == MODE_GAZE:
            # 绘制躲避战下的红色眼球敌人和状态数据
            draw_flat_panel(img, 760, 125, 230, 120, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))
            img.draw_string_advanced(780, 150, 20, "最佳生存: %d 秒" % self.high_score_evasion, color=(255, 20, 24, 30))
            img.draw_string_advanced(780, 195, 20, "生存时间: %d 秒" % self.score, color=(255, 20, 24, 30))

            # 绘制生命值血条 (HP Bar)
            draw_flat_panel(img, 760, 260, 230, 45, border=(255, 80, 140, 200), bg=(255, 255, 255, 255))
            draw_progress_bar(img, 770, 270, 210, 25, self.hp / 100.0, COLOR_RED)

            # --- 绘制运动中的红色眼球方形区域 (大小 100x100) ---
            box_thickness = 4 if self.last_collision_state else 2
            box_color = COLOR_RED

            # 强转整型以满足 MicroPython 绘图 API 限制
            ex = int(self.eye_x)
            ey = int(self.eye_y)

            # 绘制外边框
            img.draw_rectangle(ex, ey, 100, 100, color=box_color, thickness=box_thickness)

            # 绘制里面的科幻眼睛图标细节
            ecx = ex + 50
            ecy = ey + 50
            img.draw_circle(ecx, ecy, 35, color=box_color, thickness=1)
            img.draw_circle(ecx, ecy, 12, color=box_color, thickness=1, fill=True)

            img.draw_line(ecx - 35, ecy, ecx - 18, ecy, color=box_color, thickness=1)
            img.draw_line(ecx + 18, ecy, ecx + 35, ecy, color=box_color, thickness=1)
            img.draw_line(ecx, ecy - 35, ecx, ecy - 18, color=box_color, thickness=1)
            img.draw_line(ecx, ecy + 18, ecx, ecy + 35, color=box_color, thickness=1)


# GT911 触摸屏硬件轮询线程
def gt911_polling_thread(btn_inst):
    print("[LOG] GT911 touch polling thread started.")
    I2C_ADDR = 0x14
    time.sleep_ms(200)
    try:
        from machine import I2C
        i2c = I2C(3, freq=100000)
    except Exception as e:
        print("[WARN] Failed to initialize I2C3 in touch thread:", e)
        return

    last_ids = set()

    while True:
        try:
            status_reg = i2c.readfrom_mem(I2C_ADDR, 0x814E, 1, addrsize=16)
            status = status_reg[0] if status_reg else 0

            if status & 0x80:
                finger_num = status & 0x0F
                current_ids = set()

                if finger_num > 0 and finger_num <= 5:
                    data = i2c.readfrom_mem(I2C_ADDR, 0x814F, finger_num * 6, addrsize=16)
                    if len(data) >= finger_num * 6:
                        for i in range(finger_num):
                            offset = i * 6
                            track_id = data[offset]
                            current_ids.add(track_id)

                            raw_x = data[offset + 1] | (data[offset + 2] << 8)
                            raw_y = data[offset + 3] | (data[offset + 4] << 8)

                            tx = int(-1.0038 * raw_x + 1027)
                            ty = int(-1.0030 * raw_y + 604)

                            tx = max(0, min(tx, DISPLAY_WIDTH - 1))
                            ty = max(0, min(ty, DISPLAY_HEIGHT - 1))

                            if DISPLAY_MIRROR_MODE == 1:
                                tx = DISPLAY_WIDTH - 1 - tx
                            elif DISPLAY_MIRROR_MODE == 2:
                                ty = DISPLAY_HEIGHT - 1 - ty

                            if track_id not in last_ids:
                                event = "DOWN"
                            else:
                                event = "MOVE"

                            with touch_lock:
                                btn_inst.pending_events.append(TouchPoint(tx, ty, event))

                for tid in last_ids:
                    if tid not in current_ids:
                        with touch_lock:
                            btn_inst.pending_events.append(TouchPoint(0, 0, "UP"))

                last_ids = current_ids
                i2c.writeto_mem(I2C_ADDR, 0x814E, b'\x00', addrsize=16)

            time.sleep_ms(8) # 125Hz
        except Exception as e:
            time.sleep_ms(10)


# face detect
class FaceDetectionApp(AIBase):
    def __init__(self, kmodel_path, model_input_size, confidence_threshold=0.5, nms_threshold=0.2, top_k=50, rgb888p_size=[224,224], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.scale = 1.0
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right, self.scale = letterbox_pad_param(self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [114, 114, 114])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]], [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            strides = [8, 16, 32]
            dets_out = aidemo.yunet_postprocess(results, [self.rgb888p_size[1], self.rgb888p_size[0]], [self.model_input_size[1], self.model_input_size[0]], [self.display_size[1], self.display_size[0]], strides, self.confidence_threshold, self.nms_threshold, self.top_k)
            return dets_out


# ----------------------------------------------------------------------
# 【系统24小时定时自动软重启维护流程】
def system_soft_reboot(pl=None, face_det=None, eye_controller=None, uvc_module=None, osd_rotation=0):
    """24小时定时软重启：按规范依序释放外设与资源，使系统干净重启"""
    print("\n=======================================================")
    print("[SYSTEM] 达到 %s 小时自动维护周期，正在执行安全软重启..." % str(AUTO_REBOOT_HOURS))
    print("=======================================================")

    # 1. 舵机安全回中并完全闭合，避免断电/复位瞬间眼球停留在极限角度
    if eye_controller is not None:
        try:
            print("[REBOOT] 正在将仿生眼球归位并闭合...")
            eye_controller.update(SERVO_DEFAULT_DEG)
            time.sleep_ms(400)
        except Exception as e:
            print("[REBOOT] 舵机归位异常:", e)

    # 2. 屏幕显示维护重启友好提示，避免突兀黑屏
    if pl is not None and hasattr(pl, 'osd_img') and pl.osd_img is not None:
        try:
            pl.osd_img.clear()
            draw_panel(pl.osd_img, scale_x(120), scale_y(150), scale_x(400), scale_y(180), border=(255, 80, 180, 255), bg=(255, 20, 30, 45))
            draw_bold_string(pl.osd_img, scale_x(150), scale_y(190), scale_px(24), "系统定期自检维护", (255, 255, 255, 255))
            draw_bold_string(pl.osd_img, scale_x(150), scale_y(235), scale_px(18), "正在执行安全软重启，请稍候...", (255, 200, 230, 255))
            draw_bold_string(pl.osd_img, scale_x(150), scale_y(275), scale_px(15), "Auto Maintenance Rebooting...", (255, 140, 180, 220))
            pl.show_image(flag=osd_rotation)
            time.sleep_ms(800)
        except Exception:
            pass

    # 3. 安全停止 UVC 摄像头流
    if uvc_module is not None:
        try:
            print("[REBOOT] 正在停止 UVC 摄像头流...")
            uvc_module.stop()
        except Exception as e:
            print("[REBOOT] UVC 停止异常:", e)

    # 4. 释放 AI 模型资源
    if face_det is not None:
        try:
            print("[REBOOT] 正在注销人脸检测模型...")
            face_det.deinit()
        except Exception as e:
            print("[REBOOT] 模型注销异常:", e)

    # 5. 销毁 PipeLine 与 Display/MediaManager
    if pl is not None:
        try:
            print("[REBOOT] 正在释放 PipeLine 与 Display 图层...")
            pl.destroy()
        except Exception:
            pass
    try:
        Display.deinit()
    except Exception:
        pass
    try:
        MediaManager.deinit()
    except Exception:
        pass

    # 6. 同步文件系统缓冲区
    try:
        import uos
        uos.sync()
    except Exception:
        pass

    time.sleep_ms(300)

    # 7. 触发硬件软复位
    try:
        import machine
        print("[REBOOT] 正在调用 machine.reset()...")
        machine.reset()
    except Exception as e:
        print("[REBOOT] machine.reset() 异常，尝试 sys.exit():", e)
        try:
            import sys
            sys.exit(0)
        except Exception:
            pass


# ----------------------------------------------------------------------
# 【厂测老化模式持久化管理函数】
def load_factory_test():
    """读取 SD 卡中的厂测状态记录"""
    try:
        with open(FACTORY_TEST_FILE, "r") as f:
            data = ujson.loads(f.read())
            if isinstance(data, dict) and data.get("enabled", False):
                return data
    except Exception:
        pass
    return None

def save_factory_test(reboot_count, max_reboots=50, current_game=0):
    """持久化记录厂测老化状态 (保存重启次数与当前轮次)"""
    try:
        data = {
            "enabled": True,
            "reboot_count": reboot_count,
            "max_reboots": max_reboots,
            "current_game": current_game,
            "timestamp": time.ticks_ms()
        }
        with open(FACTORY_TEST_FILE, "w") as f:
            f.write(ujson.dumps(data))
        try:
            import uos
            uos.sync()
        except Exception:
            pass
        return True
    except Exception as e:
        print("[FACTORY] Save state error:", e)
        return False

def clear_factory_test():
    """清除厂测持久化状态，恢复正常模式"""
    try:
        import os
        os.remove(FACTORY_TEST_FILE)
    except Exception:
        try:
            with open(FACTORY_TEST_FILE, "w") as f:
                f.write('{"enabled":false}')
        except Exception:
            pass
    try:
        import uos
        uos.sync()
    except Exception:
        pass


if __name__ == "__main__":
    import uos
    try:
        uos.dupterm(None)
        print("[LOG] Duplicate terminal disabled on UART.")
    except Exception as e:
        print("[LOG] dupterm not supported or failed:", e)

    import os

    try:
        display_mode = "lt9611"
        display_size = [DISPLAY_WIDTH, DISPLAY_HEIGHT]
        rgb888p_size = RGB888P_SIZE
        kmodel_path = "/sdcard/examples/kmodel/yunet_640.kmodel"
        confidence_threshold = 0.6
        nms_threshold = 0.3
        top_k = 50

        # 初始化 I2C/串口控制器
        eye_controller = EyeMechanismController(
            enable=True,
            port=FOLLOW_UART_PORT,
            baudrate=FOLLOW_UART_BAUDRATE,
            tx_pin=FOLLOW_UART_TX_PIN,
            rx_pin=FOLLOW_UART_RX_PIN,
            send_interval_ms=FOLLOW_UART_SEND_INTERVAL_MS,
            min_delta_deg=FOLLOW_UART_MIN_DELTA_DEG
        )

        # 初始化平滑滤波器
        filter_yaw = SmoothFilter(alpha=TRACKING_ALPHA_YAW)
        filter_pitch = SmoothFilter(alpha=TRACKING_ALPHA_PITCH)
        motion_filter = ServoMotionFilter(init_angles=SERVO_DEFAULT_DEG)

        # 初始化眨眼控制器
        blink_ctrl = BlinkController()

        # 初始化触摸按键组件
        buttons = TouchButtons()
        buttons.prepare_menu()

        # 触摸屏改为由 CH32V203 (PA11/PA12 USB Host) 读取 HDMI 触控并通过串口 (PB10/PB11) 实时推送
        # _thread.start_new_thread(gt911_polling_thread, (buttons,))

        # --- USB (UVC) 摄像头与 HDMI 显示初始化 ---
        UVC_module = None
        uvc_running = False
        try:
            from media.uvc import UVC
            UVC_module = UVC
        except Exception as e:
            print("[INFO] UVC module import error:", e)

        # 初始化 PipeLine 并配置 HDMI LT9611 (指定 osd_num=2 供 OSD0/OSD3 硬件双图层融合)
        pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode, display_size=display_size)
        Display.init(Display.LT9611, width=1024, height=600, osd_num=2, to_ide=False)
        pl.osd_img = image.Image(1024, 600, image.ARGB8888)
        MediaManager.init()

        display_size = [1024, 600]
        ai_rgb888p_size = [640, 480]

        osd_rotation = Display.FLAG_ROTATION_0
        video_rotation = Display.FLAG_ROTATION_0
        sensor_hmirror = SENSOR_HMIRROR
        sensor_vflip = SENSOR_VFLIP

        if DISPLAY_ROTATION_MODE == 1:
            osd_rotation = Display.FLAG_ROTATION_180
            video_rotation = Display.FLAG_ROTATION_180
        elif DISPLAY_ROTATION_MODE == 2:
            osd_rotation = Display.FLAG_ROTATION_90
            video_rotation = Display.FLAG_ROTATION_90
        elif DISPLAY_ROTATION_MODE == 3:
            osd_rotation = Display.FLAG_ROTATION_270
            video_rotation = Display.FLAG_ROTATION_270

        if DISPLAY_MIRROR_MODE == 1:
            osd_rotation |= Display.FLAG_MIRROR_HOR
            video_rotation |= Display.FLAG_MIRROR_HOR
        elif DISPLAY_MIRROR_MODE == 2:
            osd_rotation |= Display.FLAG_MIRROR_VER
            video_rotation |= Display.FLAG_MIRROR_VER

        pl.img_scaled = None
        pl.img_rgb888 = None
        pl.img_raw = None

        def try_connect_uvc(timeout_ms=0):
            global UVC_module, uvc_running
            if uvc_running:
                return True
            if UVC_module is None:
                try:
                    from media.uvc import UVC
                    UVC_module = UVC
                except Exception as e:
                    print("[UVC] Failed to import UVC module:", e)
                    return False

            start_t = time.ticks_ms()
            detected = False
            while True:
                try:
                    plugin, dev = UVC_module.probe()
                    if plugin:
                        print(f"[UVC] USB camera connected: {dev}")
                        detected = True
                        break
                except Exception:
                    pass
                if timeout_ms <= 0 or time.ticks_diff(time.ticks_ms(), start_t) >= timeout_ms:
                    break
                time.sleep_ms(100)

            if detected:
                try:
                    mode = UVC_module.video_mode(640, 480, UVC_module.FOURCC_MJPEG, 30)
                    UVC_module.select_video_mode(mode)
                    UVC_module.start(cvt=False)
                    uvc_running = True
                    print("[UVC] USB camera streaming started successfully (640x480 MJPEG).")
                    return True
                except Exception as e:
                    print("[UVC] Failed to start UVC video mode:", e)
                    try:
                        UVC_module.stop()
                    except Exception:
                        pass
                    uvc_running = False
                    return False
            else:
                uvc_running = False
                return False

        # 开机时自动尝试探测连接一次（给 USB 硬件 1.5 秒枚举，若无相机直接平滑进入主菜单）
        try_connect_uvc(timeout_ms=1500)

        # 覆盖 PipeLine.show_image 进行 OSD 画面和 UVC 画面重合叠加
        def uvc_show_image(flag=None):
            if not in_menu:
                # 使用硬件双层混合：底层 OSD0 渲染 USB 摄像头画面（使用 0 度 + 水平镜像，保证上下不颠倒且左右同向移动），顶层 OSD3 渲染游戏 UI 和准星
                if pl.img_scaled is not None:
                    Display.show_image(pl.img_scaled, 0, 0, Display.LAYER_OSD0, flag=Display.FLAG_ROTATION_0 | Display.FLAG_MIRROR_HOR)
                Display.show_image(pl.osd_img, 0, 0, Display.LAYER_OSD3, flag=flag)

                # 严格执行 FILO 先进后出顺序释放内存，防止破坏 OpenMV FB 栈而导致大内存块回退到 MicroPython 堆引起卡顿
                if pl.img_scaled is not None:
                    pl.img_scaled.__del__()
                    pl.img_scaled = None
                if pl.img_rgb888 is not None:
                    pl.img_rgb888.__del__()
                    pl.img_rgb888 = None
                if pl.img_raw is not None:
                    pl.img_raw.__del__()
                    pl.img_raw = None
            else:
                # 菜单模式下，直接显示 OSD3
                Display.show_image(pl.osd_img, 0, 0, Display.LAYER_OSD3, flag=flag)
        pl.show_image = uvc_show_image

        # 覆盖 PipeLine.destroy 防止 NoneType 崩溃
        def uvc_destroy():
            os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
            if UVC_module is not None:
                try:
                    UVC_module.stop()
                except Exception:
                    pass
            Display.deinit()
            time.sleep_ms(50)
            MediaManager.deinit()
        pl.destroy = uvc_destroy
        # --- USB 摄像头与 HDMI 显示初始化结束 ---

        # 第一阶段加载界面：从候选路径寻找背景图
        loading_bg = None
        paths_to_try = [
            "/sdcard/data/images/loading_bg_1024.bmp",
            "/sdcard/data/image/loading_bg_1024.bmp",
            "/sdcard/CanMV/data/images/loading_bg_1024.bmp",
            "/sdcard/CanMV/data/image/loading_bg_1024.bmp",
            "/sdcard/canmv/data/images/loading_bg_1024.bmp",
            "/sdcard/canmv/data/image/loading_bg_1024.bmp"
        ]
        for p in paths_to_try:
            try:
                loading_bg = image.Image(p)
                print("[SYSTEM] Custom loading background image loaded successfully from:", p)
                break
            except Exception as e:
                print("[DEBUG] Failed loading loading_bg from %s: %s" % (p, repr(e)))

        def refresh_loading_screen(status_text, progress_pct):
            if loading_bg is not None:
                # 复制一份加载背景，在其上绘制进度 HUD 后显示
                temp_bg = loading_bg.copy()

                # 绘制霓虹色高科技文字 (无方框遮挡)
                draw_bold_string(temp_bg, 360, 180, 32, "系统初始化中", color=(255, 0, 220, 255)) # 亮青色/霓虹蓝

                temp_bg.draw_string_advanced(292, 250, 20, "正在加载模型及硬件配置...", color=(255, 220, 220, 220)) # 淡白灰色
                temp_bg.draw_string_advanced(292, 290, 18, "当前状态: " + status_text, color=(255, 255, 180, 0))    # 炫酷橙黄色
                temp_bg.draw_string_advanced(292, 330, 16, "硬件平台: K230 (CanMV V3P0)", color=(255, 130, 140, 150)) # 科技灰

                # 进度条直接使用图片上自带的精美设计，这里不再重复叠加虚假进度条，仅在屏幕刷新时更新状态文字即可
                Display.show_image(temp_bg, 0, 0, Display.LAYER_OSD3, flag=osd_rotation)
                del temp_bg
                gc.collect()
            else:
                pl.osd_img.clear()
                # 纯黑色背景 (当没找到图时)
                pl.osd_img.draw_rectangle(0, 0, display_size[0], display_size[1], color=(255, 0, 0, 0), fill=True)
                draw_bold_string(pl.osd_img, 360, 180, 32, "系统初始化中", color=(255, 0, 220, 255))
                pl.osd_img.draw_string_advanced(292, 250, 20, "正在加载模型及硬件配置...", color=(255, 220, 220, 220))
                pl.osd_img.draw_string_advanced(292, 290, 18, "当前状态: " + status_text, color=(255, 255, 180, 0))
                pl.osd_img.draw_string_advanced(292, 330, 16, "硬件平台: K230 (CanMV V3P0)", color=(255, 130, 140, 150))

                # 进度条
                bar_w = 440
                pl.osd_img.draw_rectangle(292, 375, bar_w, 14, color=(255, 40, 45, 55), fill=True)
                pl.osd_img.draw_rectangle(292, 375, int(bar_w * (progress_pct / 100.0)), 14, color=(255, 0, 180, 70), fill=True)
                pl.show_image(flag=osd_rotation)

        # 模拟高科技系统逐步初始化，展示炫酷加载过程
        steps = [
            ("Core System Initializing...", 12),
            ("Loading Camera Sensor Driver...", 24),
            ("Configuring I2C & UART Buses...", 36),
            ("Loading AI Model: yunet_640.kmodel...", 50),
        ]
        for msg, pct in steps:
            refresh_loading_screen(msg, pct)
            time.sleep(0.8)

        # 初始化自定义人脸检测实例
        face_det = FaceDetectionApp(kmodel_path, model_input_size=[640, 640], confidence_threshold=confidence_threshold, nms_threshold=nms_threshold, top_k=top_k, rgb888p_size=ai_rgb888p_size, display_size=display_size, debug_mode=0)

        # 重写 AI2D 预处理以支持 RGB_packed 输入格式，防止硬件内存对齐或格式冲突导致死机
        def uvc_config_preprocess(input_image_size=None):
            with ScopedTiming("set preprocess config (UVC)", face_det.debug_mode > 0):
                ai2d_input_size = input_image_size if input_image_size else face_det.rgb888p_size
                face_det.ai2d.set_ai2d_dtype(nn.ai2d_format.RGB_packed, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)
                top, bottom, left, right, face_det.scale = letterbox_pad_param(face_det.rgb888p_size, face_det.model_input_size)
                face_det.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [114, 114, 114])
                face_det.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
                # 输入为 NHWC [1, H, W, 3] 格式
                face_det.ai2d.build(
                    [1, ai2d_input_size[1], ai2d_input_size[0], 3],
                    [1, 3, face_det.model_input_size[1], face_det.model_input_size[0]]
                )
        face_det.config_preprocess = uvc_config_preprocess
        face_det.config_preprocess()

        steps_post = [
            ("Neural Network Model Loaded.", 68),
            ("Calibrating Eye Servo Motors...", 82),
            ("Initializing Touch Screen Controller...", 92),
            ("System Ready.", 100),
        ]
        for msg, pct in steps_post:
            refresh_loading_screen(msg, pct)
            time.sleep(0.8)

        # 实例化游戏控制状态机
        game = GameState()
        in_menu = True

        # 寻人待机扫视相位
        scan_phase = 0.0

        print("[SYSTEM] Starting YuNet Eye Interactive Game Loop...")

        # ARGB888P 颜色元组格式定义 (alpha, red, green, blue)
        COLOR_GREEN = (255, 0, 255, 0)
        COLOR_GREEN_SEMI = (200, 0, 255, 0)

        # 默认档位与增益初始化
        dist_gear = "MED"
        gear_gain = 1.0

        backdoor_triggered = False
        face_detected_voice_played = False
        face_missing_voice_played = False
        face_missing_start_time = 0
        last_has_face = False

        prev_in_menu = True
        last_uvc_probe_time = 0
        consecutive_none_frames = 0

        # 24小时自动维护计时器 (基于时间差递增累计秒数，彻底避免 ticks_ms 溢出)
        uptime_seconds = 0
        last_uptime_tick = time.ticks_ms()
        target_reboot_seconds = int(AUTO_REBOOT_HOURS * 3600)
        last_logged_hour = 0

        # 厂测老化模式初始化与断电/重启自恢复检测
        factory_state = load_factory_test()
        in_factory_test = False
        factory_reboot_count = 0
        factory_game_index = 0
        factory_game_start_ms = 0
        factory_games = [MODE_FOLLOW, MODE_STARING, MODE_GAZE]
        factory_game_names = ["视线跟随", "木头人模式", "大眼躲避球"]

        if factory_state is not None:
            factory_reboot_count = factory_state.get("reboot_count", 1)
            if factory_reboot_count > FACTORY_MAX_REBOOTS:
                # 50 次软重启与老化全部通过！
                clear_factory_test()
                print("\n" + "="*60)
                print("[FACTORY] ★★★ 50 次软重启与老化测试全部通过！厂测圆满完成 ★★★")
                print("="*60 + "\n")
                in_factory_test = False
                eye_controller.play_voice(19)
            else:
                in_factory_test = True
                in_menu = False # 跳过主菜单，直接进入老化测试
                factory_game_index = 0
                factory_game_start_ms = time.ticks_ms()
                game.set_mode(factory_games[factory_game_index])
                print("\n" + "="*60)
                print("[FACTORY] 厂测老化恢复运行: 第 %d / %d 次软重启" % (factory_reboot_count, FACTORY_MAX_REBOOTS))
                print("[FACTORY] 当前运行游戏: %s (%d/%d)" % (factory_game_names[factory_game_index], factory_game_index + 1, len(factory_games)))
                print("="*60 + "\n")

        while True:
            # --- 24小时定时自动软重启维护检测 ---
            if AUTO_REBOOT_ENABLE:
                now_tick = time.ticks_ms()
                tick_delta = time.ticks_diff(now_tick, last_uptime_tick)
                if tick_delta >= 1000:
                    add_sec = tick_delta // 1000
                    uptime_seconds += add_sec
                    last_uptime_tick = now_tick

                    # 整点日志打印
                    current_hour = uptime_seconds // 3600
                    if current_hour > last_logged_hour:
                        last_logged_hour = current_hour
                        remain_h = max(0, int(AUTO_REBOOT_HOURS - current_hour))
                        print("[SYSTEM] 设备已连续稳定运行 %d 小时 (距离 24h 维护重启还剩 %d 小时)" % (current_hour, remain_h))

                if uptime_seconds >= target_reboot_seconds:
                    can_reboot = False
                    if in_menu:
                        can_reboot = True
                    elif not AUTO_REBOOT_ONLY_IDLE:
                        can_reboot = True
                    elif uptime_seconds >= (target_reboot_seconds + 3600):
                        # 超过预定时间 1 小时，强制重启
                        can_reboot = True
                    elif face_missing_start_time > 0 and time.ticks_diff(now_tick, face_missing_start_time) > 30000:
                        # 处于游戏中但连续 30 秒无人脸交互，判定为空闲安全期，执行重启
                        can_reboot = True

                    if can_reboot:
                        system_soft_reboot(pl=pl, face_det=face_det, eye_controller=eye_controller, uvc_module=UVC_module, osd_rotation=osd_rotation)
                        break

            # --- 厂测老化逻辑处理：自动轮流切换 3 个游戏，一轮完成后执行软重启 ---
            if in_factory_test:
                now_factory = time.ticks_ms()
                game_elapsed = time.ticks_diff(now_factory, factory_game_start_ms) // 1000
                if game_elapsed >= FACTORY_GAME_DURATION_SEC:
                    factory_game_index += 1
                    if factory_game_index < len(factory_games):
                        # 切换到下一个游戏
                        next_mode = factory_games[factory_game_index]
                        game.set_mode(next_mode)
                        blink_ctrl.reset()
                        factory_game_start_ms = now_factory
                        print("[FACTORY] 厂测切换游戏 (%d/%d): %s" % (factory_game_index + 1, len(factory_games), factory_game_names[factory_game_index]))
                        eye_controller.play_voice(11 + factory_game_index)
                    else:
                        # 本轮 3 个游戏已全部完成老化，进入下一次软重启！
                        next_reboot = factory_reboot_count + 1
                        save_factory_test(reboot_count=next_reboot, max_reboots=FACTORY_MAX_REBOOTS)
                        print("\n[FACTORY] 第 %d / %d 轮 3 游戏老化完成！准备执行软重启进入下一轮..." % (factory_reboot_count, FACTORY_MAX_REBOOTS))
                        try:
                            pl.osd_img.clear()
                            draw_panel(pl.osd_img, scale_x(80), scale_y(150), scale_x(480), scale_y(180), border=(255, 255, 120, 0), bg=(255, 30, 20, 10))
                            draw_bold_string(pl.osd_img, scale_x(100), scale_y(190), scale_px(24), "【厂测老化】第 %d / %d 次完成" % (factory_reboot_count, FACTORY_MAX_REBOOTS), (255, 255, 200, 50))
                            draw_bold_string(pl.osd_img, scale_x(100), scale_y(235), scale_px(18), "正在执行软重启，请稍候...", (255, 255, 255, 255))
                            draw_bold_string(pl.osd_img, scale_x(100), scale_y(275), scale_px(16), "Rebooting for next burn-in cycle...", (255, 200, 220, 240))
                            pl.show_image(flag=osd_rotation)
                            time.sleep_ms(800)
                        except Exception:
                            pass
                        system_soft_reboot(pl=pl, face_det=face_det, eye_controller=eye_controller, uvc_module=UVC_module, osd_rotation=osd_rotation)
                        break

            # A. 从串口读取外设数据 (将来自 CH32 的 USB 触摸事件灌入 buttons.pending_events，并提取语音指令)
            voice_action = eye_controller.read_command(buttons)

            # B. 判定动作来源：语音指令优先；若无语音指令，则解析屏幕触摸
            if voice_action is not None:
                action = voice_action
            else:
                action = buttons.read_action(in_menu)

            # C. 调试后门强制模式处理
            if BACKDOOR_MODE != 0 and not backdoor_triggered:
                backdoor_triggered = True
                forced_mode = BACKDOOR_MODE - 1
                game.set_mode(forced_mode)
                blink_ctrl.reset()
                in_menu = False
                if not uvc_running:
                    try_connect_uvc(timeout_ms=0)
                if forced_mode == MODE_FOLLOW:
                    eye_controller.play_voice(11)
                elif forced_mode == MODE_STARING:
                    eye_controller.play_voice(12)
                elif forced_mode == MODE_GAZE:
                    eye_controller.play_voice(13)
            else:
                if action is not None:
                    if action[0] == "wake":
                        print("[SYSTEM] Wake word '你好大眼' detected! 8-second command priority window active.")
                        face_missing_voice_played = False
                        face_missing_start_time = time.ticks_ms()
                    elif action[0] == "mode":
                        game.set_mode(action[1])
                        blink_ctrl.reset()
                        in_menu = False
                        # 每次从主菜单进入游戏界面，若 UVC 未运行快速探测（0ms 非阻塞）
                        if not uvc_running:
                            try_connect_uvc(timeout_ms=0)
                        # 播报对应模式进入语音
                        if action[1] == MODE_FOLLOW:
                            eye_controller.play_voice(11)
                        elif action[1] == MODE_STARING:
                            eye_controller.play_voice(12)
                        elif action[1] == MODE_GAZE:
                            eye_controller.play_voice(13)
                        # 重置语音状态
                        face_detected_voice_played = False
                        face_missing_voice_played = False
                        face_missing_start_time = 0
                        last_has_face = False
                    elif action[0] == "factory_test":
                        if not in_factory_test:
                            print("\n[FACTORY] 收到进入厂测模式指令！启动老化测试并记录 1/50 次软重启...")
                            in_factory_test = True
                            factory_reboot_count = 1
                            factory_game_index = 0
                            factory_game_start_ms = time.ticks_ms()
                            save_factory_test(reboot_count=1, max_reboots=FACTORY_MAX_REBOOTS)
                            in_menu = False
                            game.set_mode(factory_games[0])
                            blink_ctrl.reset()
                            if not uvc_running:
                                try_connect_uvc(timeout_ms=0)
                            eye_controller.play_voice(19)
                        else:
                            print("\n[FACTORY] 厂测模式下再次触发，安全退出厂测！")
                            clear_factory_test()
                            in_factory_test = False
                            in_menu = True
                            prev_in_menu = True
                            game.reset()
                            # 退出模式直接了当闭眼，不搞平滑过渡
                            motion_filter.reset_to(SERVO_DEFAULT_DEG)
                            eye_controller.update(SERVO_DEFAULT_DEG)
                            eye_controller.play_voice(10)
                            buttons.prepare_menu()
                            continue
                    elif action[0] == "menu":
                        if in_factory_test:
                            print("\n[FACTORY] 用户在厂测模式下点击返回菜单，安全退出厂测！")
                            clear_factory_test()
                            in_factory_test = False
                        in_menu = True
                        prev_in_menu = True
                        game.reset()
                        # 退出模式直接了当闭眼，不搞平滑过渡
                        motion_filter.reset_to(SERVO_DEFAULT_DEG)
                        eye_controller.update(SERVO_DEFAULT_DEG)
                        eye_controller.play_voice(10)
                        face_detected_voice_played = False
                        face_missing_voice_played = False
                        face_missing_start_time = 0
                        last_has_face = False
                        buttons.prepare_menu()
                        continue
                    elif action[0] == "restart":
                        game.reset()
                        game.set_mode(game.mode)
                        blink_ctrl.reset()
                        if not uvc_running:
                            try_connect_uvc(timeout_ms=0)
                        if game.mode == MODE_FOLLOW:
                            eye_controller.play_voice(11)
                        elif game.mode == MODE_STARING:
                            eye_controller.play_voice(12)
                        elif game.mode == MODE_GAZE:
                            eye_controller.play_voice(13)
                        face_detected_voice_played = False
                        face_missing_voice_played = False
                        face_missing_start_time = 0
                        last_has_face = False
                    elif action[0] == "volume":
                        # 发送音量指令：音量 x 对应虚拟语音 ID: 90 + x (ASR Pro 解析 91~97 进行 vol_set 设定)
                        vol_voice_id = 90 + action[1]
                        eye_controller.play_voice(vol_voice_id)

            # 状态转移保障：当从菜单切换到游戏界面时，若摄像头未连接快速探测一次（0ms耗时，不卡顿）
            if prev_in_menu and not in_menu:
                if not uvc_running:
                    try_connect_uvc(timeout_ms=0)

            with ScopedTiming("total", 0):
                # 只有在非主菜单，即实际游戏中，才执行人脸推理与摄像头帧处理
                if not in_menu:
                    # 如果在游戏界面中摄像头未连接，每隔 2 秒快速非阻塞尝试连接一次 (0ms 耗时，不卡死 UI 与触控)
                    if not uvc_running:
                        now_t = time.ticks_ms()
                        if time.ticks_diff(now_t, last_uvc_probe_time) > 2000:
                            last_uvc_probe_time = now_t
                            try_connect_uvc(timeout_ms=0)

                    if uvc_running:
                        img = None
                        try:
                            img = UVC_module.snapshot()
                        except Exception as e:
                            print("[UVC] Snapshot exception:", e)
                            img = None

                        if img is not None:
                            consecutive_none_frames = 0
                            try:
                                pl.img_raw = img
                                # 1. 转换为 RGB888 格式供 AI 推理
                                pl.img_rgb888 = img.to_rgb888()
                                img_np_hwc = pl.img_rgb888.to_numpy_ref()
                                # 2. 将 HWC (H, W, 3) 调整为 NHWC (1, H, W, 3) 形状以适配 AI2D
                                input_np = img_np_hwc.reshape((1, ai_rgb888p_size[1], ai_rgb888p_size[0], 3))
                                dets = face_det.run(input_np)

                                # 3. 直接缩放 RGB888 图像到 1024x600 铺满用于显示（省去额外的 RGB565 转换开销）
                                pl.img_scaled = pl.img_rgb888.copy(x_size=DISPLAY_WIDTH, y_size=DISPLAY_HEIGHT)
                            except Exception as e:
                                print("[DEBUG] UVC snapshot processing error:", e)
                                pl.img_scaled = None
                                pl.img_rgb888 = None
                                pl.img_raw = None
                                dets = None
                        else:
                            consecutive_none_frames += 1
                            pl.img_scaled = None
                            pl.img_rgb888 = None
                            pl.img_raw = None
                            dets = None
                            # 连续超过 15 帧获取不到图像，判定为摄像头连接松动或断开
                            if consecutive_none_frames > 15:
                                print("[UVC] USB camera disconnected (15 None frames). Stopping stream.")
                                try:
                                    UVC_module.stop()
                                except Exception:
                                    pass
                                uvc_running = False
                                consecutive_none_frames = 0
                    else:
                        pl.img_scaled = None
                        pl.img_rgb888 = None
                        pl.img_raw = None
                        dets = None

                    # 清空 OSD 图像画布
                    pl.osd_img.clear()

                    # 若摄像头断开或未检测到，绘制高对比度全屏黑底及提示框，避免底层残留冻结帧
                    if not uvc_running:
                        fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (255, 18, 22, 28), 1)
                        draw_panel(pl.osd_img, 180, 210, 664, 140, border=(255, 230, 80, 80), bg=(255, 30, 34, 42))
                        draw_bold_string(pl.osd_img, 240, 235, 26, "【提示】未检测到 USB 摄像头", color=(255, 255, 100, 100))
                        pl.osd_img.draw_string_advanced(240, 280, 20, "请插紧摄像头 USB 连接线，系统将自动连接...", color=(255, 220, 220, 220))
                        pl.osd_img.draw_string_advanced(240, 312, 18, "可随时点击左下角【返回菜单】退出游戏", color=(255, 180, 200, 220))

                    best_det = None
                    max_area = 0

                    # 1. 过滤锁定最大的人脸（离得最近的人）
                    if dets and len(dets) > 0 and len(dets[0]) > 0:
                        for i in range(len(dets[0])):
                            x, y, w, h = map(lambda x: int(round(x, 0)), dets[0][i][:4])
                            area = w * h
                            if area > max_area:
                                max_area = area
                                best_det = dets[0][i]

                    has_face = (best_det is not None)
                    face_center = None
                    face_rect = None

                    if has_face:
                        x, y, w, h = map(lambda v: int(round(v, 0)), best_det[:4])
                        cx = x + w // 2
                        cy = y + h // 2

                        # 屏幕实际显示与绘制的人脸方框坐标 (第三人称视角，照镜子对应)
                        draw_x = (display_size[0] - x - w) if OSD_MIRROR_X else x
                        draw_y = (display_size[1] - y - h) if OSD_MIRROR_Y else y
                        draw_cx = (display_size[0] - cx) if OSD_MIRROR_X else cx
                        draw_cy = (display_size[1] - cy) if OSD_MIRROR_Y else cy

                        face_rect = (draw_x, draw_y, w, h)
                        face_center = (draw_cx, draw_cy)

                        # 人脸框大小分档增益计算
                        if w < DIST_FAR_LIMIT:
                            dist_gear = "FAR"
                            gear_gain = GAIN_FAR
                        elif w > DIST_NEAR_LIMIT:
                            dist_gear = "NEAR"
                            gear_gain = GAIN_NEAR
                        else:
                            dist_gear = "MED"
                            gear_gain = GAIN_MEDIUM

                        # 基于屏幕方框中心 (draw_cx, draw_cy) 进行归一化偏差计算 (-1.0 ~ 1.0)
                        # 屏幕中心点为 (display_size[0] * 0.5, display_size[1] * 0.5)
                        # 屏幕方框在左侧：err_x < 0；在右侧：err_x > 0
                        # 屏幕方框在上方：err_y < 0；在下方：err_y > 0
                        err_x = (draw_cx - display_size[0] * 0.5) / (display_size[0] * 0.5)
                        err_y = (draw_cy - display_size[1] * 0.5) / (display_size[1] * 0.5)

                        # 计算人脸追踪目标角度 (Yaw 中心 110° 产生约 ±45° 偏差, Pitch 中心 85° 产生约 ±15° 偏差)
                        # 第一人称视角: 85° 正中间，100° 看最上面，70° 看最下面
                        # 屏幕上方 (err_y < 0) -> 向上看 (靠近 100°); 屏幕下方 (err_y > 0) -> 向下看 (靠近 70°)
                        target_yaw = 110.0 + err_x * (45.0 * gear_gain)
                        target_pitch = 85.0 - err_y * (15.0 * gear_gain)

                        target_yaw = max(SERVO_MIN_DEG[0], min(SERVO_MAX_DEG[0], target_yaw))
                        target_pitch = max(SERVO_MIN_DEG[1], min(SERVO_MAX_DEG[1], target_pitch))

                        # 平滑滤波计算
                        yaw_deg = filter_yaw.update(target_yaw)
                        pitch_deg = filter_pitch.update(target_pitch)

                        # 绘制瞄准框与准星
                        if game.mode == MODE_FOLLOW or (game.mode == MODE_STARING and not game.game_over):
                            pl.osd_img.draw_rectangle(draw_x, draw_y, w, h, color=COLOR_GREEN, thickness=4)
                            pl.osd_img.draw_line(draw_cx - 15, draw_cy, draw_cx + 15, draw_cy, color=COLOR_GREEN, thickness=1)
                            pl.osd_img.draw_line(draw_cx, draw_cy - 15, draw_cx, draw_cy + 15, color=COLOR_GREEN, thickness=1)
                        elif game.mode == MODE_GAZE and not game.game_over:
                            # 躲避模式下画人脸框表示玩家当前安全/碰撞状态
                            face_color = (255, 255, 0, 0) if game.last_collision_state else COLOR_GREEN
                            pl.osd_img.draw_rectangle(draw_x, draw_y, w, h, color=face_color, thickness=3)

                        scan_phase = 0.0
                    else:
                        if in_factory_test:
                            # 厂测老化专属：无人脸时自动进行大幅度平滑扫视，全面磨合舵机与连杆
                            scan_phase += 0.05
                            target_yaw = 110.0 + math.sin(scan_phase) * 45.0
                            target_pitch = 85.0 + math.cos(scan_phase * 0.7) * 12.0
                            yaw_deg = filter_yaw.update(target_yaw)
                            pitch_deg = filter_pitch.update(target_pitch)
                            dist_gear = "AGING"
                            gear_gain = 1.0
                        else:
                            # 找不到人脸时，保持静止停在中心 (Yaw 110°, Pitch 85°)
                            target_yaw = 110.0
                            target_pitch = 85.0

                            yaw_deg = filter_yaw.update(target_yaw)
                            pitch_deg = filter_pitch.update(target_pitch)

                            dist_gear = "STILL"
                            gear_gain = 1.0

                    # 语音人脸锁定稳定播报
                    if has_face:
                        if not face_detected_voice_played:
                            eye_controller.play_voice(15)  # 播报“找到了”
                            face_detected_voice_played = True
                        last_has_face = True
                        face_missing_start_time = 0
                        face_missing_voice_played = False
                    else:
                        if last_has_face:
                            face_missing_start_time = time.ticks_ms()
                            last_has_face = False
                        if face_missing_start_time > 0 and time.ticks_diff(time.ticks_ms(), face_missing_start_time) >= 8000:
                            if not face_missing_voice_played:
                                if game.mode in (MODE_FOLLOW, MODE_GAZE) and not game.game_over and not in_menu:
                                    eye_controller.play_voice(14)  # 播报“正在寻找” (木头人模式下不播报“没有看到你”)
                                face_missing_voice_played = True

                    # 更新自然随机眨眼 (平时大开注视，每隔 3~7 秒快速眨眼约 200ms)
                    left_eyelid, right_eyelid = blink_ctrl.update()
                    blink_angles = [left_eyelid, right_eyelid]

                    # 更新游戏逻辑状态机
                    game.update(has_face, face_rect, display_size, eye_controller)

                    # 组合成 6 轴舵机帧并通过全局仿生运动学平滑滤波器输出 (躲避模式传入显示屏参数由状态机处理)
                    target_angles = game.get_servo_angles(yaw_deg, pitch_deg, blink_angles, display_size)
                    servo_angles = motion_filter.update(target_angles)
                    eye_controller.update(servo_angles)

                    # 退出判断
                    if game.should_exit_to_menu:
                        if in_factory_test:
                            # 厂测老化模式下，游戏单局超时或结束时不退出主菜单，自动重置继续当前游戏老化
                            game.reset()
                            game.set_mode(factory_games[factory_game_index])
                        else:
                            in_menu = True
                            prev_in_menu = True
                            game.reset()
                            # 退出模式直接了当闭眼，不搞平滑过渡
                            motion_filter.reset_to(SERVO_DEFAULT_DEG)
                            eye_controller.update(SERVO_DEFAULT_DEG)
                            # 自动游戏结束时不重复播报“返回主菜单”，避免音效连播堆积
                            face_detected_voice_played = False
                            face_missing_voice_played = False
                            face_missing_start_time = 0
                            last_has_face = False
                            buttons.prepare_menu()
                            continue

                    # 绘制右上角虚拟眼球小 UI
                    R = 25
                    r = 8
                    d_max = 14

                    x1 = display_size[0] - 120
                    y1 = 60
                    x2 = display_size[0] - 50
                    y2 = 60

                    # 将要显示的眼球角度传给 UI (如果是躲避战，直接反映物理眼球正在追视方块的方向)
                    vis_yaw = servo_angles[0]
                    vis_pitch = servo_angles[1]

                    dx = (vis_yaw - 110.0) / 50.0
                    dy = (85.0 - vis_pitch) / 15.0
                    dx = max(-1.0, min(1.0, dx))
                    dy = max(-1.0, min(1.0, dy))

                    offset_x = int(dx * d_max)
                    offset_y = int(dy * d_max)

                    is_left_closed = (servo_angles[2] > 80.0)
                    is_right_closed = (servo_angles[4] < 85.0)

                    if is_left_closed:  # 眨眼/闭眼状态
                        pl.osd_img.draw_line(x1 - R, y1, x1 + R, y1, color=COLOR_GREEN, thickness=2)
                    else:
                        pl.osd_img.draw_circle(x1, y1, R, color=COLOR_GREEN, thickness=2)
                        pl.osd_img.draw_circle(x1 + offset_x, y1 + offset_y, r, color=COLOR_GREEN, thickness=2, fill=True)

                    if is_right_closed:
                        pl.osd_img.draw_line(x2 - R, y2, x2 + R, y2, color=COLOR_GREEN, thickness=2)
                    else:
                        pl.osd_img.draw_circle(x2, y2, R, color=COLOR_GREEN, thickness=2)
                        pl.osd_img.draw_circle(x2 + offset_x, y2 + offset_y, r, color=COLOR_GREEN, thickness=2, fill=True)

                    pl.osd_img.draw_string_advanced(x1 - 20, y1 + R + 5, 16, "EYE STATE", color=COLOR_GREEN)

                    # 绘制舵机调试仪表盘 (仅在跟随模式下显示)
                    if False:
                        pl.osd_img.draw_string_advanced(30, 80, 22, "SERVO DASHBOARD", color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 115, 18, "RANGE GEAR   : %s (x%.1f)" % (dist_gear, gear_gain), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 145, 18, "CH0 (Yaw)        : %d DEG" % int(servo_angles[0]), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 170, 18, "CH1 (Pitch)      : %d DEG" % int(servo_angles[1]), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 195, 18, "CH2 (L-Upper)    : %d DEG" % int(servo_angles[2]), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 220, 18, "CH3 (L-Lower)    : %d DEG" % int(servo_angles[3]), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 245, 18, "CH4 (R-Upper)    : %d DEG" % int(servo_angles[4]), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 270, 18, "CH5 (R-Lower)    : %d DEG" % int(servo_angles[5]), color=COLOR_GREEN)

                    # 绘制游戏覆盖 UI 以及返回/重启导航键
                    game.draw_game_overlay(pl.osd_img, display_size)
                    buttons.draw_game_nav(pl.osd_img)

                    # 绘制厂测模式顶部专属状态栏
                    if in_factory_test:
                        elapsed_s = time.ticks_diff(time.ticks_ms(), factory_game_start_ms) // 1000
                        draw_panel(pl.osd_img, scale_x(8), scale_y(8), scale_x(624), scale_y(38), border=(255, 255, 140, 0), bg=(255, 30, 20, 10))
                        draw_bold_string(pl.osd_img, scale_x(16), scale_y(15), scale_px(16),
                            "【厂测老化模式】软重启: %d/%d | 当前: %s (%ds/%ds) | 左下角退出" %
                            (factory_reboot_count, FACTORY_MAX_REBOOTS, factory_game_names[factory_game_index], elapsed_s, FACTORY_GAME_DURATION_SEC),
                            (255, 255, 210, 40))

                    # 如果游戏结束，清除原有游戏 UI，覆盖显示挑战结算界面并停留2秒后返回主菜单 (完美对齐机械手)
                    if game.game_over:
                        # 游戏结束/挑战结算：直接了当闭眼，不搞平滑过渡
                        motion_filter.reset_to(SERVO_DEFAULT_DEG)
                        eye_controller.update(SERVO_DEFAULT_DEG)
                        pl.osd_img.clear()

                        if game.mode == MODE_GAZE:
                            # 躲避模式死亡/结束结算：绿色半透明背景面罩
                            fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (180, 15, 38, 20), 1)
                            # 绘制金色奖杯
                            fill_rect(pl.osd_img, 482, 245, 60, 12, (255, 220, 160, 0), 1)
                            fill_rect(pl.osd_img, 507, 210, 10, 35, (255, 255, 215, 0), 1)
                            pl.osd_img.draw_circle(512, 175, 35, color=(255, 255, 215, 0), fill=True)
                            pl.osd_img.draw_circle(472, 175, 18, color=(255, 255, 215, 0), fill=False, thickness=4)
                            pl.osd_img.draw_circle(552, 175, 18, color=(255, 255, 215, 0), fill=False, thickness=4)

                            tx1 = 512 - 64
                            draw_bold_string(pl.osd_img, tx1, 310, 32, "你真棒！", color=(255, 255, 215, 0))

                            score_text = "存活了 %d 秒" % game.score
                            text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in score_text)
                            tx2 = 512 - int((text_len * 24) / 2)
                            pl.osd_img.draw_string_advanced(tx2, 360, 24, score_text, color=(255, 255, 255, 255))
                        else:
                            is_win = False
                            if game.mode == MODE_FOLLOW:
                                is_win = (game.follow_wins >= 3)
                            elif game.mode == MODE_STARING:
                                is_win = (game.staring_hp > 0)

                            if is_win:
                                # 成功：绿色半透明背景面罩
                                fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (180, 15, 38, 20), 1)
                                # 绘制金色奖杯
                                fill_rect(pl.osd_img, 482, 245, 60, 12, (255, 220, 160, 0), 1)
                                fill_rect(pl.osd_img, 507, 210, 10, 35, (255, 255, 215, 0), 1)
                                pl.osd_img.draw_circle(512, 175, 35, color=(255, 255, 215, 0), fill=True)
                                pl.osd_img.draw_circle(472, 175, 18, color=(255, 255, 215, 0), fill=False, thickness=4)
                                pl.osd_img.draw_circle(552, 175, 18, color=(255, 255, 215, 0), fill=False, thickness=4)

                                tx = 512 - 96
                                draw_bold_string(pl.osd_img, tx, 320, 32, "挑战成功", color=(255, 255, 215, 0))

                                cx = tx + 192 + 15
                                fill_rect(pl.osd_img, cx, 343, 40, 6, (255, 255, 215, 0), 1)
                                pl.osd_img.draw_line(cx, 343, cx, 323, color=(255, 255, 215, 0), thickness=3)
                                pl.osd_img.draw_line(cx, 323, cx+10, 336, color=(255, 255, 215, 0), thickness=3)
                                pl.osd_img.draw_line(cx+10, 336, cx+20, 313, color=(255, 255, 215, 0), thickness=3)
                                pl.osd_img.draw_line(cx+20, 313, cx+30, 336, color=(255, 255, 215, 0), thickness=3)
                                pl.osd_img.draw_line(cx+30, 336, cx+40, 323, color=(255, 255, 215, 0), thickness=3)
                                pl.osd_img.draw_line(cx+40, 323, cx+40, 343, color=(255, 255, 215, 0), thickness=3)
                                pl.osd_img.draw_circle(cx, 321, 3, color=(255, 255, 0, 0), fill=True)
                                pl.osd_img.draw_circle(cx+20, 311, 3, color=(255, 0, 0, 255), fill=True)
                                pl.osd_img.draw_circle(cx+40, 321, 3, color=(255, 0, 255, 0), fill=True)

                                if game.mode == MODE_STARING:
                                    score_text = "吃到星星: %d 个" % game.score
                                    text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in score_text)
                                    tx2 = 512 - int((text_len * 24) / 2)
                                    pl.osd_img.draw_string_advanced(tx2, 370, 24, score_text, color=(255, 255, 255, 255))
                            else:
                                # 失败：红色半透明背景面罩
                                fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (180, 45, 15, 15), 1)
                                # 绘制哭脸
                                pl.osd_img.draw_line(460, 175, 480, 190, color=(255, 140, 140, 160), thickness=4)
                                pl.osd_img.draw_line(560, 175, 540, 190, color=(255, 140, 140, 160), thickness=4)
                                pl.osd_img.draw_circle(480, 205, 5, color=(255, 0, 180, 255), fill=True)
                                pl.osd_img.draw_circle(540, 205, 5, color=(255, 0, 180, 255), fill=True)
                                pl.osd_img.draw_line(495, 235, 512, 225, color=(255, 255, 255, 255), thickness=3)
                                pl.osd_img.draw_line(512, 225, 529, 235, color=(255, 255, 255, 255), thickness=3)

                                tx = 512 - 128
                                draw_bold_string(pl.osd_img, tx, 320, 32, "挑战失败，加油", color=(255, 220, 80, 40))

                                if game.mode == MODE_STARING:
                                    score_text = "仅吃到星星: %d 个" % game.score
                                    text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in score_text)
                                    tx2 = 512 - int((text_len * 24) / 2)
                                    pl.osd_img.draw_string_advanced(tx2, 370, 24, score_text, color=(255, 255, 255, 255))

                    # 游戏模式下，必须刷新显示 OSD 绘制的 UI 画布，否则画面就会“死掉”停留在主菜单
                    pl.show_image(flag=osd_rotation)
                else:
                    # 主菜单/待机模式下：直接闭眼休眠，不搞平滑过渡
                    motion_filter.reset_to(SERVO_DEFAULT_DEG)
                    eye_controller.update(SERVO_DEFAULT_DEG)

                    if buttons.menu_bg_img is not None:
                        Display.show_image(buttons.menu_bg_img, 0, 0, Display.LAYER_OSD3, flag=osd_rotation)
                    else:
                        pl.osd_img.clear()
                        buttons.draw_menu(pl.osd_img)
                        pl.show_image(flag=osd_rotation)

                prev_in_menu = in_menu
                gc.collect()                    # 垃圾回收

        face_det.deinit()                       # 反初始化
        pl.destroy()                            # 销毁PipeLine实例
    except Exception as e:
        with open("/sdcard/error.log", "w") as f:
            try:
                import traceback
                traceback.print_exception(e, f)
            except:
                f.write(repr(e))
        raise e
