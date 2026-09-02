# ============================================================
# 配置文件 — 菜单 / WiFi / 刷视频参数
# ============================================================

# ===== 菜单项目 =====
MENU_ITEMS = [
    {"name": "Swipe",      "id": "swipe"},
    {"name": "Setting",    "id": "setting"},
    {"name": "Web",        "id": "web"},
]

# ===== WiFi 配置 =====
wifi_config = [
    {"ssid": "www.qiwen.cn",   "password": "miao13006331630"},
    {"ssid": "WHDC",           "password": "whdc5325"},
    {"ssid": "Honor 7X",       "password": "83842911"},
    {"ssid": "Mk",             "password": "83842911"},
    {"ssid": "MKNET",          "password": "83842911"},
]

# ===== 刷视频 — 滑动间隔（秒） =====
SWIPE_INTERVAL_MIN = 10
SWIPE_INTERVAL_MAX = 40

# ===== 刷视频 — 滑动手势参数（真机调优用） =====
# 行程占屏高百分比：过低（<25）短视频 App 常不翻页
SWIPE_TRAVEL_PCT = 40
# 起点占屏高百分比（向上滑，起点在下、终点在上）
SWIPE_START_PCT = 70
# 移动采样点数与间隔（间隔应 >= BLE 连接间隔 30ms，过快会丢报文）
SWIPE_STEPS = 10
SWIPE_STEP_MS = 30
# 按下后保持时长（部分机型需 >=80ms 才承认拖拽）
SWIPE_PRESS_MS = 80
# tip-off 后到 release 的间隔
SWIPE_RELEASE_MS = 40

# ===== 刷视频 — 目标手机屏幕分辨率 =====
PHONE_SCREEN_W = 1080
PHONE_SCREEN_H = 1920

# 预设分辨率列表 (宽, 高, 名称)
PHONE_RESOLUTIONS = [
    (1080, 1920, "1080x1920"),
    (720,  1280, "720x1280"),
    (1080, 2340, "1080x2340"),
    (1080, 2400, "1080x2400"),
    (1440, 2560, "1440x2560"),
    (1440, 3200, "1440x3200"),
]

# ===== HTTP 服务端口 =====
HTTP_PORT = 8080
