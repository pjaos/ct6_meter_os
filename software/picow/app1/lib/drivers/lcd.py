class LCD(object):
    """@brief Allow an I2C LCD display to be controlled from a Raspberry
              Pi Pico. This is based on the https://github.com/bogdal/rpi-lcd
              for the non Pico Raspberry Pi devices."""
    CLEAR_DISPLAY = 0x01
    ENABLE_BIT = 0b00000100
    LINES = {
        1: 0x80,
        2: 0xC0,
        3: 0x94,
        4: 0xD4}

    BACKLIGHT = 0x08
    NOBACKLIGHT = 0x00

    MODE_CMD = 0
    MODE_DATA = 1

    def __init__(self, i2c, address=0x27, width=20, rows=4, blight=True):
        """@brief Constructor
           @param i2c The I2C instance to communicate with the ADS1115 device.
           @param address The I2C LCD address. Default = 0x27.
           @param width The number of characters on a line of the display. Default=20, typically 20 or 16.
           @param rows The number of rows in the display. Default=4, typically 4 or 2.
           @param blight The back light state (default True = on)."""
        self._address = address
        self._i2c = i2c
        self._rows = rows
        self._width = width
        self._blight_status = blight
        #Init the display
        self._write(0x33)
        self._write(0x32)
        self._write(0x06)
        self._write(0x0C)
        self._write(0x28)
        self._write(LCD.CLEAR_DISPLAY)
        pass # A Short delay

    def _wr(self, byte):
        """@brief Write a byte to the I2C LCD device.
           @param byte The byte to write to the LCD."""
        self._i2c.writeto(self._address, bytearray( (byte,)))

    def _wr_byte(self, byte):
        """@brief Write a byte to the LCD toggling the LCD enable bit.
           @param byte The byte to write to the LCD."""
        self._wr(byte)
        self._wr((byte | LCD.ENABLE_BIT))
        pass # A Short delay
        self._wr((byte & ~LCD.ENABLE_BIT))
        pass # A Short delay

    def _write(self, byte, mode=MODE_CMD):
        """@brief Write a byte to the display. The high then low nibbles
                  are transferred to the LCD.
           @param byte The byte to be transferred to the LCD.
           @param mode The mode (CMD of DATA)."""
        bl_mode = LCD.BACKLIGHT if self._blight_status else LCD.NOBACKLIGHT
        self._wr_byte(mode | (byte & 0xF0) | bl_mode)
        self._wr_byte(mode | ((byte << 4) & 0xF0) | bl_mode)

    def backlight(self, on):
        """@brief Set the backlight on/off.
           @param on If True then the back light is set on."""
        self._blight_status = on
        self._wr(0)

    def clear(self):
        """@brief Clear the display"""
#        self._wr(LCD.CLEAR_DISPLAY)
        for lineNum in range(1, self._rows+1):
            self.write_line(" "*self._width, lineNum)

    def write_line(self, line, line_number):
        """@brief set the text on one line.
           @param line The line text.
           @param line_number The line number to set on the display (1 = the first line)"""
        if line_number <= self._rows:
            value = LCD.LINES.get(line_number, LCD.LINES[1])
            self._write(value)
            line_text = self._get_limited_line(line)
            for char in line_text:
                self._write(ord(char), mode=LCD.MODE_DATA)
            pass # A Short delay

    def write_lines(self, all_lines):
        """@brief Write lines to the display.
           @param all_lines Lines of text. Each line should be separated
                  by line feed characters."""
        lines = all_lines.split('\n')
        line_number = 1
        for line in lines:
            self.write_line(line, line_number)
            line_number += 1

    def _get_limited_line(self, line):
        """@brief Get a line limited to the number of the characters on the display line.
           @return the line text."""
        if len(line):
            line = line[:self._width]
        return line

# Example
#lcd = LCD(width=40, rows=4, i2CBus=1, sda=2, scl=3)
#lcd.backlight(True)
#lcd.clear()
#lcd.write_lines("Line 1: 01234dddddddddddddddddddddd\nLine 2\nLine 3\n Line 4")
