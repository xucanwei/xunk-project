'''
Demo: Hand Fruit Ninja Performance Test (Index & Middle Fingers Slicing + Hand Framework Drawing)
Platform: CanMV K230 (Standalone test script)
Description: Play Fruit Ninja using Hand movement! Slices fruits using the midpoint of index & middle finger tips. Draws hand skeleton framework on OSD.
'''
import os, sys, ujson, gc, math, random, time, _thread

# 异常日志记录
try:
    import media.display
    from _media import Display as OriginalDisplay

    class PatchedDisplayWrapper:
        @staticmethod
        def init(display_type, width, height, osd_num=1, to_ide=False):
            print("[PATCH] Intercepted Display.init: forcing to_ide=True for 7-inch MIPI screen")
            return OriginalDisplay.init(display_type, width=width, height=height, osd_num=osd_num, to_ide=True)

        @staticmethod
        def show_image(img, x=0, y=0, layer=None, flag=None):
            try:
                return OriginalDisplay.show_image(img)
            except Exception as e:
                if layer is None:
                    return OriginalDisplay.show_image(img, x, y)
                return OriginalDisplay.show_image(img, x, y, layer, flag)

    for attr in dir(OriginalDisplay):
        if not attr.startswith('__') and attr not in ('init', 'show_image'):
            setattr(PatchedDisplayWrapper, attr, getattr(OriginalDisplay, attr))

    media.display.Display = PatchedDisplayWrapper
    if 'media.display' in sys.modules:
        sys.modules['media.display'].Display = PatchedDisplayWrapper

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
    import aicube
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
# 【全局配置】
USE_CANMV = False
DISPLAY_ROTATION_MODE = 1
DISPLAY_MIRROR_MODE = 0
SENSOR_HMIRROR = False
SENSOR_VFLIP = True
OSD_MIRROR_X = False
OSD_MIRROR_Y = True

DISPLAY_WIDTH = 1024
DISPLAY_HEIGHT = 600
RGB888P_SIZE = [640, 360]

# 舵机与串口定义
TRACKING_ALPHA_YAW = 0.35
TRACKING_ALPHA_PITCH = 0.35
SCAN_YAW_RANGE = 28
FOLLOW_UART_PORT = 2
FOLLOW_UART_BAUDRATE = 115200
FOLLOW_UART_TX_PIN = 44
FOLLOW_UART_RX_PIN = 45
FOLLOW_UART_SEND_INTERVAL_MS = 8
FOLLOW_UART_MIN_DELTA_DEG = 1

SERVO_MIN_DEG = [20, 20, 20, 20, 0, 0]
SERVO_MAX_DEG = [160, 160, 160, 160, 90, 90]
YAW_REVERSE = True
PITCH_REVERSE = False
YAW_SENSITIVITY = 140.0
PITCH_SENSITIVITY = 110.0

# ==============================================================================
# 【基础工具方法】
def scale_px(value):
    return int(value * DISPLAY_WIDTH / 640)

def fill_rect(img, x, y, w, h, color, step=2):
    step = scale_px(step)
    for yy in range(y, y+h, step):
        img.draw_line(x, yy, x+w, yy, color=color, thickness=step)

def draw_bold_string(img, x, y, size, text, color):
    img.draw_string_advanced(x, y, size, text, color=color)
    img.draw_string_advanced(x + 1, y, size, text, color=color)
    img.draw_string_advanced(x, y + 1, size, text, color=color)
    img.draw_string_advanced(x + 1, y + 1, size, text, color=color)

def draw_flat_panel(img, x, y, w, h, border=(255,90,90,90), bg=(255,20,20,20)):
    fill_rect(img, x, y, w, h, bg, 3)
    img.draw_rectangle(x, y, w, h, color=border, thickness=scale_px(1))

# ==============================================================================
# 【眼球控制与滤波】
class SmoothFilter:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.last_val = None

    def update(self, val):
        if self.last_val is None:
            self.last_val = val
        else:
            self.last_val = self.alpha * val + (1.0 - self.alpha) * self.last_val
        return self.last_val

