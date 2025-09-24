from machine import Pin
import time
from config import BUTTON1_PIN, BUTTON2_PIN

class ButtonControl:
    def __init__(self, display, touch_controller):
        self.display = display
        self.touch_controller = touch_controller
        
        # 初始化按钮
        self.btn1 = Pin(BUTTON1_PIN, Pin.IN, Pin.PULL_UP)
        self.btn2 = Pin(BUTTON2_PIN, Pin.IN, Pin.PULL_UP)
        
        # 设置中断 - 只使用下降沿触发
        self.btn1.irq(trigger=Pin.IRQ_FALLING, handler=self.btn1_handler)
        self.btn2.irq(trigger=Pin.IRQ_FALLING, handler=self.btn2_handler)
        
        # 防抖相关变量
        self.last_btn1_time = 0
        self.last_btn2_time = 0
        self.debounce_delay = 200
        
        # 双击检测变量
        self.last_btn2_click_time = 0
        self.double_click_threshold = 400
        self.pending_single_click = False
        self.btn2_click_count = 0
        
        # ✅ 修复：不再单独维护 profiles 和 current_index，使用 display 的索引
        # 菜单相关数据统一从 display 获取
    
    def debounce(self, last_time):
        current_time = time.ticks_ms()
        return time.ticks_diff(current_time, last_time) > self.debounce_delay
    
    def btn1_handler(self, pin):
        if self.debounce(self.last_btn1_time):
            self.last_btn1_time = time.ticks_ms()
            
            self.touch_controller.request_stop()
            
            # ✅ 修复：直接调用 display 的方法，保持索引同步
            self.display.next_profile()
            
            # 更新当前 profile 显示（如果未运行）
            if not self.touch_controller.is_running():
                profile_name = self.display.get_current_profile_name()
                self.display.set_profile(profile_name)
    
    def btn2_handler(self, pin):
        """按钮2处理：简化逻辑，提高可靠性"""
        if not self.debounce(self.last_btn2_time):
            return
            
        self.last_btn2_time = time.ticks_ms()
        current_time = time.ticks_ms()
        
        # 双击检测逻辑
        if time.ticks_diff(current_time, self.last_btn2_click_time) < self.double_click_threshold:
            self.btn2_click_count += 1
        else:
            self.btn2_click_count = 1
            
        self.last_btn2_click_time = current_time
        
        # 处理点击
        if self.btn2_click_count == 2:
            # 双击：立即停止并返回主菜单
            print("双击按钮2：立即停止")
            self.touch_controller.stop_immediately()
            self.btn2_click_count = 0
            self.pending_single_click = False
        else:
            # 单击：启动/停止场景（在主循环中处理）
            self.pending_single_click = True
    
    def btn2_short_press(self):
        """按钮2短按功能：启动/停止场景"""
        # 重置双击计数
        self.btn2_click_count = 0
        
        # ✅ 修复：统一从 display 获取当前场景信息
        current_profile = self.display.get_current_profile_name()
        profiles = self.touch_controller.profiles
        
        if current_profile not in profiles:
            print(f"错误：场景 '{current_profile}' 不存在")
            return
            
        try:
            profile_config = profiles[current_profile]
            
            # 调试信息
            print(f"当前场景: {current_profile}, 方向: {profile_config['direction']}")
            
            if self.touch_controller.is_running():
                # 请求停止（非立即停止）
                print("请求停止操作")
                self.touch_controller.request_stop()
            else:
                # ✅ 修复：启动场景时更新显示状态
                self.display.set_profile(current_profile)  # 设置为运行状态
                self.display.set_running_status(True, 0, 0)  # 初始化运行状态
                
                # 启动场景
                print(f"启动场景: {current_profile}, 方向: {profile_config['direction']}")
                self.touch_controller.start_profile(
                    current_profile, 
                    profile_config["direction"],
                    profile_config["duration"],
                    profile_config["interval"],
                    profile_config["random_interval"],
                    profile_config["infinite"],
                    profile_config["edge_margin"]
                )
        except Exception as e:
            print(f"按钮操作错误: {e}")