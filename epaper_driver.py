from machine import Pin, SPI
import framebuf
import utime

EPD_WIDTH = 122
EPD_HEIGHT = 250
RST_PIN, DC_PIN, CS_PIN, BUSY_PIN = 12, 8, 9, 13


class EPD_2in13_V4_Landscape(framebuf.FrameBuffer):
    """Waveshare Pico-ePaper 2.13 V4 driver using native portrait RAM.

    The previous landscape mode produced a progressive skew on the real panel.
    This class keeps the old name so main.py can import it unchanged, but the
    exposed framebuffer is portrait: 128x250 logical pixels, with 122px visible
    width.  Using the controller's native portrait transfer avoids the landscape
    byte/stride ambiguity.
    """

    def __init__(self):
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)

        self.width = (EPD_WIDTH // 8) * 8 + 8 if EPD_WIDTH % 8 != 0 else EPD_WIDTH
        self.height = EPD_HEIGHT
        self.visible_width = EPD_WIDTH
        self.buffer = bytearray(self.height * self.width // 8)

        self.spi = SPI(1)
        self.spi.init(baudrate=4000_000)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_HLSB)
        self.init()

    def delay_ms(self, delaytime):
        utime.sleep(delaytime / 1000.0)

    def reset(self):
        self.reset_pin.value(1)
        self.delay_ms(20)
        self.reset_pin.value(0)
        self.delay_ms(2)
        self.reset_pin.value(1)
        self.delay_ms(20)

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

    def send_data_buffer(self, data):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(bytearray(data))
        self.cs_pin.value(1)

    def ReadBusy(self):
        while self.busy_pin.value() == 1:
            self.delay_ms(10)

    def SetWindows(self, Xstart, Ystart, Xend, Yend):
        self.send_command(0x44)
        self.send_data((Xstart >> 3) & 0xFF)
        self.send_data((Xend >> 3) & 0xFF)
        self.send_command(0x45)
        self.send_data(Ystart & 0xFF)
        self.send_data((Ystart >> 8) & 0xFF)
        self.send_data(Yend & 0xFF)
        self.send_data((Yend >> 8) & 0xFF)

    def SetCursor(self, Xstart, Ystart):
        self.send_command(0x4E)
        self.send_data((Xstart >> 3) & 0xFF)
        self.send_command(0x4F)
        self.send_data(Ystart & 0xFF)
        self.send_data((Ystart >> 8) & 0xFF)

    def TurnOnDisplay(self):
        self.send_command(0x22)
        self.send_data(0xf7)
        self.send_command(0x20)
        self.ReadBusy()

    def init(self):
        self.reset()
        self.delay_ms(100)
        self.ReadBusy()
        self.send_command(0x12)
        self.ReadBusy()

        self.send_command(0x01)
        self.send_data(0xf9)
        self.send_data(0x00)
        self.send_data(0x00)

        # Native portrait address progression from the Waveshare sample.
        self.send_command(0x11)
        self.send_data(0x03)

        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)
        self.send_command(0x3C)
        self.send_data(0x05)
        self.send_command(0x21)
        self.send_data(0x00)
        self.send_data(0x80)
        self.send_command(0x18)
        self.send_data(0x80)
        self.ReadBusy()

    def build_epd_buffer(self):
        # Do not send the FrameBuffer memory directly.  On the real panel the
        # direct buffer path still skews block shapes, which suggests a packing
        # mismatch.  Re-pack from logical pixels into the controller's native
        # portrait byte order: leftmost pixel is bit7, then bit6 ... bit0.
        row_bytes = self.width // 8
        out = bytearray(row_bytes * self.height)
        idx = 0
        for y in range(self.height):
            for bx in range(row_bytes):
                value = 0
                for bit in range(8):
                    x = bx * 8 + bit
                    if self.pixel(x, y):
                        value |= 0x80 >> bit
                out[idx] = value
                idx += 1
        return out

    def display(self, image=None):
        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)
        self.send_command(0x24)
        if image is None or image is self.buffer:
            self.send_data_buffer(self.build_epd_buffer())
        else:
            self.send_data_buffer(image)
        self.TurnOnDisplay()

    def Clear(self):
        self.fill(0xff)
        self.display()
