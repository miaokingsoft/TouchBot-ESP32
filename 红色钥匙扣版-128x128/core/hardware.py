"""
硬件初始化抽象层
所有功能模块从此模块导入 tft / btn_next / btn_sel
避免 SPI/TFT/Button 在各文件中重复初始化
"""
from machine import SPI, Pin
from drivers.ST7735 import TFT
from drivers.Button import Button
import gc

tft = None
btn_next = None   # GPIO12 - 光标下移 / 翻页
btn_sel = None    # GPIO14 - 确认选择

def init():
    """初始化 SPI TFT 和两个按键，返回 (tft, btn_next, btn_sel)"""
    global tft, btn_next, btn_sel
    spi = SPI(2, baudrate=20000000, polarity=0, phase=0,
              sck=Pin(18), mosi=Pin(23), miso=Pin(19))
    tft = TFT(spi, 25, 26, 27)
    tft.init_7735(tft.GREENTAB128x128)
    tft.rgb(True)
    tft.rotation(1)
    btn_next = Button(12)
    btn_sel = Button(14)
    gc.collect()
    return tft, btn_next, btn_sel
