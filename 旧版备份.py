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

DISPLAY_ROTATION_MODE = 1      # 屏幕方向 (0: 正常横屏, 1: 旋转180度, 2: 旋转90度, 3: 旋转270度)
DISPLAY_MIRROR_MODE = 0        # 屏幕镜像 (0: 无镜像, 1: 左右镜面翻转/水平镜像, 2: 上下镜面翻转/垂直镜像)
SENSOR_HMIRROR = False         # 摄像头水平镜像
SENSOR_VFLIP = True           # 摄像头垂直翻转

# OSD 绘图坐标镜像配置
OSD_MIRROR_X = False           # OSD 左右镜像
OSD_MIRROR_Y = True            # OSD 上下镜像

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
# Channel 1: 左眼垂直偏转 (Left Eye Pitch)
# Channel 2: 右眼水平偏转 (Right Eye Yaw)
# Channel 3: 右眼垂直偏转 (Right Eye Pitch)
# Channel 4: 左眼睑眨眼 (Left Eyelid)
# Channel 5: 右眼睑眨眼 (Right Eyelid)
SERVO_MIN_DEG = [20, 20, 20, 20, 0, 0]
SERVO_MAX_DEG = [160, 160, 160, 160, 90, 90]
SERVO_DEFAULT_DEG = [90, 90, 90, 90, 90, 90]

# 舵机运动方向反向标志
YAW_REVERSE = True             # 水平偏转方向反向
PITCH_REVERSE = False          # 垂直偏转方向不反向

# 追踪灵敏度 (基础映射系数)
YAW_SENSITIVITY = 140.0        # 归一化偏差 [-0.5, 0.5] 乘以该系数映射为舵机偏转角
PITCH_SENSITIVITY = 110.0      # 垂直灵敏度

# 平滑滤波因子 (0.01 ~ 1.0, 越小动作越平滑平缓，防止舵机抖动)
TRACKING_ALPHA_YAW = 0.35
TRACKING_ALPHA_PITCH = 0.35

# 寻人待机扫视参数
SCAN_YAW_RANGE = 28            # 左右扫视角度范围
SCAN_SPEED = 2.0               # 扫视速度因子
# ==============================================================================

# 串口与控制配置 (与机械手 UART2 一致)
FOLLOW_UART_PORT = 2
FOLLOW_UART_BAUDRATE = 115200
FOLLOW_UART_SEND_INTERVAL_MS = 8
FOLLOW_UART_MIN_DELTA_DEG = 1
FOLLOW_UART_TX_PIN = 44
FOLLOW_UART_RX_PIN = 45

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


# 自动随机眨眼控制器（非阻塞状态机）
class BlinkController:
    def __init__(self, close_angle=30, open_angle=90):
        self.close_angle = close_angle
        self.open_angle = open_angle
        self.state = 0  # 0: 睁眼, 1: 闭眼
        self.next_blink_time = time.ticks_ms() + random.randint(3000, 7000)
        self.blink_end_time = 0

    def update(self):
        now = time.ticks_ms()
        if self.state == 0:
            if time.ticks_diff(now, self.next_blink_time) >= 0:
                self.state = 1
                self.blink_end_time = now + 150
                self.next_blink_time = now + random.randint(3000, 8000)
                return self.close_angle, self.close_angle
            else:
                return self.open_angle, self.open_angle
        else:
            if time.ticks_diff(now, self.blink_end_time) >= 0:
                self.state = 0
                return self.open_angle, self.open_angle
            else:
                return self.close_angle, self.close_angle


