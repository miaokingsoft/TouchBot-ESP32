"""
启动入口 — v2.0
薄壳：硬件初始化 → splash → 隐式执行 main.py
WiFi 不在开机阶段连接（BLE 优先），仅在 Web 菜单按需连接
"""
import gc
try:
    import mdns
    mdns.Active(False)
except Exception:
    pass

from core.hardware import init
from core.splash import run as splash_run

gc.collect()
tft, _, _ = init()

gc.collect()
splash_run(tft)
gc.collect()

print("Boot done. Free heap:", gc.mem_free())
