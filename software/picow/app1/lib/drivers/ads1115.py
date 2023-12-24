from time import sleep_us

class ADS1115Error(Exception):
  pass

class ADS1115ADC():
    """@brief Responsible for communication with ADS1115 quad ADC devices."""

    ADDR_PIN_LOW_SLAVE_ADDR  = 0b01001000
    ADDR_PIN_HIGH_SLAVE_ADDR = 0b01001001
    ADDR_PIN_SDA_SLAVE_ADDR  = 0b01001010
    ADDR_PIN_SCL_SLAVE_ADDR  = 0b01001011

    OS_CFG_REG_BIT          = 15
    MUX_CFG_REG_BIT         = 12
    PGA_CFG_REG_BIT         = 9
    MODE_CFG_REG_BIT        = 8
    DR_CFG_REG_BIT          = 5
    COMP_MODE_CFG_REG_BIT   = 4
    COMP_POL_CFG_REG_BIT    = 3
    COMP_LAT_CFG_REG_BIT    = 2
    COMP_QUE_CFG_REG_BIT    = 0

    CONVERSION_REG          = 0
    CONFIG_REG              = 1
    LO_THREH_REG            = 2
    HI_THREH_REG            = 3

    FS_VOLTAGE_6144         = 6.144
    FS_VOLTAGE_4096         = 4.096
    FS_VOLTAGE_2048         = 2.048
    FS_VOLTAGE_1024         = 1.024
    FS_VOLTAGE_0512         = 0.512
    FS_VOLTAGE_0256         = 0.256

    SPS_8                   = 8
    SPS_16                  = 16
    SPS_32                  = 32
    SPS_64                  = 64
    SPS_128                 = 128
    SPS_250                 = 250
    SPS_475                 = 475
    SPS_860                 = 860

    def __init__(self, i2c, deviceAddr):
        """@brief Constructor
           @param i2c The I2C bus.
           @param deviceAddr The I2C device address."""
        self._i2c = i2c
        self._deviceAddr       = deviceAddr

        #Define the default state of all config register parts
        self._os                    = 0b0
        self._mux                   = 0b000
        self._pga                   = 0b010
        self._mode                  = 0b1
        self._dr                    = 0b100
        self._compMode              = 0b0
        self._compPol               = 0b0
        self._compLat               = 0b0
        self._compQue               = 0b11

        self._adc0FSVoltage         = None
        self._adc0SamplesPerSecond  = None
        self._adc1FSVoltage         = None
        self._adc1SamplesPerSecond  = None
        self._adc2FSVoltage         = None
        self._adc2SamplesPerSecond  = None
        self._adc3FSVoltage         = None
        self._adc3SamplesPerSecond  = None


    def setADC0(self, fsVoltage, samplesPerSecond):
        """@brief set parameters for ADC0.
           @param fsVoltage The full scale voltage.
           @param samplesPerSecond The samples per second."""
        self._adc0FSVoltage = fsVoltage
        self._adc0SamplesPerSecond = samplesPerSecond

    def setADC1(self, fsVoltage, samplesPerSecond):
        """@brief set parameters for ADC1.
           @param fsVoltage The full scale voltage.
           @param samplesPerSecond The samples per second."""
        self._adc1FSVoltage = fsVoltage
        self._adc1SamplesPerSecond = samplesPerSecond

    def setADC2(self, fsVoltage, samplesPerSecond):
        """@brief set parameters for ADC2.
           @param fsVoltage The full scale voltage.
           @param samplesPerSecond The samples per second."""
        self._adc2FSVoltage = fsVoltage
        self._adc2SamplesPerSecond = samplesPerSecond

    def setADC3(self, fsVoltage, samplesPerSecond):
        """@brief set parameters for ADC3.
           @param fsVoltage The full scale voltage.
           @param samplesPerSecond The samples per second."""
        self._adc3FSVoltage = fsVoltage
        self._adc3SamplesPerSecond = samplesPerSecond

    def getADC0(self, singleEnded=True):
        """@brief Get the value from ADC0.
                  setADC0() must have been called first.
           @param singleEnded If True then single ended mode.
                              If False then differential mod is
                              selected (A0 and A1 pins)."""
        self._mux = self._getMux(0, singleEnded=singleEnded)
        self._pga = self._getPGAValue(self._adc0FSVoltage)
        self._dr = self._getDataRate(self._adc0SamplesPerSecond)
        return self._getADCValue()

    def getADC1(self, singleEnded=True):
        """@brief Get the value from ADC1.
                  setADC1() must have been called first.
           @param singleEnded If True then single ended mode.
                              If False then differential mod is
                              selected (A0 and A3 pins)."""
        self._mux = self._getMux(1, singleEnded=singleEnded)
        self._pga = self._getPGAValue(self._adc1FSVoltage)
        self._dr = self._getDataRate(self._adc1SamplesPerSecond)
        return self._getADCValue()

    def getADC2(self, singleEnded=True):
        """@brief Get the value from ADC2.
                  setADC2() must have been called first.
           @param singleEnded If True then single ended mode.
                              If False then differential mod is
                              selected (A1 and A3 pins)."""
        self._mux = self._getMux(2, singleEnded=singleEnded)
        self._pga = self._getPGAValue(self._adc2FSVoltage)
        self._dr = self._getDataRate(self._adc2SamplesPerSecond)
        return self._getADCValue()

    def getADC3(self, singleEnded=True):
        """@brief Get the value from ADC3.
                  setADC3() must have been called first.
           @param singleEnded If True then single ended mode.
                              If False then differential mod is
                              selected (A2 and A3 pins)."""
        self._mux = self._getMux(3, singleEnded=singleEnded)
        self._pga = self._getPGAValue(self._adc3FSVoltage)
        self._dr = self._getDataRate(self._adc3SamplesPerSecond)
        return self._getADCValue()

    def getSignedValue(self, adc, singleEnded=True, bitCount=16):
        """@brief Get a signed value from an ADC.
           @param adc The ADC to read (0-3).
           @param singleEnded If True read ADC in single ended mode.
           @param bitCount The number of bits read (16 or 12 for ADS1115)."""
        mask = 1<<(bitCount-1)
        if adc == 0:
            adcValue = self.getADC0(singleEnded=singleEnded)
        elif adc == 1:
            adcValue = self.getADC1(singleEnded=singleEnded)
        elif adc == 2:
            adcValue = self.getADC2(singleEnded=singleEnded)
        elif adc == 3:
            adcValue = self.getADC3(singleEnded=singleEnded)
        else:
            raise Exception("{} is an invalid ADC.".format(adc))

        #-ve value
        if adcValue&mask:
            value = -((2**bitCount)-adcValue)
        #+ve value
        else:
            value = adcValue

        return value

    def _getMux(self, adc, singleEnded):
        """@brief Get the mux register value
           @param adc 0,1,2 or 3.
                  In single ended mode the ADC is the selected ADC.
                  In non single ended mode (differential) the following inputs are selected
                  0 = AIN0 and AIN1
                  1 = AIN0 and AIN3
                  2 = AIN1 and AIN3
                  3 = AIN2 and AIN3
           @param singleEnded If True adc can be 0,1,2 or 3.
                              If False then adc can be 0 or 2."""
        if singleEnded:
            if adc == 0:
                return 0b100
            elif adc == 1:
                return 0b101
            elif adc == 2:
                return 0b110
            elif adc == 3:
                return 0b111
            else:
                raise ADS1115Error("%s adc is invalid in single ended mode" % ( str(adc)) )
        else:
            if adc == 0:
                return 0b000
            elif adc == 1:
                return 0b001
            elif adc == 2:
                return 0b010
            elif adc == 3:
                return 0b011
            else:
                raise ADS1115Error("%s adc is invalid in differential mode" % ( str(adc)) )

    def _getPGAValue(self, fsVoltage):
        """@brief Get the PGA value associated with the full scale voltage."""
        if fsVoltage == 6.144:
            return 0b000
        elif fsVoltage == 4.096:
            return 0b001
        elif fsVoltage == 2.048:
            return 0b010
        elif fsVoltage == 1.024:
            return 0b011
        elif fsVoltage == 0.512:
            return 0b100
        elif fsVoltage == 0.256:
            return 0b101
        else:
            raise ADS1115Error("%s is an invalid full scale (+/-) voltage" % ( str(fsVoltage))  )

    def _getDataRate(self, samplesPerSecond):
        """@brief Get the data rate register value
           @param samplesPerSecond The sampels per second required."""
        if samplesPerSecond == 8:
            return 0b000
        elif samplesPerSecond == 16:
            return 0b001
        elif samplesPerSecond == 32:
            return 0b010
        elif samplesPerSecond == 64:
            return 0b011
        elif samplesPerSecond == 128:
            return 0b100
        elif samplesPerSecond == 250:
            return 0b101
        elif samplesPerSecond == 475:
            return 0b110
        elif samplesPerSecond == 860:
            return 0b111
        else:
            raise ADS1115Error("%s is an invalid data rate." % ( str(samplesPerSecond))  )

    def _read16BitValue(self, register):
        """@brief Read a 16 bit value from the devide (big endian)."""
        values = self._i2c.readfrom_mem(self._deviceAddr, register, 2)
        retVal = values[0]<<8 | values[1]
        return retVal

    def _write16BitValue(self, register, value):
        """@brief write a 16 bit value to a register (big endian)."""
        byteList = []
        byteList.append( (value>>8)&0xff )
        byteList.append( value&0xff )
        self._i2c.writeto_mem(self._deviceAddr, register, bytearray(byteList))

    def _waitForConversionCompletion(self, sleepMicroSeconds=100):
        """@brief wait for a conversion to complete."""
        while True:
            cfgRegState = self._read16BitValue(ADS1115ADC.CONFIG_REG)
            if cfgRegState&(1<<ADS1115ADC.OS_CFG_REG_BIT):
                break
            #We used to spin lock here and this generated occasional
            #'IOError: I2C transaction failed.' errors
            #so we now wait for a short period of time to elapse.
            #Note that this may slow execution of i2c device access.
            sleep_us(sleepMicroSeconds)

    def _getADCValue(self):
        """@brief This sets the config and poll the device until conversion is
                  complete, then returns the converted value."""
        #Set start conversion bit
        self._os = 1

        regValue16Bit = self._os        << ADS1115ADC.OS_CFG_REG_BIT         |\
                        self._mux       << ADS1115ADC.MUX_CFG_REG_BIT        |\
                        self._pga       << ADS1115ADC.PGA_CFG_REG_BIT        |\
                        self._mode      << ADS1115ADC.MODE_CFG_REG_BIT       |\
                        self._dr        << ADS1115ADC.DR_CFG_REG_BIT         |\
                        self._compMode  << ADS1115ADC.COMP_MODE_CFG_REG_BIT  |\
                        self._compPol   << ADS1115ADC.COMP_POL_CFG_REG_BIT   |\
                        self._compLat   << ADS1115ADC.COMP_LAT_CFG_REG_BIT   |\
                        self._compQue   << ADS1115ADC.COMP_QUE_CFG_REG_BIT


        byteList = []
        byteList.append( (regValue16Bit>>8)&0xff )
        byteList.append( regValue16Bit&0xff )

        #Called in case a conversion is in progress
        self._waitForConversionCompletion()

        #Initiate a conversion
        self._write16BitValue(ADS1115ADC.CONFIG_REG, regValue16Bit)

        #Wait for the conversion to complete
        self._waitForConversionCompletion()

        #read the ADC value
        cnvValue = self._read16BitValue(ADS1115ADC.CONVERSION_REG)

        return cnvValue
