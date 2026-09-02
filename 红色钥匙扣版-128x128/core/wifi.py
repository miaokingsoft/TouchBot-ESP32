"""
WiFi 按需连接 — v2.0
仅在进入 Web 菜单时调用；先扫描一遍环境，只对存在的已知 SSID 发起连接
"""
from drivers.ST7735 import TFT
from drivers.sysfont import sysfont
import network, time, gc

WHITE = TFT.WHITE
GRAY = TFT.GRAY
CYAN = TFT.CYAN
GREEN = TFT.GREEN
RED = TFT.RED
BLACK = TFT.BLACK


def _kill_mdns():
    try:
        import mdns
        mdns.Active(False)
    except Exception:
        pass


def connect(tft, wifi_config):
    """
    扫描优先的按需连接。
    返回 (成功bool, ip)；全部失败返回 (False, None)
    """
    sta = network.WLAN(network.STA_IF)

    _kill_mdns()

    tft.fill(BLACK)
    tft.text((4, 8), "WiFi Connect", WHITE, sysfont, 1)
    tft.text((4, 24), "Scanning...", GRAY, sysfont, 1)

    # 先扫描一次，只尝试环境中实际存在的已知 SSID
    try:
        sta.active(True)
        scan_result = sta.scan()
        if not scan_result:
            time.sleep_ms(1000)  # 刚激活可能扫不到，稍候重试一次
            scan_result = sta.scan()
        visible = {ap[0].decode() if isinstance(ap[0], bytes) else ap[0]
                   for ap in scan_result}
        if not visible:
            visible = None  # 扫描结果为空则退回逐个盲试
    except Exception:
        visible = None  # 扫描失败则退回逐个盲试

    candidates = ([ap for ap in wifi_config
                   if visible is None or ap["ssid"] in visible])

    if not candidates:
        tft.fillrect((4, 38), (120, 60), BLACK)
        tft.text((4, 50), "No known AP", RED, sysfont, 1)
        time.sleep(1.5)
        gc.collect()
        return False, None

    for idx, ap in enumerate(candidates):
        ssid = ap["ssid"]
        pwd = ap["password"]

        tft.fillrect((4, 38), (120, 50), BLACK)
        tft.text((4, 40), "Try: {}".format(idx + 1), GRAY, sysfont, 1)
        tft.text((4, 56), ssid, CYAN, sysfont, 1)

        sta.connect(ssid, pwd)
        for tick in range(40):          # 40 × 200ms = 8s
            if sta.isconnected():
                ip = sta.ifconfig()[0]
                tft.fillrect((4, 38), (120, 80), BLACK)
                tft.text((4, 44), "Connected!", GREEN, sysfont, 1)
                tft.text((4, 62), ssid, WHITE, sysfont, 1)
                tft.text((4, 80), ip, CYAN, sysfont, 1)
                time.sleep(1)
                gc.collect()
                return True, ip

            dot = "." * ((tick // 4) % 4 + 1)
            tft.fillrect((80, 24), (44, 12), BLACK)
            tft.text((80, 24), dot, GRAY, sysfont, 1)
            time.sleep_ms(200)

        sta.disconnect()
        time.sleep_ms(50)

    tft.fillrect((4, 38), (120, 80), BLACK)
    tft.text((4, 50), "All failed", RED, sysfont, 1)
    tft.text((4, 70), "Offline mode", GRAY, sysfont, 1)
    time.sleep(1.5)
    gc.collect()
    return False, None


def disconnect():
    """断开 WiFi 并关闭 STA（省电，回到离线状态）"""
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            sta.disconnect()
            time.sleep_ms(100)
        sta.active(False)
    except Exception:
        pass
