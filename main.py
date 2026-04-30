import time
import epaper_driver

# Block-only smoke test: no text, no rect/hline/vline helpers.
# If only the outer border changes, the coordinate/window/driver mapping is
# still wrong below the application layer.

epd = epaper_driver.EPD_2in13_V4_Landscape()
print("Block pattern smoke test...")
epd.Clear()

epd.fill(0xff)

# Corner markers
epd.fill_rect(0, 0, 18, 18, 0x00)
epd.fill_rect(100, 0, 18, 18, 0x00)
epd.fill_rect(0, 220, 18, 18, 0x00)
epd.fill_rect(100, 220, 18, 18, 0x00)

# Large interior blocks, spaced vertically
epd.fill_rect(20, 35, 30, 22, 0x00)
epd.fill_rect(60, 70, 30, 22, 0x00)
epd.fill_rect(20, 105, 70, 10, 0x00)
epd.fill_rect(20, 140, 30, 22, 0x00)
epd.fill_rect(60, 175, 30, 22, 0x00)

# Center vertical reference made from short blocks
epd.fill_rect(56, 20, 10, 30, 0x00)
epd.fill_rect(56, 85, 10, 30, 0x00)
epd.fill_rect(56, 150, 10, 30, 0x00)
epd.fill_rect(56, 215, 10, 25, 0x00)

epd.display()

while True:
    time.sleep(1)
