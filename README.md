# TouchBot-ESP32
TouchBot-ESP32 是一个开源的安卓手机滑屏控制系统，允许ESP32设备通过蓝牙HID协议模拟触摸屏操作安卓手机。支持OLED菜单显示、可以预设滑屏场景，已预设刷短视频、刷长视频、看小说、浏览等场景。

## 主要特性

- 📱 蓝牙HID触摸屏模拟
- 🔄 多种预设滑屏场景
- 🎮 物理按钮控制
- 📟 OLED状态显示
- ⚡ MicroPython开发
- 🔧 高度可配置

## 预制应用场景

- 短视频自动滑动，  间隔时间大于10秒随机
- 长视频自动滑动，  间隔时间大于100秒随机
- 电子书自动翻页，  间隔时间（10，20）秒随机

## 包含的文件：
- main.py - 主程序入口
- config.py - 配置文件（预设场景、引脚定义等）
- ble_hid.py - 蓝牙HID服务实现
- touch_controller.py - 触摸控制核心逻辑
- oled_display.py - OLED显示管理
- button_control.py - 物理按钮处理
- ssd1306.py - SSD1306 OLED驱动

## 硬件要求：
- ESP32-C3 Mini
- 0.96 OLED 128*64
- 按钮2个

