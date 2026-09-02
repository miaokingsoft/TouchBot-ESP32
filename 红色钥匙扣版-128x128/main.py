"""
创意钥匙扣 v2.1 — 主菜单调度
开机直进 Swipe（BLE 优先），退出后进入菜单：Swipe / Setting / Web
"""
from core.hardware import tft, btn_next, btn_sel
from drivers.ST7735 import TFT
from drivers.sysfont import sysfont
from config import MENU_ITEMS
import time, gc

from app import swipe, setting, web

gc.collect()
print("Free heap before app: ", gc.mem_free())

BLACK = TFT.BLACK
WHITE = TFT.WHITE
BLUE  = TFT.BLUE
NAVY  = TFT.NAVY
GRAY  = TFT.GRAY
CYAN  = TFT.CYAN
GREEN = TFT.GREEN

# ── 菜单布局常量（固定像素坐标，便于局部更新） ──
TITLE_H      = 16
TITLE_TXT_Y  = 4
ITEM_START_Y = 24
ITEM_H       = 14
HILITE_X     = 4
HILITE_W     = 120
TEXT_X       = 12
VERSION_Y    = 112

NUM_ITEMS = len(MENU_ITEMS)

DISPATCH = {
    "swipe":   swipe.run,
    "setting": setting.run,
    "web":     web.run,
}


def draw_menu_first(cur):
    tft.fill(BLACK)

    tft.fillrect((0, 0), (128, TITLE_H), NAVY)
    tft.text((4, TITLE_TXT_Y), "\x07 MENU", WHITE, sysfont, 1)
    tft.text((96, TITLE_TXT_Y), "v2.1", CYAN, sysfont, 1)

    tft.text((30, VERSION_Y), "esp32-xm", GRAY, sysfont, 1)

    for i, item in enumerate(MENU_ITEMS):
        y = ITEM_START_Y + i * ITEM_H
        if i == cur:
            tft.fillrect((HILITE_X, y), (HILITE_W, ITEM_H - 1), BLUE)
            tft.text((TEXT_X, y + 3), item["name"], WHITE, sysfont, 1)
        else:
            tft.text((TEXT_X, y + 3), item["name"], WHITE, sysfont, 1)


def refresh_menu(old, new):
    y_old = ITEM_START_Y + old * ITEM_H
    tft.fillrect((HILITE_X, y_old), (HILITE_W, ITEM_H - 1), BLACK)
    tft.text((TEXT_X, y_old + 3), MENU_ITEMS[old]["name"], WHITE, sysfont, 1)

    y_new = ITEM_START_Y + new * ITEM_H
    tft.fillrect((HILITE_X, y_new), (HILITE_W, ITEM_H - 1), BLUE)
    tft.text((TEXT_X, y_new + 3), MENU_ITEMS[new]["name"], WHITE, sysfont, 1)


def wait_key():
    while True:
        n = btn_next.was_pressed()
        s = btn_sel.was_pressed()
        if n or s:
            return n, s
        time.sleep_ms(30)


def main():
    # 加载持久化设置（覆盖 config 默认值）
    try:
        setting.load_settings()
    except Exception:
        pass
    gc.collect()

    # 开机直进刷视频模式（BLE 优先），退出后回主菜单
    try:
        swipe.run()
    except Exception as e:
        tft.fill(BLACK)
        tft.text((10, 50), "Swipe Error!", TFT.RED, sysfont, 1)
        tft.text((10, 70), str(e)[:30], TFT.RED, sysfont, 1)
        time.sleep(2)

    gc.collect()

    cur = 0
    draw_menu_first(cur)

    while True:
        n, s = wait_key()

        if n:
            old = cur
            cur = (cur + 1) % NUM_ITEMS
            refresh_menu(old, cur)

        if s:
            mid = MENU_ITEMS[cur]["id"]
            handler = DISPATCH.get(mid)
            if handler is None:
                tft.fill(BLACK)
                tft.text((10, 50), "No handler", TFT.RED, sysfont, 1)
                tft.text((10, 70), mid, TFT.RED, sysfont, 1)
                time.sleep(2)
            else:
                try:
                    handler()
                except Exception as e:
                    tft.fill(BLACK)
                    tft.text((10, 50), "Error!", TFT.RED, sysfont, 2)
                    tft.text((10, 75), str(e)[:30], TFT.RED, sysfont, 1)
                    time.sleep(2)

            tft.fill(BLACK)
            draw_menu_first(cur)
            gc.collect()


main()
