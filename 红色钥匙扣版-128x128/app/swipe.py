"""
刷视频 — BLE 触摸屏翻页 v2.1
  - 可配置滑动间隔和手机屏幕分辨率（从 config.py 读取）
  - 滑动轨迹参数化（SWIPE_TRAVEL_PCT 等），真机可调
  - 自动模式对 interval min/max 做排序防护，避免设置越界时崩溃
"""
from core.hardware import tft, btn_next, btn_sel
from drivers.ST7735 import TFT
from drivers.sysfont import sysfont
import config
import time, random, gc, struct

try:
    import bluetooth
except ImportError:
    bluetooth = None

BLACK = TFT.BLACK
WHITE = TFT.WHITE
GRAY = TFT.GRAY
NAVY = TFT.NAVY
GREEN = TFT.GREEN
RED = TFT.RED
CYAN = TFT.CYAN
YELLOW = TFT.YELLOW

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3
_IRQ_ENCRYPTION_UPDATE = 28
_IRQ_GET_SECRET = 29
_IRQ_SET_SECRET = 30
_IRQ_PASSKEY_ACTION = 31


class HIDTouch:
    def __init__(self):
        self._ble = None
        self._conn = None
        self._rp = None
        self._cccd = None
        self._connected = False
        self.init_ok = False
        self._err = ""
        if bluetooth is None:
            self._err = "no bt module"
            return
        try:
            self._init()
            self.init_ok = True
        except Exception as e:
            self._err = str(e)
            import sys
            sys.print_exception(e)

    def _init(self):
        gc.collect()
        # BLE 与 WiFi 共存受限，进入刷视频前先关闭 STA
        try:
            import network
            sta = network.WLAN(network.STA_IF)
            if sta.isconnected():
                sta.disconnect()
            sta.active(False)
        except Exception:
            pass
        gc.collect()
        time.sleep_ms(500)

        self._ble = bluetooth.BLE()
        for i in range(3):
            try:
                self._ble.active(True)
                break
            except OSError:
                if i < 2:
                    time.sleep_ms(500)
                    gc.collect()
                else:
                    raise
        time.sleep_ms(200)

        try:
            self._ble.config(rxbuf=200)
            self._ble.config(mtu=185)
        except Exception:
            pass

        try:
            self._ble.config(bond=True)
            self._ble.config(mitm=False)
            self._ble.config(le_secure=False)
            self._ble.config(io=3)
        except Exception:
            pass

        self._ble.irq(self._irq)

        # HID 触摸报告描述符
        rp = bytes([
            0x05, 0x0D, 0x09, 0x04, 0xA1, 0x01, 0x09, 0x54, 0x15, 0x00, 0x25, 0x01,
            0x75, 0x08, 0x95, 0x01, 0x81, 0x02, 0x09, 0x55, 0x15, 0x00, 0x25, 0x01,
            0x75, 0x08, 0x95, 0x01, 0x81, 0x02, 0x05, 0x0D, 0x09, 0x22, 0xA1, 0x02,
            0x09, 0x51, 0x15, 0x00, 0x25, 0x01, 0x75, 0x08, 0x95, 0x01, 0x81, 0x02,
            0x09, 0x42, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x01, 0x81, 0x02,
            0x75, 0x07, 0x95, 0x01, 0x81, 0x03, 0x05, 0x01, 0x09, 0x30, 0x15, 0x00,
            0x26, 0xFF, 0x7F, 0x35, 0x00, 0x46, 0xFF, 0x7F, 0x65, 0x11, 0x55, 0x00,
            0x75, 0x10, 0x95, 0x01, 0x81, 0x02, 0x09, 0x31, 0x15, 0x00, 0x26, 0xFF,
            0x7F, 0x35, 0x00, 0x46, 0xFF, 0x7F, 0x65, 0x11, 0x55, 0x00, 0x75, 0x10,
            0x95, 0x01, 0x81, 0x02, 0xC0, 0xC0])

        _CCCD = (bluetooth.UUID(0x2902),
                 bluetooth.FLAG_READ | bluetooth.FLAG_WRITE)
        h = self._ble.gatts_register_services([
            (bluetooth.UUID(0x1812), [
                (bluetooth.UUID(0x2A4A), bluetooth.FLAG_READ),
                (bluetooth.UUID(0x2A4B), bluetooth.FLAG_READ),
                (bluetooth.UUID(0x2A4C), bluetooth.FLAG_WRITE),
                (bluetooth.UUID(0x2A4D),
                 bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY, (_CCCD,)),
                (bluetooth.UUID(0x2A4E),
                 bluetooth.FLAG_READ | bluetooth.FLAG_WRITE_NO_RESPONSE)])])
        sv = h[0]
        self._rp = sv[3]
        self._cccd = sv[4]

        self._ble.gatts_set_buffer(self._rp, 8)

        self._ble.gatts_write(sv[1], rp)
        self._ble.gatts_write(sv[0], struct.pack('<HBB', 0x0111, 0, 0))
        self._ble.gatts_write(sv[5], struct.pack('B', 1))
        self._ble.gatts_write(self._rp, bytearray(8))
        self._ble.gatts_write(self._cccd, struct.pack('<H', 0))

        # 广播数据：完整本地名 + HID 服务标志 + 外观（HID 触摸板）
        n = b"esp32-xm"
        a = bytearray()
        a.append(2); a.append(1); a.append(6)
        a.append(len(n) + 1); a.append(9); a.extend(n)
        a.extend(b"\x03\x03\x12\x18")
        a.extend(b"\x03\x19\xC3\x03")
        self._adv_data = a
        self._ble.gap_advertise(100, a)

    def _irq(self, e, d):
        if e == _IRQ_CENTRAL_CONNECT:
            self._conn = d[0]
            self._connected = True
        elif e == _IRQ_CENTRAL_DISCONNECT:
            self._conn = None
            self._connected = False
            try:
                self._ble.gap_advertise(100, self._adv_data)
            except Exception:
                pass
        elif e == _IRQ_GATTS_WRITE:
            try:
                attr_handle = d[1]
                if self._cccd is not None and attr_handle == self._cccd:
                    v = self._ble.gatts_read(self._cccd)
                    print("CCCD =", list(v))
            except Exception:
                pass
        elif e == _IRQ_ENCRYPTION_UPDATE:
            try:
                conn, enc, auth, bond, ks = d
                print("ENC:", enc, auth, bond, ks)
            except Exception:
                pass
        elif e == _IRQ_PASSKEY_ACTION:
            try:
                self._ble.gap_passkey(d[0], d[1], d[2])
            except Exception:
                pass
        elif e == _IRQ_SET_SECRET:
            return True
        elif e == _IRQ_GET_SECRET:
            return None

    def is_connected(self):
        return self._connected

    def deinit(self):
        try:
            if self._ble is not None:
                self._ble.active(False)
                time.sleep_ms(500)
                self._ble = None
        except Exception:
            pass
        self._connected = False
        gc.collect()

    def send_touch(self, c, tip, x, y):
        """发送触摸坐标，x/y 为手机屏幕像素坐标，自动映射到 HID 0-32767"""
        if not self._connected or self._rp is None:
            return False
        try:
            scr_w = config.PHONE_SCREEN_W
            scr_h = config.PHONE_SCREEN_H
            hx = int(x * 32767 / scr_w)
            hy = int(y * 32767 / scr_h)
            r = struct.pack('BBBBHH', c, 1, 0, tip, hx, hy)
            self._ble.gatts_write(self._rp, r)
            self._ble.gatts_notify(self._conn, self._rp)
            return True
        except Exception:
            return False

    def swipe_up(self):
        """
        向上滑动一次。
        轨迹：起点 70% 屏高 → 终点 30% 屏高（行程 SWIPE_TRAVEL_PCT%），
        报文间隔 >= 30ms（匹配 BLE 连接间隔，避免 notify 被覆盖丢弃）。
        """
        scr_w = config.PHONE_SCREEN_W
        scr_h = config.PHONE_SCREEN_H
        cx = scr_w // 2
        y0 = scr_h * config.SWIPE_START_PCT // 100
        travel = scr_h * config.SWIPE_TRAVEL_PCT // 100
        y1 = y0 - travel

        # 按下并保持，让手机确认这是一次有效拖拽
        self.send_touch(1, 1, cx, y0)
        time.sleep_ms(config.SWIPE_PRESS_MS)

        # 匀速上移，采样点数与间隔由配置决定
        steps = config.SWIPE_STEPS
        for i in range(1, steps + 1):
            ny = y0 - travel * i // steps
            self.send_touch(1, 1, cx, ny)
            time.sleep_ms(config.SWIPE_STEP_MS)

        # 到达终点稍作停顿再抬手，保证完整的手势结束时序
        time.sleep_ms(20)
        self.send_touch(1, 0, cx, y1)
        time.sleep_ms(config.SWIPE_RELEASE_MS)
        self.send_touch(0, 0, cx, y1)
        return True


