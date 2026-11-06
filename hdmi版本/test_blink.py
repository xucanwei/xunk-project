'''
脚本名称: test_blink.py
功能: 仿生眼球双眼同步眨眼与全功能联动测试脚本 (左右眼完全同步眨眼 + 眼球四向平滑扫视)
适用平台: 01Studio CanMV K230 (专用 UART3 Pin28 TX / Pin29 RX 高速串口通信)

通道与角度映射 (第一人称视角):
  - CH0 (左右移动): 110° 正中间, 60° 看向最右边, 160° 看最左边
  - CH1 (上下移动): 85° 正中间, 100° 看向最上面, 70° 看向最下面 (±15° 对称行程)
  - CH2 (左眼上眼皮): 60° 打开 / 100° 闭合
  - CH3 (左眼下眼皮): 100° 打开 / 60° 闭合
  - CH4 (右眼上眼皮): 110° 打开 / 60° 闭合
  - CH5 (右眼下眼皮): 80° 打开 / 110° 闭合

双眼同步开闭基准帧:
  - 双眼完全打开 (CH2~5): [60.0°, 100.0°, 110.0°, 80.0°]
  - 双眼完全闭合 (CH2~5): [100.0°, 60.0°, 60.0°, 110.0°]

循环测试动作:
  1. 双眼同步完全闭合 (保持 1.5 秒)
  2. 双眼同步完全睁开 (保持 1.5 秒)
  3. 双眼保持睁开，眼球左右水平扫视，回正后自然双眨眼 1 次
  4. 双眼保持睁开，眼球上下垂直扫视，回正后自然双眨眼 1 次
  5. 双眼保持睁开，眼球环顾一圈，回正后连续双眨眼 2 次
'''
import time
import uos
import gc
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
PITCH_CENTER = 85.0
PITCH_UP     = 100.0
PITCH_DOWN   = 70.0

# 双眼同步全开 (左眼: 60/100, 右眼: 110/80)
EYELIDS_OPEN   = [60.0, 100.0, 110.0, 80.0]
# 双眼同步全闭 (左眼: 100/60, 右眼: 60/110)
EYELIDS_CLOSED = [100.0, 60.0, 60.0, 110.0]

# 预分配 6 通道临时数组，零内存申请，消灭 MicroPython GC 顿挫
_temp_angles = [110.0, 85.0, 60.0, 100.0, 110.0, 80.0]


class DualUartController:
    """专用串口控制器：预分配零申请，专一定向 UART3 (Pin 28 TX / Pin 29 RX)"""
    def __init__(self):
        self.device_id = 0x5A
        self.cmd_set_angles = 0x11
        # 预分配固定 17 字节发送缓冲区，彻底避免运行中申请内存触发 GC 顿挫
        self._frame_buf = bytearray(17)
        self._frame_buf[0] = 0xAA
        self._frame_buf[1] = self.device_id
        self._frame_buf[2] = self.cmd_set_angles
        self._frame_buf[3] = 12
        self.uart = None
        self._init_uart()

    def _init_uart(self):
        # 专一定向 UART3 (Pin 28 TX, Pin 29 RX)
        try:
            fpioa = FPIOA()
            fpioa.set_function(28, FPIOA.UART3_TXD)
            fpioa.set_function(29, FPIOA.UART3_RXD)
            u3_id = UART.UART3 if hasattr(UART, 'UART3') else 3
            self.uart = UART(u3_id, 115200)
            print("[INFO] UART3 (Pin 28 TX / Pin 29 RX) 就绪")
        except Exception as e:
            print("[WARN] UART3 初始化失败:", e)

    def send(self, angles, desc=""):
        buf = self._frame_buf
        cs = 0x5A ^ 0x11 ^ 12
        for ch in range(6):
            deg_x10 = int(round(angles[ch] * 10))
            if deg_x10 < 0: deg_x10 = 0
            elif deg_x10 > 1800: deg_x10 = 1800
            idx = 4 + ch * 2
            low = deg_x10 & 0xFF
            high = (deg_x10 >> 8) & 0xFF
            buf[idx] = low
            buf[idx + 1] = high
            cs ^= low ^ high
        buf[16] = cs & 0xFF

        if self.uart:
            try:
                self.uart.write(buf)
            except Exception:
                pass
        if desc:
            print("[TX] %s | 角度: %s" % (desc, [round(a, 1) for a in angles]))


