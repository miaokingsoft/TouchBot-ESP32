import bluetooth
import time
import struct
import random
from machine import Pin
from micropython import const

# 配置参数
DEVICE_NAME = "ESP32 C3 HID Touch"  # 蓝牙设备名称
SCREEN_WIDTH = 1080              # 目标屏幕宽度（可根据需要调整）
SCREEN_HEIGHT = 2168             # 目标屏幕高度（可根据需要调整）
SWIPE_DURATION = 500             # 滑屏持续时间（毫秒）
SWIPE_STEPS = 10                 # 滑屏步骤数（越多越平滑）
RANDOM_INTERVAL_MAX = 5          # 随机间隔时间最大值（秒），全局变量

# HID报告描述符 - 绝对坐标触摸屏
_HID_REPORT_DESCRIPTOR = bytes([
    # 触摸屏集合
    0x05, 0x0D,        # Usage Page (Digitizer)
    0x09, 0x04,        # Usage (Touch Screen)
    0xA1, 0x01,        # Collection (Application)
    
    # 联系人计数
    0x09, 0x54,        # Usage (Contact Count)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x08,        # Report Size (8)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x02,        # Input (Data, Var, Abs)
    
    # 联系人标识符最大值
    0x09, 0x55,        # Usage (Contact Count Maximum)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x08,        # Report Size (8)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x02,        # Input (Data, Var, Abs)
    
    # 联系人1
    0x05, 0x0D,        # Usage Page (Digitizer)
    0x09, 0x22,        # Usage (Finger)
    0xA1, 0x02,        # Collection (Logical)
    
    # 联系人标识符
    0x09, 0x51,        # Usage (Contact Identifier)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x08,        # Report Size (8)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x02,        # Input (Data, Var, Abs)
    
    # 触点状态 (Tip Switch)
    0x09, 0x42,        # Usage (Tip Switch)
    0x15, 0x00,        # Logical Minimum (0)
    0x25, 0x01,        # Logical Maximum (1)
    0x75, 0x01,        # Report Size (1)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x02,        # Input (Data, Var, Abs)
    
    # 填充7位
    0x75, 0x07,        # Report Size (7)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x03,        # Input (Const, Var, Abs)
    
    # X坐标 (绝对位置)
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x30,        # Usage (X)
    0x15, 0x00,        # Logical Minimum (0)
    0x26, 0xFF, 0x7F,  # Logical Maximum (32767)
    0x35, 0x00,        # Physical Minimum (0)
    0x46, 0xFF, 0x7F,  # Physical Maximum (32767)
    0x65, 0x11,        # Unit (SI Lin:Length)
    0x55, 0x00,        # Unit Exponent (0)
    0x75, 0x10,        # Report Size (16)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x02,        # Input (Data, Var, Abs)
    
    # Y坐标 (绝对位置)
    0x09, 0x31,        # Usage (Y)
    0x15, 0x00,        # Logical Minimum (0)
    0x26, 0xFF, 0x7F,  # Logical Maximum (32767)
    0x35, 0x00,        # Physical Minimum (0)
    0x46, 0xFF, 0x7F,  # Physical Maximum (32767)
    0x65, 0x11,        # Unit (SI Lin:Length)
    0x55, 0x00,        # Unit Exponent (0)
    0x75, 0x10,        # Report Size (16)
    0x95, 0x01,        # Report Count (1)
    0x81, 0x02,        # Input (Data, Var, Abs)
    
    # 结束联系人1集合
    0xC0,              # End Collection
    
    # 结束触摸屏集合
    0xC0,              # End Collection
])

