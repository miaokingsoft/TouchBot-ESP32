import bluetooth
import struct
import time
from machine import Pin
from config import DEVICE_NAME, LED_PIN

class BLEHID:
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        
        # LED指示灯
        self.led = Pin(LED_PIN, Pin.OUT)
        self.led.off()  # 初始状态关闭
        
        # 连接状态和句柄
        self._connected = False
        self._conn_handle = None
        
        # HID报告描述符 - 绝对坐标触摸屏
        self._HID_REPORT_DESCRIPTOR = bytes([
            0x05, 0x0D, 0x09, 0x04, 0xA1, 0x01, 0x09, 0x54, 0x15, 0x00, 0x25, 0x01,
            0x75, 0x08, 0x95, 0x01, 0x81, 0x02, 0x09, 0x55, 0x15, 0x00, 0x25, 0x01,
            0x75, 0x08, 0x95, 0x01, 0x81, 0x02, 0x05, 0x0D, 0x09, 0x22, 0xA1, 0x02,
            0x09, 0x51, 0x15, 0x00, 0x25, 0x01, 0x75, 0x08, 0x95, 0x01, 0x81, 0x02,
            0x09, 0x42, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x01, 0x81, 0x02,
            0x75, 0x07, 0x95, 0x01, 0x81, 0x03, 0x05, 0x01, 0x09, 0x30, 0x15, 0x00,
            0x26, 0xFF, 0x7F, 0x35, 0x00, 0x46, 0xFF, 0x7F, 0x65, 0x11, 0x55, 0x00,
            0x75, 0x10, 0x95, 0x01, 0x81, 0x02, 0x09, 0x31, 0x15, 0x00, 0x26, 0xFF,
            0x7F, 0x35, 0x00, 0x46, 0xFF, 0x7F, 0x65, 0x11, 0x55, 0x00, 0x75, 0x10,
            0x95, 0x01, 0x81, 0x02, 0xC0, 0xC0
        ])
        
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
        self._ble.gatts_write(self.hid_service[1], self._HID_REPORT_DESCRIPTOR)
        
        # 设置HID信息
        self._ble.gatts_write(self.hid_service[0], struct.pack('<HBB', 0x0111, 0x00, 0x00))
        
        # 设置协议模式为报告模式
        self._ble.gatts_write(self.hid_service[4], struct.pack('B', 0x01))
        
        # 设置输入报告
        self._input_report_value = bytearray(8)
        self._ble.gatts_write(self.hid_service[3], self._input_report_value)
        
        # 构建广告数据
        adv_data = bytearray()
        adv_data.append(0x02)  # 长度
        adv_data.append(0x01)  # 类型: 标志
        adv_data.append(0x06)  # 通用可发现模式
        
        name_bytes = DEVICE_NAME.encode()
        adv_data.append(len(name_bytes) + 1)
        adv_data.append(0x09)  # 类型: 完整设备名称
        adv_data.extend(name_bytes)
        
        adv_data.append(0x03)
        adv_data.append(0x03)  # 类型: 16位UUID完整列表
        adv_data.append(0x12)  # UUID低位
        adv_data.append(0x18)  # UUID高位
        
        adv_data.append(0x03)
        adv_data.append(0x19)  # 类型: 外观
        adv_data.append(0xC2)  # 外观低位: 962 (0x03C2)
        adv_data.append(0x03)  # 外观高位
        
        # 设置广告数据
        self._ble.gap_advertise(100, adv_data)
        
    def _irq(self, event, data):
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, addr_type, addr = data
            self._connected = True
            self._conn_handle = conn_handle
            self.led.on()  # 连接时点亮LED
            print("Connected to:", bytes(addr).hex())
        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            conn_handle, addr_type, addr = data
            self._connected = False
            self._conn_handle = None
            self.led.off()  # 断开时熄灭LED
            print("Disconnected")
            # 重新开始广告
            self._ble.gap_advertise(100)
        elif event == 3:  # _IRQ_GATTS_WRITE
            conn_handle, attr_handle = data
            print("Data written to handle:", attr_handle)
    
    def is_connected(self):
        return self._connected
    
    def send_touch_report(self, contact_count, contact_max, contact_id, tip_switch, x, y):
        """发送触摸报告（绝对坐标）- 参考C3_tools.py的实现"""
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
            print("Error sending touch report:", e)
            # 如果发送失败，标记为断开连接
            self._connected = False
            self._conn_handle = None
            return False