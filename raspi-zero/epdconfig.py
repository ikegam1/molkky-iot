import lgpio
import spidev
import time

# ピン定義
RST_PIN = 17
DC_PIN  = 25
CS_PIN  = 8
BUSY_PIN = 24
PWR_PIN = 18

class RaspberryPi:
    def __init__(self):
        self.SPI = spidev.SpiDev()
        # メイン側と共有できるように、すでに開いている場合はそれを使う
        try:
            self.h = lgpio.gpiochip_open(0)
        except:
            pass

    def digital_write(self, pin, value):
        # CS_PIN (8) のときは lgpio で書き込まず、スルーする
        if pin == CS_PIN:
            return
        lgpio.gpio_write(self.h, pin, value)

    def digital_read(self, pin):
        return lgpio.gpio_read(self.h, pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        self.SPI.writebytes(data)

    def spi_writebyte2(self, data):
        self.SPI.writebytes2(data)

    def module_init(self):
        # BUSY_PIN, RST_PIN, DC_PIN, PWR_PIN だけを確保する
        # CS_PIN (8) は SPI.open 側で自動制御されるため、ここでは確保しない
        lgpio.gpio_claim_output(self.h, RST_PIN)
        lgpio.gpio_claim_output(self.h, DC_PIN)
        lgpio.gpio_claim_output(self.h, PWR_PIN)
        lgpio.gpio_claim_input(self.h, BUSY_PIN)
        
        # SPIの初期化（ここでCSピンなどがシステムによって制御され始める）
        self.SPI.open(0, 0)
        self.SPI.max_speed_hz = 4000000
        self.SPI.mode = 0b00
        return 0

    def module_exit(self):
        self.SPI.close()
        lgpio.gpio_write(self.h, RST_PIN, 0)
        lgpio.gpio_write(self.h, DC_PIN, 0)

# インスタンス化
implementation = RaspberryPi()

def digital_write(pin, value): implementation.digital_write(pin, value)
def digital_read(pin): return implementation.digital_read(pin)
def delay_ms(delaytime): implementation.delay_ms(delaytime)
def spi_writebyte(data): implementation.spi_writebyte(data)
def spi_writebyte2(data): implementation.spi_writebyte2(data)
def module_init(): return implementation.module_init()
def module_exit(): implementation.module_exit()