class BlinkController:
    def __init__(self, close_angle, open_angle):
        self.close_angle = close_angle
        self.open_angle = open_angle
        self.blink_active = False
        self.blink_start_ms = 0
        self.blink_duration_ms = 220

    def trigger_blink(self):
        self.blink_active = True
        self.blink_start_ms = time.ticks_ms()

    def update(self):
        if not self.blink_active:
            return self.open_angle, self.open_angle
        elapsed = time.ticks_diff(time.ticks_ms(), self.blink_start_ms)
        if elapsed >= self.blink_duration_ms:
            self.blink_active = False
            return self.open_angle, self.open_angle
        half_dur = self.blink_duration_ms // 2
        if elapsed < half_dur:
            pct = elapsed / half_dur
            deg = self.open_angle - (self.open_angle - self.close_angle) * pct
        else:
            pct = (elapsed - half_dur) / half_dur
            deg = self.close_angle + (self.open_angle - self.close_angle) * pct
        return deg, deg

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
        payload_len = 12
        payload = bytearray(payload_len + 4)
        payload[0] = self.device_id
        payload[1] = self.cmd_set_angles
        payload[2] = payload_len
        for channel in range(6):
            angle_x10 = int(servo_angles[channel] * 10)
            if angle_x10 < 0: angle_x10 = 0
            elif angle_x10 > 1800: angle_x10 = 1800
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
        if not self.enable: return
        if not self._ensure_uart(): return

        changed = False
        for i in range(6):
            if abs(int(servo_angles[i]) - int(self.last_servo[i])) >= self.min_delta_deg:
                changed = True
                break
        if not changed: return

        now = time.ticks_ms()
        if self.last_send_ms is not None and time.ticks_diff(now, self.last_send_ms) < self.send_interval_ms:
            return

        frame = self._build_frame(servo_angles)
        try:
            self.uart.write(frame)
            self.last_servo = [int(angle) for angle in servo_angles]
            self.last_send_ms = now
        except Exception as e:
            print("[WARN] UART write failed:", e)
            self.ready = False

    def play_voice(self, voice_id):
        now = time.ticks_ms()
        is_low_priority = (voice_id in (14, 15))
        if is_low_priority and time.ticks_diff(now, self.last_voice_play_ms) < 2500:
            return
        self.last_voice_play_ms = now

        if not self._ensure_uart(): return
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
        except Exception as e:
            print("[WARN] Failed to play voice:", e)

# ==============================================================================
# 【半圆/切开水果绘制助手】
def draw_semi_fruit(img, cx, cy, r, angle_deg, peel_color, flesh_color, is_left_half):
    base_angle = math.radians(angle_deg)
    start_angle = base_angle if is_left_half else base_angle + math.pi

    steps = 10
    # 填充半圆果肉
    for i in range(steps + 1):
        theta = start_angle + (math.pi * i / steps)
        px = cx + r * math.cos(theta)
        py = cy + r * math.sin(theta)
        img.draw_line(int(cx), int(cy), int(px), int(py), color=flesh_color, thickness=1)

    prev_px, prev_py = None, None
    for i in range(steps + 1):
        theta = start_angle + (math.pi * i / steps)
        px = cx + r * math.cos(theta)
        py = cy + r * math.sin(theta)
        if prev_px is not None:
            img.draw_line(int(prev_px), int(prev_py), int(px), int(py), color=peel_color, thickness=3)
        prev_px, prev_py = px, py

    x_start = cx + r * math.cos(start_angle)
    y_start = cy + r * math.sin(start_angle)
    x_end = cx + r * math.cos(start_angle + math.pi)
    y_end = cy + r * math.sin(start_angle + math.pi)
    img.draw_line(int(x_start), int(y_start), int(x_end), int(y_end), color=(255, 255, 255, 255), thickness=2)

