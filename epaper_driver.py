from machine import Pin, SPI
import framebuf
import utime

# Waveshare Pico-ePaper-2.7 V2 / Rev2.2
# 264 x 176 pixels, black/white, SPI1 on Pico pins GP8-13.
EPD_WIDTH = 176   # controller native portrait width
EPD_HEIGHT = 264  # controller native portrait height

RST_PIN = 12
DC_PIN = 8
CS_PIN = 9
BUSY_PIN = 13

EPD_2IN7_LUT_VCOM_DC = [
    0x00, 0x00,
    0x00, 0x08, 0x00, 0x00, 0x00, 0x02,
    0x60, 0x28, 0x28, 0x00, 0x00, 0x01,
    0x00, 0x14, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x12, 0x12, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]
EPD_2IN7_LUT_WW = [
    0x40, 0x08, 0x00, 0x00, 0x00, 0x02,
    0x90, 0x28, 0x28, 0x00, 0x00, 0x01,
    0x40, 0x14, 0x00, 0x00, 0x00, 0x01,
    0xA0, 0x12, 0x12, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]
EPD_2IN7_LUT_BW = EPD_2IN7_LUT_WW
EPD_2IN7_LUT_BB = [
    0x80, 0x08, 0x00, 0x00, 0x00, 0x02,
    0x90, 0x28, 0x28, 0x00, 0x00, 0x01,
    0x80, 0x14, 0x00, 0x00, 0x00, 0x01,
    0x50, 0x12, 0x12, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]
EPD_2IN7_LUT_WB = EPD_2IN7_LUT_BB


class EPD_2in7_V2_Landscape(framebuf.FrameBuffer):
    """FrameBuffer-compatible driver for the Waveshare Pico-ePaper-2.7.

    Public drawing area is landscape 264x176.  The controller RAM is native
    portrait 176x264, so display() rotates the landscape framebuffer into the
    order used by Waveshare's sample driver.
    """

    def __init__(self):
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)
        self.cs_pin.value(1)

        self.width = EPD_HEIGHT   # 264 landscape width exposed to app
        self.height = EPD_WIDTH   # 176 landscape height exposed to app
        self.native_width = EPD_WIDTH
        self.native_height = EPD_HEIGHT
        self.buffer = bytearray(self.width * self.height // 8)

        self.spi = SPI(1)
        self.spi.init(baudrate=4_000_000)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init()

    def delay_ms(self, ms):
        utime.sleep(ms / 1000.0)

    def reset(self):
        self.reset_pin.value(1)
        self.delay_ms(200)
        self.reset_pin.value(0)
        self.delay_ms(2)
        self.reset_pin.value(1)
        self.delay_ms(200)

    def send_command(self, command):
        self.dc_pin.value(0)
        self.cs_pin.value(0)
        self.spi.write(bytearray([command]))
        self.cs_pin.value(1)

    def send_data(self, data):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(bytearray([data]))
        self.cs_pin.value(1)

    def ReadBusy(self):
        # Waveshare 2.7 sample: 0=busy, 1=idle.
        while self.busy_pin.value() == 0:
            self.send_command(0x71)
            self.delay_ms(10)
        self.delay_ms(200)

    def SetLut(self):
        self.send_command(0x20)
        for v in EPD_2IN7_LUT_VCOM_DC:
            self.send_data(v)
        self.send_command(0x21)
        for v in EPD_2IN7_LUT_WW:
            self.send_data(v)
        self.send_command(0x22)
        for v in EPD_2IN7_LUT_BW:
            self.send_data(v)
        self.send_command(0x23)
        for v in EPD_2IN7_LUT_BB:
            self.send_data(v)
        self.send_command(0x24)
        for v in EPD_2IN7_LUT_WB:
            self.send_data(v)

    def init(self):
        self.reset()

        self.send_command(0x01)  # POWER_SETTING
        self.send_data(0x03)
        self.send_data(0x00)
        self.send_data(0x2B)
        self.send_data(0x2B)
        self.send_data(0x09)

        self.send_command(0x06)  # BOOSTER_SOFT_START
        self.send_data(0x07)
        self.send_data(0x07)
        self.send_data(0x17)

        for a, b in ((0x60, 0xA5), (0x89, 0xA5), (0x90, 0x00),
                     (0x93, 0x2A), (0xA0, 0xA5), (0xA1, 0x00),
                     (0x73, 0x41)):
            self.send_command(0xF8)
            self.send_data(a)
            self.send_data(b)

        self.send_command(0x16)
        self.send_data(0x00)
        self.send_command(0x04)  # POWER_ON
        self.ReadBusy()

        self.send_command(0x00)  # PANEL_SETTING
        self.send_data(0xAF)
        self.send_command(0x30)  # PLL_CONTROL
        self.send_data(0x3A)
        self.send_command(0x61)  # RESOLUTION_SETTING
        self.send_data(0x00)
        self.send_data(0xB0)  # 176
        self.send_data(0x01)
        self.send_data(0x08)  # 264
        self.send_command(0x82)  # VCOM_DC_SETTING
        self.send_data(0x12)
        self.SetLut()

    def _send_white_plane(self):
        wide = self.native_width // 8  # 22 bytes per native row
        self.send_command(0x10)
        for _ in range(self.native_height * wide):
            self.send_data(0xFF)

    def display(self, image=None):
        if image is None or image is self.buffer:
            image = self.buffer

        high = self.native_height  # 264
        wide = self.native_width // 8  # 22
        self._send_white_plane()

        self.send_command(0x13)
        # Rotate landscape buffer into controller portrait byte order.
        for j in range(high):
            for i in range(wide):
                self.send_data(image[(wide - 1 - i) * high + j])

        self.send_command(0x12)
        self.ReadBusy()

    def Clear(self):
        self.fill(0xFF)
        self._send_white_plane()
        self.send_command(0x13)
        for _ in range(self.native_height * (self.native_width // 8)):
            self.send_data(0xFF)
        self.send_command(0x12)
        self.ReadBusy()

    def Sleep(self):
        self.send_command(0x50)
        self.send_data(0xF7)
        self.send_command(0x02)
        self.send_command(0x07)
        self.send_data(0xA5)


# Backward-compatible alias used by main.py during transition.
EPD_2in13_V4_Landscape = EPD_2in7_V2_Landscape
