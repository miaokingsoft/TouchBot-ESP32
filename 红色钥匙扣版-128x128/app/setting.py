"""
设置界面 — 滑动间隔 / 手机分辨率配置
持久化到 settings.json，内存写入 config 模块
"""
from core.hardware import tft, btn_next, btn_sel
from drivers.ST7735 import TFT
from drivers.sysfont import sysfont
import config
import time, gc

BLACK = TFT.BLACK
WHITE = TFT.WHITE
GRAY  = TFT.GRAY
NAVY  = TFT.NAVY
GREEN = TFT.GREEN
CYAN  = TFT.CYAN
YELLOW = TFT.YELLOW
RED   = TFT.RED
BLUE  = TFT.BLUE

SETTINGS_FILE = "settings.json"

# ── 持久化 ──

def load_settings():
    """从 settings.json 加载配置，覆盖 config 默认值"""
    try:
        import json
        with open(SETTINGS_FILE, "r") as f:
            d = json.load(f)
        if "interval_min" in d:
            config.SWIPE_INTERVAL_MIN = int(d["interval_min"])
        if "interval_max" in d:
            config.SWIPE_INTERVAL_MAX = int(d["interval_max"])
        if "screen_w" in d:
            config.PHONE_SCREEN_W = int(d["screen_w"])
        if "screen_h" in d:
            config.PHONE_SCREEN_H = int(d["screen_h"])
        # 兜底：旧版本可能保存过 min > max 的非法组合
        if config.SWIPE_INTERVAL_MIN > config.SWIPE_INTERVAL_MAX:
            config.SWIPE_INTERVAL_MIN, config.SWIPE_INTERVAL_MAX = \
                config.SWIPE_INTERVAL_MAX, config.SWIPE_INTERVAL_MIN
        print("Settings loaded:", d)
    except OSError:
        print("No settings file, using defaults")
    except Exception as e:
        print("Load settings error:", e)


