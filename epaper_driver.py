from machine import Pin, SPI
import framebuf
import utime

# Waveshare Pico-ePaper 2.13 V4 physical resolution.
EPD_WIDTH = 122
EPD_HEIGHT = 250

# Logical landscape canvas exposed to the app.
LANDSCAPE_WIDTH = EPD_HEIGHT
LANDSCAPE_HEIGHT = EPD_WIDTH

RST_PIN, DC_PIN, CS_PIN, BUSY_PIN = 12, 8, 9, 13


class EPD_2in13_V4_Landscape(framebuf.FrameBuffer):
    def __init__(self):
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)

        self.width = LANDSCAPE_WIDTH
        self.height = LANDSCAPE_HEIGHT
        self._physical_width = (EPD_WIDTH // 8) * 8 + 8 if EPD_WIDTH % 8 else EPD_WIDTH
        self._physical_height = EPD_HEIGHT

        self.spi = SPI(1)
        self.spi.init(baudrate=4000_000)

        # Keep the application framebuffer as a normal landscape HLSB canvas
        # (250x122).  The previous VLSB landscape transfer sheared the image on
        # some panels: lines near the bottom drifted to the right.  display()
        # now rotates this canvas into the controller's native portrait RAM
        # explicitly, so every row starts at the correct byte boundary.
        self.buffer = bytearray(((self.width + 7) // 8) * self.height)
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

    def set_window(self, x_start, y_start, x_end, y_end):
        self.send_command(0x44)
        self.send_data((x_start >> 3) & 0xff)
        self.send_data((x_end >> 3) & 0xff)
        self.send_command(0x45)
        self.send_data(y_start & 0xff)
        self.send_data((y_start >> 8) & 0xff)
        self.send_data(y_end & 0xff)
        self.send_data((y_end >> 8) & 0xff)

    def set_cursor(self, x_start, y_start):
        self.send_command(0x4E)
        self.send_data((x_start >> 3) & 0xff)
        self.send_command(0x4F)
        self.send_data(y_start & 0xff)
        self.send_data((y_start >> 8) & 0xff)

    def init(self):
        self.reset()
        self.ReadBusy()
        self.send_command(0x12)
        self.ReadBusy()

        self.send_command(0x01)
        self.send_data(0xf9)
        self.send_data(0x00)
        self.send_data(0x00)

        # Native portrait RAM order.  Landscape is handled in software during
        # transfer instead of relying on controller address remapping.
        self.send_command(0x11)
        self.send_data(0x03)

        self.set_window(0, 0, self._physical_width - 1, self._physical_height - 1)
        self.set_cursor(0, 0)
        self.send_command(0x3C)
        self.send_data(0x05)
        self.send_command(0x21)
        self.send_data(0x00)
        self.send_data(0x80)
        self.send_command(0x18)
        self.send_data(0x80)
        self.ReadBusy()

    def _landscape_pixel_for_physical(self, px, py):
        # Rotate the logical landscape framebuffer into portrait controller RAM.
        # Logical (0,0) appears at the upper-left in landscape orientation.
        lx = py
        ly = EPD_WIDTH - 1 - px
        if 0 <= lx < self.width and 0 <= ly < self.height:
            return self.pixel(lx, ly)
        return 1

    def _build_physical_buffer(self):
        row_bytes = self._physical_width // 8
        out = bytearray(row_bytes * self._physical_height)
        idx = 0
        for py in range(self._physical_height):
            for bx in range(row_bytes):
                value = 0
                for bit in range(8):
                    px = bx * 8 + bit
                    if self._landscape_pixel_for_physical(px, py):
                        value |= 0x80 >> bit
                out[idx] = value
                idx += 1
        return out

    def display(self):
        self.set_window(0, 0, self._physical_width - 1, self._physical_height - 1)
        self.set_cursor(0, 0)
        self.send_command(0x24)
        self.send_data_buffer(self._build_physical_buffer())
        self.send_command(0x22)
        self.send_data(0xf7)
        self.send_command(0x20)
        self.ReadBusy()

    def Clear(self):
        self.fill(0xff)
        self.display()
