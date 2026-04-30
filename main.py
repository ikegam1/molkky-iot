import time
import epaper_driver

# Official-sample style smoke test.
# This intentionally removes the game/keypad code so we can check whether the
# panel/driver can render simple text and straight lines at all.

epd = epaper_driver.EPD_2in13_V4_Landscape()
print("Official smoke test clear...")
epd.Clear()

epd.fill(0xff)
epd.text("Waveshare", 0, 10, 0x00)
epd.text("ePaper-2.13", 0, 25, 0x00)
epd.text("Raspberry Pico", 0, 40, 0x00)
epd.text("Hello World", 0, 55, 0x00)

# Simple reference geometry. Use fill_rect only: some MicroPython framebuf
# builds do not provide rect/hline/vline, which would stop after Clear().
epd.fill_rect(0, 0, 120, 3, 0x00)
epd.fill_rect(0, 0, 3, 120, 0x00)
epd.fill_rect(0, 117, 120, 3, 0x00)
epd.fill_rect(117, 0, 3, 120, 0x00)
epd.fill_rect(0, 80, 120, 3, 0x00)
epd.fill_rect(60, 0, 3, 120, 0x00)
epd.fill_rect(10, 90, 20, 20, 0x00)
epd.fill_rect(45, 90, 20, 20, 0x00)
epd.fill_rect(80, 90, 20, 20, 0x00)

epd.display()

while True:
    time.sleep(1)
