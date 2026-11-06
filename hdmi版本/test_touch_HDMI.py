'''
=============================================================================
测试脚本: K230 HDMI 触摸屏实时坐标标记与绘图测试程序
适用平台: 01Studio CanMV K230 (1024x600 HDMI / LT9611)
通讯方式: UART2 (Pin 44 TXD, Pin 45 RXD) @ 115200 波特率
功能说明:
  1. 实时接收 CH32 USB Host 转发的 "TOUCH:x,y,event" 触控数据包
  2. 在 1024x600 屏幕上实时绘制十字准星、光环光标与浮动坐标标签
  3. 保留划屏连续移动轨迹线 (画板模式)，检验触摸平滑度与是否有跳点
  4. 屏幕四角设置校准测试靶心框，直观检验边缘与四角对齐情况
  5. 顶部 HUD 状态栏实时显示当前事件 (DOWN/MOVE/UP)、坐标值与接收计数
=============================================================================
'''
import os, sys, time, gc
from media.display import *
import image
from machine import FPIOA, UART

# 屏幕尺寸与串口配置
DISPLAY_WIDTH = 1024
DISPLAY_HEIGHT = 600

UART_PORT = 2
UART_BAUDRATE = 115200
UART_TX_PIN = 44
UART_RX_PIN = 45

# ------------------ 硬件初始化 ------------------
print("==================================================")
print("[TEST] K230 HDMI Touch Screen Visual Test Starting...")

# 1. 禁用控制台重定向以保证串口专属通信
try:
    import uos
    uos.dupterm(None)
except Exception:
    pass

# 2. 引脚复用与串口初始化
try:
    fpioa = FPIOA()
    fpioa.set_function(UART_TX_PIN, FPIOA.UART2_TXD)
    fpioa.set_function(UART_RX_PIN, FPIOA.UART2_RXD)
    print(f"[INIT] FPIOA Configured: Pin {UART_TX_PIN} -> UART2_TXD, Pin {UART_RX_PIN} -> UART2_RXD")
except Exception as e:
    print("[WARN] FPIOA pinmux warning:", e)

uart = None
try:
    uart_id = UART.UART2 if hasattr(UART, 'UART2') else UART_PORT
    uart = UART(uart_id, UART_BAUDRATE)
    print(f"[INIT] UART2 opened at {UART_BAUDRATE} bps.")
except Exception as e:
    print("[ERROR] Failed to open UART2:", e)

# 3. 初始化 HDMI 显示器与 OSD 画布
try:
    Display.init(Display.LT9611, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, osd_num=1, to_ide=False)
    print("[INIT] Display LT9611 initialized (1024x600).")
except Exception as e:
    try:
        Display.init(Display.LT9611, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
        print("[INIT] Display LT9611 fallback initialized.")
    except Exception as e2:
        print("[ERROR] Display.init failed:", e2)

canvas = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.ARGB8888)

def safe_show_canvas(img):
    try:
        Display.show_image(img, 0, 0, Display.LAYER_OSD3)
    except Exception:
        try:
            Display.show_image(img)
        except Exception:
            pass