def save_settings():
    """将当前配置保存到 settings.json"""
    try:
        import json
        d = {
            "interval_min": config.SWIPE_INTERVAL_MIN,
            "interval_max": config.SWIPE_INTERVAL_MAX,
            "screen_w": config.PHONE_SCREEN_W,
            "screen_h": config.PHONE_SCREEN_H,
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(d, f)
        print("Settings saved:", d)
    except Exception as e:
        print("Save settings error:", e)


# ── UI 辅助 ──

_ITEMS = ["Interval Min", "Interval Max", "Phone Resolution"]
_ITEM_Y_START = 22
_ITEM_H = 14
_VAL_Y = _ITEM_Y_START + 3 * _ITEM_H + 2   # 数值显示 Y 坐标
_EDIT_Y = 80
_MAX_INTERVAL = 60  # 间隔上限（秒），下限固定为 0


def _adjust_interval(value, delta, lo, hi):
    """在 [lo, hi] 闭区间内循环调整，保证 min <= max 始终成立"""
    span = hi - lo + 1
    if span < 1:
        return lo
    return lo + (value - lo + delta) % span


def _clear(y, h=10):
    tft.fillrect((0, y), (128, h), BLACK)


def _draw_title():
    tft.fill(BLACK)
    tft.fillrect((0, 0), (128, 16), NAVY)
    tft.text((4, 3), "SETTINGS", WHITE, sysfont, 1)


def _draw_items(cur, editing):
    """绘制 3 个设置项"""
    for i, name in enumerate(_ITEMS):
        y = _ITEM_Y_START + i * _ITEM_H
        _clear(y, _ITEM_H)
        if i == cur:
            tft.fillrect((4, y), (120, _ITEM_H - 1), BLUE)
            tft.text((8, y + 3), name, WHITE, sysfont, 1)
        else:
            tft.text((8, y + 3), name, WHITE, sysfont, 1)

    # 在选中项下方显示当前值（局部刷新区域）
    _draw_value(cur)


def _draw_value(cur):
    """仅刷新数值行，不重绘菜单项"""
    _clear(_VAL_Y, 14)
    if cur == 0:
        tft.text((8, _VAL_Y), "Min: %ds" % config.SWIPE_INTERVAL_MIN,
                 CYAN, sysfont, 1)
    elif cur == 1:
        tft.text((8, _VAL_Y), "Max: %ds" % config.SWIPE_INTERVAL_MAX,
                 CYAN, sysfont, 1)
    elif cur == 2:
        tft.text((8, _VAL_Y), "%dx%d" % (
            config.PHONE_SCREEN_W, config.PHONE_SCREEN_H), CYAN, sysfont, 1)


def _draw_edit_hint(cur):
    """绘制编辑模式提示"""
    _clear(_EDIT_Y, 48)
    tft.fillrect((0, _EDIT_Y), (128, 2), YELLOW)
    if cur <= 1:
        tft.text((4, _EDIT_Y + 6), "NXT:+1  Long:-1", YELLOW, sysfont, 1)
        tft.text((4, _EDIT_Y + 18), "SEL:Back Long:Save", YELLOW, sysfont, 1)
    else:
        tft.text((4, _EDIT_Y + 6), "NXT: Next preset", YELLOW, sysfont, 1)
        tft.text((4, _EDIT_Y + 18), "SEL:Back Long:Save", YELLOW, sysfont, 1)


def _draw_normal_hints():
    _clear(_EDIT_Y, 48)
    tft.text((4, _EDIT_Y + 6), "NXT: Move", GRAY, sysfont, 1)
    tft.text((4, _EDIT_Y + 18), "SEL: Edit", GRAY, sysfont, 1)
    tft.text((4, _EDIT_Y + 30), "Long SEL: Save&Exit", GRAY, sysfont, 1)


def _draw_holding():
    """长按等待中的视觉反馈"""
    _clear(_EDIT_Y, 48)
    tft.fillrect((0, _EDIT_Y), (128, 2), RED)
    tft.text((4, _EDIT_Y + 10), "Saving...", RED, sysfont, 2)


def _draw_saved():
    _clear(_EDIT_Y, 48)
    tft.text((4, _EDIT_Y + 10), "Saved!", GREEN, sysfont, 2)


def _find_resolution_index():
    """查找当前分辨率在预设列表中的索引"""
    w = config.PHONE_SCREEN_W
    h = config.PHONE_SCREEN_H
    for i, res in enumerate(config.PHONE_RESOLUTIONS):
        if res[0] == w and res[1] == h:
            return i
    return 0


# ── 主入口 ──

def run():
    _draw_title()
    cur = 0
    editing = False

    _draw_items(cur, editing)
    _draw_normal_hints()

    while True:
        # ── 长按 SEL 保存并退出（任意模式下均生效） ──
        if btn_sel.is_pressed():
            t0 = time.ticks_ms()
            _draw_holding()  # 立即显示“Saving...”反馈
            while btn_sel.is_pressed():
                if time.ticks_diff(time.ticks_ms(), t0) >= 1500:
                    save_settings()
                    _draw_saved()
                    time.sleep(1)
                    return
                time.sleep_ms(20)
            # 松手了，恢复提示区
            if editing:
                _draw_edit_hint(cur)
            else:
                _draw_normal_hints()

        # ── 短按 SEL ──
        if btn_sel.was_pressed():
            if editing:
                # 编辑模式下短按 SEL = 确认，退出编辑
                editing = False
                _draw_items(cur, editing)
                _draw_normal_hints()
            else:
                # 非编辑模式下短按 SEL = 进入编辑
                editing = True
                _draw_edit_hint(cur)
            continue

        # ── btn_next 短按 +1（Min 在 [0, Max]、Max 在 [Min, 60] 内循环） ──
        if btn_next.was_pressed():
            if editing:
                if cur == 0:
                    config.SWIPE_INTERVAL_MIN = _adjust_interval(
                        config.SWIPE_INTERVAL_MIN, 1,
                        0, config.SWIPE_INTERVAL_MAX)
                elif cur == 1:
                    config.SWIPE_INTERVAL_MAX = _adjust_interval(
                        config.SWIPE_INTERVAL_MAX, 1,
                        config.SWIPE_INTERVAL_MIN, _MAX_INTERVAL)
                elif cur == 2:
                    idx = _find_resolution_index()
                    idx = (idx + 1) % len(config.PHONE_RESOLUTIONS)
                    config.PHONE_SCREEN_W = config.PHONE_RESOLUTIONS[idx][0]
                    config.PHONE_SCREEN_H = config.PHONE_RESOLUTIONS[idx][1]
                _draw_value(cur)  # 仅刷新数值
            else:
                cur = (cur + 1) % len(_ITEMS)
                _draw_items(cur, editing)

        # ── 长按 NXT 在编辑模式下 -1（同样受 min<=max 钳制） ──
        if editing and cur <= 1 and btn_next.is_pressed():
            t0 = time.ticks_ms()
            while btn_next.is_pressed():
                if time.ticks_diff(time.ticks_ms(), t0) >= 600:
                    if cur == 0:
                        config.SWIPE_INTERVAL_MIN = _adjust_interval(
                            config.SWIPE_INTERVAL_MIN, -1,
                            0, config.SWIPE_INTERVAL_MAX)
                    elif cur == 1:
                        config.SWIPE_INTERVAL_MAX = _adjust_interval(
                            config.SWIPE_INTERVAL_MAX, -1,
                            config.SWIPE_INTERVAL_MIN, _MAX_INTERVAL)
                    _draw_value(cur)  # 仅刷新数值
                    # 等用户松手
                    while btn_next.is_pressed():
                        time.sleep_ms(20)
                    btn_next.was_pressed()  # 清除标志
                    break
                time.sleep_ms(20)

        time.sleep_ms(40)
