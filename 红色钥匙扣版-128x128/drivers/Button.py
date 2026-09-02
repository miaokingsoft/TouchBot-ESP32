from machine import Pinfrom micropython import schedule,constimport time# buttonsclass Button:    def __init__(self, pin_num, reverse=False):        self.__reverse = reverse        (self.__press_level, self.__release_level) = (0, 1) if not self.__reverse else (1, 0)        self.__pin = Pin(pin_num, Pin.IN, pull=Pin.PULL_UP)        self.__pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self.__irq_handler)        # self.__user_irq = None        self.event_pressed = None        self.event_released = None        self.__pressed_count = 0        self.__was_pressed = False        print("level: pressed is {}, released is {}." .format(self.__press_level, self.__release_level))        def __irq_handler(self, pin):        irq_falling = True if pin.value() == self.__press_level else False        # debounce        time.sleep_ms(10)        if self.__pin.value() == (self.__press_level if irq_falling else self.__release_level):            # new event handler            # pressed event            if irq_falling:                if self.event_pressed is not None:                    schedule(self.event_pressed, self.__pin)                # key status                self.__was_pressed = True                if (self.__pressed_count < 100):                    self.__pressed_count = self.__pressed_count + 1            # release event            else:                if self.event_released is not None:                    schedule(self.event_released, self.__pin)    #返回当前是否按住。 True 表示按键按下，False 则未按下                def is_pressed(self):
        if self.__pin.value() == self.__press_level:
            return True
        else:
            return False
    #返回 True 或 False 指示自设备启动以来或上次调用此方法以来是否按下按钮。调用此方法将清除按下状态，因此必须再次按下按钮，然后才能再次返回 True 
    def was_pressed(self):
        r = self.__was_pressed
        self.__was_pressed = False
        return r
    #返回按键的按下总数，并在返回之前将该总数重置为零。注意，计数器超过100将不再计数。
    def get_presses(self):
        r = self.__pressed_count
        self.__pressed_count = 0        return r    def value(self):        return self.__pin.value()    #配置在引脚的触发源处于活动状态时调用的中断处理程序。用法与 machine.Pin.irq 一样    def irq(self, *args, **kws):        self.__pin.irq(*args, **kws)# button_a = Pin(0, Pin.IN, Pin.PULL_UP)# button_b = Pin(2, Pin.IN, Pin.PULL_UP)'''button_up = Button(12)button_down = Button(14)if button_a.value() == 0 and button_b.value() == 1:    self.bats_position -= 2    self.start = True'''