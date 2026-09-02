"""
Web 配置服务 — v2.0
按需连接 WiFi 并启动 HTTP 服务，手机/电脑浏览器远程配置刷视频参数
退出时停止服务并断开 WiFi，回到离线状态
"""
from core.hardware import tft, btn_next, btn_sel
from drivers.ST7735 import TFT
from drivers.sysfont import sysfont
import config
import time, gc

BLACK = TFT.BLACK
WHITE = TFT.WHITE
GRAY = TFT.GRAY
NAVY = TFT.NAVY
GREEN = TFT.GREEN
CYAN = TFT.CYAN
RED = TFT.RED


def _clear(y, h=10):
    tft.fillrect((0, y), (128, h), BLACK)


def _wait_key_exit():
    """轮询按键，返回 'exit' / 'sel' / None"""
    if btn_next.was_pressed():
        return "exit"
    if btn_sel.was_pressed():
        return "sel"
    return None


def run():
    from core import wifi
    from app import http_server

    tft.fill(BLACK)
    tft.fillrect((0, 0), (128, 16), NAVY)
    tft.text((4, 3), "WEB CONFIG", WHITE, sysfont, 1)

    ok, ip = wifi.connect(tft, config.wifi_config)
    if not ok:
        _clear(20, 100)
        tft.text((4, 50), "WiFi failed", RED, sysfont, 1)
        tft.text((4, 70), "Btn: exit", GRAY, sysfont, 1)
        while not (btn_next.was_pressed() or btn_sel.was_pressed()):
            time.sleep_ms(100)
        return

    http_server.start()
    gc.collect()

    tft.fill(BLACK)
    tft.fillrect((0, 0), (128, 16), NAVY)
    tft.text((4, 3), "WEB CONFIG", WHITE, sysfont, 1)
    tft.text((4, 26), "HTTP running", GREEN, sysfont, 1)
    _clear(44, 14)
    tft.text((4, 44), ip, CYAN, sysfont, 1)
    tft.text((4, 60), "Port: %d" % config.HTTP_PORT, CYAN, sysfont, 1)
    tft.text((4, 84), "Open in browser:", GRAY, sysfont, 1)
    tft.text((4, 98), "%s:%d" % (ip, config.HTTP_PORT), WHITE, sysfont, 1)
    tft.text((4, 116), "NXT: Exit", GRAY, sysfont, 1)

    try:
        while True:
            try:
                http_server.poll()
            except Exception:
                pass
            if _wait_key_exit() == "exit":
                return
            time.sleep_ms(30)
    finally:
        http_server.stop()
        wifi.disconnect()
        gc.collect()
