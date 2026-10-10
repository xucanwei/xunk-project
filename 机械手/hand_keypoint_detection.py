'''
Demo: Robotic Arm Control System (Standalone Consolidated Version)
Platform: 01Studio CanMV K230
'''
from libs.PipeLine import PipeLine
from media.display import *

# ==============================================================================
# DISPLAY SETTINGS
DISPLAY_ROTATION_MODE = 1      # \u5c4f\u5e55\u65b9\u5411 (0: \u6b63\u5e38\u6a2a\u5c4f, 1: \u65cb\u8f6c180\u5ea6, 2: \u65cb\u8f6c90\u5ea6, 3: \u65cb\u8f6c270\u5ea6)
DISPLAY_MIRROR_MODE = 0        # \u5c4f\u5e55\u955c\u50cf (0: \u65e0\u955c\u50cf, 1: \u5de6\u53f3\u955c\u9762\u7ffb\u8f6c/\u6c34\u5e73\u955c\u50cf, 2: \u4e0a\u4e0b\u955c\u9762\u7ffb\u8f6c/\u5782\u76f4\u955c\u50cf)
SENSOR_HMIRROR = False         # \u6444\u50cf\u5934\u6c34\u5e73\u955c\u50cf (\u5982\u679c\u753b\u9762\u5de6\u53f3\u53cd\u4e86\uff0c\u53ef\u8bbe\u4e3a True)
SENSOR_VFLIP = True           # \u6444\u50cf\u5934\u5782\u76f4\u7ffb\u8f6c (\u5982\u679c\u753b\u9762\u4e0a\u4e0b\u53cd\u4e86\uff0c\u53ef\u8bbe\u4e3a True)
DISPLAY_MODE = "ek79007"       # \u5c4f\u5e55\u578b\u53f7
DISPLAY_SIZE = [1024, 600]     # \u5c4f\u5e55\u7269\u7406\u5206\u8fa8\u7387
RGB888P_SIZE = [1024, 600]     # \u6444\u50cf\u5934\u7ed9AI\u7684\u91c7\u96c6\u5206\u8fa8\u7387\uff0c\u8bbe\u4e3a 1024x600 \u4ee5\u5339\u914d\u5c4f\u5e55
# ==============================================================================

from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *
import os,sys,ujson,gc,math,random
from media.media import *
import nncase_runtime as nn
import ulab.numpy as np
import image
import aicube
from machine import FPIOA, UART
import _thread

# Configs
DISPLAY_FPS = 30
FOLLOW_UART_PORT = 2
FOLLOW_UART_BAUDRATE = 115200
FOLLOW_UART_SEND_INTERVAL_MS = 8
FOLLOW_UART_MIN_DELTA_DEG = 3
FOLLOW_UART_TX_PIN = 44
FOLLOW_UART_RX_PIN = 45
HAND_ANGLE_LOG_INTERVAL_MS = 500

# Servo angles range configuration
SERVO_MIN_DEG = [55, 70, 70, 70, 70]
SERVO_MAX_DEG = [130, 150, 150, 150, 150]
SERVO_CLOSE_GAMMA = [0.82, 0.84, 0.84, 0.86, 0.88]
SERVO_CURL_DEADBAND = [0.02, 0.03, 0.03, 0.03, 0.03]
SERVO_CURL_GAIN = [1.08, 1.02, 1.02, 1.02, 1.00]
SERVO_SMOOTH_FOLLOW_GAIN = [0.75, 0.70, 0.70, 0.70, 0.70]
SERVO_SMOOTH_MAX_STEP_CLOSE = [25, 25, 25, 25, 25]
SERVO_SMOOTH_MAX_STEP_OPEN = [22, 22, 22, 22, 22]
SERVO_SMOOTH_SLOW_ZONE = [6, 5, 5, 5, 5]

MODE_FOLLOW = 0
MODE_MIMIC = 1
MODE_RPS = 2
MODE_NAMES = ("Follow", "Mimic", "RPS")
FINGER_NAMES = ("\u62c7", "\u98df", "\u4e2d", "\u65e0", "\u5c0f")

FINGER_OPEN_CURL_LIMITS = (0.28, 0.30, 0.30, 0.32, 0.34)
FINGER_CLOSED_CURL_LIMITS = (0.62, 0.64, 0.64, 0.62, 0.60)

GESTURES = (
    ("OPEN", [0.0, 0.0, 0.0, 0.0, 0.0]),
    ("FIST", [1.0, 1.0, 1.0, 1.0, 1.0]),
    ("ONE", [1.0, 0.0, 1.0, 1.0, 1.0]),
    ("TWO", [1.0, 0.0, 0.0, 1.0, 1.0]),
    ("THREE", [1.0, 0.0, 0.0, 0.0, 1.0]),
    ("THUMB", [0.0, 1.0, 1.0, 1.0, 1.0]),
)

RPS_GESTURES = (
    ("ROCK", [1.0, 1.0, 1.0, 1.0, 1.0]),
    ("PAPER", [0.0, 0.0, 0.0, 0.0, 0.0]),
    ("SCISSORS", [1.0, 0.0, 0.0, 1.0, 1.0]),
)

class HandDetApp(AIBase):
    def __init__(self,kmodel_path,labels,model_input_size,anchors,confidence_threshold=0.2,nms_threshold=0.5,nms_option=False, strides=[8,16,32],rgb888p_size=[1920,1080],display_size=[1920,1080],debug_mode=0):
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path=kmodel_path
        self.labels=labels
        self.model_input_size=model_input_size
        self.confidence_threshold=confidence_threshold
        self.nms_threshold=nms_threshold
        self.anchors=anchors
        self.strides = strides
        self.nms_option = nms_option
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode=debug_mode
        self.ai2d=Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,input_image_size=None):
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right, _ =center_pad_param(self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [114, 114, 114])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        with ScopedTiming("postprocess",self.debug_mode > 0):
            dets = aicube.anchorbasedet_post_process(results[0], results[1], results[2], self.model_input_size, self.rgb888p_size, self.strides, len(self.labels), self.confidence_threshold, self.nms_threshold, self.anchors, self.nms_option)
            return dets

