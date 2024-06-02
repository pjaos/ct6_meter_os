import sys

from machine import Timer, reset_cause, deepsleep

class Hardware(object):
    """@brief Provide functionality to ease cross platform use."""
    
    RPI_PICO_PLATFORM   = "rp2"
    ESP32_PLATFORM      = "esp32"
        
    @staticmethod
    def IsPico():
        """@return True if running on a RPi pico platform."""
        pico=False
        if sys.platform == Hardware.RPI_PICO_PLATFORM:
            pico=True
        return pico

    @staticmethod
    def IsESP32():
        """@return True if running on an ESP32 platform."""
        esp32=False
        if sys.platform == Hardware.ESP32_PLATFORM:
            esp32=True
        return esp32
        
    @staticmethod
    def GetTimer():
        """@brief Get a machine.Timer instance.
           @return a Timer instance."""
        timer = None
        if Hardware.IsPico():
            timer = Timer(-1)
        else:
            timer = Timer(0)
        return timer
    
    @staticmethod
    def GetLastResetCause(self):
        """@brief Get the reset cause.
                  See, https://docs.micropython.org/en/latest/library/machine.html#machine-constants."""
        return reset_cause()
    
    @staticmethod
    def DeepSleep(microSeconds):
        """@brief Put the microcontroller to sleep for a period of time.
           @param microSeconds The period of time to put the micro controller to sleep."""
        if microSeconds > 0:
            deepsleep(microSeconds)
    
    