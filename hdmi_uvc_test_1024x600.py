'''
HDMI (7寸 1024x600) + USB (UVC) 摄像头高清缩放显示测试程序
平台: 01Studio CanMV K230 (V3.0)
显示芯片: LT9611 (HDMI 转接芯片, 分辨率 1024x600 @ 60Hz)
摄像头: USB UVC 摄像头 (640x480 MJPEG 输入 ➔ 1024x600 高清极速平铺)
'''
import time
import gc
from media.display import *
from media.uvc import *

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

print("[HDMI TEST 1024x600] Starting UVC Camera to HDMI (LT9611 1024x600) Display Test...")

# 初始化 HDMI LT9611 显示, 设定分辨率为 1024x600
Display.init(Display.LT9611, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, to_ide=False)

while True:
    plugin, dev = UVC.probe()
    if plugin:
        print(f"[INFO] USB Camera Detected: {dev}")
        break
    time.sleep_ms(100)

mode = UVC.video_mode(640, 480, UVC.FOURCC_MJPEG, 30)
succ, mode = UVC.select_video_mode(mode)
print(f"[INFO] UVC 640x480 video mode select status: {succ}, mode: {mode}")

UVC.start(cvt=False)
fps = time.clock()

try:
    while True:
        fps.tick()
        img = UVC.snapshot()
        if img is not None:
            try:
                # 1. 转换为 RGB565 基础图像
                img_rgb = img.to_rgb565()
                
                # 2. 将 640x480 的图像拉伸平铺至 1024x600 HDMI 7寸屏幕
                img_scaled = img_rgb.copy(x_size=SCREEN_WIDTH, y_size=SCREEN_HEIGHT)
                
                # 3. 在画面上绘制高科技 HDMI 标识与 FPS 统计
                img_scaled.draw_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, color=(0, 255, 0), thickness=3)
                img_scaled.draw_string_advanced(40, 40, 32, "DISPLAY: HDMI 7-INCH (LT9611 1024x600)", color=(0, 255, 0))
                img_scaled.draw_string_advanced(40, 90, 28, f"CAMERA : USB UVC MODE | FPS: {fps.fps():.1f}", color=(255, 255, 0))
                
                # 4. 推送到 HDMI 屏幕输出
                Display.show_image(img_scaled)
                
                img_scaled.__del__()
                img_rgb.__del__()
                img.__del__()
            except OSError:
                pass
        gc.collect()
except KeyboardInterrupt:
    pass
finally:
    print("[INFO] Shutting down HDMI UVC Mode...")
    UVC.stop()
    time.sleep_ms(100)
    Display.deinit()
