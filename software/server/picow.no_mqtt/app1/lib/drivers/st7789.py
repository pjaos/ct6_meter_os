"""

from machine import SPI, Pin
import st7789

# Example code for driving a display containing the ST7789 device
# micropython must be compiled with the st7789 module built in
# This provices a fast (C code) interface to the SPI display.
# See https://github.com/russhughes/st7789_mpy for more information on this.
# Currently the vga2_bold_16x32.py file must be loaded onto the PICOW for this example.
 
def config(rotation=0, buffer_size=0, options=0):
    return st7789.ST7789(
        # 31250000
        SPI(0, baudrate=31250000, sck=Pin(2), mosi=Pin(3)),
        240,
        320,
        reset=Pin(21, Pin.OUT),
        cs=Pin(19, Pin.OUT),
        dc=Pin(20, Pin.OUT),
        backlight=Pin(15, Pin.OUT),
        rotation=rotation,
        options=options,
        buffer_size=buffer_size)

import random
import utime
import st7789
import vga2_bold_16x32 as font

tft = config(1)

def center(text):
    length = 1 if isinstance(text, int) else len(text)
    tft.text(
        font,
        text,
        tft.width() // 2 - length // 2 * font.WIDTH,
        tft.height() // 2 - font.HEIGHT //2,
        st7789.WHITE,
        st7789.RED)

def main():
    tft.init()
    tft.fill(st7789.RED)
    center(b'\xADHola!')
    utime.sleep(2)
    tft.fill(st7789.BLACK)

    while True:
        for rotation in range(4):
            print(f"PJA: rotation={rotation}")
            tft.rotation(rotation)
            tft.fill(0)
            col_max = tft.width() - font.WIDTH*6
            row_max = tft.height() - font.HEIGHT

            for _ in range(128):
                tft.text(
                    font,
                    b'\xADHola!',
                    random.randint(0, col_max),
                    random.randint(0, row_max),
                    st7789.color565(
                        random.getrandbits(8),
                        random.getrandbits(8),
                        random.getrandbits(8)),
                    st7789.color565(
                        random.getrandbits(8),
                        random.getrandbits(8),
                        random.getrandbits(8)))


main()
"""