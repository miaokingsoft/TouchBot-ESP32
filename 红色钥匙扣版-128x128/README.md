# 创意钥匙扣 v2.1（红色钥匙扣版 128x128）

ESP32 + ST7735 128x128 TFT 创意钥匙扣项目。
核心功能：BLE HID 触摸设备模拟手机上滑手势，自动刷短视频。

## v2.1 主要变更

- **开机直进 Swipe**：上电后跳过菜单直接进入刷视频模式，BLE 广播等待手机连接
- **WiFi 按需连接**：开机不再连 WiFi；进入 Web 菜单时才扫描连接（先 `scan()` 再连，只连环境中存在的已知 SSID）
- **滑动手势修复**：行程从 1/6 屏高提升到 40% 屏高，采样点 5→10 个、间隔放慢到 30ms（匹配 BLE 连接间隔，避免 notify 报文被覆盖），显著提升翻页成功率
- **min/max 钳制**：设置界面与 HTTP 接口均保证 `interval_min <= interval_max`，修复自动滑动随机崩溃
- **HTTP body 完整接收**：按 `Content-Length` 收满请求体，修复 POST 保存偶发失败

## 目录结构

```
├── boot.py              # 启动入口：硬件初始化 → splash（不连 WiFi）
├── main.py              # 开机直进 Swipe，退出后主菜单调度（分发表）
├── config.py            # 菜单/WiFi/滑动参数配置
├── README.md
│
├── app/                 # 应用层（与 MENU_ITEMS 一一对应）
│   ├── swipe.py         # id=swipe    BLE 触控刷视频
│   ├── setting.py       # id=setting  滑动间隔/分辨率设置（持久化 settings.json）
│   ├── web.py           # id=web      按需连 WiFi + 启动 HTTP 配置服务
│   └── http_server.py   # 轻量 HTTP 服务（被 web.py 按需加载）
│
├── core/                # 核心抽象层
│   ├── hardware.py      # SPI/TFT/Button 初始化
│   ├── wifi.py          # WiFi 按需连接（扫描优先）/ 断开
│   └── splash.py        # 启动动画
│
└── drivers/             # 第三方驱动（不修改）
    ├── ST7735.py
    ├── Button.py
    └── sysfont.py
```

## 启动流程

1. ESP32 上电 → `boot.py` 自动执行
2. `boot.py`：灭 mDNS → 初始化硬件 → splash 动画（**不连接 WiFi**）
3. MicroPython 隐式执行 `main.py`
4. `main.py`：加载 settings.json → **直接进入 Swipe 模式**（BLE 广播）
5. 手机蓝牙连接 `esp32-xm` → 按 SEL 开始/停止自动滑动
6. NXT / 长按 SEL 退出 → 主菜单（Swipe / Setting / Web）

## 菜单与按键

| 菜单 | 功能 | 按键 |
| --- | --- | --- |
| Swipe | BLE 刷视频 | NXT：退出；SEL：开始/停止自动滑；长按 SEL：退出 |
| Setting | 间隔/分辨率设置 | NXT：移动/+1（长按 -1）；SEL：进入/退出编辑；长按 SEL：保存退出 |
| Web | WiFi + HTTP 配置 | NXT：退出（断开 WiFi） |

## 滑动手势参数（config.py，真机调优）

| 常量 | 默认 | 说明 |
| --- | --- | --- |
| `SWIPE_TRAVEL_PCT` | 40 | 行程占屏高百分比；<25 时多数短视频 App 不翻页 |
| `SWIPE_START_PCT` | 70 | 起点占屏高百分比（终点 = 起点 - 行程） |
| `SWIPE_STEPS` | 10 | 移动采样点数 |
| `SWIPE_STEP_MS` | 30 | 采样间隔；应 ≥ BLE 连接间隔（30~50ms），过快报文会被覆盖 |
| `SWIPE_PRESS_MS` | 80 | 按下保持时长；部分机型需 ≥80ms 才承认拖拽 |
| `SWIPE_RELEASE_MS` | 40 | tip-off 到 release 的间隔 |

**若仍偶发滑动失败**：依次尝试增大 `SWIPE_TRAVEL_PCT`（40→50）、`SWIPE_STEP_MS`（30→40）、`SWIPE_PRESS_MS`（80→100）。

## HTTP 远程配置

进入 Web 菜单 → 自动连接已知 WiFi → 屏幕显示 IP，浏览器访问
`http://<IP>:8080` 即可修改滑动间隔与手机分辨率（保存到 settings.json）。
按 NXT 退出 Web 菜单会停止服务并断开 WiFi（省电）。

> 注意：BLE 与 WiFi 在 ESP32 上不能同时使用，进入 Swipe 会关闭 WiFi；
> 退出后需要远程配置时重新进入 Web 菜单即可。

## 新增菜单项

1. 在 `app/` 下新建 `xxx.py`，暴露 `def run():`
2. `config.py` 的 `MENU_ITEMS` 追加 `{"name": "...", "id": "xxx"}`
3. `main.py` 的 `DISPATCH` 字典加 `"xxx": xxx.run`

## 部署

```bash
# mpremote（示例）
mpremote cp boot.py main.py config.py :/
mpremote cp -r app core drivers :/

# 或用 Thonny 上传整个目录到 ESP32 根路径
```

## 真机验证清单

- [ ] 开机：splash 后直接进入 Swipe 界面，BLE 等待连接
- [ ] 手机连接 `esp32-xm` 后显示 Connected
- [ ] 按 SEL 开始自动滑动，**连续观察 20 次以上翻页成功率**（重点）
- [ ] SEL 停止 / NXT 退出回主菜单，可再次进入 Swipe
- [ ] Setting：Min 调到 Max 后不再继续增大（钳制生效）；长按 SEL 保存退出
- [ ] Web：连接 WiFi 后浏览器打开 `IP:8080`，修改配置提示 Saved
- [ ] Web 退出后再进 Swipe → 退出 → 再进 Web，WiFi 可重新连接
