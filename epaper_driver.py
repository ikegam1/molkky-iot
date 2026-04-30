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
        self.dc_pin = Pin(DC_PIN, Pin.OUT)

        # Waveshare official landscape framebuffer shape:
        # logical app coordinates are 250x128, visible panel area is 250x122.
        self.width = (EPD_WIDTH // 8) * 8 + 8 if EPD_WIDTH % 8 != 0 else EPD_WIDTH
        self.height = EPD_HEIGHT
        self.buffer = bytearray(self.height * self.width // 8)

        self.spi = SPI(1)
        self.spi.init(baudrate=4000_000)
        self.transfer_variant = 0
        self.entry_mode_variant = 0
        self.entry_modes = [0x07, 0x03, 0x05, 0x06]
        super().__init__(self.buffer, self.height, self.width, framebuf.MONO_VLSB)
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
        self.send_data(Xstart & 0xFF)
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

        self.set_entry_mode(0)
        self.send_command(0x3C)
        self.send_data(0x05)
        self.send_command(0x21)
        self.send_data(0x00)
        self.send_data(0x80)
        self.send_command(0x18)
        self.send_data(0x80)
        self.ReadBusy()

    def set_entry_mode(self, variant):
        # Diagnostic only: switch controller data entry mode (register 0x11).
        self.entry_mode_variant = variant
        self.send_command(0x11)
        self.send_data(self.entry_modes[variant])
        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)

    def set_transfer_variant(self, variant):
        # Diagnostic only: switch byte-transfer order without changing drawing.
        self.transfer_variant = variant

    def _write_landscape_buffer(self, image):
        # Variant 0 is the Waveshare official landscape transfer order.
        # Other variants are for real-panel diagnosis.  The current symptom is
        # a progressive skew/flow, which is usually a byte order / stride issue.
        row_bytes = int(self.width / 8)
        if self.transfer_variant == 0:
            for j in range(row_bytes - 1, -1, -1):
                base = j * self.height
                for i in range(0, self.height):
                    self.send_data(image[i + base])
        elif self.transfer_variant == 1:
            for j in range(0, row_bytes):
                base = j * self.height
                for i in range(0, self.height):
                    self.send_data(image[i + base])
        elif self.transfer_variant == 2:
            for i in range(0, self.height):
                for j in range(row_bytes - 1, -1, -1):
                    self.send_data(image[i + j * self.height])
        elif self.transfer_variant == 3:
            for i in range(0, self.height):
                for j in range(0, row_bytes):
                    self.send_data(image[i + j * self.height])

    def display(self, image=None):
        if image is None:
            image = self.buffer
        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)
        self.send_command(0x24)
        self._write_landscape_buffer(image)
        self.TurnOnDisplay()

    def Clear(self):
        self.fill(0xff)
        self.display()
