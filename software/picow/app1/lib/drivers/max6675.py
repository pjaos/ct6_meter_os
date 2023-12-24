class MAX6675(object):
    """@brief An interface to a MAX6675 Cold-Junction-Compensated K-Thermocouple-to-Digital Converter.
              Note !!!
                   The type K temperature probe must be connected the correct way round + to + - to -.
    """
    
    INPUT_BIT = 2
    TEMP_VALUE_MASK = 0xfff
        
    def __init__(self, spi, cs):
        """@brief Constructor
           @param spi The SPI bus to use to communicate with the MAX66785 device. A machine.SPI() instance.
           @param cs A The active low chip select pin. A machine.Pin() instance.
           @return The temperature read or None """
        self._spi = spi
        self._cs  = cs
        self._cs.value(1)
        
    def readTemp(self, calFactor=1.0):
        """@brief Read the temperature in °C.
           @param calFactor The calibration factor. This is simply the multiplier
                            for the temperature read. The default is 1.0 (uncalibrated).
           @return The temperature in °C. This may not be very accurate unless calibration is used.
                   A value of None will be returned if there was an error reading the temperature value. """
        temp = None
        # Set CS low
        self._cs.value(0)
        bList = self._spi.read(2)
        value = bList[0] << 8 | bList[1]
        # set CS high
        self._cs.value(1)
        # If error
        if value & (1<<MAX6675.INPUT_BIT):
            pass
        
        else:
            value >>= 3 # 12 bits, bit 15 = 0
            # Scale by 0.25 degrees C per bit and return value.
            temp = value * 0.25

        # If an error occurred reading the temperature
        if temp is None:
            return temp

        else:
            return temp*calFactor            
    
"""
# Example RPi Pico SPI bus 0 pinout

from machine import Pin, SPI, SoftSPI

spiBus=0
clkFreqHz=5000000
sckGPIO=2
mosiGPIO=3
misoGPIO=4
csGPIO=5
"""

"""
# Example ESP32 SPI bus 1 pinout

from machine import Pin, SPI, SoftSPI

spiBus=1
clkFreqHz=5000000
sckGPIO=18
mosiGPIO=23
misoGPIO=19
csGPIO=5
"""

"""
#Example code to read temp in a loop

from time import sleep

spi = SPI(spiBus, baudrate=clkFreqHz, sck=Pin(sckGPIO), mosi=Pin(mosiGPIO), miso=Pin(misoGPIO))

cs = Pin(csGPIO, mode=Pin.OUT, value=1)

max6675 = MAX6675(spi, cs)
while True:
    temp = max6675.readTemp()
    print("Temperature = {:.1f} °C".format(temp))
    sleep(1)
"""