def smooth_move_eye(controller, start_yaw, start_pitch, end_yaw, end_pitch, eyelids, duration_ms=1000, step_ms=25):
    """平滑移动眼球方向，眼皮保持指定状态 (零内存分配)"""
    steps = max(1, int(duration_ms / step_ms))
    for i in range(steps + 1):
        ratio = i / float(steps)
        _temp_angles[0] = start_yaw + (end_yaw - start_yaw) * ratio
        _temp_angles[1] = start_pitch + (end_pitch - start_pitch) * ratio
        _temp_angles[2] = eyelids[0]
        _temp_angles[3] = eyelids[1]
        _temp_angles[4] = eyelids[2]
        _temp_angles[5] = eyelids[3]
        controller.send(_temp_angles)
        time.sleep_ms(step_ms)


def smooth_eyelids(controller, curr_yaw, curr_pitch, start_eyelids, end_eyelids, duration_ms=250, step_ms=25):
    """双眼皮平滑过渡 (全开 <-> 全闭，零内存分配)"""
    steps = max(1, int(duration_ms / step_ms))
    for i in range(steps + 1):
        ratio = i / float(steps)
        _temp_angles[0] = curr_yaw
        _temp_angles[1] = curr_pitch
        _temp_angles[2] = start_eyelids[0] + (end_eyelids[0] - start_eyelids[0]) * ratio
        _temp_angles[3] = start_eyelids[1] + (end_eyelids[1] - start_eyelids[1]) * ratio
        _temp_angles[4] = start_eyelids[2] + (end_eyelids[2] - start_eyelids[2]) * ratio
        _temp_angles[5] = start_eyelids[3] + (end_eyelids[3] - start_eyelids[3]) * ratio
        controller.send(_temp_angles)
        time.sleep_ms(step_ms)


def blink_action(controller, curr_yaw, curr_pitch, blink_count=1):
    """双眼同步自然眨眼：闭合 -> 睁开"""
    for b in range(blink_count):
        # 1. 快速合拢 (120ms)
        smooth_eyelids(controller, curr_yaw, curr_pitch, EYELIDS_OPEN, EYELIDS_CLOSED, duration_ms=120)
        time.sleep_ms(80) # 闭目轻顿

        # 2. 迅速睁开 (150ms)
        smooth_eyelids(controller, curr_yaw, curr_pitch, EYELIDS_CLOSED, EYELIDS_OPEN, duration_ms=150)

        if b < blink_count - 1:
            time.sleep_ms(120)


