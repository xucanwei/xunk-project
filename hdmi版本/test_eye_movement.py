'''
脚本名称: test_eye_movement.py
功能: 仿生眼球与眼皮全功能联动测试脚本 (眼球左右、上下与眨眼联动)
适用平台: 01Studio CanMV K230 (支持 UART2 Pin44/45 与 UART3 Pin28/29 双串口同时广播)

通道与角度映射 (第一人称视角):
  - CH0 (左右移动): 110° 正中间, 60° 看向最右边, 160° 看最左边
  - CH1 (上下移动): 90° 正中间, 110° 看最上面, 70° 看最下面
  - CH2 (左眼上眼皮): 60° 打开 / 100° 闭合
  - CH3 (左眼下眼皮): 100° 打开 / 60° 闭合
  - CH4 (右眼上眼皮): 90° 打开 / 140° 闭合
  - CH5 (右眼下眼皮): 110° 打开 / 80° 闭合

循环测试动作序列:
  1. 开机初始：眼球居中 (110°, 90°)，眼皮完全打开
  2. 左右横向扫视：从最左 (160°) -> 最右 (60°) -> 最左 (160°) -> 回中 (110°)
  3. 上下纵向扫视：从最上 (110°) -> 最下 (70°) -> 最上 (110°) -> 回中 (90°)
  4. 顺时针全向看：左到右 -> 上到下 -> 右到左 -> 下到上
  5. 回中眨眼：回正中 (110°, 90°)，自然眨眼一次 (闭合 0.4s 后重新大开)
'''
import time
import uos
from machine import FPIOA, UART

try:
    uos.dupterm(None)
except Exception:
    pass

# ================= 舵机参数配置 (第一人称视角) =================
# Channel 0: 左右移动
YAW_CENTER = 110.0
YAW_RIGHT  = 60.0
YAW_LEFT   = 160.0

# Channel 1: 上下移动
PITCH_CENTER = 90.0
PITCH_UP     = 110.0
PITCH_DOWN   = 70.0

# 眼皮全开与全闭角度 (CH2 ~ CH5)
EYELIDS_OPEN   = [60.0, 100.0, 90.0, 110.0]
EYELIDS_CLOSED = [100.0, 60.0, 140.0, 80.0]


class DualUartController:
    """双串口直通控制器：同时向 UART2(Pin 44/45) 与 UART3(Pin 28/29) 广播"""
    def __init__(self):
        self.device_id = 0x5A
        self.cmd_set_angles = 0x11
        self.uarts = []
        self._init_uarts()

    def _init_uarts(self):
        # 兼容 UART2 (Pin 44 TX, Pin 45 RX)
        try:
            fpioa = FPIOA()
            fpioa.set_function(44, FPIOA.UART2_TXD)
            fpioa.set_function(45, FPIOA.UART2_RXD)
            u2_id = UART.UART2 if hasattr(UART, 'UART2') else 2
            self.uarts.append(("UART2", UART(u2_id, 115200)))
            print("[INFO] UART2 (Pin 44/45) 就绪")
        except Exception:
            pass

        # 兼容 UART3 (Pin 28 TX, Pin 29 RX)
        try:
            fpioa = FPIOA()
            fpioa.set_function(28, FPIOA.UART3_TXD)
            fpioa.set_function(29, FPIOA.UART3_RXD)
            u3_id = UART.UART3 if hasattr(UART, 'UART3') else 3
            self.uarts.append(("UART3", UART(u3_id, 115200)))
            print("[INFO] UART3 (Pin 28/29) 就绪")
        except Exception:
            pass

    def _checksum(self, data):
        cs = 0
        for b in data:
            cs ^= b
        return cs & 0xFF

    def build_frame(self, angles):
        payload_len = 12
        payload = bytearray(payload_len + 4)
        payload[0] = self.device_id
        payload[1] = self.cmd_set_angles
        payload[2] = payload_len
        for ch in range(6):
            deg_x10 = int(round(angles[ch] * 10))
            if deg_x10 < 0: deg_x10 = 0
            elif deg_x10 > 1800: deg_x10 = 1800
            idx = 3 + ch * 2
            payload[idx] = deg_x10 & 0xFF
            payload[idx + 1] = (deg_x10 >> 8) & 0xFF
        payload[-1] = self._checksum(payload[:-1])

        frame = bytearray(len(payload) + 1)
        frame[0] = 0xAA
        for i in range(len(payload)):
            frame[i + 1] = payload[i]
        return bytes(frame)

    def send(self, angles, desc=""):
        frame_bytes = self.build_frame(angles)
        for name, uart in self.uarts:
            try:
                uart.write(frame_bytes)
            except Exception:
                pass
        if desc:
            hex_str = " ".join(["%02X" % b for b in frame_bytes])
            print("[TX] %s | 角度: %s" % (desc, [round(a, 1) for a in angles]))


