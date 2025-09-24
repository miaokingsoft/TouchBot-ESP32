"""
ESP32 OLED 蓝牙HID滑屏控制系统 - 配置文件

配置说明：
- direction: 滑动方向 ("up", "down", "left", "right")
- duration: 单次滑动持续时间(毫秒)
- interval: 固定间隔时间(毫秒)，0表示使用随机间隔
- random_interval: 随机间隔时间范围(毫秒)
- infinite: 是否无限循环模式
- edge_margin: 滑屏起始/结束位置距离边缘的像素值
"""
# 在配置文件开头添加方向验证
VALID_DIRECTIONS = {"up", "down", "left", "right"}

# 预设场景配置
PRESET_PROFILES = {
    "Short Video": {
        "direction": "up", 
        "duration": 800, 
        "interval": 0, 
        "random_interval": (2000, 48000),  # 2-48秒随机间隔
        "infinite": True, # 无限循环模式
        "edge_margin": 400
    },
    "Long Video": {
        "direction": "up", 
        "duration": 600, 
        "interval": 0, 
        "random_interval": (100000, 300000),  # 100-300秒随机间隔
        "infinite": True, # 无限循环模式  
        "edge_margin": 400
    },
    "Read Book": {
        "direction": "left", 
        "duration": 400, 
        "interval": 0, 
        "random_interval": (10000, 20000),  # 10-20秒随机间隔
        "infinite": True,  # 无限循环模式
        "edge_margin": 100
    },
    "Down Browse": {
        "direction": "down", 
        "duration": 400, 
        "interval": 6,
        "random_interval": (8000, 12000),  # 8-1.2秒随机间隔
        "infinite": False,
        "edge_margin": 400
    }
}

# 屏幕配置
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 2168

# 设备名称
DEVICE_NAME = "ESP32C3-Touch"  # 使用更简单的设备名称
# HID设备类型
HID_DEVICE_TYPE = 0x03C1  # 鼠标设备类型，兼容性更好

# 默认滑屏参数
SWIPE_DURATION = 600  # 毫秒
SWIPE_STEPS = 20

# OLED显示配置
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_I2C_SCL = 5
OLED_I2C_SDA = 4

# 按钮配置
BUTTON1_PIN = 1  # 菜单导航/翻页
BUTTON2_PIN = 2  # 启动/停止功能

# LED配置
LED_PIN = 8  # 蓝牙连接状态指示灯

# 名称缩写映射（用于长名称显示）
NAME_ABBREVIATIONS = {
    "Short Video": "SHT_VID",
    "Long Video": "LNG_VID", 
    "Read Book": "RD_Book",
    "Down Browse": "Do_BRW"
}

for profile_name, config in PRESET_PROFILES.items():
    if config["direction"] not in VALID_DIRECTIONS:
        print(f"警告: 场景 '{profile_name}' 的方向 '{config['direction']}' 无效")
        # 默认设置为向上
        config["direction"] = "up"