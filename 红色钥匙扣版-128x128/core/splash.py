"""
启动动画 — v1.2 (防 OOM 版)
渐变矩形 + Miao 文字
"""
from drivers.ST7735 import TFT
from drivers.sysfont import sysfont
import gc

BLACK = TFT.BLACK
RED   = TFT.RED


def run(tft):
    """启动动画：渐变矩形 + WWZU 文字"""
    tft.fill(BLACK)
    tft.text((40, 56), "WWZU", RED, sysfont, 2, nowrap=True)
    color = 100
    for t in range(10):
        x = 0
        y = 0
        w = tft.size()[0] - 2
        h = tft.size()[1] - 2
        for i in range(17):
            tft.rect((x, y), (w, h), color)
            x += 2
            y += 3
            w -= 4
            h -= 6
            color += 1100
        color += 100
    gc.collect()  # 动画产生大量临时变量，画完立刻清理
