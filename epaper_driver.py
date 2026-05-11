from machine import Pin, SPI
import framebuf
import utime

# Waveshare Pico-ePaper-2.7 V2 / Rev2.2
# Native panel: 176 x 264 portrait. App-facing framebuffer: 264 x 176 landscape.
EPD_WIDTH = 176
EPD_HEIGHT = 264

RST_PIN = 12
DC_PIN = 8
CS_PIN = 9
BUSY_PIN = 13

LUT_DATA_4GRAY = [
    0x40,0x48,0x80,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x8,0x48,0x10,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x2,0x48,0x4,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x20,0x48,0x1,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0xA,0x19,0x0,0x3,0x8,0x0,0x0,
    0x14,0x1,0x0,0x14,0x1,0x0,0x3,
    0xA,0x3,0x0,0x8,0x19,0x0,0x0,
    0x1,0x0,0x0,0x0,0x0,0x0,0x1,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x22,0x22,0x22,0x22,0x22,0x22,0x0,0x0,0x0,
    0x22,0x17,0x41,0x0,0x32,0x1C,
]


def _reverse_byte(value):
    value = ((value & 0xF0) >> 4) | ((value & 0x0F) << 4)
    value = ((value & 0xCC) >> 2) | ((value & 0x33) << 2)
    value = ((value & 0xAA) >> 1) | ((value & 0x55) << 1)
    return value


class EPD_2in7_V2_Landscape:
    """FrameBuffer-compatible wrapper around Waveshare's 2.7_V2 driver.

    This intentionally follows the working Waveshare Pico_ePaper-2.7_V2.py
    init/display sequence. The public buffer is landscape (264x176), using the
    same MONO_VLSB packing as Waveshare's landscape sample.
    """

    def __init__(self):
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)
        self.cs_pin.value(1)

        self.native_width = EPD_WIDTH
        self.native_height = EPD_HEIGHT
        self.width = EPD_HEIGHT    # 264 landscape width
        self.height = EPD_WIDTH    # 176 landscape height

        self.black = 0x00
        self.white = 0xFF
        self.darkgray = 0xAA
        self.grayish = 0x55
        self.LUT_DATA_4Gray = LUT_DATA_4GRAY

        self.spi = SPI(1)
        self.spi.init(baudrate=4_000_000)

        self.buffer = bytearray(self.native_height * self.native_width // 8)
        self.fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)

        self.init()

    def delay_ms(self, delaytime):
        utime.sleep(delaytime / 1000.0)

    # Minimal FrameBuffer API used by main.py.  Use composition instead of
    # subclassing framebuf.FrameBuffer because some MicroPython builds do not
    # behave well when native types are subclassed.
    def fill(self, color):
        return self.fb.fill(color)

    def fill_rect(self, x, y, w, h, color):
        return self.fb.fill_rect(x, y, w, h, color)

    def hline(self, x, y, w, color):
        return self.fb.hline(x, y, w, color)

    def vline(self, x, y, h, color):
        return self.fb.vline(x, y, h, color)

    def line(self, x1, y1, x2, y2, color):
        return self.fb.line(x1, y1, x2, y2, color)

    def rect(self, x, y, w, h, color):
        return self.fb.rect(x, y, w, h, color)

    def pixel(self, x, y, color=None):
        if color is None:
            return self.fb.pixel(x, y)
        return self.fb.pixel(x, y, color)

    def text(self, s, x, y, color):
        return self.fb.text(s, x, y, color)

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

    def send_data_buffer(self, buf):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(bytearray(buf))
        self.cs_pin.value(1)

    def ReadBusy(self, timeout_ms=10000):
        print("e-Paper busy")
        waited = 0
        # Match the working Waveshare 2.7_V2 sample exactly: wait while BUSY=1.
        while self.busy_pin.value() == 1:
            self.delay_ms(2)
            waited += 2
            if waited >= timeout_ms:
                print("EPD BUSY timeout; continuing")
                break
        self.delay_ms(200)
        print("e-Paper busy release")

    def TurnOnDisplay(self):
        self.send_command(0x22)
        self.send_data(0xF7)
        self.send_command(0x20)
        self.ReadBusy()

    def TurnOnDisplay_Fast(self):
        self.send_command(0x22)
        self.send_data(0xC7)
        self.send_command(0x20)
        self.ReadBusy()

    def TurnOnDisplay_Partial(self):
        self.send_command(0x22)
        self.send_data(0xFF)
        self.send_command(0x20)
        self.ReadBusy()

    def Lut(self):
        self.send_command(0x32)
        for i in range(159):
            self.send_data(self.LUT_DATA_4Gray[i])

    def init(self):
        self.reset()
        self.ReadBusy()

        self.send_command(0x12)  # SWRESET
        self.ReadBusy()

        self.send_command(0x45)  # RAM-Y start/end: 0..263
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x07)
        self.send_data(0x01)

        self.send_command(0x4F)  # RAM-Y counter = 0
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x11)  # data entry mode
        self.send_data(0x03)

    def init_Fast(self):
        self.reset()
        self.ReadBusy()

        self.send_command(0x12)
        self.ReadBusy()
        self.send_command(0x12)
        self.ReadBusy()

        self.send_command(0x18)
        self.send_data(0x80)
        self.send_command(0x22)
        self.send_data(0xB1)
        self.send_command(0x20)
        self.ReadBusy()

        self.send_command(0x1A)
        self.send_data(0x64)
        self.send_data(0x00)

        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x07)
        self.send_data(0x01)

        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x11)
        self.send_data(0x03)

        self.send_command(0x22)
        self.send_data(0x91)
        self.send_command(0x20)
        self.ReadBusy()

    def clear(self):
        width_bytes = self.native_width // 8
        height = self.native_height
        self.send_command(0x24)
        self.send_data_buffer([0xFF] * width_bytes * height)
        self.TurnOnDisplay()

    def Clear(self):
        print("EPD clear")
        self.fill(0xFF)
        self.clear()

    def display(self, image=None):
        if image is None or image is self.buffer:
            image = self.buffer
        print("EPD display")
        width_bytes = self.native_width // 8  # 22
        height = self.native_height          # 264
        self.send_command(0x24)
        # Exact landscape transfer formula from the working Waveshare V2 sample,
        # plus 180-degree rotation so the KEY buttons are on the right side.
        for j in range(height):
            src_x = height - 1 - j
            for i in range(width_bytes):
                # Original formula uses byte row (21-i). For 180-degree rotation
                # use the opposite byte row and reverse bit order within the byte.
                self.send_data(_reverse_byte(image[i * height + src_x]))
        self.TurnOnDisplay()

    def display_Fast(self, image=None):
        if image is None or image is self.buffer:
            image = self.buffer
        self.send_command(0x24)
        self.send_data_buffer(image)
        self.TurnOnDisplay_Fast()

    def display_Base_color(self, color):
        width_bytes = self.native_width // 8
        height = self.native_height
        data = [color] * width_bytes * height
        self.send_command(0x24)
        self.send_data_buffer(data)
        self.send_command(0x26)
        self.send_data_buffer(data)

    def sleep(self):
        self.send_command(0x10)
        self.send_data(0x01)

    def Sleep(self):
        self.sleep()


# Backward-compatible alias.
EPD_2in13_V4_Landscape = EPD_2in7_V2_Landscape