def draw_text(img, x, y, size, text, color):
    try:
        img.draw_string_advanced(x, y, size, text, color=color)
    except Exception:
        try:
            img.draw_string(x, y, text, color=color, scale=max(1, size // 16))
        except Exception:
            pass

# ------------------ 状态跟踪变量 ------------------
rx_buffer = ""
total_packets = 0

current_x = -1
current_y = -1
current_event = "NONE"
last_up_x = -1
last_up_y = -1

# 轨迹点列表: [(x, y, is_new_stroke), ...]
trail_points = []
MAX_TRAIL_LEN = 400

# 四角校准触发状态 (命中后亮绿灯)
corner_hits = {
    "TL": False,  # 左上 Top-Left
    "TR": False,  # 右上 Top-Right
    "BL": False,  # 左下 Bottom-Left
    "BR": False,  # 右下 Bottom-Right
}

# 按钮区域定义
CLEAR_BTN_RECT = (450, 10, 124, 38)

# ------------------ 串口数据轮询 ------------------
def poll_touch_events():
    global rx_buffer, total_packets
    if uart is None:
        return []

    events = []
    if uart.any():
        try:
            raw = uart.read()
            if raw:
                try:
                    decoded = raw.decode('utf-8', 'ignore')
                    rx_buffer += decoded.replace('\r', '\n')
                except Exception:
                    pass
        except Exception as e:
            print("[WARN] UART read error:", e)

    if not rx_buffer:
        return events

    # 防粘包/防溢出保护
    if len(rx_buffer) > 2048:
        rx_buffer = rx_buffer[-512:]

    while '\n' in rx_buffer:
        line, rx_buffer = rx_buffer.split('\n', 1)
        line = line.strip()
        if not line:
            continue
        line_upper = line.upper()
        if line_upper.startswith("TOUCH:"):
            # 格式: TOUCH:x,y,DOWN / MOVE / UP
            parts = line[6:].split(',')
            if len(parts) >= 3:
                try:
                    px = int(parts[0].strip())
                    py = int(parts[1].strip())
                    pevent = parts[2].strip().upper()
                    events.append((px, py, pevent))
                    total_packets += 1
                except Exception as e:
                    print("[WARN] Coordinate parse failed for line:", line, e)

    return events

# ------------------ 界面渲染函数 ------------------
def render_ui():
    global canvas, corner_hits, trail_points

    # 1. 深色科技背景底板
    canvas.clear()
    canvas.draw_rectangle(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, color=(255, 18, 22, 32), fill=True)

    # 绘制细网格底纹 (每 100 像素一条暗线)
    for gx in range(100, DISPLAY_WIDTH, 100):
        canvas.draw_line(gx, 55, gx, DISPLAY_HEIGHT, color=(255, 30, 36, 50), thickness=1)
    for gy in range(100, DISPLAY_HEIGHT, 100):
        canvas.draw_line(0, gy, DISPLAY_WIDTH, gy, color=(255, 30, 36, 50), thickness=1)

    # 2. 四角校准靶心指示框
    corner_boxes = [
        ("TL", 10, 65, 80, 50, "TL (0,0)"),
        ("TR", 934, 65, 80, 50, "TR (1024,0)"),
        ("BL", 10, 540, 80, 50, "BL (0,600)"),
        ("BR", 934, 540, 80, 50, "BR (1024,600)")
    ]
    for cid, bx, by, bw, bh, blabel in corner_boxes:
        is_hit = corner_hits[cid]
        box_bg = (255, 10, 80, 40) if is_hit else (255, 28, 35, 52)
        box_border = (255, 0, 255, 100) if is_hit else (255, 70, 90, 130)
        canvas.draw_rectangle(bx, by, bw, bh, color=box_bg, fill=True)
        canvas.draw_rectangle(bx, by, bw, bh, color=box_border, thickness=2, fill=False)
        label_col = (255, 150, 255, 180) if is_hit else (255, 160, 180, 210)
        draw_text(canvas, bx + 6, by + 16, 16, blabel + (" OK" if is_hit else ""), label_col)

    # 3. 绘制划屏历史轨迹连线
    if len(trail_points) >= 2:
        for i in range(1, len(trail_points)):
            p1 = trail_points[i - 1]
            p2 = trail_points[i]
            # p2[2] 为 True 表示该笔画起始点，不与前一点相连
            if not p2[2]:
                canvas.draw_line(p1[0], p1[1], p2[0], p2[1], color=(255, 0, 220, 255), thickness=3)

    # 4. 绘制上一次抬手 (UP) 的释放标记点
    if last_up_x >= 0 and last_up_y >= 0:
        canvas.draw_circle(last_up_x, last_up_y, 16, color=(255, 180, 80, 255), thickness=2, fill=False)
        canvas.draw_circle(last_up_x, last_up_y, 4, color=(255, 200, 120, 255), fill=True)
        draw_text(canvas, last_up_x - 30, last_up_y + 18, 14, f"UP:({last_up_x},{last_up_y})", (255, 180, 120, 255))

    # 5. 绘制当前活跃的触摸点 (准星、双层光环、浮动标签)
    if current_event in ("DOWN", "MOVE") and current_x >= 0 and current_y >= 0:
        # 大十字瞄准线 (长 60 像素)
        canvas.draw_line(current_x - 35, current_y, current_x + 35, current_y, color=(255, 255, 220, 0), thickness=2)
        canvas.draw_line(current_x, current_y - 35, current_x, current_y + 35, color=(255, 255, 220, 0), thickness=2)
        # 外层光环 (半径 24)
        canvas.draw_circle(current_x, current_y, 24, color=(255, 0, 255, 255), thickness=3, fill=False)
        # 内层实心触点 (半径 6)
        canvas.draw_circle(current_x, current_y, 6, color=(255, 255, 50, 50), fill=True)
        # 浮动坐标信息气泡 (显示在手指上方 45 像素处)
        bubble_y = max(60, current_y - 45)
        bubble_x = max(10, min(DISPLAY_WIDTH - 160, current_x - 65))
        canvas.draw_rectangle(bubble_x, bubble_y, 130, 30, color=(255, 10, 15, 25), fill=True)
        canvas.draw_rectangle(bubble_x, bubble_y, 130, 30, color=(255, 0, 255, 255), thickness=1, fill=False)
        draw_text(canvas, bubble_x + 8, bubble_y + 6, 18, f"({current_x}, {current_y})", (255, 255, 255, 0))

    # 6. 顶部 HUD 状态栏
    canvas.draw_rectangle(0, 0, DISPLAY_WIDTH, 55, color=(255, 24, 30, 44), fill=True)
    canvas.draw_line(0, 55, DISPLAY_WIDTH, 55, color=(255, 60, 80, 110), thickness=2)

    # 标题
    draw_text(canvas, 16, 15, 24, "K230 触摸屏实时测试", (255, 0, 220, 255))

    # 清空画板按钮
    bx, by, bw, bh = CLEAR_BTN_RECT
    canvas.draw_rectangle(bx, by, bw, bh, color=(255, 45, 55, 80), fill=True)
    canvas.draw_rectangle(bx, by, bw, bh, color=(255, 100, 130, 180), thickness=1, fill=False)
    draw_text(canvas, bx + 18, by + 9, 20, "清空画板", (255, 220, 230, 255))

    # 实时触控状态指示灯
    if current_event == "DOWN":
        ev_col = (255, 50, 240, 50)     # 亮绿
    elif current_event == "MOVE":
        ev_col = (255, 255, 165, 0)    # 亮橙
    elif current_event == "UP":
        ev_col = (255, 230, 70, 70)     # 红色
    else:
        ev_col = (255, 150, 150, 150)  # 灰色待机

    draw_text(canvas, 600, 16, 22, f"[{current_event}]", ev_col)

    # 坐标读数与接收计数
    if current_x >= 0 and current_y >= 0:
        coord_str = f"X:{current_x:4d}  Y:{current_y:4d}"
    else:
        coord_str = "X: ---   Y: --- "
    draw_text(canvas, 710, 16, 22, coord_str, (255, 255, 255, 255))
    draw_text(canvas, 925, 18, 18, f"Pkt:{total_packets}", (255, 160, 200, 240))

    # 7. 提交刷新显示
    safe_show_canvas(canvas)

# ------------------ 主循环 ------------------
def main():
    global current_x, current_y, current_event, last_up_x, last_up_y
    global trail_points, corner_hits

    print("[RUN] Touch visual testing loop started! Touch screen now...")
    render_ui()

    last_render_time = time.ticks_ms()
    needs_render = True

    try:
        while True:
            now = time.ticks_ms()
            events = poll_touch_events()

            if events:
                for tx, ty, tevent in events:
                    current_x = tx
                    current_y = ty
                    current_event = tevent
                    print(f"[TOUCH RX] x={tx:4d}, y={ty:4d}, event={tevent}")

                    # 检查是否点击了顶部【清空画板】按钮
                    cbx, cby, cbw, cbh = CLEAR_BTN_RECT
                    if cbx <= tx <= cbx + cbw and cby <= ty <= cby + cbh and tevent == "DOWN":
                        trail_points.clear()
                        for k in corner_hits:
                            corner_hits[k] = False
                        print("[ACTION] Clear canvas triggered.")
                        continue

                    # 检查四角校准区域命中
                    if tx <= 120 and ty <= 130:
                        corner_hits["TL"] = True
                    elif tx >= 900 and ty <= 130:
                        corner_hits["TR"] = True
                    elif tx <= 120 and ty >= 500:
                        corner_hits["BL"] = True
                    elif tx >= 900 and ty >= 500:
                        corner_hits["BR"] = True

                    # 记录笔画轨迹
                    if tevent == "DOWN":
                        trail_points.append((tx, ty, True))  # 新笔画起始
                    elif tevent == "MOVE":
                        trail_points.append((tx, ty, False)) # 连续笔画连线
                    elif tevent == "UP":
                        last_up_x = tx
                        last_up_y = ty

                    # 轨迹防溢出
                    if len(trail_points) > MAX_TRAIL_LEN:
                        trail_points = trail_points[-MAX_TRAIL_LEN:]

                needs_render = True

            # 刷新屏幕显示 (有新数据或每隔 100ms 保持 HUD 响应)
            if needs_render or time.ticks_diff(now, last_render_time) > 80:
                render_ui()
                last_render_time = now
                needs_render = False

            # 短暂休眠出让 CPU 时间
            time.sleep_ms(5)

    except KeyboardInterrupt:
        print("\n[STOP] Program stopped by user.")
    except Exception as e:
        print("\n[ERROR] Exception in main loop:", e)
    finally:
        try:
            Display.deinit()
        except Exception:
            pass
        print("[EXIT] Cleaned up. Test finished.")

if __name__ == "__main__":
    main()