class BLEHID:
    def __init__(self, ble, name):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        
        # 添加连接状态和句柄存储
        self._connected = False
        self._conn_handle = None
        
        # 定义HID服务UUID
        self.hid_service_uuid = bluetooth.UUID(0x1812)  # Human Interface Device
        self.hid_uuid = bluetooth.UUID(0x2A4A)  # HID Information
        self.report_map_uuid = bluetooth.UUID(0x2A4B)  # HID Report Map
        self.hid_control_point_uuid = bluetooth.UUID(0x2A4C)  # HID Control Point
        self.input_report_uuid = bluetooth.UUID(0x2A4D)  # Report
        self.protocol_mode_uuid = bluetooth.UUID(0x2A4E)  # Protocol Mode
        
        # 创建HID服务
        services = [
            (
                self.hid_service_uuid,
                [
                    (self.hid_uuid, bluetooth.FLAG_READ),
                    (self.report_map_uuid, bluetooth.FLAG_READ),
                    (self.hid_control_point_uuid, bluetooth.FLAG_WRITE),
                    (self.input_report_uuid, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY),
                    (self.protocol_mode_uuid, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE_NO_RESPONSE),
                ]
            )
        ]
        
        # 注册服务
        self.services = self._ble.gatts_register_services(services)
        self.hid_service = self.services[0]
        
        # 设置报告描述符
        self._ble.gatts_write(self.hid_service[1], _HID_REPORT_DESCRIPTOR)
        
        # 设置HID信息 (版本号: 0x0111, 国家代码: 0x00, 标志: 0x00)
        self._ble.gatts_write(self.hid_service[0], struct.pack('<HBB', 0x0111, 0x00, 0x00))
        
        # 设置协议模式为报告模式 (1)
        self._ble.gatts_write(self.hid_service[4], struct.pack('B', 0x01))
        
        # 设置输入报告 (8字节: contact_count, contact_max, contact_id, tip_switch, x, y)
        self._input_report_value = bytearray(8)
        self._ble.gatts_write(self.hid_service[3], self._input_report_value)
        
        # 构建广告数据
        adv_data = bytearray()
        # 添加标志
        adv_data.append(0x02)  # 长度
        adv_data.append(0x01)  # 类型: 标志
        adv_data.append(0x06)  # 通用可发现模式
        
        # 添加设备名称
        name_bytes = name.encode()
        adv_data.append(len(name_bytes) + 1)  # 长度
        adv_data.append(0x09)  # 类型: 完整设备名称
        adv_data.extend(name_bytes)
        
        # 添加16位UUID
        adv_data.append(0x03)  # 长度
        adv_data.append(0x03)  # 类型: 16位UUID完整列表
        adv_data.append(0x12)  # UUID低位
        adv_data.append(0x18)  # UUID高位
        
        # 添加外观
        adv_data.append(0x03)  # 长度
        adv_data.append(0x19)  # 类型: 外观
        adv_data.append(0xC2)  # 外观低位: 962 (0x03C2)
        adv_data.append(0x03)  # 外观高位
        
        # 设置广告数据
        self._ble.gap_advertise(100, adv_data)
        
        # 连接状态
        self._connected = False
        
    def _irq(self, event, data):
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, addr_type, addr = data
            self._connected = True
            self._conn_handle = conn_handle
            print("Connected to:", bytes(addr).hex())
            print("Connection handle:", conn_handle)
        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            conn_handle, addr_type, addr = data
            self._connected = False
            self._conn_handle = None
            print("Disconnected")
            # 重新开始广告
            self._ble.gap_advertise(100)
        elif event == 3:  # _IRQ_GATTS_WRITE
            conn_handle, attr_handle = data
            print("Data written to handle:", attr_handle)
    
    def is_connected(self):
        return self._connected
    
    def send_touch_report(self, contact_count, contact_max, contact_id, tip_switch, x, y):
        """发送触摸报告（绝对坐标）"""
        if not self._connected or self._conn_handle is None:
            return False
        
        try:
            # 构建报告数据 (8字节)
            report = struct.pack('BBBBHH', contact_count, contact_max, contact_id, tip_switch, x, y)
            self._ble.gatts_write(self.hid_service[3], report)
            
            # 使用正确的连接句柄发送通知
            self._ble.gatts_notify(self._conn_handle, self.hid_service[3])
            return True
        except Exception as e:
            print("Error sending report:", e)
            # 如果发送失败，可能是连接已断开
            self._connected = False
            self._conn_handle = None
            return False