class HandKPDetApp(AIBase):
    def __init__(self,kmodel_path,model_input_size,rgb888p_size=[1920,1080],display_size=[1920,1080],debug_mode=0):
        super().__init__(kmodel_path,model_input_size,rgb888p_size,debug_mode)
        self.kmodel_path=kmodel_path
        self.model_input_size=model_input_size
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.crop_params=[]
        self.debug_mode=debug_mode
        self.ai2d=Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)

    def config_preprocess(self,det,input_image_size=None):
        with ScopedTiming("set preprocess config",self.debug_mode > 0):
            ai2d_input_size=input_image_size if input_image_size else self.rgb888p_size
            self.crop_params = self.get_crop_param(det)
            self.ai2d.crop(self.crop_params[0],self.crop_params[1],self.crop_params[2],self.crop_params[3])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1,3,ai2d_input_size[1],ai2d_input_size[0]],[1,3,self.model_input_size[1],self.model_input_size[0]])

    def postprocess(self,results):
        with ScopedTiming("postprocess",self.debug_mode > 0):
            results=results[0].reshape(results[0].shape[0]*results[0].shape[1])
            results_show = np.zeros(results.shape,dtype=np.int16)
            results_show[0::2] = results[0::2] * self.crop_params[2] + self.crop_params[0]
            results_show[1::2] = results[1::2] * self.crop_params[3] + self.crop_params[1]
            results_show[0::2] = results_show[0::2] * (self.display_size[0] / self.rgb888p_size[0])
            results_show[1::2] = results_show[1::2] * (self.display_size[1] / self.rgb888p_size[1])
            return results_show

    def get_crop_param(self,det_box):
        x1, y1, x2, y2 = det_box[2],det_box[3],det_box[4],det_box[5]
        w,h= int(x2 - x1),int(y2 - y1)
        w_det = int(float(x2 - x1) * self.display_size[0] // self.rgb888p_size[0])
        h_det = int(float(y2 - y1) * self.display_size[1] // self.rgb888p_size[1])
        x_det = int(x1*self.display_size[0] // self.rgb888p_size[0])
        y_det = int(y1*self.display_size[1] // self.rgb888p_size[1])
        length = max(w, h)/2
        cx = (x1+x2)/2
        cy = (y1+y2)/2
        ratio_num = 1.26*length
        x1_kp = int(max(0,cx-ratio_num))
        y1_kp = int(max(0,cy-ratio_num))
        x2_kp = int(min(self.rgb888p_size[0]-1, cx+ratio_num))
        y2_kp = int(min(self.rgb888p_size[1]-1, cy+ratio_num))
        w_kp = int(x2_kp - x1_kp + 1)
        h_kp = int(y2_kp - y1_kp + 1)
        return [x1_kp, y1_kp, w_kp, h_kp]

class HandKeyPointDet:
    def __init__(self,hand_det_kmodel,hand_kp_kmodel,det_input_size,kp_input_size,labels,anchors,confidence_threshold=0.25,nms_threshold=0.3,nms_option=False,strides=[8,16,32],rgb888p_size=[1280,720],display_size=[1920,1080],debug_mode=0):
        self.hand_det_kmodel=hand_det_kmodel
        self.hand_kp_kmodel=hand_kp_kmodel
        self.det_input_size=det_input_size
        self.kp_input_size=kp_input_size
        self.labels=labels
        self.anchors=anchors
        self.confidence_threshold=confidence_threshold
        self.nms_threshold=nms_threshold
        self.nms_option=nms_option
        self.strides=strides
        self.rgb888p_size=[ALIGN_UP(rgb888p_size[0],16),rgb888p_size[1]]
        self.display_size=[ALIGN_UP(display_size[0],16),display_size[1]]
        self.debug_mode=debug_mode
        self.hand_det=HandDetApp(self.hand_det_kmodel,self.labels,model_input_size=self.det_input_size,anchors=self.anchors,confidence_threshold=self.confidence_threshold,nms_threshold=self.nms_threshold,nms_option=self.nms_option,strides=self.strides,rgb888p_size=self.rgb888p_size,display_size=self.display_size,debug_mode=0)
        self.hand_kp=HandKPDetApp(self.hand_kp_kmodel,model_input_size=self.kp_input_size,rgb888p_size=self.rgb888p_size,display_size=self.display_size)
        self.hand_det.config_preprocess()

    def run(self,input_np):
        det_boxes=self.hand_det.run(input_np)
        hand_res=[]
        boxes=[]
        for det_box in det_boxes:
            x1, y1, x2, y2 = det_box[2],det_box[3],det_box[4],det_box[5]
            w,h= int(x2 - x1),int(y2 - y1)
            if (h<(0.1*self.rgb888p_size[1])):
                continue
            if (w<(0.25*self.rgb888p_size[0]) and ((x1<(0.03*self.rgb888p_size[0])) or (x2>(0.97*self.rgb888p_size[0])))):
                continue
            if (w<(0.15*self.rgb888p_size[0]) and ((x1<(0.01*self.rgb888p_size[0])) or (x2>(0.99*self.rgb888p_size[0])))):
                continue
            self.hand_kp.config_preprocess(det_box)
            results_show=self.hand_kp.run(input_np)
            boxes.append(det_box)
            hand_res.append(results_show)

        # 当同时检测到多只手时，按检测框面积进行降序排列，并且只保留最近的一只手，彻底丢弃/忽略其他远处的背景手势
        if len(boxes) > 1:
            paired = list(zip(boxes, hand_res))
            paired.sort(key=lambda item: (item[0][4] - item[0][2]) * (item[0][5] - item[0][3]), reverse=True)
            boxes = [paired[0][0]]
            hand_res = [paired[0][1]]

        return boxes,hand_res

    def draw_result(self,pl,dets,hand_res):
        pl.osd_img.clear()
        if dets:
            for k in range(len(dets)):
                det_box=dets[k]
                x1, y1, x2, y2 = det_box[2],det_box[3],det_box[4],det_box[5]
                w,h= int(x2 - x1),int(y2 - y1)
                w_det = int(float(x2 - x1) * self.display_size[0] // self.rgb888p_size[0])
                h_det = int(float(y2 - y1) * self.display_size[1] // self.rgb888p_size[1])
                x_det = int(x1*self.display_size[0] // self.rgb888p_size[0])
                y_det = int(y1*self.display_size[1] // self.rgb888p_size[1])
                pl.osd_img.draw_rectangle(x_det, y_det, w_det, h_det, color=(255, 0, 255, 0), thickness = 2)

                results_show=hand_res[k]
                for i in range(len(results_show)/2):
                    pl.osd_img.draw_circle(results_show[i*2], results_show[i*2+1], 1, color=(255, 0, 255, 0),fill=False)
                for i in range(5):
                    j = i*8
                    if i==0:
                        R = 255; G = 0; B = 0
                    if i==1:
                        R = 255; G = 0; B = 255
                    if i==2:
                        R = 255; G = 255; B = 0
                    if i==3:
                        R = 0; G = 255; B = 0
                    if i==4:
                        R = 0; G = 0; B = 255
                    pl.osd_img.draw_line(results_show[0], results_show[1], results_show[j+2], results_show[j+3], color=(255,R,G,B), thickness = 3)
                    pl.osd_img.draw_line(results_show[j+2], results_show[j+3], results_show[j+4], results_show[j+5], color=(255,R,G,B), thickness = 3)
                    pl.osd_img.draw_line(results_show[j+4], results_show[j+5], results_show[j+6], results_show[j+7], color=(255,R,G,B), thickness = 3)
                    pl.osd_img.draw_line(results_show[j+6], results_show[j+7], results_show[j+8], results_show[j+9], color=(255,R,G,B), thickness = 3)

class MechanicalHandState:
    def __init__(self, alpha=0.22):
        self.alpha = alpha
        self.valid = False
        self.curl = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.servo = [0, 0, 0, 0, 0]
        self.stable_curl = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.raw_history = [[], [], [], [], []]
        self.miss_count = 0
        self.presence_count = 0
        self.smoothed_keypoints = None

    def _dist(self, points, a, b):
        dx = points[a][0] - points[b][0]
        dy = points[a][1] - points[b][1]
        return (dx*dx + dy*dy)**0.5

    def _clamp(self, v, lo, hi):
        if v < lo: return lo
        if v > hi: return hi
        return v

    def _points(self, keypoints):
        pts = []
        for i in range(len(keypoints) // 2):
            pts.append((float(keypoints[i*2]), float(keypoints[i*2+1])))
        return pts

    def _clear_history(self):
        for i in range(5):
            self.raw_history[i] = []

    def estimate_raw_curl(self, keypoints):
        points = self._points(keypoints)
        wrist = points[0]
        index_mcp = points[5]
        middle_mcp = points[9]
        ring_mcp = points[13]
        pinky_mcp = points[17]
        palm_center = ((wrist[0]+index_mcp[0]+middle_mcp[0]+ring_mcp[0]+pinky_mcp[0])/5.0,
                       (wrist[1]+index_mcp[1]+middle_mcp[1]+ring_mcp[1]+pinky_mcp[1])/5.0)
        palm_len = self._dist(points, 0, 9)
        palm_width = self._dist(points, 5, 17)
        if palm_len < 1.0: palm_len = 1.0
        if palm_width < 1.0: palm_width = palm_len
        curls = []
        for finger_index in range(len(FINGER_SPECS)):
            spec = FINGER_SPECS[finger_index]
            ids = spec[1]
            arc = self._dist(points, ids[0], ids[1]) + self._dist(points, ids[1], ids[2]) + self._dist(points, ids[2], ids[3])
            direct = self._dist(points, ids[0], ids[3])
            if arc < 1.0:
                arc_curl = 0.0
            else:
                raw = 1.0 - direct / arc
                arc_curl = (raw - 0.04) / 0.20
            tip = points[ids[3]]
            tip_wrist = ((tip[0]-wrist[0])**2 + (tip[1]-wrist[1])**2)**0.5
            tip_palm = ((tip[0]-palm_center[0])**2 + (tip[1]-palm_center[1])**2)**0.5
            base_len = self._dist(points, 0, ids[0]) + arc
            if base_len < 1.0: base_len = 1.0
            dist_ratio = tip_wrist / base_len
            open_ratio = FINGER_DISTANCE_THRESHOLDS[finger_index][0]
            closed_ratio = FINGER_DISTANCE_THRESHOLDS[finger_index][1]
            wrist_curl = (open_ratio - dist_ratio) / (open_ratio - closed_ratio)
            if spec[0] == "T":
                tip_index = self._dist(points, 4, 5)
                dist_curl = (1.02 - tip_index / palm_width) / 0.62
                palm_curl = (0.88 - tip_palm / palm_width) / 0.62
                curl = max(arc_curl * 0.85, wrist_curl, dist_curl, palm_curl)
            else:
                palm_curl = (1.18 - tip_palm / palm_width) / 0.70
                curl = max(arc_curl, wrist_curl, palm_curl)
            curl = self._clamp(curl, 0.0, 1.0)
            if curl < 0.12: curl = 0.0
            curls.append(curl)
        return curls

    def stabilize_raw_curl(self, raw):
        stable = []
        for i in range(5):
            v = self._clamp(raw[i], 0.0, 1.0)
            if v < 0.08:
                v = 0.0
            elif v > 0.92:
                v = 1.0
            self.stable_curl[i] = v
            stable.append(v)
        return stable

    def update(self, hand_res):
        if hand_res is None or len(hand_res) == 0:
            self.miss_count += 1
            self.presence_count = 0
            if self.miss_count >= 3:
                self._clear_history()
                self.smoothed_keypoints = None
            return self.curl
        self.miss_count = 0
        self.presence_count += 1

        # 对原始关键点坐标进行低通平滑滤波，从源头消灭识别噪点和抖动
        raw_kps = hand_res[0]
        if self.smoothed_keypoints is None:
            self.smoothed_keypoints = list(raw_kps)
        else:
            kps_alpha = 0.45
            for idx in range(42):
                self.smoothed_keypoints[idx] = self.smoothed_keypoints[idx] * (1.0 - kps_alpha) + raw_kps[idx] * kps_alpha

        raw = self.stabilize_raw_curl(self.estimate_raw_curl(self.smoothed_keypoints))
        if not self.valid:
            for i in range(5):
                self.curl[i] = raw[i]
            self.valid = True
        else:
            for i in range(5):
                delta_raw = raw[i] - self.curl[i]
                abs_delta = abs(delta_raw)
                alpha = 0.18
                if abs_delta > 0.15:
                    alpha = 0.95
                elif abs_delta > 0.06:
                    alpha = 0.55
                next_value = self.curl[i] * (1.0 - alpha) + raw[i] * alpha
                delta = next_value - self.curl[i]
                if delta > 0.65:
                    next_value = self.curl[i] + 0.65
                elif delta < -0.65:
                    next_value = self.curl[i] - 0.65
                self.curl[i] = self._clamp(next_value, 0.0, 1.0)
        for i in range(5):
            servo_value = int(5 + self.curl[i] * 115)
            if abs(servo_value - self.servo[i]) >= 1:
                self.servo[i] = servo_value
        return self.curl

    def get_servo_angles(self):
        return self.servo

class MechanicalHandController:
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
        self.last_servo = [-1000, -1000, -1000, -1000, -1000]
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

    def _ticks_ms(self):
        return time.ticks_ms()

    def _ticks_diff(self, now, last):
        if last is None: return 0
        return time.ticks_diff(now, last)

    def _checksum(self, data):
        checksum = 0
        for item in data:
            checksum ^= item
        return checksum & 0xFF

    def _build_frame(self, servo_angles):
        payload_len = 10
        payload = bytearray(payload_len + 4)
        payload[0] = self.device_id
        payload[1] = self.cmd_set_angles
        payload[2] = payload_len
        for channel in range(5):
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
            print("[WARN] Failed to open UART2:", e)
            self.ready = False
            return False

    def play_voice(self, voice_id):
        now = time.ticks_ms()
        is_low_priority = (voice_id in (14, 15))

        if is_low_priority:
            # 状态提示类低优先级语音在 2.5 秒内只能播报一次，避免与其他音频重叠
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

    def update(self, servo_angles):
        if not self.enable:
            return
        if not self._ensure_uart():
            return

        # 高频抖动滑动检测窗口
        if not hasattr(self, "angle_history"):
            self.angle_history = [[] for _ in range(5)]

        filtered_angles = list(servo_angles)
        for i in range(5):
            history = self.angle_history[i]
            history.append(int(servo_angles[i]))
            if len(history) > 5:
                history.pop(0)

            if len(history) == 5:
                total_mov = sum(abs(history[t] - history[t-1]) for t in range(1, 5))
                net_mov = abs(history[4] - history[0])
                # 若总运动跨度大但净位移极小，判定为高频无效抖动，强制冻结为上一帧稳定状态
                if total_mov >= 6 and net_mov <= 2:
                    filtered_angles[i] = self.last_servo[i] if self.last_servo[i] != -1000 else history[0]
                    history[-1] = filtered_angles[i]

        changed = False
        for i in range(5):
            if abs(int(filtered_angles[i]) - int(self.last_servo[i])) >= self.min_delta_deg:
                changed = True
                break
        if not changed:
            return

        now = self._ticks_ms()
        if self.last_send_ms is not None and self._ticks_diff(now, self.last_send_ms) < self.send_interval_ms:
            return

        frame = self._build_frame(filtered_angles)
        try:
            self.uart.write(frame)
            self.last_servo = [int(angle) for angle in filtered_angles]
            self.tx_frames += 1
            self.last_send_ms = now
        except Exception as e:
            print("[WARN] UART write failed:", e)
            self.ready = False

    def read_command(self):
        # 确保串口就绪并读取接收数据
        if not self._ensure_uart():
            return None
        # 读取串口缓存中的字符数据
        if self.uart.any():
            try:
                # 一次性读取全部可用字节
                data = self.uart.read()
                if data:
                    print("[UART RXD Raw Bytes]:", data)
                    self.rx_buffer += data.decode()
                    if "\n" in self.rx_buffer:
                        lines = self.rx_buffer.split("\n")
                        # 最后一个项可能不完整，保留在缓冲区
                        self.rx_buffer = lines[-1]
                        # 逆序搜索最新的完整指令以保证响应时效性
                        for line_str in reversed(lines[:-1]):
                            line_str = line_str.strip()
                            if line_str:
                                print("[UART RXD] Raw line:", line_str)
                            if line_str.startswith("CMD:"):
                                cmd_val = line_str[4:]
                                if cmd_val == "FOLLOW":
                                    return ("mode", MODE_FOLLOW)
                                elif cmd_val == "MIMIC":
                                    return ("mode", MODE_MIMIC)
                                elif cmd_val == "RPS":
                                    return ("mode", MODE_RPS)
                                elif cmd_val == "MENU":
                                    return ("menu", None)
                                elif cmd_val == "RESTART":
                                    return ("restart", None)
            except Exception as e:
                print("[WARN] UART read failed:", e)
        return None

class TouchPoint:
    def __init__(self, x, y, event):
        self.x = x
        self.y = y
        self.event = event

class TouchButtons:
    def __init__(self):
        self.menu_cards = (
            (120, 200, 780, 75, MODE_FOLLOW, "", "\u8ddf\u968f\u6a21\u5f0f", "", "\u63a7\u5236\u624b\u4e0e\u5b83\u505a\u6bd4\u5212\u4e0e\u624b\u52bf\u52a8\u4f5c"),
            (120, 305, 780, 75, MODE_RPS, "", "\u731c\u62f3\u6a21\u5f0f", "", "\u4e0e\u673a\u68b0\u624b\u8fdb\u884c\u8da3\u5473\u731c\u62f3\u6e38\u620f"),
            (120, 410, 780, 75, MODE_MIMIC, "", "\u6a21\u4eff\u6a21\u5f0f", "", "\u6a21\u4eff\u673a\u68b0\u624b\u7684\u52a8\u4f5c\u8fdb\u884c\u8bad\u7ec3"),
        )
        self.menu_button = (20, 535, 120, 45, "\u8fd4\u56de\u83dc\u5355")
        self.restart_button = (884, 535, 120, 45, "\u91cd\u65b0\u5f00\u59cb")
        self.last_press_ms = 0
        self._init_touch()

    def _init_touch(self):
        self.pending_events = []
        self.touch_backend = "gt911"
        self.enabled = True
        try:
            _thread.start_new_thread(gt911_polling_thread, (self,))
            print("[LOG] GT911 touch thread spawned.")
        except Exception as e:
            self.enabled = False
            print("[WARN] Failed to spawn Touch thread:", e)

    def _read_points(self):
        if not self.enabled: return ()
        with touch_lock:
            if not self.pending_events: return ()
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
        if not self.enabled: return None
        points = self._read_points()
        if not len(points): return None

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_press_ms) < 350: return None

        # 寻找队列中第一个有效的按下或长按移动事件
        pt = None
        for p in points:
            if p.event in ("DOWN", "MOVE"):
                pt = p
                break
        if pt is None: return None

        if in_menu:
            for b in self.menu_cards:
                x, y, w, h, mode, t_en, t_zh, d_en, d_zh = b
                if pt.x >= x and pt.x <= x+w and pt.y >= y and pt.y <= y+h:
                    self.last_press_ms = now
                    return ("mode", mode)
            return None

        mx, my, mw, mh, mtext = self.menu_button
        if pt.x >= mx and pt.x <= mx+mw and pt.y >= my and pt.y <= my+mh:
            self.last_press_ms = now
            return ("menu", None)

        rx, ry, rw, rh, rtext = self.restart_button
        if pt.x >= rx and pt.x <= rx+rw and pt.y >= ry and pt.y <= ry+rh:
            self.last_press_ms = now
            return ("restart", None)
        return None

    def draw_menu(self, img, tick):
        # 1. 绘制渐变浅蓝色背景 (从亮天蓝到柔和粉蓝)
        draw_gradient_bg(img, 0, 0, pl.display_size[0], pl.display_size[1], (255, 225, 240, 255), (255, 185, 215, 255), step=6)

        # 2. 顶部居中大标题，左右各空 1/5 空间（x=205 到 819）
        draw_flat_panel(img, 205, 25, 614, 75, border=(255, 100, 160, 220), bg=(255, 255, 255, 255))
        img.draw_string_advanced(376, 43, 38, "AI\u4e92\u52a8\u673a\u68b0\u624b\u638c", color=(255, 20, 24, 30))

        # 3. 中间一层深色蓝背景
        draw_flat_panel(img, 80, 125, 864, 440, border=(255, 80, 140, 200), bg=(255, 150, 185, 225))

        # 4. 中间一层顶部提示词
        img.draw_string_advanced(382, 150, 26, "\u8bf7\u8bf4\u51fa\u60f3\u4f53\u9a8c\u7684\u6a21\u5f0f\u5427", color=(255, 20, 24, 30))

        # 5. 三个游戏选择行（拆分为独立的左、右两个实心框）
        for b in self.menu_cards:
            x, y, w, h, mode, _, title_zh, _, desc_zh = b

            # 自适应色彩搭配与实心背景匹配
            if mode == MODE_FOLLOW:
                border = (255, 0, 180, 70)       # 亮绿
                bg_left = border                  # 左侧按钮为纯亮绿底色！
                bg_right = (255, 235, 255, 240)   # 右侧长条为浅薄荷白 (不透明)
            elif mode == MODE_MIMIC:
                border = (255, 80, 160, 220)     # 亮蓝
                bg_left = border                  # 左侧按钮为纯亮蓝底色！
                bg_right = (255, 230, 242, 255)   # 右侧长条为浅天空白 (不透明)
            else:
                border = (255, 230, 150, 0)      # 橙金
                bg_left = border                  # 左侧按钮为纯亮橙底色！
                bg_right = (255, 255, 250, 235)   # 右侧长条为浅奶油白 (不透明)

            # 绘制左侧“模式名称”按钮 (宽 180)
            draw_panel(img, x, y, 180, h, border=border, bg=bg_left)
            # 中文标题在左侧按钮内加粗且居中书写 (白色高对比度)
            draw_bold_string(img, x + 42, y + 25, 24, title_zh, color=(255, 255, 255, 255))

            # 绘制右侧“模式解释”长条 (宽 580，从 x + 200 开始)
            draw_panel(img, x + 200, y, 580, h, border=border, bg=bg_right)
            # 模式解释说明文本 (深炭灰色，常规字体)
            img.draw_string_advanced(x + 225, y + 28, 18, desc_zh, color=(255, 50, 60, 70))
            # 绘制最右侧的指示箭头 “>”
            img.draw_string_advanced(x + 745, y + 28, 18, ">", color=border)

    def draw_game_nav(self, img, tick):
        mx, my, mw, mh, mtext = self.menu_button
        draw_flat_panel(img, mx, my, mw, mh, border=(255, 80, 160, 220), bg=(76, 255, 255, 255))
        img.draw_string_advanced(mx+22, my+12, 14, mtext, color=(255, 20, 24, 30))

        rx, ry, rw, rh, rtext = self.restart_button
        draw_flat_panel(img, rx, ry, rw, rh, border=(255, 220, 80, 40), bg=(76, 255, 255, 255))
        img.draw_string_advanced(rx+18, ry+12, 14, rtext, color=(255, 20, 24, 30))

class GameState:
    def __init__(self):
        self.mode = MODE_FOLLOW
        self.reset()

    def reset(self, mech_controller=None):
        self.score = 0
        self.computer_score = 0
        self.should_exit_to_menu = False
        self.game_over = False
        self.game_over_start_ms = None
        self.rounds = 0
        self.message = "\u5b9e\u65f6\u8ddf\u968f\u6a21\u5f0f"
        self.phase = "follow"
        self.phase_start_ms = time.ticks_ms()
        self.no_hand_start_ms = None
        self.target_index = 0
        self.target_curl = GESTURES[0][1]
        self.target_name = GESTURES[0][0]
        self.match_count = 0
        self.rps_robot = "ROCK"
        self.rps_robot_curl = RPS_GESTURES[0][1]
        self.rps_result = "-"
        self.user_rps = "UNKNOWN"
        self.result_text = ""
        self.result_log = ""
        if self.mode == MODE_MIMIC:
            self.next_mimic_target()
            self.phase = "wait_hand"
            self.message = "\u59ff\u6001\u6a21\u4eff: \u8bf7\u505a\u51fa\u76ee\u6807\u624b\u52bf"
            if mech_controller is not None:
                mech_controller.play_voice(14)
        elif self.mode == MODE_RPS:
            self.start_rps_countdown(mech_controller)

    def set_mode(self, mode, mech_controller=None):
        self.mode = mode
        self.reset()
        if mech_controller is not None:
            if mode == MODE_FOLLOW:
                mech_controller.play_voice(11)
            elif mode == MODE_MIMIC:
                mech_controller.play_voice(12)
            elif mode == MODE_RPS:
                mech_controller.play_voice(13)

    def next_mimic_target(self):
        self.target_index = random.getrandbits(8) % len(GESTURES)
        self.target_name = GESTURES[self.target_index][0]
        self.target_curl = GESTURES[self.target_index][1]
        self.match_count = 0

    def start_mimic_round(self):
        self.phase = "countdown"
        self.phase_start_ms = time.ticks_ms()
        self.match_count = 0

    def finish_mimic_round(self, success, mech_controller=None):
        self.rounds += 1
        if success:
            self.score += 1
            self.result_text = "\u52a8\u4f5c\u5339\u914d\u6210\u529f"
            if mech_controller is not None:
                mech_controller.play_voice(19)
        else:
            self.result_text = "\u5339\u914d\u8d85\u65f6"
            if mech_controller is not None:
                mech_controller.play_voice(20)
        self.result_log = self.result_text
        self.message = self.result_text
        self.phase = "result"
        self.phase_start_ms = time.ticks_ms()
        self.no_hand_start_ms = None

    def start_rps_countdown(self, mech_controller=None):
        self.phase = "countdown"
        self.phase_start_ms = time.ticks_ms()
        self.rps_result = "-"
        self.user_rps = "UNKNOWN"
        self.rps_robot = "READY"
        self.rps_robot_curl = [1.0, 1.0, 1.0, 1.0, 1.0]
        self.rps_voice_played = False
        if mech_controller is not None:
            mech_controller.play_voice(16)

    def finish_rps_round(self, curl, has_hand, mech_controller=None):
        robots = RPS_GESTURES
        item = robots[random.getrandbits(8) % len(robots)]
        self.rps_robot = item[0]
        self.rps_robot_curl = item[1]
        self.user_rps = self.classify_rps(curl) if has_hand else "UNKNOWN"
        self.rps_result = self.rps_winner(self.user_rps, self.rps_robot)
        self.result_text = self.rps_result
        self.result_log = "You:%s Robot:%s %s" % (self.user_rps, self.rps_robot, self.rps_result)
        self.rounds += 1
        self.phase = "result"
        self.phase_start_ms = time.ticks_ms()
        self.no_hand_start_ms = None

        if mech_controller is not None:
            if self.user_rps == "UNKNOWN":
                mech_controller.play_voice(20)
            elif "\u4f60\u8d62\u4e86" in self.result_text:
                mech_controller.play_voice(17)
            elif "\u673a\u5668\u4eba\u8d62\u4e86" in self.result_text:
                mech_controller.play_voice(18)
            elif "\u5e73\u5c40" in self.result_text:
                mech_controller.play_voice(23)

    def classify_rps(self, curl):
        thumb, index, middle, ring, pinky = curl
        if index > 0.62 and middle > 0.62 and ring > 0.62 and pinky > 0.62:
            return "ROCK"
        if index < 0.38 and middle < 0.38 and ring < 0.38 and pinky < 0.38:
            return "PAPER"
        if index < 0.38 and middle < 0.38 and ring > 0.58 and pinky > 0.58:
            return "SCISSORS"
        return "UNKNOWN"

    def rps_winner(self, user, robot):
        if user == "UNKNOWN":
            return "\u8bf7\u505a\u51fa\u624b\u52bf"
        if user == robot:
            return "\u5e73\u5c40"
        if (user == "ROCK" and robot == "SCISSORS") or (user == "SCISSORS" and robot == "PAPER") or (user == "PAPER" and robot == "ROCK"):
            self.score += 1
            return "\u4f60\u8d62\u4e86\uff01"
        self.computer_score += 1
        return "\u673a\u5668\u4eba\u8d62\u4e86"

    def update_no_hand(self, has_hand):
        now = time.ticks_ms()
        if has_hand:
            self.no_hand_start_ms = None
            return False
        if self.no_hand_start_ms is None:
            self.no_hand_start_ms = now
            return False
        return time.ticks_diff(now, self.no_hand_start_ms) >= 2000

    def finger_matches_target(self, finger_index, value, target):
        if target <= 0.05:
            return value <= FINGER_OPEN_CURL_LIMITS[finger_index]
        if target >= 0.95:
            return value >= FINGER_CLOSED_CURL_LIMITS[finger_index]
        return abs(value-target) <= 0.18

    def mimic_match(self, curl):
        for i in range(5):
            if not self.finger_matches_target(i, curl[i], self.target_curl[i]):
                return False
        return True

    def update(self, curl, has_hand, mech_controller=None):
        now = time.ticks_ms()
        if self.mode == MODE_FOLLOW:
            if has_hand:
                self.message = "\u5b9e\u65f6\u8ddf\u968f\u4e2d"
            else:
                self.message = "\u7b49\u5f85\u624b\u638c\u5165\u955c"
        elif self.mode == MODE_MIMIC:
            if self.game_over:
                self.message = self.result_text
                # 3 秒展示后自动返回主菜单
                if time.ticks_diff(now, self.game_over_start_ms) >= 3000:
                    self.should_exit_to_menu = True
                return

            if self.rounds >= 10:
                self.game_over = True
                self.game_over_start_ms = now
                self.result_text = "\u6a21\u4eff\u8bad\u7ec3\u7ed3\u675f! \u5f97\u5206:%d/10" % self.score
                self.message = self.result_text
                return

            if self.phase == "wait_hand":
                name_zh = GESTURE_ZH.get(self.target_name, self.target_name)
                self.message = "\u6a21\u4eff\u76ee\u6807: %s \u8bf7\u4eae\u51fa\u624b\u638c" % name_zh
                if has_hand:
                    self.start_mimic_round()
            elif self.phase == "countdown":
                remain = 10 - time.ticks_diff(now, self.phase_start_ms)//1000
                if remain < 0: remain = 0
                matched = False
                if has_hand:
                    matched = self.mimic_match(curl)
                if matched:
                    self.match_count += 1
                else:
                    self.match_count = 0
                name_zh = GESTURE_ZH.get(self.target_name, self.target_name)
                self.message = "\u5339\u914d\u624b\u52bf [%s] \u5012\u8ba1\u65f6 %ds" % (name_zh, remain)
                if self.match_count >= 6:
                    self.finish_mimic_round(True, mech_controller)
                elif time.ticks_diff(now, self.phase_start_ms) >= 10000:
                    self.finish_mimic_round(False, mech_controller)
            else:
                self.message = self.result_text
                if time.ticks_diff(now, self.phase_start_ms) >= 2000:
                    self.next_mimic_target()
                    self.phase = "wait_hand"
                    self.message = "\u51c6\u5907\u4e0b\u4e00\u4e2a\u624b\u52bf..."
        else:
            if self.game_over:
                self.message = self.result_text
                # 2 秒展示后自动返回主菜单
                if time.ticks_diff(now, self.game_over_start_ms) >= 2000:
                    self.should_exit_to_menu = True
                return

            # 胜局达到 3 场，或者累计局数达 5 局，判定整场游戏结束
            if self.score >= 3 or self.computer_score >= 3 or self.rounds >= 5:
                self.game_over = True
                self.game_over_start_ms = now
                if self.score > self.computer_score:
                    self.result_text = "\u6e38\u620f\u83b7\u80dc! \u4f60\u8d62\u4e86" # 游戏获胜! 你赢了
                    if mech_controller is not None:
                        mech_controller.play_voice(21) # 恭喜挑战成功 (保持语音ID不变)
                elif self.score < self.computer_score:
                    self.result_text = "\u6e38\u620f\u5931\u8d25! \u7535\u8111\u8d62\u4e86" # 游戏失败! 电脑赢了
                    if mech_controller is not None:
                        mech_controller.play_voice(22) # 挑战失败，再接再厉 (保持语音ID不变)
                else:
                    self.result_text = "\u5e73\u5c40\u7ed3\u6755!" # 平局结束!
                    if mech_controller is not None:
                        mech_controller.play_voice(23) # 是平局喔
                self.message = self.result_text
                return

            if self.phase == "countdown":
                diff = time.ticks_diff(now, self.phase_start_ms)
                remain = 5 - diff // 1000
                if remain < 0: remain = 0
                self.message = "\u731c\u62f3\u5012\u8ba1\u65f6... \u51fa\u62f3! %ds" % remain
                
                # 倒计时进行到 2.0 秒（即剩余 3 秒）时开始播放语音“石头，剪刀，布”，说完正好结束倒计时，衔接上胜负播报
                if diff >= 2000 and not self.rps_voice_played:
                    if mech_controller is not None:
                        mech_controller.play_voice(24) # 石头，剪刀，布
                    self.rps_voice_played = True
                
                if diff >= 5000:
                    self.finish_rps_round(curl, has_hand, mech_controller)
            else:
                self.message = self.rps_result
                if time.ticks_diff(now, self.phase_start_ms) >= 2000:
                    self.start_rps_countdown(mech_controller)

    def get_robot_curl(self, user_curl):
        if self.mode == MODE_FOLLOW:
            return user_curl
        if self.mode == MODE_MIMIC:
            return self.target_curl
        return self.rps_robot_curl

    def countdown_total_ms(self):
        if self.phase != "countdown": return 0
        return 10000 if self.mode == MODE_MIMIC else 5000

    def countdown_remain_ms(self):
        total = self.countdown_total_ms()
        if total <= 0: return 0
        remain = total - time.ticks_diff(time.ticks_ms(), self.phase_start_ms)
        return max(0, remain)

    def feedback_text(self):
        if self.phase != "result": return ""
        if time.ticks_diff(time.ticks_ms(), self.phase_start_ms) > 1600: return ""
        return self.result_text

    def feedback_good(self):
        return ("动作" in self.result_text) or ("赢" in self.result_text)

    def draw_target(self, img):
        if self.mode == MODE_FOLLOW: return
        x0 = 684
        y0 = 20
        w = 320
        if self.mode == MODE_RPS:
            h = 130
            draw_flat_panel(img, x0, y0, w, h, border=(255, 80, 160, 220), bg=(76, 255, 255, 255))
            # 绘制“电脑”标题并居中对齐
            draw_bold_string(img, x0 + 160 - 48, y0 + 12, 24, "\u7535\u8111", color=(255, 20, 24, 30))

            # 第一行：得分
            score_text = "\u5f97\u5206: %d" % self.computer_score
            text_len1 = sum(1.0 if ord(c) > 127 else 0.6 for c in score_text)
            tx1 = x0 + 160 - int((text_len1 * 26) / 2)
            img.draw_string_advanced(tx1, y0 + 48, 26, score_text, color=(255, 220, 80, 40))

            # 第二行：出拳
            name_zh = GESTURE_ZH.get(self.rps_robot, self.rps_robot)
            choice_text = "\u51fa\u62f3: " + name_zh
            text_len2 = sum(1.0 if ord(c) > 127 else 0.6 for c in choice_text)
            tx2 = x0 + 160 - int((text_len2 * 26) / 2)
            img.draw_string_advanced(tx2, y0 + 84, 26, choice_text, color=(255, 255, 140, 0))
        else:
            h = 130
            draw_flat_panel(img, x0, y0, w, h, border=(255, 80, 160, 220), bg=(76, 255, 255, 255))
            # 绘制“电脑”标题并居中对齐
            draw_bold_string(img, x0 + 160 - 48, y0 + 12, 24, "\u7535\u8111", color=(255, 20, 24, 30))
            name_zh = GESTURE_ZH.get(self.target_name, self.target_name)
            sub_title = "\u76ee\u6807: " + name_zh
            text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in sub_title)
            tx = x0 + 160 - int((text_len * 26) / 2)
            img.draw_string_advanced(tx, y0 + 60, 26, sub_title, color=(255, 220, 120, 0))

# Finger Specs
FINGER_SPECS = (
    ("T", (1, 2, 3, 4), (255, 80, 80)),
    ("I", (5, 6, 7, 8), (255, 220, 40)),
    ("M", (9, 10, 11, 12), (80, 255, 80)),
    ("R", (13, 14, 15, 16), (80, 220, 255)),
    ("P", (17, 18, 19, 20), (220, 120, 255)),
)

FINGER_DISTANCE_THRESHOLDS = (
    (0.78, 0.42),  # thumb
    (0.88, 0.50),  # index
    (0.90, 0.52),  # middle
    (0.86, 0.50),  # ring
    (0.82, 0.48),  # pinky
)

FINGER_NAMES = ("\u62c7", "\u98df", "\u4e2d", "\u65e0", "\u5c0f")

GESTURE_ZH = {
    "OPEN": "\u5f20\u5f00",      # 张开
    "FIST": "\u63e1\u62f3",      # 握拳
    "ONE": "\u6570\u5b571",      # 数字1
    "TWO": "\u526a\u5200",      # 剪刀
    "ROCK": "\u77f3\u5934",     # 石头
    "PAPER": "\u5e03",          # 布
    "SCISSORS": "\u526a\u5200",  # 剪刀
    "READY": "\u51c6\u5907",     # 准备
    "UNKNOWN": "\u672a\u77e5"    # 未知
}

def scale_x(value):
    return int(value * pl.display_size[0] / 640)

def scale_y(value):
    return int(value * pl.display_size[1] / 480)

def scale_px(value):
    return int(value * pl.display_size[0] / 640)

def scale_rect(rect):
    return (scale_x(rect[0]), scale_y(rect[1]), scale_x(rect[2]), scale_y(rect[3]))

def fill_rect(img, x, y, w, h, color, step=2):
    step = scale_px(step)
    for yy in range(y, y+h, step):
        img.draw_line(x, yy, x+w, yy, color=color, thickness=step)

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
    # 多向 1 像素偏移叠加重绘实现中文文字加粗
    img.draw_string_advanced(x, y, size, text, color=color)
    img.draw_string_advanced(x + 1, y, size, text, color=color)
    img.draw_string_advanced(x, y + 1, size, text, color=color)
    img.draw_string_advanced(x + 1, y + 1, size, text, color=color)

def draw_panel(img, x, y, w, h, border=(255,90,90,90), bg=(255,20,20,20)):
    # 若 bg 的 alpha 通道小于 255 (代表半透明)，则不绘制底部的纯黑投影块，防止黑底污染浅色透明度
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

def draw_round_dots(img, x, y, rounds, max_rounds, score):
    gap = scale_x(15)
    dot_w = scale_x(10)
    dot_h = scale_y(10)
    thickness = scale_px(2)
    for i in range(max_rounds):
        if i < score: color = (255, 0, 220, 80)
        elif i < rounds: color = (255, 220, 80, 40)
        else: color = (255, 80, 80, 80)
        img.draw_rectangle(x+i*gap, y, dot_w, dot_h, color=color, thickness=thickness)

def draw_countdown_meter(img, x, y, w, h, remain_ms, total_ms):
    if total_ms <= 0: return
    value = remain_ms / total_ms
    draw_progress_bar(img, x, y, w, h, value, (255, 255, 210, 40))
    sec = int((remain_ms + 999) // 1000)
    img.draw_string_advanced(x+w+scale_x(8), y-scale_y(6), scale_px(22), "%d" % sec, color=(255, 255, 210, 40))

def draw_pulse_rect(img, x, y, w, h, tick, color):
    offset = scale_px((tick // 180) % 4)
    img.draw_rectangle(x-offset, y-offset, w+offset*2, h+offset*2, color=color, thickness=scale_px(1))
    img.draw_rectangle(x, y, w, h, color=color, thickness=scale_px(2))

def draw_feedback(img, text, tick, good=True):
    if not text: return
    color = (255, 0, 220, 80) if good else (255, 220, 80, 40)
    x = pl.display_size[0] // 2 - scale_x(180) # 精确居中
    y = scale_y(220)
    w = scale_x(360)
    h = scale_y(58)
    # 使用 30% 透明度的浅色毛玻璃背景，排布工整
    draw_panel(img, x, y, w, h, border=color, bg=(76, 255, 255, 255))

    # 动态居中计算文字渲染位置
    text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in text)
    char_w = scale_px(24)
    tx = x + (w // 2) - int((text_len * char_w) / 2)
    ty = y + (h // 2) - (char_w // 2)

    # 采用加粗字体使屏幕弹出式提示更醒目
    draw_bold_string(img, tx, ty, char_w, text, color=color)

def draw_status(img, game, curl, servo, tick, mech_controller):
    x = 352
    y = 20
    w = 320
    now = time.ticks_ms()

    if game.mode == MODE_RPS:
        # 不绘制中间小卡片面板背景，只在屏幕上方的中央直接悬浮打印大字状态提示（如“出拳! 3s”）
        text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in game.message)
        # 用较小字号（22px）并下移位置，防止超出 352-672 像素宽度的中间缝隙，避免被两边的面板遮挡
        tx = 512 - int((text_len * 22) / 2)
        draw_bold_string(img, tx, 65, 22, game.message, color=(255, 255, 255, 0))
        return

    h = 45 if game.mode == MODE_FOLLOW else 95
    draw_flat_panel(img, x, y, w, h, border=(255, 80, 160, 220), bg=(76, 255, 255, 255))

    # 第一行：状态消息
    text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in game.message)
    tx = x + 160 - int((text_len * 20) / 2)
    draw_bold_string(img, tx, y + 10, 20, game.message, color=(255, 20, 24, 30))

    if game.mode != MODE_FOLLOW:
        # 模仿模式
        p_text = "\u6210\u529f: %d \u6b21" % game.score # 成功: X 次
        r_text = "\u5c40\u6570: %d/10" % game.rounds # 局数: Y/10
        img.draw_string_advanced(x + 25, y + 42, 15, p_text, color=(255, 0, 180, 70))
        img.draw_string_advanced(x + 180, y + 42, 15, r_text, color=(255, 220, 120, 0))

        # 第三行：时间进度条
        total = game.countdown_total_ms()
        if total > 0:
            draw_countdown_meter(img, x + 20, y + 72, 280, 10, game.countdown_remain_ms(), total)

def draw_user_panel(img, game, curl, servo_deg, has_hand):
    if game.mode != MODE_RPS: return
    x = 20
    y = 20
    w = 320
    h = 130
    draw_flat_panel(img, x, y, w, h, border=(255, 0, 180, 70), bg=(76, 255, 255, 255))

    # 绘制“玩家”标题并居中对齐
    draw_bold_string(img, x + 160 - 48, y + 12, 24, "\u73a9\u5bb6", color=(255, 20, 24, 30))

    # 绘制玩家得分
    p_text = "\u5f97\u5206: %d" % game.score
    text_len = sum(1.0 if ord(c) > 127 else 0.6 for c in p_text)
    tx = x + 160 - int((text_len * 32) / 2)
    img.draw_string_advanced(tx, y + 60, 32, p_text, color=(255, 0, 180, 70))

def curl_to_servo_deg(curl_value, finger_index):
    # 阈值判断：超过 0.45 判定为极致闭合，否则为极致张开，忽略所有中间过渡状态
    if curl_value >= 0.45:
        return SERVO_MAX_DEG[finger_index]
    else:
        return SERVO_MIN_DEG[finger_index]

class ServoAngleSmoother:
    def __init__(self):
        self.current = [SERVO_MIN_DEG[i] for i in range(5)]
        self.initialized = False

    def reset(self, target_angles=None):
        if target_angles is None:
            self.current = [SERVO_MIN_DEG[i] for i in range(5)]
            self.initialized = False
            return
        self.current = [int(target_angles[i]) for i in range(5)]
        self.initialized = True

    def update(self, target_angles):
        if not self.initialized:
            self.reset(target_angles)
            return self.current[:]
        output = [0, 0, 0, 0, 0]
        for i in range(5):
            target = int(target_angles[i])
            current = float(self.current[i])
            delta = target - current
            if delta == 0:
                output[i] = int(current)
                continue
            delta_abs = abs(delta)
            step = delta * SERVO_SMOOTH_FOLLOW_GAIN[i]
            slow_zone = SERVO_SMOOTH_SLOW_ZONE[i]
            if delta_abs <= slow_zone:
                ratio = delta_abs / slow_zone
                ease = (ratio * ratio * 0.55) + 0.18
                step *= ease
            else:
                far_ratio = (delta_abs - slow_zone) / max(1.0, 40.0 - slow_zone)
                if far_ratio > 1.0: far_ratio = 1.0
                step *= (0.82 + far_ratio * 0.18)
            if delta > 0:
                if delta_abs <= slow_zone and step < 0.6: step = 0.6
                elif step < 1.0: step = 1.0
                if step > SERVO_SMOOTH_MAX_STEP_CLOSE[i]:
                    step = SERVO_SMOOTH_MAX_STEP_CLOSE[i]
            else:
                if delta_abs <= slow_zone and step > -0.6: step = -0.6
                elif step > -1.0: step = -1.0
                if step < -SERVO_SMOOTH_MAX_STEP_OPEN[i]:
                    step = -SERVO_SMOOTH_MAX_STEP_OPEN[i]
            next_value = current + step
            if delta > 0 and next_value > target: next_value = target
            elif delta < 0 and next_value < target: next_value = target
            self.current[i] = next_value
            output[i] = int(next_value)
        return output

touch_lock = _thread.allocate_lock()

def gt911_polling_thread(btn_inst):
    print("GT911 polling thread started.")
    I2C_ADDR = 0x14
    time.sleep_ms(200)
    try:
        from machine import I2C
        i2c = I2C(3, freq=100000)
    except Exception as e:
        print("Failed to initialize I2C3 in touch thread:", e)
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

                            tx = max(0, min(tx, DISPLAY_SIZE[0] - 1))
                            ty = max(0, min(ty, DISPLAY_SIZE[1] - 1))

                            if DISPLAY_MIRROR_MODE == 1:
                                tx = DISPLAY_SIZE[0] - 1 - tx
                            elif DISPLAY_MIRROR_MODE == 2:
                                ty = DISPLAY_SIZE[1] - 1 - ty

                            if track_id not in last_ids: event = "DOWN"
                            else: event = "MOVE"

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

if __name__=="__main__":
    # 解除可能占用了 UART2 的 RT-Thread 控制台终端映射
    import uos
    try:
        uos.dupterm(None)
        print("[LOG] Duplicate terminal disabled on UART.")
    except Exception as e:
        print("[LOG] dupterm not supported or failed:", e)

    display_mode = DISPLAY_MODE
    display_size = DISPLAY_SIZE
    rgb888p_size = RGB888P_SIZE
    hand_det_kmodel_path="/sdcard/examples/kmodel/hand_det.kmodel"
    hand_kp_kmodel_path="/sdcard/examples/kmodel/handkp_det.kmodel"
    anchors_path="/sdcard/examples/utils/prior_data_320.bin"
    hand_det_input_size=[512,512]
    hand_kp_input_size=[256,256]
    confidence_threshold=0.2
    nms_threshold=0.5
    labels=["hand"]
    anchors = [26,27, 53,52, 75,71, 80,99, 106,82, 99,134, 140,113, 161,172, 245,276]

    pl=PipeLine(rgb888p_size=rgb888p_size,display_mode=display_mode, display_size=display_size)
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

    pl.create(to_ide=False, hmirror=sensor_hmirror, vflip=sensor_vflip)

    # 立即隐藏摄像头画面，在启动与主界面期间关闭摄像头
    try:
        Display.unbind_layer(Display.LAYER_VIDEO1)
    except:
        pass
    camera_layer_bound = False

    display_size = pl.get_display_size()

    # 第一阶段加载界面：加载模型
    pl.osd_img.clear()
    fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (255, 255, 255, 255), 4)
    pl.osd_img.draw_string_advanced(200, 190, 40, "\u667a\u80fd\u673a\u68b0\u624b\u63a7\u5236\u7cfb\u7edf", color=(255, 20, 24, 30))
    pl.osd_img.draw_string_advanced(200, 250, 20, "\u59ff\u6001\u8ddf\u968f\u4e0e\u8da3\u5473\u4e92\u52a8", color=(255, 100, 105, 110))
    pl.osd_img.draw_rectangle(200, 320, 624, 20, color=(255, 200, 202, 205), thickness=2)
    fill_rect(pl.osd_img, 200, 320, 150, 20, (255, 80, 160, 220), 2)
    pl.osd_img.draw_string_advanced(200, 355, 18, "\u6b63\u5728\u52a0\u8f7d AI \u8bc6\u522b\u6a21\u578b... 25%", color=(255, 120, 125, 130))
    pl.show_image(flag=osd_rotation)

    # 加载 AI 推理模型
    hkd = HandKeyPointDet(hand_det_kmodel_path, hand_kp_kmodel_path, det_input_size=hand_det_input_size, kp_input_size=hand_kp_input_size, labels=labels, anchors=anchors, confidence_threshold=confidence_threshold, nms_threshold=nms_threshold, nms_option=False, strides=[8,16,32], rgb888p_size=rgb888p_size, display_size=display_size)

    # 第二阶段加载界面：初始化外设
    pl.osd_img.clear()
    fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (255, 255, 255, 255), 4)
    pl.osd_img.draw_string_advanced(200, 190, 40, "\u667a\u80fd\u673a\u68b0\u624b\u63a7\u5236\u7cfb\u7edf", color=(255, 20, 24, 30))
    pl.osd_img.draw_string_advanced(200, 250, 20, "\u59ff\u6001\u8ddf\u968f\u4e0e\u8da3\u5473\u4e92\u52a8", color=(255, 100, 105, 110))
    pl.osd_img.draw_rectangle(200, 320, 624, 20, color=(255, 200, 202, 205), thickness=2)
    fill_rect(pl.osd_img, 200, 320, 400, 20, (255, 80, 160, 220), 2)
    pl.osd_img.draw_string_advanced(200, 355, 18, "\u6b63\u5728\u52a0\u8f7d\u673a\u68b0\u624b\u5916\u8bbe... 65%", color=(255, 120, 125, 130))
    pl.show_image(flag=osd_rotation)

    # 初始化状态机与外设
    mech_state = MechanicalHandState(alpha=0.22)
    mech_controller = MechanicalHandController(enable=True, port=2, baudrate=FOLLOW_UART_BAUDRATE, tx_pin=44, rx_pin=45, send_interval_ms=8, min_delta_deg=FOLLOW_UART_MIN_DELTA_DEG)
    servo_smoother = ServoAngleSmoother()
    buttons = TouchButtons()
    game = GameState()

    # 第三阶段加载界面：就绪进入
    pl.osd_img.clear()
    fill_rect(pl.osd_img, 0, 0, display_size[0], display_size[1], (255, 255, 255, 255), 4)
    pl.osd_img.draw_string_advanced(200, 190, 40, "\u667a\u80fd\u673a\u68b0\u624b\u63a7\u5236\u7cfb\u7edf", color=(255, 20, 24, 30))
    pl.osd_img.draw_string_advanced(200, 250, 20, "\u59ff\u6001\u8ddf\u968f\u4e0e\u8da3\u5473\u4e92\u52a8", color=(255, 100, 105, 110))
    pl.osd_img.draw_rectangle(200, 320, 624, 20, color=(255, 200, 202, 205), thickness=2)
    fill_rect(pl.osd_img, 200, 320, 624, 20, (255, 0, 180, 70), 2)
    pl.osd_img.draw_string_advanced(200, 355, 18, "\u7cfb\u7edf\u51c6\u5907\u5c31\u7eea! \u8fdb\u5165\u6e38\u620f... 100%", color=(255, 0, 180, 70))
    pl.show_image(flag=osd_rotation)
    time.sleep_ms(800)

    in_menu = True
    last_has_hand = False
    hand_missing_start_time = time.ticks_ms()
    hand_detected_voice_played = False
    hand_missing_voice_played = False
    hand_detect_counter = 0
    voice_hand_present = False
    boot_time = time.ticks_ms()

    # 启动引导播报：请说出想体验的模式 (仅在硬件冷启动上电的 6 秒内播报，防止 IDE 调试软重启时重复播报)
    if time.ticks_ms() < 6000:
        mech_controller.play_voice(10)

    while True:
        with ScopedTiming("total",0):
            action = buttons.read_action(in_menu)
            # 忽略上电启动前 1.5 秒内的所有触摸动作，防止触屏初始化自检校准时产生误触
            if time.ticks_diff(time.ticks_ms(), boot_time) < 1500:
                action = None

            # 同时读取并合并来自串口的语音/系统按键控制指令
            uart_action = mech_controller.read_command()
            if uart_action is not None:
                action = uart_action

            if action is not None:
                if action[0] == "mode":
                    game.set_mode(action[1], mech_controller)
                    in_menu = False
                    hand_detected_voice_played = False
                    hand_missing_voice_played = False
                    hand_missing_start_time = time.ticks_ms()
                    hand_detect_counter = 0
                    voice_hand_present = False
                elif action[0] == "menu":
                    in_menu = True
                    hand_detected_voice_played = False
                    hand_missing_voice_played = False
                    hand_missing_start_time = time.ticks_ms()
                    hand_detect_counter = 0
                    voice_hand_present = False
                    mech_controller.play_voice(10)
                elif action[0] == "restart":
                    game.reset()
                    hand_detected_voice_played = False
                    hand_missing_voice_played = False
                    hand_missing_start_time = time.ticks_ms()
                    hand_detect_counter = 0
                    voice_hand_present = False
                    if game.mode == MODE_FOLLOW:
                        mech_controller.play_voice(11)
                    elif game.mode == MODE_MIMIC:
                        mech_controller.play_voice(12)
                    elif game.mode == MODE_RPS:
                        mech_controller.play_voice(13)

            # 动态显示/隐藏摄像头画面
            if in_menu:
                if camera_layer_bound:
                    try:
                        Display.unbind_layer(Display.LAYER_VIDEO1)
                        camera_layer_bound = False
                    except Exception as e:
                        print("Failed to unbind layer:", e)
            else:
                if not camera_layer_bound:
                    try:
                        sensor_bind_info = pl.sensor.bind_info(x=0, y=0, chn=CAM_CHN_ID_0)
                        Display.bind_layer(**sensor_bind_info, layer=Display.LAYER_VIDEO1, flag=video_rotation)
                        camera_layer_bound = True
                    except Exception as e:
                        print("Failed to bind layer:", e)

            # 主菜单界面下跳过图像帧获取与KPU推理，降低CPU负载并保证菜单流畅
            if in_menu:
                tick = time.ticks_ms()
                buttons.draw_menu(pl.osd_img, tick)
                pl.show_image(flag=osd_rotation)
                gc.collect()
                time.sleep_ms(30)
                continue

            img=pl.get_frame()
            det_boxes,hand_res=hkd.run(img)

            has_hand_raw = len(hand_res) > 0
            if has_hand_raw:
                hand_detect_counter = min(20, hand_detect_counter + 1)
            else:
                hand_detect_counter = max(0, hand_detect_counter - 1)

            # 基础手势检测用于舵机运动（2帧低延迟）
            has_hand = (hand_detect_counter >= 2)

            # 迟滞状态机用于语音控制：手掌在画面时需连续 10 帧检测成功才判定为进入，离开画面时必须连续 20 帧检测失败（计数降至0）才判定为离开
            if not voice_hand_present:
                if hand_detect_counter >= 10:
                    voice_hand_present = True
            else:
                if hand_detect_counter == 0:
                    voice_hand_present = False

            has_hand_stable = voice_hand_present

            # 实时交互语音逻辑
            if not in_menu:
                if has_hand_stable:
                    if not hand_detected_voice_played:
                        mech_controller.play_voice(15) # 我识别到了你的手掌
                        hand_detected_voice_played = True
                    last_has_hand = True
                    hand_missing_start_time = 0
                    hand_missing_voice_played = False # 手掌稳定回来时，允许下次离镜后播报一次
                else:
                    if last_has_hand:
                        hand_missing_start_time = time.ticks_ms()
                        last_has_hand = False
                    if hand_missing_start_time > 0 and time.ticks_diff(time.ticks_ms(), hand_missing_start_time) >= 3000:
                        if not hand_missing_voice_played:
                            if game.mode == MODE_FOLLOW or game.phase == "wait_hand" or game.phase == "countdown":
                                mech_controller.play_voice(14) # 请把手掌放到摄像头前
                            hand_missing_voice_played = True

            curl = mech_state.update(hand_res)

            robot_curl = game.get_robot_curl(curl)
            robot_servo = [curl_to_servo_deg(robot_curl[i], i) for i in range(5)]

            game.update(curl, has_hand, mech_controller)
            if game.should_exit_to_menu:
                game.should_exit_to_menu = False
                in_menu = True
                hand_detected_voice_played = False
                hand_missing_voice_played = False
                mech_controller.play_voice(10) # 请说出想体验的模式

            tx_enabled = not in_menu
            mech_controller.enable = tx_enabled
            if tx_enabled:
                mech_controller.update(robot_servo)
                print("[HAND] servo_deg: " + " ".join("%s:%d" % (FINGER_NAMES[i], int(robot_servo[i])) for i in range(5)))
            else:
                servo_smoother.reset(robot_servo)

            tick = time.ticks_ms()

            if in_menu:
                buttons.draw_menu(pl.osd_img, tick)
            else:
                if game.game_over and game.mode == MODE_RPS:
                    pl.osd_img.clear()
                    is_win = (game.score > game.computer_score)
                    if is_win:
                        # 成功背景：带透明度的暗金色毛玻璃遮罩
                        fill_rect(pl.osd_img, 0, 0, pl.display_size[0], pl.display_size[1], (180, 15, 38, 20), 1)
                        # 绘制奖杯
                        fill_rect(pl.osd_img, 482, 245, 60, 12, (255, 220, 160, 0), 1)
                        fill_rect(pl.osd_img, 507, 210, 10, 35, (255, 255, 215, 0), 1)
                        pl.osd_img.draw_circle(512, 175, 35, color=(255, 255, 215, 0), fill=True)
                        pl.osd_img.draw_circle(472, 175, 18, color=(255, 255, 215, 0), fill=False, thickness=4)
                        pl.osd_img.draw_circle(552, 175, 18, color=(255, 255, 215, 0), fill=False, thickness=4)
                        # 绘制文本
                        tx = 512 - 96
                        draw_bold_string(pl.osd_img, tx, 300, 32, "恭喜获得胜利", color=(255, 255, 215, 0))
                        # 绘制皇冠
                        cx = tx + 192 + 15
                        fill_rect(pl.osd_img, cx, 323, 40, 6, (255, 255, 215, 0), 1)
                        pl.osd_img.draw_line(cx, 323, cx, 303, color=(255, 255, 215, 0), thickness=3)
                        pl.osd_img.draw_line(cx, 303, cx+10, 316, color=(255, 255, 215, 0), thickness=3)
                        pl.osd_img.draw_line(cx+10, 316, cx+20, 293, color=(255, 255, 215, 0), thickness=3)
                        pl.osd_img.draw_line(cx+20, 293, cx+30, 316, color=(255, 255, 215, 0), thickness=3)
                        pl.osd_img.draw_line(cx+30, 316, cx+40, 303, color=(255, 255, 215, 0), thickness=3)
                        pl.osd_img.draw_line(cx+40, 303, cx+40, 323, color=(255, 255, 215, 0), thickness=3)
                        pl.osd_img.draw_circle(cx, 301, 3, color=(255, 255, 0, 0), fill=True)
                        pl.osd_img.draw_circle(cx+20, 291, 3, color=(255, 0, 0, 255), fill=True)
                        pl.osd_img.draw_circle(cx+40, 301, 3, color=(255, 0, 255, 0), fill=True)
                    else:
                        # 失败背景：带透明度的暗红灰色毛玻璃遮罩
                        fill_rect(pl.osd_img, 0, 0, pl.display_size[0], pl.display_size[1], (180, 45, 15, 15), 1)
                        # 绘制哭泣表情
                        pl.osd_img.draw_line(460, 175, 480, 190, color=(255, 140, 140, 160), thickness=4)
                        pl.osd_img.draw_line(560, 175, 540, 190, color=(255, 140, 140, 160), thickness=4)
                        pl.osd_img.draw_circle(480, 205, 5, color=(255, 0, 180, 255), fill=True)
                        pl.osd_img.draw_circle(540, 205, 5, color=(255, 0, 180, 255), fill=True)
                        pl.osd_img.draw_line(495, 235, 512, 225, color=(255, 255, 255, 255), thickness=3)
                        pl.osd_img.draw_line(512, 225, 529, 235, color=(255, 255, 255, 255), thickness=3)
                        # 绘制文本
                        tx = 512 - 128
                        draw_bold_string(pl.osd_img, tx, 300, 32, "游戏失败，再接再厉", color=(255, 220, 80, 40))
                else:
                    hkd.draw_result(pl,det_boxes,hand_res)
                    buttons.draw_game_nav(pl.osd_img, tick)
                    draw_status(pl.osd_img, game, curl, robot_servo, tick, mech_controller)
                    draw_user_panel(pl.osd_img, game, curl, robot_servo, has_hand)
                    game.draw_target(pl.osd_img)
                    draw_feedback(pl.osd_img, game.feedback_text(), tick, game.feedback_good())

            pl.show_image(flag=osd_rotation)
            gc.collect()

    hkd.hand_det.deinit()
    hkd.hand_kp.deinit()
    pl.destroy()
