import time
from machine import Pin, I2C, SoftI2C
import framebuf
from config import OLED_WIDTH, OLED_HEIGHT, OLED_I2C_SCL, OLED_I2C_SDA, NAME_ABBREVIATIONS, PRESET_PROFILES

# SSD1306驱动类（保持不变）
class SSD1306:
    def __init__(self, width, height, i2c, addr=0x3c):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
        self.buffer = bytearray(self.height * self.width // 8)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MVLSB)
        self.init_display()
    
    def init_display(self):
        commands = [
            0xAE, 0xD5, 0x80, 0xA8, self.height - 1, 0xD3, 0x00,
            0x40, 0x8D, 0x14, 0x20, 0x00, 0xA1, 0xC8,
            0xDA, 0x12 if self.height == 64 else 0x02, 0x81, 0xCF,
            0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF
        ]
        for cmd in commands:
            self.write_cmd(cmd)
        self.fill(0)
        self.show()
    
    def write_cmd(self, cmd):
        self.i2c.writeto(self.addr, b'\x00' + bytearray([cmd]))
    
    def write_data(self, data):
        self.i2c.writeto(self.addr, b'\x40' + data)
    
    def fill(self, color):
        self.framebuf.fill(color)
    
    def text(self, text, x, y, color=1):
        self.framebuf.text(text, x, y, color)
    
    def fill_rect(self, x, y, w, h, color):
        self.framebuf.fill_rect(x, y, w, h, color)
    
    def show(self):
        for page in range(0, self.height // 8):
            self.write_cmd(0xB0 + page)
            self.write_cmd(0x00)
            self.write_cmd(0x10)
            start = page * self.width
            end = start + self.width
            self.write_data(self.buffer[start:end])


class OLEDDisplay:
    def __init__(self):
        try:
            self.i2c = I2C(0, scl=Pin(OLED_I2C_SCL), sda=Pin(OLED_I2C_SDA), freq=400000)
        except:
            self.i2c = SoftI2C(scl=Pin(OLED_I2C_SCL), sda=Pin(OLED_I2C_SDA), freq=400000)
        
        self.oled = SSD1306(OLED_WIDTH, OLED_HEIGHT, self.i2c)
        
        # 显示状态变量
        self.current_profile = None  # 当前运行的 profile 名称
        self.bt_connected = False
        self.running = False
        self.countdown = 0
        self.swipe_count = 0
        
        # ✅ 场景列表和索引：从 PRESET_PROFILES 获取全称
        self.profiles = list(PRESET_PROFILES.keys())
        self.current_index = 0  # 当前选中的场景索引
        
        self.set_profile(None)
        self.update_display()
    
    def clear(self):
        self.oled.fill(0)
    
    def show_text(self, text, x, y):
        self.oled.text(text, x, y, 1)
    
    def show_large_text(self, text, x, y):
        """模拟大号字体：显示两次略微偏移"""
        self.oled.text(text, x, y, 1)
        self.oled.text(text, x, y+1, 1)

    def update_status_bar(self):
        """更新顶部状态栏"""
        self.oled.fill_rect(0, 0, OLED_WIDTH, 12, 0)
        
        bt_status = "BT:OK" if self.bt_connected else "BT:OFF"
        self.show_text(bt_status, 0, 2)
        
        run_status = "RUN:ON" if self.running else "RUN:OFF"
        self.show_text(run_status, OLED_WIDTH - len(run_status)*8 - 2, 2)

    def update_main_display(self):
        """更新主显示区域 - 修复版本"""
        self.oled.fill_rect(0, 12, OLED_WIDTH, OLED_HEIGHT - 12, 0)
        
        # ✅ 修复：简化显示逻辑
        if self.running and self.current_profile is not None:
            # 运行中界面：显示场景名称、倒计时、滑动次数
            abbreviated_name = NAME_ABBREVIATIONS.get(self.current_profile, self.current_profile)
            
            # 场景名称（大字体）
            text_width = len(abbreviated_name) * 6
            x_pos = max(0, (OLED_WIDTH - text_width) // 2)
            self.show_large_text(abbreviated_name, x_pos, 16)
            
            # 状态信息
            countdown_text = f"Next:{self.countdown}s"
            self.show_text(countdown_text, 2, 40)
            count_text = f"Count:{self.swipe_count}"
            self.show_text(count_text, 2, 50)
            
            # 运行指示器
            self.show_text(">>> RUNNING <<<", 20, 30)
            
        else:
            # 主菜单界面：显示当前选中的场景
            try:
                current_full_name = self.profiles[self.current_index]
            except (IndexError, TypeError):
                current_full_name = "SELECT PROFILE"
            
            # 分两行显示场景名称
            words = current_full_name.split()
            if len(words) == 0:
                line1, line2 = "NO", "PROFILE"
            elif len(words) == 1:
                w = words[0]
                mid = len(w) // 2
                line1, line2 = w[:mid], w[mid:]
            else:
                split_idx = (len(words) + 1) // 2
                line1 = " ".join(words[:split_idx])
                line2 = " ".join(words[split_idx:])
            
            # 计算居中位置
            width1 = len(line1) * 6
            width2 = len(line2) * 6
            x1 = (OLED_WIDTH - width1) // 2
            x2 = (OLED_WIDTH - width2) // 2
            
            # 垂直居中
            char_h = 16
            total_h = char_h * 2
            start_y = 12 + (OLED_HEIGHT - 12 - total_h) // 2
            y1 = start_y
            y2 = start_y + char_h
            
            self.show_large_text(line1, x1, y1)
            self.show_large_text(line2, x2, y2)
            
            # 添加选择指示器
            self.show_text("^", OLED_WIDTH // 2 - 3, y2 + 5)

    def update_display(self):
        """刷新整个屏幕"""
        #print(self.current_profile)
        self.update_status_bar()
        self.update_main_display()
        self.oled.show()

    # -------------------------------
    # ✅ 新增：外部控制接口
    # -------------------------------

    def set_profile(self, profile_name):
        """
        设置当前运行的 profile。
        如果为 None，表示返回主菜单。
        """
        if profile_name is not None and profile_name not in PRESET_PROFILES:
            print(f"[OLED] Invalid profile: {profile_name}, fallback to main menu")
            profile_name = None

        self.current_profile = profile_name
        # ✅ 修复：只有在主菜单时才更新索引显示
        if profile_name is None:
            self.update_display()

    def set_bt_status(self, connected):
        """设置蓝牙连接状态并刷新显示"""
        self.bt_connected = connected
        self.update_display()

    def set_running_status(self, running, countdown=0, swipe_count=0):
        """设置运行状态、倒计时、滑动次数"""
        self.running = running
        self.countdown = countdown
        self.swipe_count = swipe_count
        # ✅ 修复：运行状态变化时立即更新显示
        self.update_display()

    def next_profile(self):
        """切换到下一个场景（用于按钮1）"""
        self.current_index = (self.current_index + 1) % len(self.profiles)
        if self.current_profile is None:  # 只有在主菜单才立即刷新
            self.update_display()

    def previous_profile(self):
        """切换到上一个场景"""
        self.current_index = (self.current_index - 1) % len(self.profiles)
        if self.current_profile is None:
            self.update_display()

    def get_current_profile_name(self):
        """获取当前选中的场景名称（全称）"""
        return self.profiles[self.current_index]