# ==============================================================================
# 【游戏元素实体类】
class Fruit:
    def __init__(self, ftype, x, y, vx, vy, radius):
        self.type = ftype
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = radius
        self.sliced = False
        self.split_angle = 0
        self.left_half_offset_x = 0
        self.right_half_offset_x = 0

        if ftype == "watermelon":
            self.peel_color = (255, 34, 139, 34)
            self.flesh_color = (255, 220, 20, 60)
        elif ftype == "apple":
            self.peel_color = (255, 255, 0, 0)
            self.flesh_color = (255, 255, 253, 208)
        elif ftype == "orange":
            self.peel_color = (255, 255, 140, 0)
            self.flesh_color = (255, 255, 165, 0)
        elif ftype == "banana":
            self.peel_color = (255, 255, 215, 0)
            self.flesh_color = (255, 255, 253, 230)
        else: # bomb
            self.peel_color = (255, 40, 40, 40)
            self.flesh_color = (255, 100, 100, 100)

    def draw(self, img):
        if not self.sliced:
            if self.type == "bomb":
                img.draw_circle(int(self.x), int(self.y), self.radius, color=self.peel_color, fill=True)
                img.draw_circle(int(self.x), int(self.y), self.radius, color=(255, 80, 80, 80), thickness=2)
                img.draw_line(int(self.x), int(self.y - self.radius), int(self.x + 10), int(self.y - self.radius - 12), color=(255, 150, 75, 0), thickness=2)
                is_bright = (time.ticks_ms() // 100) % 2 == 0
                spark_color = (255, 255, 69, 0) if is_bright else (255, 255, 215, 0)
                img.draw_circle(int(self.x + 10), int(self.y - self.radius - 12), 4, color=spark_color, fill=True)
            elif self.type == "watermelon":
                img.draw_circle(int(self.x), int(self.y), self.radius, color=self.peel_color, thickness=4)
                img.draw_circle(int(self.x), int(self.y), self.radius - 2, color=(255, 144, 238, 144), thickness=2)
                img.draw_circle(int(self.x), int(self.y), self.radius - 4, color=self.flesh_color, fill=True)
                img.draw_circle(int(self.x - 8), int(self.y - 4), 1, color=(255, 0, 0, 0), fill=True)
                img.draw_circle(int(self.x + 8), int(self.y - 4), 1, color=(255, 0, 0, 0), fill=True)
                img.draw_circle(int(self.x), int(self.y + 8), 1, color=(255, 0, 0, 0), fill=True)
            else:
                img.draw_circle(int(self.x), int(self.y), self.radius, color=self.peel_color, fill=True)
                img.draw_circle(int(self.x), int(self.y), self.radius - 3, color=self.flesh_color, fill=True)
        else:
            if self.type == "bomb":
                img.draw_circle(int(self.x), int(self.y), self.radius + 15, color=(255, 255, 0, 0), thickness=4)
            else:
                lx = self.x + self.left_half_offset_x
                ly = self.y
                draw_semi_fruit(img, lx, ly, self.radius, self.split_angle, self.peel_color, self.flesh_color, True)

                rx = self.x + self.right_half_offset_x
                ry = self.y
                draw_semi_fruit(img, rx, ry, self.radius, self.split_angle, self.peel_color, self.flesh_color, False)

class Particle:
    def __init__(self, x, y, vx, vy, color, size):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life = 15

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.3
        self.life -= 1

    def draw(self, img):
        img.draw_circle(int(self.x), int(self.y), self.size, color=self.color, fill=True)

# ==============================================================================
# 【游戏核心状态机】
class FruitNinjaGame:
    def __init__(self):
        self.reset()
        self.high_score = 0

    def reset(self):
        self.score = 0
        self.hp = 3
        self.game_over = False
        self.game_over_start_ms = 0
        self.fruits = []
        self.particles = []
        self.sword_trail = []
        self.last_spawn_ms = time.ticks_ms()
        self.bomb_flash_ms = 0

    def update(self, has_hand, hand_center, eye_controller=None):
        now = time.ticks_ms()
        if self.game_over:
            if time.ticks_diff(now, self.game_over_start_ms) >= 4000:
                self.reset()
            return

        # 1. 拖尾轨迹处理 (只放入食指中指的中心点轨迹)
        if has_hand and hand_center is not None:
            self.sword_trail.append(hand_center)
            if len(self.sword_trail) > 8:
                self.sword_trail.pop(0)
        else:
            if len(self.sword_trail) > 0:
                self.sword_trail.pop(0)

        # 2. 定时产生水果
        if time.ticks_diff(now, self.last_spawn_ms) > random.randint(1200, 2200):
            self.last_spawn_ms = now
            spawn_count = random.randint(1, 2)
            for _ in range(spawn_count):
                ftype = random.choice(["watermelon", "apple", "orange", "banana", "bomb"])
                if ftype == "bomb" and random.random() > 0.25:
                    ftype = random.choice(["watermelon", "apple", "orange", "banana"])

                fx = random.randint(150, DISPLAY_WIDTH - 150)
                fy = DISPLAY_HEIGHT
                fvy = -random.randint(17, 24)
                fvx = random.randint(-4, 4)
                if fx < DISPLAY_WIDTH // 3: fvx = random.randint(2, 6)
                elif fx > (DISPLAY_WIDTH * 2) // 3: fvx = random.randint(-6, -2)

                r_map = {"watermelon": 42, "apple": 32, "orange": 26, "banana": 22, "bomb": 34}
                self.fruits.append(Fruit(ftype, fx, fy, fvx, fvy, r_map[ftype]))

        # 3. 碰撞/切割判定
        if len(self.sword_trail) >= 2:
            p1 = self.sword_trail[-2]
            p2 = self.sword_trail[-1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            len_sq = dx*dx + dy*dy

            for f in self.fruits:
                if f.sliced: continue
                if len_sq == 0:
                    dist_sq = (f.x - p1[0])**2 + (f.y - p1[1])**2
                else:
                    t = ((f.x - p1[0]) * dx + (f.y - p1[1]) * dy) / len_sq
                    t = max(0.0, min(1.0, t))
                    cx = p1[0] + t * dx
                    cy = p1[1] + t * dy
                    dist_sq = (f.x - cx)**2 + (f.y - cy)**2

                if dist_sq <= f.radius**2:
                    f.sliced = True
                    f.split_angle = random.randint(-45, 45)

                    if f.type == "bomb":
                        self.bomb_flash_ms = now
                        if eye_controller:
                            eye_controller.play_voice(20) # 警报音
                        for _ in range(12):
                            self.particles.append(Particle(f.x, f.y, random.uniform(-8, 8), random.uniform(-8, 8), (255, 255, 69, 0), random.randint(3, 7)))
                    else:
                        self.score += 10
                        if self.score > self.high_score:
                            self.high_score = self.score
                        if eye_controller:
                            eye_controller.play_voice(19)
                        for _ in range(8):
                            self.particles.append(Particle(f.x, f.y, random.uniform(-6, 6), random.uniform(-6, 6), f.flesh_color, random.randint(2, 5)))

        # 4. 水果更新
        g = 0.65
        alive_fruits = []
        for f in self.fruits:
            f.x += f.vx
            f.y += f.vy
            f.vy += g
            if f.sliced:
                f.left_half_offset_x -= 5
                f.right_half_offset_x += 5

            if f.y > DISPLAY_HEIGHT + 40:
                continue
            alive_fruits.append(f)
        self.fruits = alive_fruits

        # 5. 粒子更新
        alive_particles = []
        for p in self.particles:
            p.update()
            if p.life > 0:
                alive_particles.append(p)
        self.particles = alive_particles

    def draw(self, img):
        if self.bomb_flash_ms > 0:
            elapsed = time.ticks_diff(time.ticks_ms(), self.bomb_flash_ms)
            if elapsed < 300:
                fill_rect(img, 0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, (255, 255, 255, 255), 15)
            else:
                self.bomb_flash_ms = 0

        for f in self.fruits:
            f.draw(img)

        for p in self.particles:
            p.draw(img)

        N = len(self.sword_trail)
        if N >= 2:
            for i in range(1, N):
                p1 = self.sword_trail[i-1]
                p2 = self.sword_trail[i]
                thickness = int(i * DISPLAY_WIDTH / 360) + 1
                img.draw_line(p1[0], p1[1], p2[0], p2[1], color=(200, 0, 191, 255), thickness=thickness + 4)
                img.draw_line(p1[0], p1[1], p2[0], p2[1], color=(255, 255, 255, 255), thickness=thickness)

        draw_flat_panel(img, 20, 20, 180, 50, border=(255, 0, 255, 0), bg=(180, 20, 30, 20))
        img.draw_string_advanced(40, 32, 24, "得分: %d" % self.score, color=(255, 255, 255, 255))

        draw_flat_panel(img, DISPLAY_WIDTH - 200, 20, 180, 50, border=(255, 255, 0, 0), bg=(180, 30, 20, 20))
        img.draw_string_advanced(DISPLAY_WIDTH - 170, 32, 24, "生命: 无限", color=(255, 255, 80, 80))

        if self.game_over:
            fill_rect(img, 0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, (160, 20, 20, 20), 4)
            cx_panel = DISPLAY_WIDTH // 2 - 200
            cy_panel = DISPLAY_HEIGHT // 2 - 120
            draw_flat_panel(img, cx_panel, cy_panel, 400, 240, border=(255, 255, 215, 0), bg=(240, 35, 30, 35))

            draw_bold_string(img, DISPLAY_WIDTH // 2 - 96, cy_panel + 30, 36, "挑战结束", color=(255, 255, 215, 0))

            score_text = "最终得分: %d 分" % self.score
            high_text = "历史最高: %d 分" % self.high_score
            img.draw_string_advanced(DISPLAY_WIDTH // 2 - 80, cy_panel + 100, 24, score_text, color=(255, 255, 255, 255))
            img.draw_string_advanced(DISPLAY_WIDTH // 2 - 80, cy_panel + 140, 22, high_text, color=(255, 200, 200, 200))

            remain_sec = 4 - (time.ticks_diff(time.ticks_ms(), self.game_over_start_ms) // 1000)
            if remain_sec < 1: remain_sec = 1
            img.draw_string_advanced(DISPLAY_WIDTH // 2 - 100, cy_panel + 190, 20, "%d 秒后自动重试..." % remain_sec, color=(255, 180, 180, 180))

# ==============================================================================
# 【手部检测 AIBase 封装类】
class HandDetApp(AIBase):
    def __init__(self, kmodel_path, labels, model_input_size, anchors, confidence_threshold=0.2, nms_threshold=0.5, nms_option=False, strides=[8,16,32], rgb888p_size=[1920,1080], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.labels = labels
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.anchors = anchors
        self.strides = strides
        self.nms_option = nms_option
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right, _ = center_pad_param(self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [114, 114, 114])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]], [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            dets = aicube.anchorbasedet_post_process(results[0], results[1], results[2], self.model_input_size, self.rgb888p_size, self.strides, len(self.labels), self.confidence_threshold, self.nms_threshold, self.anchors, self.nms_option)
            return dets

class HandKPDetApp(AIBase):
    def __init__(self, kmodel_path, model_input_size, rgb888p_size=[1920,1080], display_size=[1920,1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.model_input_size = model_input_size
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.crop_params = []
        self.debug_mode = debug_mode
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT, np.uint8, np.uint8)

    def config_preprocess(self, det, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            self.crop_params = self.get_crop_param(det)
            self.ai2d.crop(self.crop_params[0], self.crop_params[1], self.crop_params[2], self.crop_params[3])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]], [1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            results = results[0].reshape(results[0].shape[0]*results[0].shape[1])
            results_show = np.zeros(results.shape, dtype=np.int16)
            results_show[0::2] = results[0::2] * self.crop_params[2] + self.crop_params[0]
            results_show[1::2] = results[1::2] * self.crop_params[3] + self.crop_params[1]
            results_show[0::2] = results_show[0::2] * (self.display_size[0] / self.rgb888p_size[0])
            results_show[1::2] = results_show[1::2] * (self.display_size[1] / self.rgb888p_size[1])
            return results_show

    def get_crop_param(self, det_box):
        x1, y1, x2, y2 = det_box[2], det_box[3], det_box[4], det_box[5]
        w, h = int(x2 - x1), int(y2 - y1)
        length = max(w, h)/2
        cx = (x1+x2)/2
        cy = (y1+y2)/2
        ratio_num = 1.26*length
        x1_kp = int(max(0, cx-ratio_num))
        y1_kp = int(max(0, cy-ratio_num))
        x2_kp = int(min(self.rgb888p_size[0]-1, cx+ratio_num))
        y2_kp = int(min(self.rgb888p_size[1]-1, cy+ratio_num))
        w_kp = int(x2_kp - x1_kp + 1)
        h_kp = int(y2_kp - y1_kp + 1)
        return [x1_kp, y1_kp, w_kp, h_kp]

# ==============================================================================
# 【主执行入口】
if __name__ == "__main__":
    import uos
    try:
        uos.dupterm(None)
        print("[LOG] Duplicate terminal disabled on UART.")
    except Exception as e:
        print("[LOG] dupterm failed:", e)

    try:
        display_mode = "lt9611"
        display_size = [DISPLAY_WIDTH, DISPLAY_HEIGHT]
        rgb888p_size = RGB888P_SIZE

        # 机械手模型配置
        hand_det_kmodel_path = "/sdcard/examples/kmodel/hand_det.kmodel"
        hand_kp_kmodel_path = "/sdcard/examples/kmodel/handkp_det.kmodel"
        hand_det_input_size = [512, 512]
        hand_kp_input_size = [256, 256]
        confidence_threshold = 0.25
        nms_threshold = 0.3
        labels = ["hand"]
        anchors = [26, 27, 53, 52, 75, 71, 80, 99, 106, 82, 99, 134, 140, 113, 161, 172, 245, 276]

        # 初始化眼球串口控制器
        eye_controller = EyeMechanismController(
            enable=True,
            port=FOLLOW_UART_PORT,
            baudrate=FOLLOW_UART_BAUDRATE,
            tx_pin=FOLLOW_UART_TX_PIN,
            rx_pin=FOLLOW_UART_RX_PIN,
            send_interval_ms=FOLLOW_UART_SEND_INTERVAL_MS,
            min_delta_deg=FOLLOW_UART_MIN_DELTA_DEG
        )

        filter_yaw = SmoothFilter(alpha=TRACKING_ALPHA_YAW)
        filter_pitch = SmoothFilter(alpha=TRACKING_ALPHA_PITCH)
        blink_ctrl = BlinkController(
            close_angle=SERVO_MIN_DEG[4] + 30,
            open_angle=SERVO_MAX_DEG[4]
        )

        pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode, display_size=display_size)
        pl.create(to_ide=USE_CANMV, hmirror=SENSOR_HMIRROR, vflip=SENSOR_VFLIP)

        display_size = pl.get_display_size()

        # 初始化手部与关键点检测器
        hand_det = HandDetApp(hand_det_kmodel_path, labels=labels, model_input_size=hand_det_input_size, anchors=anchors, confidence_threshold=confidence_threshold, nms_threshold=nms_threshold, nms_option=False, strides=[8, 16, 32], rgb888p_size=rgb888p_size, display_size=display_size, debug_mode=0)
        hand_det.config_preprocess()

        hand_kp = HandKPDetApp(hand_kp_kmodel_path, model_input_size=hand_kp_input_size, rgb888p_size=rgb888p_size, display_size=display_size, debug_mode=0)

        game = FruitNinjaGame()

        # 启动菜单进入提示音与开始音
        eye_controller.play_voice(10)
        time.sleep_ms(300)
        eye_controller.play_voice(16)

        print("[SYSTEM] Starting Fingers Fruit Ninja Game Loop...")
        scan_phase = 0.0
        frame_count = 0
        
        finger_colors = [
            (255, 255, 0, 0),     # 大拇指：红色
            (255, 255, 0, 255),   # 食指：紫色
            (255, 255, 255, 0),   # 中指：黄色
            (255, 0, 255, 0),     # 无名指：绿色
            (255, 0, 0, 255)      # 小拇指：蓝色
        ]

        while True:
            with ScopedTiming("total", 0):
                img = pl.get_frame()
                dets = hand_det.run(img)
                pl.osd_img.clear()

                best_det = None
                max_area = 0

                # 过滤出画面中最大的一只手
                if dets and len(dets) > 0:
                    for det_box in dets:
                        x1, y1, x2, y2 = det_box[2], det_box[3], det_box[4], det_box[5]
                        area = (x2 - x1) * (y2 - y1)
                        if area > max_area:
                            max_area = area
                            best_det = det_box

                has_hand = (best_det is not None)
                hand_center = None

                if has_hand:
                    # 运行关键点模型，并输出归一化关键点
                    hand_kp.config_preprocess(best_det)
                    results_show = hand_kp.run(img)

                    # results_show 包含 21 个点 [x0, y0, x1, y1, ..., x20, y20]，由 kmodel 推理并已映射到 display_size
                    coords = list(results_show)

                    # 物理镜像由底层硬件显示自动同步缩放对齐，无需软件重映射，在此直接使用原坐标
                    
                    # 1. 用食指指尖 (TIP=8, index=16, 17) 与 中指指尖 (TIP=12, index=32, 33) 产生刀刃点
                    idx_tx = coords[16]
                    idx_ty = coords[17]
                    mid_tx = coords[32]
                    mid_ty = coords[33]
                    cx = int((idx_tx + mid_tx) / 2)
                    cy = int((idx_ty + mid_ty) / 2)
                    hand_center = (cx, cy)

                    # 2. 绘制手部骨骼框架 (OSD)
                    # 绘制 21 个关节点圆形
                    for i in range(21):
                        px = int(coords[i*2])
                        py = int(coords[i*2+1])
                        pl.osd_img.draw_circle(px, py, 4, color=(255, 255, 255, 255), fill=True)
                        pl.osd_img.draw_circle(px, py, 6, color=(255, 0, 255, 0), fill=False, thickness=1)

                    # 绘制五根手指的手部连线
                    for i in range(5):
                        j = i * 8
                        color = finger_colors[i]
                        # 腕骨到指根
                        pl.osd_img.draw_line(int(coords[0]), int(coords[1]), int(coords[j+2]), int(coords[j+3]), color=color, thickness=3)
                        # 指骨连线 1
                        pl.osd_img.draw_line(int(coords[j+2]), int(coords[j+3]), int(coords[j+4]), int(coords[j+5]), color=color, thickness=3)
                        # 指骨连线 2
                        pl.osd_img.draw_line(int(coords[j+4]), int(coords[j+5]), int(coords[j+6]), int(coords[j+7]), color=color, thickness=3)
                        # 指尖连线 3
                        pl.osd_img.draw_line(int(coords[j+6]), int(coords[j+7]), int(coords[j+8]), int(coords[j+9]), color=color, thickness=3)

                    # 特殊绘制刀刃聚焦点，以增强动感
                    pl.osd_img.draw_circle(cx, cy, 8, color=(255, 255, 255, 255), fill=True)
                    pl.osd_img.draw_circle(cx, cy, 14, color=(255, 0, 191, 255), fill=False, thickness=2)

                    # 计算未镜像的物理偏差，用于控制仿生眼球移动 (使用食指与中指的中点进行平滑凝视)
                    raw_idx_tx = results_show[16]
                    raw_idx_ty = results_show[17]
                    raw_mid_tx = results_show[32]
                    raw_mid_ty = results_show[33]
                    raw_cx = (raw_idx_tx + raw_mid_tx) / 2
                    raw_cy = (raw_idx_ty + raw_mid_ty) / 2

                    x_norm = raw_cx / display_size[0]
                    y_norm = raw_cy / display_size[1]
                    err_x = x_norm - 0.5
                    err_y = y_norm - 0.5

                    if YAW_REVERSE: err_x = -err_x
                    if PITCH_REVERSE: err_y = -err_y

                    target_yaw = 90.0 - err_x * YAW_SENSITIVITY
                    target_pitch = 90.0 - err_y * PITCH_SENSITIVITY
                    target_yaw = max(SERVO_MIN_DEG[0], min(SERVO_MAX_DEG[0], target_yaw))
                    target_pitch = max(SERVO_MIN_DEG[1], min(SERVO_MAX_DEG[1], target_pitch))

                    yaw_deg = filter_yaw.update(target_yaw)
                    pitch_deg = filter_pitch.update(target_pitch)
                    scan_phase = 0.0
                else:
                    # 待机摆头扫视
                    scan_phase += 0.04
                    target_yaw = 90.0 + SCAN_YAW_RANGE * math.sin(scan_phase)
                    target_pitch = 90.0
                    yaw_deg = filter_yaw.update(target_yaw)
                    pitch_deg = filter_pitch.update(target_pitch)

                # 炸弹撞击眨眼控制
                if game.bomb_flash_ms > 0:
                    blink_ctrl.trigger_blink()

                left_eyelid, right_eyelid = blink_ctrl.update()
                blink_angles = [left_eyelid, right_eyelid]

                # 舵机更新 (物理眼球转动凝视您的“手剑”位置)
                servo_angles = [yaw_deg, pitch_deg, yaw_deg, pitch_deg, left_eyelid, right_eyelid]
                eye_controller.update(servo_angles)

                # 游戏逻辑与拖尾刀锋更新绘制
                game.update(has_hand, hand_center, eye_controller)
                game.draw(pl.osd_img)

                pl.show_image(flag=Display.FLAG_ROTATION_180 | Display.FLAG_MIRROR_HOR)
                
                # 每 15 帧垃圾回收一次，显著缩短单帧延迟，提升运行帧率
                frame_count += 1
                if frame_count % 15 == 0:
                    gc.collect()

        hand_det.deinit()
        hand_kp.deinit()
        pl.destroy()
    except Exception as e:
        with open("/sdcard/error.log", "w") as f:
            try:
                import traceback
                traceback.print_exception(e, f)
            except:
                f.write(repr(e))
        raise e
