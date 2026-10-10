import os
import image
import gc
from media.display import *

print("==================================================")
print("[TEST] Starting background image test script...")

# 1. 自动扫描 /sdcard/data/images/ 下的文件
try:
    print("Files in /sdcard/data/images/:", os.listdir("/sdcard/data/images"))
except Exception as e:
    print("Failed to list directory:", e)

# 初始化显示器
try:
    Display.init(Display.LT9611, width=1024, height=600, osd_num=1, to_ide=False)
    print("Display initialized successfully.")
except Exception as e:
    print("Failed to init Display:", e)

display_size = [1024, 600]
osd_img = image.Image(1024, 600, image.ARGB8888)

def test_draw(path, name):
    print("\n--- Testing:", name, "(", path, ") ---")
    gc.collect()
    print("Free memory before load:", gc.mem_free())
    
    # 尝试加载
    img_obj = None
    try:
        img_obj = image.Image(path)
        print("Successfully loaded. Format:", img_obj.format(), "Size:", img_obj.width(), "x", img_obj.height())
    except Exception as e:
        print("Failed to load:", repr(e))
        return

    # 尝试绘制到 OSD 画布
    try:
        osd_img.clear()
        # 1. 先用不透明黑色填底
        osd_img.draw_rectangle(0, 0, 1024, 600, color=(255, 0, 0, 0), fill=True)
        # 2. 尝试 draw_image
        osd_img.draw_image(img_obj, 0, 0, alpha=255)
        print("Successfully drew on ARGB8888.")
        Display.show_image(osd_img, 0, 0, Display.LAYER_OSD3)
        print("Successfully displayed OSD image.")
    except Exception as e:
        print("Failed to draw/display:", repr(e))

# 测试 1: 1024x600 24位 BMP
test_draw("/sdcard/data/images/menu_bg_1024.bmp", "1024x600 24-bit BMP")

# 测试 2: 320x188 24位 BMP (不缩放)
test_draw("/sdcard/data/images/menu_bg.bmp", "320x188 24-bit BMP (No Scale)")

# 测试 3: 320x188 24位 BMP (缩放)
try:
    print("\n--- Testing: 320x188 BMP with 3.2x Scale ---")
    img_obj = image.Image("/sdcard/data/images/menu_bg.bmp")
    osd_img.clear()
    osd_img.draw_rectangle(0, 0, 1024, 600, color=(255, 0, 0, 0), fill=True)
    osd_img.draw_image(img_obj, 0, 0, x_scale=3.2, y_scale=3.2, alpha=255)
    Display.show_image(osd_img, 0, 0, Display.LAYER_OSD3)
    print("Success scale draw.")
except Exception as e:
    print("Failed scale draw:", repr(e))

# 测试 4: JPG 格式直接加载
test_draw("/sdcard/data/images/menu_bg.jpg", "JPG format standard load")

# 测试 5: JPG 格式带 copy_to_fb=True
try:
    print("\n--- Testing: JPG with copy_to_fb=True ---")
    img_obj = image.Image("/sdcard/data/images/menu_bg.jpg", copy_to_fb=True)
    print("Successfully loaded JPG to FB. Format:", img_obj.format())
    osd_img.clear()
    osd_img.draw_image(img_obj, 0, 0, alpha=255)
    Display.show_image(osd_img, 0, 0, Display.LAYER_OSD3)
    print("Success JPG copy_to_fb draw.")
except Exception as e:
    print("Failed JPG copy_to_fb:", repr(e))

print("\n==================================================")
print("Test completed. Please report which tests printed 'Success' and which method displayed the image on screen!")
print("==================================================")