def main():
    print("=" * 65)
    print("      【仿生眼球双眼 100% 同步眨眼与眼球联动测试】")
    print("=" * 65)
    print("开合角度 (第一人称视角):")
    print("  - 左眼: 60°/100° 完全打开, 100°/60° 完全闭合")
    print("  - 右眼: 110°/80° 完全打开, 60°/110° 完全闭合 (左右眼完全同相同步)")
    print("  - 眼球中位: 左右 110°, 上下 85° (上100°, 下70°)")
    print("\n提示: 终端随时按 Ctrl+C 可停止并回正闭眼休眠。")
    print("=" * 65)

    controller = DualUartController()
    time.sleep_ms(300)

    # 1. 初始就位：双眼同步完全打开，眼球居中
    print("\n[INIT] 双眼同步完全打开，眼球居中 (110°, 85°)...")
    controller.send([YAW_CENTER, PITCH_CENTER] + EYELIDS_OPEN, desc="【双眼全开初始就位】")
    time.sleep_ms(1500)

    loop_count = 1
    try:
        while True:
            gc.collect()
            print("\n" + "=" * 55)
            print(">>> 开始第 %d 轮双眼同步联动测试 <<<" % loop_count)
            print("=" * 55)

            # -----------------------------------------------------------------
            # 测试 1: 双眼纯眨眼开闭同步测试 (眼球居中不动)
            # -----------------------------------------------------------------
            print("\n--- [1/4] 双眼同步纯开闭测试 (保持 1.5 秒观察同步度) ---")
            print("  >>> 【双眼同步闭合】(左: 100°/60°, 右: 60°/110°)...")
            smooth_eyelids(controller, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, EYELIDS_CLOSED, duration_ms=200)
            controller.send([YAW_CENTER, PITCH_CENTER] + EYELIDS_CLOSED, desc="【双眼完全闭合】")
            time.sleep_ms(1300)

            print("  >>> 【双眼同步打开】(左: 60°/100°, 右: 110°/80°)...")
            smooth_eyelids(controller, YAW_CENTER, PITCH_CENTER, EYELIDS_CLOSED, EYELIDS_OPEN, duration_ms=200)
            controller.send([YAW_CENTER, PITCH_CENTER] + EYELIDS_OPEN, desc="【双眼完全打开】")
            time.sleep_ms(1300)

            # -----------------------------------------------------------------
            # 测试 2: 左右水平扫视 + 回正眨眼
            # -----------------------------------------------------------------
            print("\n--- [2/4] 左右扫视 + 回正眨眼 ---")
            print("  1. 从正中间 (110°) 扫视到最左边 (160°)...")
            smooth_move_eye(controller, YAW_CENTER, PITCH_CENTER, YAW_LEFT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(250)

            print("  2. 从最左边 (160°) 匀速扫视到最右边 (60°)...")
            smooth_move_eye(controller, YAW_LEFT, PITCH_CENTER, YAW_RIGHT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=1300)
            time.sleep_ms(250)

            print("  3. 从最右边 (60°) 回正到正中间 (110°)...")
            smooth_move_eye(controller, YAW_RIGHT, PITCH_CENTER, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(300)

            print("  >>> 【双眼同步自然眨眼 1 次】...")
            blink_action(controller, YAW_CENTER, PITCH_CENTER, blink_count=1)
            time.sleep_ms(500)

            # -----------------------------------------------------------------
            # 测试 3: 上下垂直扫视 + 回正眨眼
            # -----------------------------------------------------------------
            print("\n--- [3/4] 上下垂直扫视 + 回正眨眼 ---")
            print("  1. 从正中间 (85°) 抬起到最上面 (100°)...")
            smooth_move_eye(controller, YAW_CENTER, PITCH_CENTER, YAW_CENTER, PITCH_UP, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(250)

            print("  2. 从最上面 (100°) 匀速扫视到最下面 (70°)...")
            smooth_move_eye(controller, YAW_CENTER, PITCH_UP, YAW_CENTER, PITCH_DOWN, EYELIDS_OPEN, duration_ms=1100)
            time.sleep_ms(250)

            print("  3. 从最下面 (70°) 回正到正中间 (85°)...")
            smooth_move_eye(controller, YAW_CENTER, PITCH_DOWN, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, duration_ms=600)
            time.sleep_ms(300)

            print("  >>> 【双眼同步自然眨眼 1 次】...")
            blink_action(controller, YAW_CENTER, PITCH_CENTER, blink_count=1)
            time.sleep_ms(500)

            # -----------------------------------------------------------------
            # 测试 4: 环顾一圈 + 连续双眨眼
            # -----------------------------------------------------------------
            print("\n--- [4/4] 四向环视 + 连续双眨眼 ---")
            smooth_move_eye(controller, YAW_CENTER, PITCH_CENTER, YAW_LEFT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=450)
            smooth_move_eye(controller, YAW_LEFT, PITCH_CENTER, YAW_CENTER, PITCH_UP, EYELIDS_OPEN, duration_ms=500)
            smooth_move_eye(controller, YAW_CENTER, PITCH_UP, YAW_RIGHT, PITCH_CENTER, EYELIDS_OPEN, duration_ms=500)
            smooth_move_eye(controller, YAW_RIGHT, PITCH_CENTER, YAW_CENTER, PITCH_DOWN, EYELIDS_OPEN, duration_ms=500)
            smooth_move_eye(controller, YAW_CENTER, PITCH_DOWN, YAW_CENTER, PITCH_CENTER, EYELIDS_OPEN, duration_ms=450)
            time.sleep_ms(250)

            print("  >>> 【双眼同步连眨两下】...")
            blink_action(controller, YAW_CENTER, PITCH_CENTER, blink_count=2)
            time.sleep_ms(1200)

            loop_count += 1

    except KeyboardInterrupt:
        print("\n[EXIT] 收到中断信号，眼球回正并双眼完全闭合休眠...")
        controller.send([YAW_CENTER, PITCH_CENTER] + EYELIDS_CLOSED, desc="【双眼全闭休眠退出】")
        print("[EXIT] 测试结束。")


if __name__ == "__main__":
    main()
