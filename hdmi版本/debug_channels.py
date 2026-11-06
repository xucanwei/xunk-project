'''
脚本名称: debug_channels.py
功能: 6 通道逐一单独排查定位工具 (通道确认专用脚本)
原理: 
  每次只让 1 个通道运动，其它 5 个通道严格保持静止不变！
  依次测试 通道 0 -> 通道 1 -> 通道 2 -> 通道 3 -> 通道 4 -> 通道 5
  让您一眼就能 100% 确认哪一个通道控制哪个部位（左右、上下、左上皮、左下皮、右上皮、右下皮）！
'''
import time
import uos
from machine import FPIOA, UART

try:
    uos.dupterm(None)
except Exception:
    pass

class ChannelTester:
    def __init__(self):
        self.device_id = 0x5A
        self.cmd_set_angles = 0x11
        self.uarts = []
        self._init_uarts()

    def _init_uarts(self):
        # 兼容 UART2 与 UART3 同时广播
        try:
            fpioa = FPIOA()
            fpioa.set_function(44, FPIOA.UART2_TXD)
            fpioa.set_function(45, FPIOA.UART2_RXD)
            u2_id = UART.UART2 if hasattr(UART, 'UART2') else 2
            self.uarts.append(UART(u2_id, 115200))
            print("[INFO] UART2 (Pin 44/45) 初始化就绪")
        except Exception:
            pass

        try:
            fpioa = FPIOA()
            fpioa.set_function(28, FPIOA.UART3_TXD)
            fpioa.set_function(29, FPIOA.UART3_RXD)
            u3_id = UART.UART3 if hasattr(UART, 'UART3') else 3
            self.uarts.append(UART(u3_id, 115200))
            print("[INFO] UART3 (Pin 28/29) 初始化就绪")
        except Exception:
            pass

    def _checksum(self, data):
        cs = 0
        for b in data:
            cs ^= b
        return cs & 0xFF

    def send(self, angles):
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
        
        frame_bytes = bytes(frame)
        for u in self.uarts:
            try:
                u.write(frame_bytes)
            except Exception:
                pass


def sweep_single_channel(tester, active_ch, min_deg, max_deg, base_angles, duration_s=4.0):
    """单独往复摆动指定通道，其它通道严格保持 base_angles"""
    start_t = time.ticks_ms()
    step_delay = 30
    steps = 40

    while time.ticks_diff(time.ticks_ms(), start_t) < int(duration_s * 1000):
        # 正向摆动
        for i in range(steps + 1):
            deg = min_deg + (max_deg - min_deg) * (i / float(steps))
            current = list(base_angles)
            current[active_ch] = deg
            tester.send(current)
            time.sleep_ms(step_delay)
        # 反向摆动
        for i in range(steps + 1):
            deg = max_deg - (max_deg - min_deg) * (i / float(steps))
            current = list(base_angles)
            current[active_ch] = deg
            tester.send(current)
            time.sleep_ms(step_delay)


def main():
    print("=" * 65)
    print("      【6 轴舵机通道独立排查定位测试】")
    print("=" * 65)
    print("说明:")
    print("  本脚本将依次只让【1个通道】运动，其它通道保持 90° 不动！")
    print("  请仔细观察每一个阶段，具体是哪一个舵机在转动！\n")

    tester = ChannelTester()
    time.sleep_ms(500)

    # 安全基准角度 (全 90°)
    base = [90.0, 90.0, 90.0, 90.0, 90.0, 90.0]
    print("[基准归中] 所有 6 个通道归中 90°...")
    tester.send(base)
    time.sleep_ms(1500)

    # 准备逐个测试通道
    channels_info = [
        (0, 70.0, 110.0, "通道 0 (servo_set 0)"),
        (1, 70.0, 110.0, "通道 1 (servo_set 1)"),
        (2, 60.0, 100.0, "通道 2 (servo_set 2)"),
        (3, 60.0, 100.0, "通道 3 (servo_set 3)"),
        (4, 90.0, 140.0, "通道 4 (servo_set 4)"),
        (5, 80.0, 110.0, "通道 5 (servo_set 5)"),
    ]

    try:
        while True:
            for ch, min_d, max_d, desc in channels_info:
                print("\n" + "=" * 55)
                print(">>> 正在单独测试: 【%s】 <<<" % desc)
                print(">>> 运动范围: %.1f° <---> %.1f° (持续 4 秒)" % (min_d, max_d))
                print(">>> 请观察: 此时是【左右】？【上下】？还是【哪个眼皮】在动？")
                print("=" * 55)

                sweep_single_channel(tester, ch, min_d, max_d, base, duration_s=4.0)

                # 测试完该通道后，回正到 90° 停顿 1 秒
                tester.send(base)
                print("[完成] %s 结束，暂停 1 秒后测试下一个通道..." % desc)
                time.sleep_ms(1000)

            print("\n一轮全部 6 个通道排查完毕，2 秒后重新开始循环排查...")
            time.sleep_ms(2000)

    except KeyboardInterrupt:
        print("\n[EXIT] 退出测试，全部通道回中 90°。")
        tester.send(base)


if __name__ == "__main__":
    main()