class TouchController:
    def __init__(self, ble_hid, screen_width, screen_height):
        self.ble_hid = ble_hid
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.current_x = screen_width // 2
        self.current_y = screen_height // 2
        self.is_touching = False
        self.stop_requested = False
    
    def request_stop(self):
        """请求停止当前操作"""
        self.stop_requested = True
        print("停止请求已发送...")
    
    def check_stop(self):
        """检查是否请求停止"""
        if self.stop_requested:
            self.stop_requested = False
            self.touch_up()  # 确保触摸被释放
            return True
        return False
    
    def move_to(self, x, y):
        """移动触摸点到指定位置（绝对坐标）"""
        if self.check_stop():
            return False
            
        # 确保坐标在屏幕范围内
        x = max(0, min(self.screen_width, x))
        y = max(0, min(self.screen_height, y))
        
        # 转换坐标为HID报告格式 (0-32767)
        hid_x = int(x * 32767 / self.screen_width)
        hid_y = int(y * 32767 / self.screen_height)
        
        # 发送触摸报告
        if self.is_touching:
            # 如果正在触摸，发送带触摸状态的报告
            success = self.ble_hid.send_touch_report(1, 1, 1, 1, hid_x, hid_y)
        else:
            # 如果未触摸，发送移动但不触摸的报告
            success = self.ble_hid.send_touch_report(1, 1, 1, 0, hid_x, hid_y)
        
        if success:
            self.current_x = x
            self.current_y = y
        
        time.sleep(0.05)
        return success
    
    def touch_down(self, x=None, y=None):
        """按下触摸"""
        if self.check_stop():
            return False
            
        if x is not None and y is not None:
            if not self.move_to(x, y):
                return False
        
        # 发送触摸按下报告
        hid_x = int(self.current_x * 32767 / self.screen_width)
        hid_y = int(self.current_y * 32767 / self.screen_height)
        self.ble_hid.send_touch_report(1, 1, 1, 1, hid_x, hid_y)
        self.is_touching = True
        time.sleep(0.05)
        return True
    
    def touch_up(self):
        """释放触摸"""
        # 发送触摸释放报告
        hid_x = int(self.current_x * 32767 / self.screen_width)
        hid_y = int(self.current_y * 32767 / self.screen_height)
        self.ble_hid.send_touch_report(1, 1, 1, 0, hid_x, hid_y)
        self.is_touching = False
        time.sleep(0.05)
    
    def tap(self, x, y):
        """在指定位置点击"""
        if self.check_stop():
            return
            
        if not self.move_to(x, y):
            return
            
        if not self.touch_down():
            return
            
        time.sleep(0.1)
        self.touch_up()
        time.sleep(0.1)
    
    def swipe(self, start_x, start_y, end_x, end_y, duration=SWIPE_DURATION, steps=SWIPE_STEPS):
        """执行滑屏操作"""
        if self.check_stop():
            return
            
        # 移动到起始位置
        if not self.move_to(start_x, start_y):
            return
            
        time.sleep(0.1)
        
        # 按下触摸
        if not self.touch_down():
            return
            
        time.sleep(0.1)
        
        # 计算每一步的移动量
        step_delay = duration / steps / 1000  # 转换为秒
        dx_step = (end_x - start_x) / steps
        dy_step = (end_y - start_y) / steps
        
        # 执行滑屏
        for i in range(steps):
            if self.check_stop():
                return
                
            target_x = int(start_x + dx_step * (i + 1))
            target_y = int(start_y + dy_step * (i + 1))
            if not self.move_to(target_x, target_y):
                return
            time.sleep(step_delay)
        
        # 释放触摸
        self.touch_up()
        time.sleep(0.1)
    
    def swipe_direction(self, direction, distance=None, duration=SWIPE_DURATION):
        """按指定方向滑动"""
        if self.check_stop():
            return
            
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        if distance is None:
            distance = min(self.screen_width, self.screen_height) // 3
        
        if direction == "up":
            start_y = self.screen_height - 100
            end_y = max(0, start_y - distance)
            self.swipe(center_x, start_y, center_x, end_y, duration)
        elif direction == "down":
            start_y = 100
            end_y = min(self.screen_height, start_y + distance)
            self.swipe(center_x, start_y, center_x, end_y, duration)
        elif direction == "left":
            start_x = self.screen_width - 100
            end_x = max(0, start_x - distance)
            self.swipe(start_x, center_y, end_x, center_y, duration)
        elif direction == "right":
            start_x = 100
            end_x = min(self.screen_width, start_x + distance)
            self.swipe(start_x, center_y, end_x, center_y, duration)
    
    def continuous_swipe(self, direction, count=5, interval=1.0, distance=None, duration=SWIPE_DURATION):
        """连续滑动指定次数"""
        print(f"开始连续{direction}滑动 {count} 次")
        
        for i in range(count):
            if self.check_stop():
                print("连续滑动已停止")
                return
                
            print(f"第 {i+1}/{count} 次滑动...")
            self.swipe_direction(direction, distance, duration)
            
            # 如果不是最后一次，等待间隔时间
            if i < count - 1:
                # 如果interval为0，使用随机间隔时间
                if interval == 0:
                    random_interval = random.uniform(1, RANDOM_INTERVAL_MAX)
                    print(f"随机间隔: {random_interval:.1f}秒")
                    wait_time = random_interval
                else:
                    wait_time = interval
                
                # 分段等待，以便可以随时停止
                for j in range(int(wait_time * 10)):
                    if self.check_stop():
                        print("连续滑动已停止")
                        return
                    time.sleep(0.1)
        
        print("连续滑动完成")
    
    def move_to_custom(self):
        """移动到自定义位置"""
        print("\n=== 移动到指定位置 ===")
        try:
            x = int(input(f"X坐标 (0-{self.screen_width}): ") or self.current_x)
            y = int(input(f"Y坐标 (0-{self.screen_height}): ") or self.current_y)
            self.move_to(x, y)
        except:
            print("输入无效，使用当前位置")
    
    def tap_custom(self):
        """在自定义位置点击"""
        print("\n=== 在指定位置点击 ===")
        try:
            x = int(input(f"X坐标 (0-{self.screen_width}): ") or self.current_x)
            y = int(input(f"Y坐标 (0-{self.screen_height}): ") or self.current_y)
            self.tap(x, y)
        except:
            print("输入无效，在当前位置点击")
            self.tap(self.current_x, self.current_y)
    
    def swipe_custom(self):
        """自定义滑动"""
        print("\n=== 自定义滑动 ===")
        try:
            start_x = int(input("起始X坐标: ") or self.screen_width // 2)
            start_y = int(input("起始Y坐标: ") or self.screen_height // 2)
            end_x = int(input("结束X坐标: ") or self.screen_width // 2)
            end_y = int(input("结束Y坐标: ") or self.screen_height // 2)
            duration = int(input("持续时间(ms): ") or SWIPE_DURATION)
            steps = int(input("步骤数: ") or SWIPE_STEPS)
            
            self.swipe(start_x, start_y, end_x, end_y, duration, steps)
        except:
            print("输入无效，使用默认值")
            self.swipe(self.screen_width // 2, self.screen_height - 100, 
                      self.screen_width // 2, 100)
    
    def continuous_swipe_custom(self):
        """自定义连续滑动"""
        print("\n=== 自定义连续滑动 ===")
        try:
            print("选择滑动方向:")
            print("1. 向上")
            print("2. 向下")
            print("3. 向左")
            print("4. 向右")
            dir_choice = int(input("方向选择 (1-4): ") or 1)
            
            directions = ["up", "down", "left", "right"]
            direction = directions[dir_choice - 1] if 1 <= dir_choice <= 4 else "up"
            
            count = int(input("滑动次数: ") or 5)
            
            # 询问间隔时间，说明0表示随机
            interval_input = input("间隔时间(秒, 0=随机): ") or "1.0"
            interval = 0 if interval_input == "0" else float(interval_input)
            
            distance = int(input("滑动距离(像素, 回车默认): ") or None)
            duration = int(input("单次滑动时间(ms): ") or SWIPE_DURATION)
            
            self.continuous_swipe(direction, count, interval, distance, duration)
            
        except:
            print("输入无效，使用默认值")
            self.continuous_swipe("up", 5, 1.0)

def show_menu():
    """显示调试菜单"""
    print("\n" + "="*50)
    print("           ESP32 蓝牙触摸控制菜单")
    print("="*50)
    print("1. 移动到指定位置")
    print("2. 在指定位置点击")
    print("3. 向上滑动")
    print("4. 向下滑动")
    print("5. 向左滑动")
    print("6. 向右滑动")
    print("7. 自定义单次滑动")
    print("8. 自定义连续滑动")
    print("9. 测试所有方向")
    print("10. 显示当前位置")
    print("11. 停止当前操作")
    print("12. 重新连接")
    print("13. 退出")
    print("="*50)
    print(f"随机间隔最大值: {RANDOM_INTERVAL_MAX}秒")
    
    try:
        choice = input("请选择操作 (1-13): ")
        return int(choice) if choice.isdigit() else 0
    except:
        return 0

def test_all_swipes(touch_controller):
    """测试所有滑屏方向"""
    print("\n=== 测试所有滑屏方向 ===")
    
    actions = [
        ("向上滑动", lambda: touch_controller.swipe_direction("up")),
        ("向下滑动", lambda: touch_controller.swipe_direction("down")),
        ("向左滑动", lambda: touch_controller.swipe_direction("left")),
        ("向右滑动", lambda: touch_controller.swipe_direction("right")),
    ]
    
    for name, action in actions:
        if touch_controller.check_stop():
            print("测试已停止")
            return
        print(f"{name}...")
        action()
        time.sleep(1)
    
    print("所有测试完成!")

def main():
    # 初始化BLE
    ble = bluetooth.BLE()
    hid = BLEHID(ble, DEVICE_NAME)
    touch_controller = TouchController(hid, SCREEN_WIDTH, SCREEN_HEIGHT)
    
    print("等待蓝牙连接...")
    print("请在安卓设备上搜索并连接: {}".format(DEVICE_NAME))
    
    while not hid.is_connected():
        time.sleep(0.5)
        print(".", end="")
    
    print("\n已连接! 进入调试模式...")
    print(f"屏幕分辨率: {SCREEN_WIDTH}×{SCREEN_HEIGHT}")
    print(f"当前位置: ({touch_controller.current_x}, {touch_controller.current_y})")
    print(f"随机间隔时间范围: 1.0 ~ {RANDOM_INTERVAL_MAX}秒")
    print("提示: 在任何时候可以按 11 来停止当前操作")
    print("提示: 连续滑动时设置间隔时间为0使用随机间隔")
    
    # 主循环
    while True:
        if not hid.is_connected():
            print("连接已断开，等待重新连接...")
            while not hid.is_connected():
                time.sleep(1)
                print(".", end="")
            print("\n重新连接成功!")
        
        choice = show_menu()
        
        if choice == 1:
            touch_controller.move_to_custom()
        elif choice == 2:
            touch_controller.tap_custom()
        elif choice == 3:
            print("执行向上滑动...")
            touch_controller.swipe_direction("up")
        elif choice == 4:
            print("执行向下滑动...")
            touch_controller.swipe_direction("down")
        elif choice == 5:
            print("执行向左滑动...")
            touch_controller.swipe_direction("left")
        elif choice == 6:
            print("执行向右滑动...")
            touch_controller.swipe_direction("right")
        elif choice == 7:
            touch_controller.swipe_custom()
        elif choice == 8:
            touch_controller.continuous_swipe_custom()
        elif choice == 9:
            test_all_swipes(touch_controller)
        elif choice == 10:
            print(f"当前位置: ({touch_controller.current_x}, {touch_controller.current_y})")
        elif choice == 11:
            touch_controller.request_stop()
        elif choice == 12:
            print("重新启动广告...")
            hid._ble.gap_advertise(100)
            print("等待重新连接...")
        elif choice == 13:
            print("退出程序...")
            break
        else:
            print("无效选择，请重新输入")
        
        time.sleep(0.5)  # 短暂延迟

if __name__ == "__main__":
    main()