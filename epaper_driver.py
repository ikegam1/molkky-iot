from machine import Pin, SPI
import framebuf
import utime

EPD_WIDTH = 122
EPD_HEIGHT = 250
RST_PIN, DC_PIN, CS_PIN, BUSY_PIN = 12, 8, 9, 13

class EPD_2in13_V4_Landscape(framebuf.FrameBuffer):
    def __init__(self):
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.width = (EPD_WIDTH // 8) * 8 + 8 if EPD_WIDTH % 8 != 0 else EPD_WIDTH
        self.height = EPD_HEIGHT
        self.spi = SPI(1)
        self.spi.init(baudrate=4000_000)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)
        self.buffer = bytearray(self.height * self.width // 8)
        super().__init__(self.buffer, self.height, self.width, framebuf.MONO_VLSB)
        self.init()

    def delay_ms(self, delaytime):
        utime.sleep(delaytime / 1000.0)

    def reset(self):
        self.reset_pin.value(1)
        self.delay_ms(20); self.reset_pin.value(0)
        self.delay_ms(2); self.reset_pin.value(1)
        self.delay_ms(20)

    def send_command(self, command):
        self.dc_pin.value(0); self.cs_pin.value(0)
        self.spi.write(bytearray([command]))
        self.cs_pin.value(1)

    def send_data(self, data):
        self.dc_pin.value(1); self.cs_pin.value(0)
        self.spi.write(bytearray([data]))
        self.cs_pin.value(1)

    def ReadBusy(self):
        while(self.busy_pin.value() == 1): self.delay_ms(10)

    def init(self):
        self.reset()
        self.ReadBusy()
        self.send_command(0x12); self.ReadBusy()
        self.send_command(0x01); self.send_data(0xf9); self.send_data(0x00); self.send_data(0x00)
        self.send_command(0x11); self.send_data(0x07) # Landscape mode
        self.send_command(0x44); self.send_data(0); self.send_data((self.width-1)>>3)
        self.send_command(0x45); self.send_data(0); self.send_data(0); self.send_data((self.height-1)&0xff); self.send_data((self.height-1)>>8)
        self.send_command(0x3C); self.send_data(0x05)
        self.send_command(0x21); self.send_data(0x00); self.send_data(0x80)
        self.send_command(0x18); self.send_data(0x80)
        self.ReadBusy()

    def display(self):
        self.send_command(0x24)
        # サンプルコードにあった Landscape 用の転送ロジック
        for j in range(int(self.width / 8) - 1, -1, -1):
            for i in range(0, self.height):
                self.send_data(self.buffer[i + j * self.height])
        self.send_command(0x22); self.send_data(0xf7)
        self.send_command(0x20); self.ReadBusy()

    def Clear(self):
        self.fill(0xff)
        self.display()