def smooth_move(controller, start_yaw, start_pitch, end_yaw, end_pitch, eyelids, duration_ms=1000, step_ms=25):
    """平滑插值移动眼球"""
    steps = max(1, int(duration_ms / step_ms))
    for i in range(steps + 1):
        ratio = i / float(steps)
        curr_yaw = start_yaw + (end_yaw - start_yaw) * ratio
        curr_pitch = start_pitch + (end_pitch - start_pitch) * ratio
        frame_angles = [curr_yaw, curr_pitch] + eyelids
        controller.send(frame_angles)
        time.sleep_ms(step_ms)


def main():
    print("=" * 65)
    print("      【仿生眼球全功能运动测试：左右 + 上下 + 眨眼联动】")
    print("=" * 65)
    print("设定参数 (第一人称视角):")
    print("  - CH0 (左右): 最右 %d° <--- 中间 %d° ---> 最左 %d°" % (YAW_RIGHT, YAW_CENTER, YAW_LEFT))
    print("  - CH1 (上下): 最下 %d° <--- 中间 %d° ---> 最上 %d°" % (PITCH_DOWN, PITCH_CENTER, PITCH_UP))
    print("  - CH2~5 眼皮: 全开 [60°, 100°, 140°, 80°], 闭合 [100°, 60°, 90°, 110°]")
    print("\n提示: 在终端按 Ctrl+C 可停止并回正闭眼休眠。")
    print("=" * 65)

    controller = DualUartController()
    time.sleep_ms(300)

    # 1. 开机初始就位：眼球居中，眼皮大开
    print("\n[INIT] 眼球居中 (110°, 90°)，打开眼皮...")
    init_angles = [YAW_CENTER, PITCH_CENTER] + EYELIDS_OPEN
    controller.send(init_angles, desc="【初始居中全开】")
    time.sleep_ms(1000)

    loop_count = 1
    try:
        while True:
            print("\n" + "=" * 55)
            print(">>> 开始第 %d 轮完整运动测试 <<<" % loop_count)
            print("=" * 55)

            # =================================================================
            # 测试项目 1：左右移动专项测试 (Pitch 锁定在 90° 正中间)
            # =================================================================
            print("\n--- [测试 1/3] 左右移动测试 (Pitch 保持 90°) ---")
            
            print("  1. 从正中间 (110°) 看到最左边 (160°)...")
            smooth_move(controller, YAW_CENTER, PITCH_CENTER, YAW_LEFT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(400)

            print("  2. >>> 从最左边 (160°) 匀速扫到最右边 (60°)...")
            smooth_move(controller, YAW_LEFT, PITCH_CENTER, YAW_RIGHT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=1400)
            time.sleep_ms(400)

            print("  3. >>> 从最右边 (60°) 匀速扫回最左边 (160°)...")
            smooth_move(controller, YAW_RIGHT, PITCH_CENTER, YAW_LEFT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=1400)
            time.sleep_ms(400)

            print("  4. 左右回正到中间 (110°)...")
            smooth_move(controller, YAW_LEFT, PITCH_CENTER, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(500)

            # =================================================================
            # 测试项目 2：上下移动专项测试 (Yaw 锁定在 110° 正中间)
            # =================================================================
            print("\n--- [测试 2/3] 上下移动测试 (Yaw 保持 110°) ---")

            print("  1. 从正中间 (90°) 看到最上面 (110°)...")
            smooth_move(controller, YAW_CENTER, PITCH_CENTER, YAW_CENTER, PITCH_UP, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(400)

            print("  2. >>> 从最上面 (110°) 匀速扫到最下面 (70°)...")
            smooth_move(controller, YAW_CENTER, PITCH_UP, YAW_CENTER, PITCH_DOWN, EYELIDS_OPEN, duration_ms=1200)
            time.sleep_ms(400)

            print("  3. >>> 从最下面 (70°) 匀速扫回最上面 (110°)...")
            smooth_move(controller, YAW_CENTER, PITCH_DOWN, YAW_CENTER, PITCH_UP, EYELIDS_OPEN, duration_ms=1200)
            time.sleep_ms(400)

            print("  4. 上下回正到中间 (90°)...")
            smooth_move(controller, YAW_CENTER, PITCH_UP, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(500)

            # =================================================================
            # 测试项目 3：组合轨迹 (左到右 -> 上到下 -> 右到左 -> 下到上)
            # =================================================================
            print("\n--- [测试 3/3] 四向环顾组合轨迹 ---")

            # 1. 从左看到右
            print("  (A) 从左看到右 (Yaw: 160° -> 60°)...")
            smooth_move(controller, YAW_CENTER, PITCH_CENTER, YAW_LEFT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=500)
            smooth_move(controller, YAW_LEFT, PITCH_CENTER, YAW_RIGHT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=1200)
            time.sleep_ms(300)

            # 2. 从上看到下
            print("  (B) 从上看到下 (Pitch: 110° -> 70°)...")
            smooth_move(controller, YAW_RIGHT, PITCH_CENTER, YAW_CENTER, PITCH_UP, EYELIDS_OPEN, duration_ms=500)
            smooth_move(controller, YAW_CENTER, PITCH_UP, YAW_CENTER, PITCH_DOWN, EYELIDS_OPEN, duration_ms=1000)
            time.sleep_ms(300)

            # 3. 从右看到左
            print("  (C) 从右看到左 (Yaw: 60° -> 160°)...")
            smooth_move(controller, YAW_CENTER, PITCH_DOWN, YAW_RIGHT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=500)
            smooth_move(controller, YAW_RIGHT, PITCH_CENTER, YAW_LEFT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=1200)
            time.sleep_ms(300)

            # 4. 从下看到上
            print("  (D) 从下看到上 (Pitch: 70° -> 110°)...")
            smooth_move(controller, YAW_LEFT, PITCH_CENTER, YAW_CENTER, PITCH_DOWN, EYELIDS_OPEN, duration_ms=500)
            smooth_move(controller, YAW_CENTER, PITCH_DOWN, YAW_CENTER, PITCH_UP, EYELIDS_OPEN, duration_ms=1000)
            time.sleep_ms(300)

            # 回正
            print("  (E) 回正中间 (110°, 90°)...")
            smooth_move(controller, YAW_CENTER, PITCH_UP, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, duration_ms=500)
            time.sleep_ms(400)

            # =================================================================
            # 测试项目 4：眨眼一次交互
            # =================================================================
            print("\n--- [眨眼动作] 自然眨眼一次 (闭合 0.4s -> 重新大开) ---")
            close_frame = [YAW_CENTER, PITCH_CENTER] + EYELIDS_CLOSED
            controller.send(close_frame, desc="【眨眼: 闭合】")
            time.sleep_ms(400)

            open_frame = [YAW_CENTER, PITCH_CENTER] + EYELIDS_OPEN
            controller.send(open_frame, desc="【眨眼: 睁开】")
            time.sleep_ms(800)

            loop_count += 1

    except KeyboardInterrupt:
        print("\n[EXIT] 收到中断信号，眼球回正居中并完全闭合眼皮...")
        sleep_frame = [YAW_CENTER, PITCH_CENTER] + EYELIDS_CLOSED
        controller.send(sleep_frame, desc="【安全休眠】")
        print("[EXIT] 测试结束。")


if __name__ == "__main__":
    main()
