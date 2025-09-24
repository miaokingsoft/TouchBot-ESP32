'''
# 自动滑屏助手 v1.0
'''
import time
import random
import gc
from machine import Pin
from config import PRESET_PROFILES, SCREEN_WIDTH, SCREEN_HEIGHT, SWIPE_DURATION, SWIPE_STEPS
from oled_display import OLEDDisplay
from button_control import ButtonControl
from ble_hid import BLEHID

class TouchController:
    def __init__(self, ble_hid, screen_width, screen_height):
        self.ble_hid = ble_hid
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.current_x = screen_width // 2
        self.current_y = screen_height // 2
        self.is_touching = False
        self.stop_requested = False
        self.running = False
        self.profiles = PRESET_PROFILES
    
    def is_running(self):
        return self.running
    
    def request_stop(self):
        """请求停止当前操作"""
        self.stop_requested = True
    
    def stop_immediately(self):
        """立即停止并返回主菜单 - 修复版本"""
        print("立即停止并返回主菜单")
        self.stop_requested = True
        self.running = False
        
        # 确保触摸被释放
        try:
            self.touch_up()
        except Exception as e:
            print(f"触摸释放错误: {e}")
        
        # 立即返回主菜单
        if hasattr(self, 'display'):
            self.display.set_profile(None)
        
        # 重置状态
        self.stop_requested = False
    
    def check_stop(self):
        """检查是否请求停止"""
        if self.stop_requested:
            self.stop_requested = False
            self.running = False
            self.touch_up()  # 确保触摸被释放
            if hasattr(self, 'display'):
                self.display.set_profile(None)  # 返回主菜单
            return True
        return False
    
    def move_to(self, x, y):
        """移动触摸点 - 参考C3_tools.py的实现"""
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
            success = self.ble_hid.send_touch_report(1, 1, 1, 1, hid_x, hid_y)
        else:
            success = self.ble_hid.send_touch_report(1, 1, 1, 0, hid_x, hid_y)
        
        if success:
            self.current_x = x
            self.current_y = y
        
        time.sleep(0.05)
        return success
    
    def touch_down(self, x=None, y=None):
        if self.check_stop():
            return False
            
        if x is not None and y is not None:
            if not self.move_to(x, y):
                return False
        
        hid_x = int(self.current_x * 32767 / self.screen_width)
        hid_y = int(self.current_y * 32767 / self.screen_height)
        self.ble_hid.send_touch_report(1, 1, 1, 1, hid_x, hid_y)
        self.is_touching = True
        time.sleep(0.05)
        return True

    def touch_up(self):
        """释放触摸 - 参考C3_tools.py的实现"""
        try:
            hid_x = int(self.current_x * 32767 / self.screen_width)
            hid_y = int(self.current_y * 32767 / self.screen_height)
            success = self.ble_hid.send_touch_report(1, 1, 1, 0, hid_x, hid_y)
            if not success:
                print("触摸释放失败（蓝牙可能已断开）")
        except Exception as e:
            print(f"触摸释放出错: {e}")
        
        self.is_touching = False
        time.sleep(0.05)
    
    def swipe(self, start_x, start_y, end_x, end_y, duration=SWIPE_DURATION, steps=SWIPE_STEPS):
        if self.check_stop():
            return False
            
        if not self.move_to(start_x, start_y):
            return False
            
        time.sleep(0.1)
        
        if not self.touch_down():
            return False
            
        time.sleep(0.1)
        
        step_delay = duration / steps / 1000
        dx_step = (end_x - start_x) / steps
        dy_step = (end_y - start_y) / steps
        
        for i in range(steps):
            if self.check_stop():
                return False
                
            target_x = int(start_x + dx_step * (i + 1))
            target_y = int(start_y + dy_step * (i + 1))
            if not self.move_to(target_x, target_y):
                return False
            time.sleep(step_delay)
        
        self.touch_up()
        time.sleep(0.1)
        return True
    
    def swipe_direction(self, direction, edge_margin=100, duration=SWIPE_DURATION):
        if self.check_stop():
            return False
            
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        
        # 修复方向判断逻辑
        if direction == "up":
            start_x, start_y = center_x, self.screen_height - edge_margin
            end_x, end_y = center_x, edge_margin
        elif direction == "down":
            start_x, start_y = center_x, edge_margin
            end_x, end_y = center_x, self.screen_height - edge_margin
        elif direction == "left":
            start_x, start_y = self.screen_width - edge_margin, center_y
            end_x, end_y = edge_margin, center_y
        elif direction == "right":
            start_x, start_y = edge_margin, center_y
            end_x, end_y = self.screen_width - edge_margin, center_y
        else:
            print(f"错误的方向: {direction}")
            return False
            
        return self.swipe(start_x, start_y, end_x, end_y, duration)
    
    def wait_with_stop_check(self, wait_time):
        """等待指定时间，但可以随时被停止"""
        wait_steps = int(wait_time * 10)  # 每0.1秒检查一次
        for i in range(wait_steps):
            if self.check_stop():
                return True  # 被停止
            
            # 更新倒计时显示
            if hasattr(self, 'display'):
                remaining = wait_time - (i * 0.1)
                self.display.set_running_status(True, round(remaining, 1), getattr(self, 'swipe_count', 0))
            
            time.sleep(0.1)
        
        return False  # 正常完成等待
    
    def start_profile(self, profile_name, direction, duration, interval, random_interval, infinite, edge_margin):
        # ✅ 修复：启动时确保显示状态正确
        if hasattr(self, 'display'):
            self.display.set_profile(profile_name)
            self.display.set_running_status(True, 0, 0)
        
        self.running = True
        self.stop_requested = False
        
        swipe_count = 0
        print(f"开始执行场景: {profile_name}")
        
        while self.running:
            if self.check_stop():
                break
                
            # 执行滑屏操作
            success = self.swipe_direction(direction, edge_margin, duration)
            
            if not success:
                break
                
            swipe_count += 1
            self.swipe_count = swipe_count
            
            # 更新显示信息
            if hasattr(self, 'display'):
                countdown = 0
                if interval > 0:
                    countdown = interval / 1000
                elif random_interval:
                    min_val, max_val = random_interval
                    next_interval = random.randint(min_val, max_val)
                    countdown = next_interval / 1000
                
                self.display.set_running_status(True, round(countdown, 1), swipe_count)
            
            # 检查是否达到非无限模式的次数限制
            if not infinite and interval > 0 and swipe_count >= (interval // 1000):
                break
                
            # 计算等待时间
            if interval > 0:
                wait_time = interval / 1000
            elif random_interval:
                min_val, max_val = random_interval
                wait_time = random.randint(min_val, max_val) / 1000
            else:
                wait_time = 1.0
            
            # 等待，但可以随时被停止
            stopped = self.wait_with_stop_check(wait_time)
            if stopped:
                break
        
        # 清理状态
        self.running = False
        self.stop_requested = False
        
        # ✅ 修复：场景结束时正确返回主菜单
        if hasattr(self, 'display'):
            self.display.set_running_status(False)
            self.display.set_profile(None)  # 返回主菜单
        
        print("场景执行结束")

def main():
    gc.enable()
    
    ble_hid = BLEHID()
    touch_controller = TouchController(ble_hid, SCREEN_WIDTH, SCREEN_HEIGHT)
    display = OLEDDisplay()
    display.set_bt_status(ble_hid.is_connected())
    touch_controller.display = display
    
    button_control = ButtonControl(display, touch_controller)
    
    print("系统初始化完成")
    print("等待蓝牙连接...")
    print("按钮2单击: 启动/停止场景")
    print("按钮2双击: 立即停止并返回主菜单") 
    print("按钮1: 切换场景")
    
    while True:
        display.set_bt_status(ble_hid.is_connected())
        
        # 处理待定的单击 - 使用正确的变量名
        if button_control.pending_single_click:
            current_time = time.ticks_ms()
            elapsed = time.ticks_diff(current_time, button_control.last_btn2_click_time)
            
            # 等待双击超时后再执行单击
            if elapsed >= button_control.double_click_threshold:
                button_control.btn2_short_press()
                button_control.pending_single_click = False
                button_control.btn2_click_count = 0  # 重置计数
        
        time.sleep(0.05)  # 缩短等待时间，提高响应性
        gc.collect()
if __name__ == "__main__":
    main()