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

# Simple reference geometry. If these are skewed, the problem is below the app
# layout layer: panel variant, wiring, or low-level driver mismatch.
epd.rect(0, 0, 120, 120, 0x00)
epd.hline(0, 80, 120, 0x00)
epd.vline(60, 0, 120, 0x00)
epd.fill_rect(10, 90, 20, 20, 0x00)
epd.fill_rect(45, 90, 20, 20, 0x00)
epd.fill_rect(80, 90, 20, 20, 0x00)

epd.display()

while True:
    time.sleep(1)