# ── UI 辅助 ──
def _clear_row(y, h=10):
    tft.fillrect((0, y), (128, h), BLACK)

def _draw_title():
    tft.fill(BLACK)
    tft.fillrect((0, 0), (128, 16), NAVY)
    tft.text((4, 3), "SWIPE VIDEO", WHITE, sysfont, 1)
    tft.text((100, 3), "v2", CYAN, sysfont, 1)

def _draw_info_line(y, label, val, color=WHITE):
    _clear_row(y, 10)
    tft.text((4, y), label, GRAY, sysfont, 1)
    tft.text((50, y), val, color, sysfont, 1)

def _draw_status(connected):
    _clear_row(30, 10)
    tft.text((4, 30), "BLE:", GRAY, sysfont, 1)
    if connected:
        tft.text((30, 30), "Connected", GREEN, sysfont, 1)
    else:
        tft.text((30, 30), "Waiting...", YELLOW, sysfont, 1)

def _draw_resolution():
    w = config.PHONE_SCREEN_W
    h = config.PHONE_SCREEN_H
    _clear_row(18, 10)
    tft.text((4, 18), "Phone:", GRAY, sysfont, 1)
    tft.text((44, 18), "%dx%d" % (w, h), CYAN, sysfont, 1)

def _draw_idle_hints():
    _clear_row(84, 44)
    tft.text((4, 86), "SEL: Auto mode", GRAY, sysfont, 1)
    tft.text((4, 98), "NXT: Exit", GRAY, sysfont, 1)
    tft.text((4, 110), "Long SEL: Exit", GRAY, sysfont, 1)

