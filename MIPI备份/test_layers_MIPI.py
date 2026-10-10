import os
import image
import gc
from media.display import *
from media.sensor import *

print("==================================================")
print("[TEST] Starting layer-based background test...")

# 初始化显示器
try:
    Display.init(Display.EK79007, width=1024, height=600, osd_num=1, to_ide=False)
    print("Display initialized successfully.")
except Exception as e:
    print("Failed to init Display:", e)

# 尝试加载 1024x600 24位 BMP
img_obj = None
try:
    img_obj = image.Image("/sdcard/data/images/menu_bg_1024.bmp")
    print("Loaded 1024x600 BMP. Format:", img_obj.format())
except Exception as e:
    print("Failed to load BMP:", e)

import time

# 试验 1: 解绑 Video 图层并直接在 LAYER_VIDEO1 上显示背景图
if img_obj:
    try:
        print("\n--- Testing: show_image on LAYER_VIDEO1 (Video Layer) ---")
        Display.unbind_layer(Display.LAYER_VIDEO1)
        Display.show_image(img_obj, 0, 0, Display.LAYER_VIDEO1)
        print("Success displaying on LAYER_VIDEO1. Sleeping for 8 seconds. Please check the screen!")
        time.sleep(8)
    except Exception as e:
        print("Failed to show on LAYER_VIDEO1:", e)

# 试验 2: 在 LAYER_OSD3 上直接显示背景图 (不经过 draw_image)
if img_obj:
    try:
        print("\n--- Testing: show_image on LAYER_OSD3 directly ---")
        Display.show_image(img_obj, 0, 0, Display.LAYER_OSD3)
        print("Success displaying on LAYER_OSD3 directly. Sleeping for 8 seconds. Please check the screen!")
        time.sleep(8)
    except Exception as e:
        print("Failed to show on LAYER_OSD3 directly:", e)

print("==================================================")