# 仿生眼球串口控制器
class EyeMechanismController:
    def __init__(self, enable=True, port=2, baudrate=115200, device_id=0x5A, cmd_set_angles=0x11, send_interval_ms=8, min_delta_deg=1, tx_pin=44, rx_pin=45):
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
        self.pinmux_ready = False
        self.rx_buffer = ""
        self.last_voice_play_ms = time.ticks_ms() - 3000

    def _resolve_uart_id(self):
        const_name = "UART%d" % self.port
        if hasattr(UART, const_name):
            return getattr(UART, const_name)
        return self.port

    def _ensure_pinmux(self):
        if self.pinmux_ready:
            return True
        try:
            fpioa = FPIOA()
            tx_func_name = "UART%d_TXD" % self.port
            rx_func_name = "UART%d_RXD" % self.port
            tx_func = getattr(FPIOA, tx_func_name)
            rx_func = getattr(FPIOA, rx_func_name)
            fpioa.set_function(self.tx_pin, tx_func)
            fpioa.set_function(self.rx_pin, rx_func)
            self.pinmux_ready = True
            return True
        except Exception as e:
            print("[WARN] pinmux setting failed:", e)
            return False

    def _ensure_uart(self):
        if self.uart is not None and self.ready:
            return True
        if not self._ensure_pinmux():
            return False
        try:
            resolved_uart_id = self._resolve_uart_id()
            self.uart = UART(resolved_uart_id, self.baudrate)
            self.ready = True
            return True
        except Exception as e:
            print("[WARN] Failed to open UART:", e)
            self.ready = False
            return False

    def _checksum(self, data):
        checksum = 0
        for item in data:
            checksum ^= item
        return checksum & 0xFF

    def _build_frame(self, servo_angles):
        payload_len = 12  # 6 通道 * 2 字节
        payload = bytearray(payload_len + 4)
        payload[0] = self.device_id
        payload[1] = self.cmd_set_angles
        payload[2] = payload_len
        for channel in range(6):
            angle_x10 = int(servo_angles[channel] * 10)
            if angle_x10 < 0:
                angle_x10 = 0
            elif angle_x10 > 1800:
                angle_x10 = 1800
            data_index = 3 + channel * 2
            payload[data_index] = angle_x10 & 0xFF
            payload[data_index + 1] = (angle_x10 >> 8) & 0xFF
        payload[-1] = self._checksum(payload[:-1])
        frame = bytearray(len(payload) + 1)
        frame[0] = 0xAA
        for i in range(len(payload)):
            frame[i+1] = payload[i]
        return frame

    def update(self, servo_angles):
        if not self.enable:
            return
        if not self._ensure_uart():
            return

        changed = False
        for i in range(6):
            if abs(int(servo_angles[i]) - int(self.last_servo[i])) >= self.min_delta_deg:
                changed = True
                break
        if not changed:
            return

        now = time.ticks_ms()
        if self.last_send_ms is not None and time.ticks_diff(now, self.last_send_ms) < self.send_interval_ms:
            return

        frame = self._build_frame(servo_angles)
        try:
            self.uart.write(frame)
            self.last_servo = [int(angle) for angle in servo_angles]
            self.tx_frames += 1
            self.last_send_ms = now
        except Exception as e:
            print("[WARN] UART write failed:", e)
            self.ready = False

    def play_voice(self, voice_id):
        now = time.ticks_ms()
        is_low_priority = (voice_id in (14, 15))

        if is_low_priority:
            if time.ticks_diff(now, self.last_voice_play_ms) < 2500:
                print("[VOICE] Low priority voice %d suppressed (cooldown active)" % voice_id)
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
            self.uart.write(frame)
            print("[VOICE] Sent play command for voice ID: %d" % voice_id)
        except Exception as e:
            print("[WARN] Failed to send play voice command:", e)

    def read_command(self):
        if not self._ensure_uart():
            return None
        if self.uart.any():
            try:
                data = self.uart.read()
                if data:
                    print("[UART RXD Raw Bytes]:", data)
                    self.rx_buffer += data.decode()
                    if "\n" in self.rx_buffer:
                        lines = self.rx_buffer.split("\n")
                        self.rx_buffer = lines[-1]
                        for line_str in reversed(lines[:-1]):
                            line_str = line_str.strip()
                            if line_str:
                                print("[UART RXD] Raw line:", line_str)
                            if line_str.startswith("CMD:"):
                                cmd_val = line_str[4:]
                                if cmd_val == "FOLLOW":
                                    return ("mode", MODE_FOLLOW)
                                elif cmd_val == "MIMIC":
                                    return ("mode", MODE_STARING)
                                elif cmd_val == "RPS":
                                    return ("mode", MODE_GAZE)
                                elif cmd_val == "MENU":
                                    return ("menu", None)
                                elif cmd_val == "RESTART":
                                    return ("restart", None)
            except Exception as e:
                print("[WARN] UART read failed:", e)
        return None


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
            (120, 200, 780, 75, MODE_FOLLOW, "", "视线躲猫猫", "", "人脸去靠近绿色眼球跟着它的视线"),
            (120, 305, 780, 75, MODE_STARING, "", "木头人模式", "", "123木头人！红灯绝对静止，绿灯可以活动"),
            (120, 410, 780, 75, MODE_GAZE, "", "大眼躲避球", "", "移动人脸框躲避屏幕上运动的眼球")
        )

        # 底部返回与重启菜单按钮 (尺寸与位置完全同步机械手 100% 对齐)
        self.menu_button = (20, 535, 120, 45, "返回菜单")
        self.restart_button = (884, 535, 120, 45, "重新开始")
        
        # 音量控制状态 (范围 1~7)
        self.volume = 5
        self.vol_button = (844, 535, 160, 45)

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
        points = self._read_points()
        if not len(points):
            return None

        now = time.ticks_ms()
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
            # 检查是否点击了右下角的音量按钮
            vx, vy, vw, vh = self.vol_button
            if pt.x >= vx and pt.x <= vx+vw and pt.y >= vy and pt.y <= vy+vh:
                self.last_press_ms = now
                # 音量分为 1, 3, 5, 7 四档进行循环切换
                if self.volume == 1:
                    self.volume = 3
                elif self.volume == 3:
                    self.volume = 5
                elif self.volume == 5:
                    self.volume = 7
                else:
                    self.volume = 1
                
                # 实时刷新背景图上的音量按钮显示
                if self.menu_bg_img is not None:
                    self.draw_volume_button(self.menu_bg_img)
                return ("volume", self.volume)

            for b in self.menu_cards:
                x, y, w, h, mode, _, _, _, _ = b
                if pt.x >= x and pt.x <= x+w and pt.y >= y and pt.y <= y+h:
                    self.last_press_ms = now
                    return ("mode", mode)
            return None

        mx, my, mw, mh, _ = self.menu_button
        if pt.x >= mx and pt.x <= mx+mw and pt.y >= my and pt.y <= my+mh:
            self.last_press_ms = now
            return ("menu", None)

        rx, ry, rw, rh, _ = self.restart_button
        if pt.x >= rx and pt.x <= rx+rw and pt.y >= ry and pt.y <= ry+rh:
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

    def draw_volume_button(self, img):
        x, y, w, h = self.vol_button
        # 1. 绘制暗 slate-dark 的实色小块作为毛玻璃底色
        img.draw_rectangle(x, y, w, h, color=(25, 30, 38), fill=True)
        # 2. 绘制亮蓝色细边框 (使用 3-tuple 颜色在 RGB565 画布上绘制，否则会抛出 TypeError)
        img.draw_rectangle(x, y, w, h, color=(80, 160, 220), thickness=1)
        # 3. 绘制当前音量状态文字 (居中，使用 3-tuple 颜色)
        vol_str = "音量: %d" % self.volume
        img.draw_string_advanced(x + 35, y + 10, 20, vol_str, color=(255, 255, 255))

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

        # 模式 1: 视线跟随对齐挑战 (过关模式，最多4关)
        if self.mode == MODE_FOLLOW:
            if self.game_over:
                if time.ticks_diff(now, self.game_over_start_ms) >= 2000:
                    self.should_exit_to_menu = True
                return

            # 如果5局已满，做关卡结算
            if self.follow_rounds >= 5 and not self.follow_round_active:
                if self.follow_wins >= 3:
                    if self.follow_level < 4:
                        self.follow_level += 1
                        self.follow_rounds = 0
                        self.follow_wins = 0
                        if self.follow_level == 4:
                            self.follow_speed = 20
                        else:
                            self.follow_speed = 4 + (self.follow_level - 1) * 3
                        self.message = "挑战通过！晋级第 %d 关！" % self.follow_level
                        self.follow_round_active = False
                        self.game_over_start_ms = now
                        time.sleep_ms(1500)
                    else:
                        self.game_over = True
                        self.game_over_start_ms = now
                        self.message = "恭喜通关！挑战成功！"
                        if eye_controller:
                            eye_controller.play_voice(21)
                        return
                else:
                    self.game_over = True
                    self.game_over_start_ms = now
                    self.message = "挑战失败！未跟上视线"
                    if eye_controller:
                        eye_controller.play_voice(22)
                    return

            # 开启新的一轮
            if not self.follow_round_active and self.follow_rounds < 5:
                # 检查是否可能达到 3 胜
                if 5 - self.follow_rounds + self.follow_wins < 3:
                    self.game_over = True
                    self.game_over_start_ms = now
                    self.message = "挑战失败！未跟上视线"
                    if eye_controller:
                        eye_controller.play_voice(22)
                    return
                self.follow_rounds += 1
                self.follow_round_start_ms = now
                self.follow_round_active = True
                self.follow_overlap_duration = 0
                self.follow_last_overlap_time = 0
                self.follow_target_tx = random.randint(50, 850)
                self.follow_target_ty = random.randint(150, 450)
                self.message = "第 %d 关 (第 %d/5 轮): 跟随绿色眼球！" % (self.follow_level, self.follow_rounds)

            # 局内追踪与判定
            if self.follow_round_active:
                # 第三、四关时间延长到 10 秒以对应高速移动，第一、二关依然为 6 秒
                round_limit_ms = 10000 if self.follow_level >= 3 else 6000
                elapsed = time.ticks_diff(now, self.follow_round_start_ms)
                remain_ms = round_limit_ms - elapsed

                if remain_ms <= 0:
                    self.follow_round_active = False
                    self.follow_last_collision_state = False
                    self.message = "第 %d/5 轮: 未跟上视线！" % self.follow_rounds
                    if eye_controller:
                        eye_controller.play_voice(20)
                    time.sleep_ms(1000)
                    return

                # 移动绿色眼球
                fdx = self.follow_target_tx - self.follow_target_x
                fdy = self.follow_target_ty - self.follow_target_y
                fdist = math.sqrt(fdx*fdx + fdy*fdy)

                if fdist < self.follow_speed:
                    self.follow_target_tx = random.randint(50, 850)
                    self.follow_target_ty = random.randint(150, 450)
                else:
                    self.follow_target_x = int(self.follow_target_x + (fdx / fdist) * self.follow_speed)
                    self.follow_target_y = int(self.follow_target_y + (fdy / fdist) * self.follow_speed)

                overlap = False
                if has_face and face_rect is not None:
                    fx, fy, fw, fh = face_rect
                    if not (fx + fw < self.follow_target_x or self.follow_target_x + 100 < fx or fy + fh < self.follow_target_y or self.follow_target_y + 100 < fy):
                        overlap = True

                self.follow_last_collision_state = overlap

                if overlap:
                    if self.follow_last_overlap_time == 0:
                        self.follow_last_overlap_time = now
                    else:
                        dt = time.ticks_diff(now, self.follow_last_overlap_time)
                        self.follow_overlap_duration += dt
                        self.follow_last_overlap_time = now

                    if self.follow_overlap_duration >= 1200: # 累计重合 1.2 秒
                        self.follow_wins += 1
                        self.follow_round_active = False
                        self.follow_last_collision_state = False
                        self.message = "第 %d/5 轮: 成功跟上！" % self.follow_rounds
                        if eye_controller:
                            eye_controller.play_voice(19)
                        time.sleep_ms(1000)

                        # 成功达到 3 次，直接晋级下一关或通关
                        if self.follow_wins >= 3:
                            if self.follow_level < 4:
                                self.follow_level += 1
                                self.follow_rounds = 0
                                self.follow_wins = 0
                                if self.follow_level == 4:
                                    self.follow_speed = 20  # 第四关速度翻倍
                                else:
                                    self.follow_speed = 4 + (self.follow_level - 1) * 3
                                self.message = "挑战通过！晋级第 %d 关！" % self.follow_level
                                self.game_over_start_ms = now
                                time.sleep_ms(1500)
                            else:
                                self.game_over = True
                                self.game_over_start_ms = now
                                self.message = "恭喜通关！挑战成功！"
                                if eye_controller:
                                    eye_controller.play_voice(21)
                        return
                else:
                    self.follow_last_overlap_time = 0
                    self.follow_overlap_duration = 0  # 断开对准立即重置清零，不可保留蓄力

                self.message = "第%d/5轮 (胜:%d): 靠近它！倒计时 %.1f秒" % (self.follow_rounds, self.follow_wins, remain_ms/1000.0)

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
                self.staring_state_duration_ms = random.randint(2500, 4500)
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

            # 随机产生金星
            if not self.staring_star_active:
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
                    self.staring_star_active = False  # 被吃掉，下一帧产生新位置

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
                    self.staring_state_duration_ms = random.randint(2500, 4500)
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
                        if eye_controller:
                            eye_controller.play_voice(20)
                        self.staring_lock_cx = cx
                        self.staring_lock_cy = cy
                    else:
                        dx = cx - self.staring_lock_cx
                        dy = cy - self.staring_lock_cy

                        # 根据人脸大小级别动态确定允许的抖动阈值量 (更远处人脸偏小，近处人脸偏大)
                        # 用户要求抖动容差允许大一些，因此系数设置为 0.20 倍人脸宽度，且最远也有至少 55 像素的容差
                        dynamic_thresh = int(fw * 0.20)
                        if dynamic_thresh < 55:
                            dynamic_thresh = 55

                        if math.sqrt(dx*dx + dy*dy) > dynamic_thresh:
                            self.staring_hp -= 34
                            self.staring_warn_flash_ms = now
                            self.staring_lock_cx = cx
                            self.staring_lock_cy = cy
                else:
                    if self.staring_lock_cx is not None:
                        self.staring_hp -= 34
                        self.staring_warn_flash_ms = now
                        if eye_controller:
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

    # 获得对应模式下的舵机目标角度
    def get_servo_angles(self, follow_yaw, follow_pitch, blink_angles, display_size):
        if self.mode == MODE_FOLLOW:
            if self.game_over:
                return [90, 90, 90, 90, 30, 30] # 闭眼

            ecx = self.follow_target_x + 50
            ecy = self.follow_target_y + 50

            eye_x_norm = ecx / display_size[0]
            eye_y_norm = ecy / display_size[1]
            err_x = eye_x_norm - 0.5
            err_y = eye_y_norm - 0.5

            if YAW_REVERSE:
                err_x = -err_x
            if PITCH_REVERSE:
                err_y = -err_y

            target_yaw = 90.0 - err_x * YAW_SENSITIVITY
            target_pitch = 90.0 - err_y * PITCH_SENSITIVITY

            target_yaw = max(SERVO_MIN_DEG[0], min(SERVO_MAX_DEG[0], target_yaw))
            target_pitch = max(SERVO_MIN_DEG[1], min(SERVO_MAX_DEG[1], target_pitch))
            return [target_yaw, target_pitch, target_yaw, target_pitch, 90, 90]

        elif self.mode == MODE_STARING:
            if self.game_over:
                return [90, 90, 90, 90, 30, 30] # 闭眼
            if self.staring_state == 1:
                # 红灯：双眼大睁盯紧人脸！
                return [follow_yaw, follow_pitch, follow_yaw, follow_pitch, 90, 90]
            else:
                # 绿灯：懒洋洋斜向下看并且半闭眼
                return [90, 120, 90, 120, 40, 40]

        elif self.mode == MODE_GAZE:
            # 机器人眼球物理跟随屏幕上运动的小眼球方块
            if self.game_over:
                return [90, 90, 90, 90, 30, 30] # 挑战失败闭眼

            # 计算小眼球方块的中心点坐标
            ecx = self.eye_x + 50
            ecy = self.eye_y + 50

            # 计算相对屏幕的物理归一化偏移量
            eye_x_norm = ecx / display_size[0]
            eye_y_norm = ecy / display_size[1]
            err_x = eye_x_norm - 0.5
            err_y = eye_y_norm - 0.5

            # 反向计算舵机旋转以跟随方块
            if YAW_REVERSE:
                err_x = -err_x
            if PITCH_REVERSE:
                err_y = -err_y

            target_yaw = 90.0 - err_x * YAW_SENSITIVITY
            target_pitch = 90.0 - err_y * PITCH_SENSITIVITY

            target_yaw = max(SERVO_MIN_DEG[0], min(SERVO_MAX_DEG[0], target_yaw))
            target_pitch = max(SERVO_MIN_DEG[1], min(SERVO_MAX_DEG[1], target_pitch))

            # 强制不加低通滤波器以让物理眼球显得更加灵敏凝视
            return [target_yaw, target_pitch, target_yaw, target_pitch, 90, 90]

        return [90, 90, 90, 90, 90, 90]

    def draw_game_overlay(self, img, display_size):
        COLOR_GREEN = (255, 0, 255, 0)
        COLOR_RED = (255, 255, 0, 0)

        # 1. 顶部半透明背景条和信息文字
        draw_flat_panel(img, 200, 30, 624, 70, border=(255, 100, 160, 220), bg=(255, 255, 255, 255))

        text_color = COLOR_RED if (self.mode == MODE_GAZE and self.last_collision_state) else (255, 20, 24, 30)
        img.draw_string_advanced(230, 50, 24, self.message, color=text_color)

        # 2. 绘制模式特殊 UI 元素
        if self.mode == MODE_FOLLOW:
            # 绘制对齐挑战的记分板
            draw_flat_panel(img, 760, 125, 230, 120, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))
            img.draw_string_advanced(780, 150, 20, "关卡: 第 %d/4 关" % self.follow_level, color=(255, 20, 24, 30))
            img.draw_string_advanced(780, 182, 20, "轮数: 第 %d/5 轮" % self.follow_rounds, color=(255, 20, 24, 30))
            img.draw_string_advanced(780, 212, 20, "成功: %d/3 次" % self.follow_wins, color=(255, 20, 24, 30))

            # 绘制重合时间进度条
            draw_flat_panel(img, 760, 260, 230, 45, border=(255, 80, 140, 200), bg=(255, 255, 255, 255))
            overlap_pct = min(1.0, self.follow_overlap_duration / 1200.0)
            draw_progress_bar(img, 770, 270, 210, 25, overlap_pct, COLOR_GREEN)

            # 绘制绿色眼球目标 (大小 100x100)
            box_thickness = 4 if self.follow_last_collision_state else 2
            box_color = COLOR_GREEN

            ex = int(self.follow_target_x)
            ey = int(self.follow_target_y)
            img.draw_rectangle(ex, ey, 100, 100, color=box_color, thickness=box_thickness)

            ecx = ex + 50
            ecy = ey + 50
            img.draw_circle(ecx, ecy, 35, color=box_color, thickness=1)
            img.draw_circle(ecx, ecy, 12, color=box_color, thickness=1, fill=True)
            img.draw_line(ecx - 35, ecy, ecx - 18, ecy, color=box_color, thickness=1)
            img.draw_line(ecx + 18, ecy, ecx + 35, ecy, color=box_color, thickness=1)
            img.draw_line(ecx, ecy - 35, ecx, ecy - 18, color=box_color, thickness=1)
            img.draw_line(ecx, ecy + 18, ecx, ecy + 35, color=box_color, thickness=1)

            if self.follow_last_collision_state:
                img.draw_string_advanced(ex + 15, ey - 25, 20, "LOCKING!", color=COLOR_GREEN)

        elif self.mode == MODE_STARING:
            # 绘制 123 木头人的记分板
            draw_flat_panel(img, 760, 125, 230, 120, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))
            img.draw_string_advanced(780, 150, 20, "最高吃星: %d 个" % self.high_score_staring, color=(255, 20, 24, 30))
            img.draw_string_advanced(780, 182, 20, "当前吃星: %d 个" % self.score, color=(255, 20, 24, 30))

            # 计算并绘制剩余时间
            remain_sec = 30 - (time.ticks_diff(time.ticks_ms(), self.staring_start_time) // 1000)
            if remain_sec < 0: remain_sec = 0
            img.draw_string_advanced(780, 212, 20, "剩余时间: %d 秒" % remain_sec, color=(255, 20, 24, 30))

            # 绘制生命值血条 (HP Bar)
            draw_flat_panel(img, 760, 260, 230, 45, border=(255, 80, 140, 200), bg=(255, 255, 255, 255))
            draw_progress_bar(img, 770, 270, 210, 25, self.staring_hp / 100.0, COLOR_RED)

            # 绘制发光星星
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
                img.draw_string_advanced(self.staring_star_x - 10, self.staring_star_y - 25, 16, "STAR", color=COLOR_YELLOW)

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

            if self.last_collision_state:
                img.draw_string_advanced(ex + 10, ey - 25, 20, "DANGER!", color=COLOR_RED)


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


if __name__ == "__main__":
    import uos
    try:
        uos.dupterm(None)
        print("[LOG] Duplicate terminal disabled on UART.")
    except Exception as e:
        print("[LOG] dupterm not supported or failed:", e)

    import os

    try:
        display_mode = "ek79007"
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

        # 初始化眨眼控制器
        blink_ctrl = BlinkController(
            close_angle=SERVO_MIN_DEG[4] + 30,
            open_angle=SERVO_MAX_DEG[4]
        )

        # 初始化触摸按键组件
        buttons = TouchButtons()
        buttons.prepare_menu()

        # 启动触摸屏轮询监听线程
        _thread.start_new_thread(gt911_polling_thread, (buttons,))

        # 初始化 PipeLine (正常传入 display_mode 与 size 以完成 1024x600 摄像头铺满配置)
        pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode, display_size=display_size)

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

        # 激活 PipeLine (触发被 monkey patch 拦截 of Display.init，自动实现 to_ide=True 注入)
        pl.create(to_ide=USE_CANMV, hmirror=sensor_hmirror, vflip=sensor_vflip)

        display_size = pl.get_display_size()

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
        face_det = FaceDetectionApp(kmodel_path, model_input_size=[640, 640], confidence_threshold=confidence_threshold, nms_threshold=nms_threshold, top_k=top_k, rgb888p_size=rgb888p_size, display_size=display_size, debug_mode=0)
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

        prev_in_menu = None

        while True:
            # A. 读取并处理触摸事件动作 (如果有后门标志且首次进入，忽略触摸直接跳转进入)
            action = buttons.read_action(in_menu)
            if BACKDOOR_MODE != 0 and not backdoor_triggered:
                backdoor_triggered = True
                forced_mode = BACKDOOR_MODE - 1
                game.set_mode(forced_mode)
                in_menu = False
                if forced_mode == MODE_FOLLOW:
                    eye_controller.play_voice(11)
                elif forced_mode == MODE_STARING:
                    eye_controller.play_voice(12)
                elif forced_mode == MODE_GAZE:
                    eye_controller.play_voice(13)
            else:
                # 读取 ASR Pro 串口命令并覆盖屏幕触摸动作
                uart_action = eye_controller.read_command()
                if uart_action is not None:
                    action = uart_action

                if action is not None:
                    if action[0] == "mode":
                        game.set_mode(action[1])
                        in_menu = False
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
                    elif action[0] == "menu":
                        in_menu = True
                        game.reset()
                        eye_controller.play_voice(10)
                        face_detected_voice_played = False
                        face_missing_voice_played = False
                        face_missing_start_time = 0
                        last_has_face = False
                    elif action[0] == "restart":
                        game.reset()
                        game.set_mode(game.mode)
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

            with ScopedTiming("total", 0):
                # 只有在非主菜单，即实际游戏中，才执行人脸推理与摄像头帧处理
                if not in_menu:
                    img = pl.get_frame()            # 获取当前帧捕获
                    dets = face_det.run(img)         # 推理当前帧

                    # 清空 OSD 图像画布
                    pl.osd_img.clear()

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
                        x, y, w, h = map(lambda x: int(round(x, 0)), best_det[:4])
                        cx = x + w // 2
                        cy = y + h // 2
                        face_center = (cx, cy)

                        # 归一化人脸中心偏差 (-0.5 ~ 0.5)
                        x_norm = cx / display_size[0]
                        y_norm = cy / display_size[1]
                        err_x = x_norm - 0.5
                        err_y = y_norm - 0.5

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

                        # 镜像与反向处理
                        if YAW_REVERSE:
                            err_x = -err_x
                        if PITCH_REVERSE:
                            err_y = -err_y

                        # 计算人脸追踪目标角度
                        target_yaw = 90.0 - err_x * (YAW_SENSITIVITY * gear_gain)
                        target_pitch = 90.0 - err_y * (PITCH_SENSITIVITY * gear_gain)

                        target_yaw = max(SERVO_MIN_DEG[0], min(SERVO_MAX_DEG[0], target_yaw))
                        target_pitch = max(SERVO_MIN_DEG[1], min(SERVO_MAX_DEG[1], target_pitch))

                        # 平滑滤波计算
                        yaw_deg = filter_yaw.update(target_yaw)
                        pitch_deg = filter_pitch.update(target_pitch)

                        # 镜像反向转换（绘制 OSD 对齐人脸）
                        draw_x = (display_size[0] - x - w) if OSD_MIRROR_X else x
                        draw_y = (display_size[1] - y - h) if OSD_MIRROR_Y else y
                        draw_cx = (display_size[0] - cx) if OSD_MIRROR_X else cx
                        draw_cy = (display_size[1] - cy) if OSD_MIRROR_Y else cy

                        face_rect = (draw_x, draw_y, w, h)

                        # 绘制瞄准框与准星
                        if game.mode == MODE_FOLLOW or (game.mode == MODE_STARING and not game.game_over):
                            pl.osd_img.draw_rectangle(draw_x, draw_y, w, h, color=COLOR_GREEN, thickness=4)
                            pl.osd_img.draw_line(draw_cx - 15, draw_cy, draw_cx + 15, draw_cy, color=COLOR_GREEN, thickness=1)
                            pl.osd_img.draw_line(draw_cx, draw_cy - 15, draw_cx, draw_cy + 15, color=COLOR_GREEN, thickness=1)
                            pl.osd_img.draw_string_advanced(draw_x, draw_y - 30, 24, "TARGET DETECTED", color=COLOR_GREEN)
                        elif game.mode == MODE_GAZE and not game.game_over:
                            # 躲避模式下画绿色人脸框表示玩家当前安全状态
                            face_color = (255, 255, 0, 0) if game.last_collision_state else COLOR_GREEN
                            pl.osd_img.draw_rectangle(draw_x, draw_y, w, h, color=face_color, thickness=3)
                            pl.osd_img.draw_string_advanced(draw_x, draw_y - 25, 20, "USER FACE", color=face_color)

                        scan_phase = 0.0
                    else:
                        # 待机正弦扫视
                        scan_phase += 0.04
                        target_yaw = 90.0 + SCAN_YAW_RANGE * math.sin(scan_phase)
                        target_pitch = 90.0

                        yaw_deg = filter_yaw.update(target_yaw)
                        pitch_deg = filter_pitch.update(target_pitch)

                        dist_gear = "SCAN"
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
                        if face_missing_start_time > 0 and time.ticks_diff(time.ticks_ms(), face_missing_start_time) >= 3000:
                            if not face_missing_voice_played:
                                if game.mode in (MODE_FOLLOW, MODE_STARING, MODE_GAZE):
                                    eye_controller.play_voice(14)  # 播报“正在寻找”
                                face_missing_voice_played = True

                    # 更新眨眼
                    left_eyelid, right_eyelid = blink_ctrl.update()
                    blink_angles = [left_eyelid, right_eyelid]

                    # 更新游戏逻辑状态机
                    game.update(has_face, face_rect, display_size, eye_controller)

                    # 组合成 6 轴舵机帧并写入串口 (躲避模式传入显示屏参数由状态机处理)
                    servo_angles = game.get_servo_angles(yaw_deg, pitch_deg, blink_angles, display_size)
                    eye_controller.update(servo_angles)

                    # 退出判断
                    if game.should_exit_to_menu:
                        in_menu = True
                        game.reset()
                        eye_controller.play_voice(10)  # 返回菜单播报
                        face_detected_voice_played = False
                        face_missing_voice_played = False
                        face_missing_start_time = 0
                        last_has_face = False
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

                    dx = (vis_yaw - 90.0) / 45.0
                    dy = (90.0 - vis_pitch) / 45.0
                    dx = max(-1.0, min(1.0, dx))
                    dy = max(-1.0, min(1.0, dy))

                    offset_x = int(dx * d_max)
                    offset_y = int(dy * d_max)

                    if servo_angles[4] < 55:  # 眨眼/闭眼状态
                        pl.osd_img.draw_line(x1 - R, y1, x1 + R, y1, color=COLOR_GREEN, thickness=2)
                    else:
                        pl.osd_img.draw_circle(x1, y1, R, color=COLOR_GREEN, thickness=2)
                        pl.osd_img.draw_circle(x1 + offset_x, y1 + offset_y, r, color=COLOR_GREEN, thickness=2, fill=True)

                    if servo_angles[5] < 55:
                        pl.osd_img.draw_line(x2 - R, y2, x2 + R, y2, color=COLOR_GREEN, thickness=2)
                    else:
                        pl.osd_img.draw_circle(x2, y2, R, color=COLOR_GREEN, thickness=2)
                        pl.osd_img.draw_circle(x2 + offset_x, y2 + offset_y, r, color=COLOR_GREEN, thickness=2, fill=True)

                    pl.osd_img.draw_string_advanced(x1 - 20, y1 + R + 5, 16, "EYE STATE", color=COLOR_GREEN)

                    # 绘制舵机调试仪表盘 (仅在跟随模式下显示)
                    if False:
                        pl.osd_img.draw_string_advanced(30, 80, 22, "SERVO DASHBOARD", color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 115, 18, "RANGE GEAR   : %s (x%.1f)" % (dist_gear, gear_gain), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 145, 18, "CH0 (L-Yaw)  : %d DEG" % int(yaw_deg), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 170, 18, "CH1 (L-Pitch): %d DEG" % int(pitch_deg), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 195, 18, "CH2 (R-Yaw)  : %d DEG" % int(yaw_deg), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 220, 18, "CH3 (R-Pitch): %d DEG" % int(pitch_deg), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 245, 18, "CH4 (L-Eyelid): %d DEG" % int(left_eyelid), color=COLOR_GREEN)
                        pl.osd_img.draw_string_advanced(30, 270, 18, "CH5 (R-Eyelid): %d DEG" % int(right_eyelid), color=COLOR_GREEN)

                    # 绘制游戏覆盖 UI 以及返回/重启导航键
                    game.draw_game_overlay(pl.osd_img, display_size)
                    buttons.draw_game_nav(pl.osd_img)

                    # 如果游戏结束，清除原有游戏 UI，覆盖显示挑战结算界面并停留2秒后返回主菜单 (完美对齐机械手)
                    if game.game_over:
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
                    # 主菜单模式下，眼球回正，闭眼眨动
                    eye_controller.update([90, 90, 90, 90, 90, 90])

                    if buttons.menu_bg_img is not None:
                        Display.show_image(buttons.menu_bg_img, 0, 0, Display.LAYER_OSD3, flag=osd_rotation)
                    else:
                        pl.osd_img.clear()
                        buttons.draw_menu(pl.osd_img)
                        pl.show_image(flag=osd_rotation)

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