def _draw_auto_header():
    _clear_row(84, 44)
    tft.text((4, 84), "Auto swiping", GREEN, sysfont, 1)
    tft.text((4, 110), "SEL:Stop NXT:Exit", GRAY, sysfont, 1)

def _update_auto_wait(cnt, secs):
    _clear_row(96, 10)
    tft.text((4, 96), "Cnt:%d W:%ds" % (cnt, secs), YELLOW, sysfont, 1)


# ── 主入口 ──
def run():
    _draw_title()
    _draw_resolution()

    h = HIDTouch()
    try:
        if not h.init_ok:
            _clear_row(44, 20)
            tft.text((4, 44), "BLE Error!", RED, sysfont, 1)
            tft.text((4, 58), h._err[:20], RED, sysfont, 1)
            tft.text((4, 80), "Btn: exit", GRAY, sysfont, 1)
            while not (btn_next.was_pressed() or btn_sel.was_pressed()):
                time.sleep_ms(100)
            return

        _draw_info_line(42, "Interval:", "%d-%ds" % (
            config.SWIPE_INTERVAL_MIN, config.SWIPE_INTERVAL_MAX), WHITE)
        tft.text((4, 56), "BLE ready", GREEN, sysfont, 1)
        auto = False
        _idle_drawn = False
        _last_conn = None

        while True:
            _conn = h.is_connected()
            if _conn != _last_conn:
                _draw_status(_conn)
                _last_conn = _conn

            if auto and h.is_connected():
                _draw_auto_header()
                cnt = 0
                _nxt_exit = False
                _last_cnt = -1
                _last_s = -1
                _update_auto_wait(cnt, 0)
                _last_cnt = cnt
                _last_s = 0
                while True:
                    if btn_sel.was_pressed():
                        auto = False
                        break
                    if btn_next.was_pressed():
                        auto = False
                        _nxt_exit = True
                        break
                    if not h.is_connected():
                        auto = False
                        break
                    h.swipe_up()
                    cnt += 1
                    # 排序防护：设置界面可能保存 min > max
                    lo, hi = sorted((config.SWIPE_INTERVAL_MIN,
                                     config.SWIPE_INTERVAL_MAX))
                    wait = random.randint(lo, hi)
                    for s in range(wait, 0, -1):
                        if btn_sel.was_pressed():
                            auto = False
                            break
                        if btn_next.was_pressed():
                            auto = False
                            _nxt_exit = True
                            break
                        if not h.is_connected():
                            auto = False
                            break
                        if cnt != _last_cnt or s != _last_s:
                            _update_auto_wait(cnt, s)
                            _last_cnt = cnt
                            _last_s = s
                        time.sleep(1)
                    if not auto:
                        break
                if _nxt_exit:
                    return
                if not h.is_connected():
                    auto = False
                    _idle_drawn = False
            else:
                if not _idle_drawn:
                    _draw_idle_hints()
                    _idle_drawn = True

            if btn_sel.was_pressed():
                if h.is_connected():
                    auto = not auto
                    _idle_drawn = False
                else:
                    return

            # btn_next 退出刷视频，返回主菜单
            if btn_next.was_pressed():
                return

            # 长按 SEL 退出
            if btn_sel.is_pressed():
                t0 = time.ticks_ms()
                while btn_sel.is_pressed():
                    if time.ticks_diff(time.ticks_ms(), t0) >= 2000:
                        return
                    time.sleep_ms(20)
                btn_sel.was_pressed()

            time.sleep_ms(50)
    finally:
        h.deinit()
