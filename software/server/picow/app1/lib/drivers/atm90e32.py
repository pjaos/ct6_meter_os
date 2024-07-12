"""
    A micropython driver for the ATM90E32 device.
    Many thanks to git@github.com:warthog9/CircuitSetup_EnergyMeter_MicroPython.git
    as this was used as a base for this implementation. 
"""
from machine import Pin, SPI
import utime
import struct
import math

class ATM90E32:
    class Register(object):
        # -------------------------- start of ATM90E32 register definition --------------------------------------------------
        
        # Convention would dictate that the register addresses are all upper case.
        # However here we keep the same case as the data sheet.
        #* STATUS REGISTERS *#
        MeterEn = 0x00          # Metering Enable
        ChannelMapI = 0x01      # Current Channel Mapping Configuration
        ChannelMapU = 0x02      # Voltage Channel Mapping Configuration
        SagPeakDetCfg = 0x05    # Sag and Peak Detector Period Configuration
        OVth = 0x06             # Over Voltage Threshold
        ZXConfig = 0x07         # Zero-Crossing Config
        SagTh = 0x08            # Voltage Sag Th
        PhaseLossTh = 0x09      # Voltage Phase Losing Th
        INWarnTh = 0x0A         # Neutral Current (Calculated) Warning Threshold
        OIth = 0x0B             # Over Current Threshold
        FreqLoTh = 0x0C         # Low Threshold for Frequency Detection
        FreqHiTh = 0x0D         # High Threshold for Frequency Detection
        PMPwrCtrl = 0x0E        # Partial Measurement Mode Power Control
        IRQ0MergeCfg = 0x0F     # IRQ0 Merge Configuration
    
        #* EMM STATUS REGISTERS *#
        SoftReset = 0x70        # Software Reset
        EMMState0 = 0x71        # EMM State 0
        EMMState1 = 0x72        # EMM State 1
        EMMIntState0 = 0x73     # EMM Interrupt Status 0
        EMMIntState1 = 0x74     # EMM Interrupt Status 1
        EMMIntEn0 = 0x75        # EMM Interrupt Enable 0
        EMMIntEn1 = 0x76        # EMM Interrupt Enable 1
        LastSPIData = 0x78      # Last Read/Write SPI Value
        CRCErrStatus = 0x79     # CRC Error Status
        CRCDigest = 0x7A        # CRC Digest
        CfgRegAccEn = 0x7F      # Configure Register Access Enable
    
        #* LOW POWER MODE REGISTERS - NOT USED *#
        DetectCtrl = 0x10
        DetectTh1 = 0x11
        DetectTh2 = 0x12
        DetectTh3 = 0x13
        PMOffsetA = 0x14
        PMOffsetB = 0x15
        PMOffsetC = 0x16
        PMPGA = 0x17
        PMIrmsA = 0x18
        PMIrmsB = 0x19
        PMIrmsC = 0x1A
        PMConfig = 0x10B
        PMAvgSamples = 0x1C
        PMIrmsLSB = 0x1D
    
        #* CONFIGURATION REGISTERS *#
        PLconstH = 0x31         # High Word of PL_Constant
        PLconstL = 0x32         # Low Word of PL_Constant
        MMode0 = 0x33           # Metering Mode Config
        MMode1 = 0x34           # PGA Gain Configuration for Current Channels
        PStartTh = 0x35         # Startup Power Th (P)
        QStartTh = 0x36         # Startup Power Th (Q)
        SStartTh = 0x37         # Startup Power Th (S)
        PPhaseTh = 0x38         # Startup Power Accum Th (P)
        QPhaseTh = 0x39         # Startup Power Accum Th (Q)
        SPhaseTh = 0x3A         # Startup Power Accum Th (S)
    
        #* CALIBRATION REGISTERS *#
        PoffsetA = 0x41         # A Line Power Offset (P)
        QoffsetA = 0x42         # A Line Power Offset (Q)
        PoffsetB = 0x43         # B Line Power Offset (P)
        QoffsetB = 0x44         # B Line Power Offset (Q)
        PoffsetC = 0x45         # C Line Power Offset (P)
        QoffsetC = 0x46         # C Line Power Offset (Q)
        PQGainA = 0x47          # A Line Calibration Gain
        PhiA = 0x48             # A Line Calibration Angle
        PQGainB = 0x49          # B Line Calibration Gain
        PhiB = 0x4A             # B Line Calibration Angle
        PQGainC = 0x4B          # C Line Calibration Gain
        PhiC = 0x4C             # C Line Calibration Angle
    
        #* FUNDAMENTAL#HARMONIC ENERGY CALIBRATION REGISTERS *#
        POffsetAF = 0x51        # A Fund Power Offset (P)
        POffsetBF = 0x52        # B Fund Power Offset (P)
        POffsetCF = 0x53        # C Fund Power Offset (P)
        PGainAF = 0x54          # A Fund Power Gain (P)
        PGainBF = 0x55          # B Fund Power Gain (P)
        PGainCF = 0x56          # C Fund Power Gain (P)
    
        #* MEASUREMENT CALIBRATION REGISTERS *#
        UgainA = 0x61           # A Voltage RMS Gain
        IgainA = 0x62           # A Current RMS Gain
        UoffsetA = 0x63         # A Voltage Offset
        IoffsetA = 0x64         # A Current Offset
        UgainB = 0x65           # B Voltage RMS Gain
        IgainB = 0x66           # B Current RMS Gain
        UoffsetB = 0x67         # B Voltage Offset
        IoffsetB = 0x68         # B Current Offset
        UgainC = 0x69           # C Voltage RMS Gain
        IgainC = 0x6A           # C Current RMS Gain
        UoffsetC = 0x6B         # C Voltage Offset
        IoffsetC = 0x6C         # C Current Offset
        IoffsetN = 0x6E         # N Current Offset
    
        #* ENERGY REGISTERS *#
        APenergyT = 0x80        # Total Forward Active
        APenergyA = 0x81        # A Forward Active
        APenergyB = 0x82        # B Forward Active
        APenergyC = 0x83        # C Forward Active
        ANenergyT = 0x84        # Total Reverse Active
        ANenergyA = 0x85        # A Reverse Active
        ANenergyB = 0x86        # B Reverse Active
        ANenergyC = 0x87        # C Reverse Active
        RPenergyT = 0x88        # Total Forward Reactive
        RPenergyA = 0x89        # A Forward Reactive
        RPenergyB = 0x8A        # B Forward Reactive
        RPenergyC = 0x8B        # C Forward Reactive
        RNenergyT = 0x8C        # Total Reverse Reactive
        RNenergyA = 0x8D        # A Reverse Reactive
        RNenergyB = 0x8E        # B Reverse Reactive
        RNenergyC = 0x8F        # C Reverse Reactive
    
        SAenergyT = 0x90        # Total Apparent Energy
        SenergyA = 0x91         # A Apparent Energy
        SenergyB = 0x92         # B Apparent Energy
        SenergyC = 0x93         # C Apparent Energy
    
    
        #* FUNDAMENTAL # HARMONIC ENERGY REGISTERS *#
        APenergyTF = 0xA0       # Total Forward Fund. Energy
        APenergyAF = 0xA1       # A Forward Fund. Energy
        APenergyBF = 0xA2       # B Forward Fund. Energy
        APenergyCF = 0xA3       # C Forward Fund. Energy
        ANenergyTF = 0xA4       # Total Reverse Fund Energy
        ANenergyAF = 0xA5       # A Reverse Fund. Energy
        ANenergyBF = 0xA6       # B Reverse Fund. Energy
        ANenergyCF = 0xA7       # C Reverse Fund. Energy
        APenergyTH = 0xA8       # Total Forward Harm. Energy
        APenergyAH = 0xA9       # A Forward Harm. Energy
        APenergyBH = 0xAA       # B Forward Harm. Energy
        APenergyCH = 0xAB       # C Forward Harm. Energy
        ANenergyTH = 0xAC       # Total Reverse Harm. Energy
        ANenergyAH = 0xAD       # A Reverse Harm. Energy
        ANenergyBH = 0xAE       # B Reverse Harm. Energy
        ANenergyCH = 0xAF       # C Reverse Harm. Energy
    
        #* POWER & P.F. REGISTERS *#
        PmeanT = 0xB0           # Total Mean Power (P)
        PmeanA = 0xB1           # A Mean Power (P)
        PmeanB = 0xB2           # B Mean Power (P)
        PmeanC = 0xB3           # C Mean Power (P)
        QmeanT = 0xB4           # Total Mean Power (Q)
        QmeanA = 0xB5           # A Mean Power (Q)
        QmeanB = 0xB6           # B Mean Power (Q)
        QmeanC = 0xB7           # C Mean Power (Q)
        SAmeanT = 0xB8          # Total Mean Power (S)
        SmeanA = 0xB9           # A Mean Power (S)
        SmeanB = 0xBA           # B Mean Power (S)
        SmeanC = 0xBB           # C Mean Power (S)
        PFmeanT = 0xBC          # Mean Power Factor
        PFmeanA = 0xBD          # A Power Factor
        PFmeanB = 0xBE          # B Power Factor
        PFmeanC = 0xBF          # C Power Factor
    
        PmeanTLSB = 0xC0        # Lower Word (Tot. Act. Power)
        PmeanALSB = 0xC1        # Lower Word (A Act. Power)
        PmeanBLSB = 0xC2        # Lower Word (B Act. Power)
        PmeanCLSB = 0xC3        # Lower Word (C Act. Power)
        QmeanTLSB = 0xC4        # Lower Word (Tot. React. Power)
        QmeanALSB = 0xC5        # Lower Word (A React. Power)
        QmeanBLSB = 0xC6        # Lower Word (B React. Power)
        QmeanCLSB = 0xC7        # Lower Word (C React. Power)
        SAmeanTLSB = 0xC8       # Lower Word (Tot. App. Power)
        SmeanALSB = 0xC9        # Lower Word (A App. Power)
        SmeanBLSB = 0xCA        # Lower Word (B App. Power)
        SmeanCLSB = 0xCB        # Lower Word (C App. Power)
    
        #* FUND#HARM POWER & V#I RMS REGISTERS *#
        PmeanTF = 0xD0          # Total Active Fund. Power
        PmeanAF = 0xD1          # A Active Fund. Power
        PmeanBF = 0xD2          # B Active Fund. Power
        PmeanCF = 0xD3          # C Active Fund. Power
        PmeanTH = 0xD4          # Total Active Harm. Power
        PmeanAH = 0xD5          # A Active Harm. Power
        PmeanBH = 0xD6          # B Active Harm. Power
        PmeanCH = 0xD7          # C Active Harm. Power
        UrmsA = 0xD9            # A RMS Voltage
        UrmsB = 0xDA            # B RMS Voltage
        UrmsC = 0xDB            # C RMS Voltage
        IrmsA = 0xDD            # A RMS Current
        IrmsB = 0xDE            # B RMS Current
        IrmsC = 0xDF            # C RMS Current
        IrmsN = 0xDC            # Calculated N RMS Current
    
        PmeanTFLSB = 0xE0       # Lower Word (Tot. Act. Fund. Power)
        PmeanAFLSB = 0xE1       # Lower Word (A Act. Fund. Power)
        PmeanBFLSB = 0xE2       # Lower Word (B Act. Fund. Power)
        PmeanCFLSB = 0xE3       # Lower Word (C Act. Fund. Power)
        PmeanTHLSB = 0xE4       # Lower Word (Tot. Act. Harm. Power)
        PmeanAHLSB = 0xE5       # Lower Word (A Act. Harm. Power)
        PmeanBHLSB = 0xE6       # Lower Word (B Act. Harm. Power)
        PmeanCHLSB = 0xE7       # Lower Word (C Act. Harm. Power)
        # 0xE8                  ## Reserved Register
        UrmsALSB = 0xE9         # Lower Word (A RMS Voltage)
        UrmsBLSB = 0xEA         # Lower Word (B RMS Voltage)
        UrmsCLSB = 0xEB         # Lower Word (C RMS Voltage)
        # 0xEC                  ## Reserved Register
        IrmsALSB = 0xED         # Lower Word (A RMS Current)
        IrmsBLSB = 0xEE         # Lower Word (B RMS Current)
        IrmsCLSB = 0xEF         # Lower Word (C RMS Current)
    
        #* PEAK, FREQUENCY, ANGLE & TEMPTEMP REGISTERS*#
        UPeakA = 0xF1           # A Voltage Peak
        UPeakB = 0xF2           # B Voltage Peak
        UPeakC = 0xF3           # C Voltage Peak
        # 0xF4        ## Reserved Register
        IPeakA = 0xF5           # A Current Peak
        IPeakB = 0xF6           # B Current Peak
        IPeakC = 0xF7           # C Current Peak
        Freq = 0xF8             # Frequency
        PAngleA = 0xF9          # A Mean Phase Angle
        PAngleB = 0xFA          # B Mean Phase Angle
        PAngleC = 0xFB          # C Mean Phase Angle
        Temp = 0xFC             # Measured Temperature
        UangleA = 0xFD          # A Voltage Phase Angle
        UangleB = 0xFE          # B Voltage Phase Angle
        UangleC = 0xFF          # C Voltage Phase Angle
        
        # -------------------------- end of register definition --------------------------------------------------
    
    SPI_WRITE = 0
    SPI_READ = 1
    
    LINE_FREQ_50HZ = 50 # Europe and others line freq.
    LINE_FREQ_60HZ = 60 # North America and others line freq.
    VALID_LINE_FREQS = (LINE_FREQ_50HZ, LINE_FREQ_60HZ)
    
    DEFAULT_VOLTAGE_GAIN = 10734
    DEFAULT_CURRENT_GAIN = 10734
    
    @staticmethod
    def SPIFactory(sckPin, mosiPin, misoPin, spiBus=0):
        """@brief Return an SPI instance to be used to communicate with the ATM90E32 device.
           @param sckPin The SPI clock GPIO pin number (integer value).
           @param mosiPin The SPI MOSI GPIO pin number (integer value).
           @param misoPin The SPI MISO GPIO pin number (integer value).
           @param spiBus The SPI bus used (default=0).
           @return An SPI instance suitable to be used to communicate with the ATM90E32 device."""
        _sckPin  = Pin(2)
        _mosiPin = Pin(3)
        _misoPin = Pin(4)
        return SPI(spiBus, baudrate=200000, polarity=1, phase=1, bits=8, sck=_sckPin, mosi=_mosiPin, miso=_misoPin)

    @staticmethod
    def Floor(value):
        """@brief Round a number to the nearest integer value.
           @param value The value to be rounded.
           @return The rounded value."""
        if value - math.floor(value) < 0.5:
            return math.floor(value)
        return math.ceil(value)

    @staticmethod
    def FromSigned(value, bitCount) :
        """@brief Convert from a signed number to an unsigned number.
           @param value The signed value to convert.
           @param bitCount The number of bits in the conversion."""
        return value & (2**bitCount - 1)

    @staticmethod
    def ToSigned(value, bitCount):
        """@brief convert an int value to a signed number.
           @param value The value to convert.
           @param bitCount The number of bits in the conversion."""
        sValue = value
        if value&(1<<bitCount-1):
            sValue=-((1<<bitCount)-value)
        return sValue

    def __init__(self,
                 spiLink,
                 csGPIOPin,
                 lineFreq,
                 pgaGain,
                 uGain1,
                 uGain2,
                 uGain3,
                 iGain1,
                 iGain2,
                 iGain3,
                 uOffset1=DEFAULT_VOLTAGE_GAIN,
                 uOffset2=DEFAULT_VOLTAGE_GAIN,
                 uOffset3=DEFAULT_VOLTAGE_GAIN,
                 iOffset1=DEFAULT_CURRENT_GAIN,
                 iOffset2=DEFAULT_CURRENT_GAIN,
                 iOffset3=DEFAULT_CURRENT_GAIN,
                 allVoltageFromPort1=True):
        """@brief ATM90E32 constructor.
            @param spiLink The SPI instance for the SPI bus connected to the ATM90E32 device.
            @param csGPIOPin The GPIO pin used as a chip select fort he ATM90E32 device (integer value).
            @param lineFreq The line frequency. Either 50 or 60 (Hz).
            @param pgaGain The amplifier gain for current 1,2 or 4.
            @param uGain1 The voltage gain for port 1 (a 16 bit unsigned value).
            @param uGain2 The voltage gain for port 2 (a 16 bit unsigned value).
            @param uGain3 The voltage gain for port 3 (a 16 bit unsigned value).
            @param iGain1 The current gain for port 1 (a 16 bit unsigned value).
            @param iGain1 The current gain for port 2 (a 16 bit unsigned value).
            @param iGain1 The current gain for port 3 (a 16 bit unsigned value).
            @param uOffset1 The voltage offset register value for port 1.
            @param uOffset2 The voltage offset register value for port 2.
            @param uOffset3 The voltage offset register value for port 3.
            @param iOffset1 The current offset register value for port 1.
            @param iOffset2 The current offset register value for port 2.
            @param iOffset3 The current offset register value for port 3.
            @param allVoltageFromPort1 If True then all measured voltages will be read from ATM90E32 port 1.
                                       If False then voltages are read from each port of the ATM90E32 device."""
        self._spiBus = spiLink
        self._csGPIOPin = csGPIOPin
        self.csPin = self._csGPIOPin
        if lineFreq not in ATM90E32.VALID_LINE_FREQS:
            raise Exception("{} Hz is an invalid line frequency ({} are valid)".format(lineFreq, ",".join(ATM90E32.VALID_LINE_FREQS) ) )
        self._lineFreq = lineFreq
        self._lineFreqReg = None
        if pgaGain == 1:
            self._pgaGain = 0x0000
        if pgaGain == 2:
            self._pgaGain = 0x0015
        if pgaGain == 4:
            self._pgaGain = 0x002A
        else:
            raise Exception(f"{pgaGain} is an invalid PGA gain (1,2 or 4 rare valid)")
        self._uGain1 = uGain1
        self._uGain2 = uGain2
        self._uGain3 = uGain3
        self._iGain1 = iGain1
        self._iGain2 = iGain2
        self._iGain3 = iGain3
        self._uOffset1 = uOffset1
        self._uOffset2 = uOffset2
        self._uOffset3 = uOffset3
        self._iOffset1 = iOffset1
        self._iOffset2 = iOffset2
        self._iOffset3 = iOffset3
        self._allVoltageFromPort1 = allVoltageFromPort1
        
        
        self._wattsGateValue = 0.4  # When reading power and the measured power is below this
                                    # value (in watts) we return a power of 0.0

        self._init_config()
        
        # Chip requires a bit less than 200mS after init for readings to stabilize
        utime.sleep_ms(200)

    @property
    def wattsGateValue(self):
        """@brief Get the power gate value.
           @return The active power gate value in watts."""
        return self._wattsGateValue
    
    @wattsGateValue.setter
    def wattsGateValue(self, wattsGateValue):
        """@brief Set the csPin. This is useful when using one instance of ATM90E32 for different devices.
            @param wattsGateValue The power gate value in watts."""
        self._wattsGateValue = wattsGateValue
        
    @property
    def csPin(self):
        """@brief Get the csPin.
           @return The csPin (integer value)."""
        return self._csGPIOPin
    
    @csPin.setter
    def csPin(self, csGPIOPin):
        """@brief Set the csPin. This is useful when using one instance of ATM90E32 for different devices.
            @param csGPIOPin The GPIO pin used as a chip select fort he ATM90E32 device (integer value)."""
        self._csPin = Pin(csGPIOPin, Pin.OUT, value=True) # Set the CS pin to inactive state in GPIO pin initialisation.
        self._csGPIOPin = csGPIOPin
           
    def _spi_raw(self, rw, address, value):
        """@brief Read/write 16 bits of data from/to an SPI register.
           @param rw ATM90E32.SPI_WRITE or ATM90E32.SPI_READ
           @param address The ATM90E32 register address.
           @param value The value (16 bits) to write to the register.
           @return 0 on success
                   -1 If rw is not ATM90E32.SPI_WRITE or ATM90E32.SPI_READ.
                   -2 If an invalid 16 bit address (0x0000 - 0xffff).
                   -3 If an invalid 16 bit value (0x0000 - 0xffff)."""
        if rw != ATM90E32.SPI_READ and rw != ATM90E32.SPI_WRITE:
            return -1 # Check that 'rw' is a valid value
        if address < 0 or address > 0xFFFF:
            return -2 # Check that 'address' is a valid value
        if value < 0 or value > 0xFFFF:
            return -3 # Check that 'value' is a valid value

        address |= rw << 15 # Set RW bit flag

        self._csPin.off() # Enable the chip select
        utime.sleep_us(10)

        self._spiBus.write(struct.pack('>H', address)) # Send the address

        if (rw == ATM90E32.SPI_READ):
            result = struct.unpack('>H', self._spiBus.read(2))[0]
        else:
            self._spiBus.write(struct.pack('>H', value))
            result = 0

        self._csPin.on() # Disable chip select, we're done with this transaction

        return result

    def _readRegister(self, address):
        """@brief Read an unsigned 16bit register.
           @param address The register address.
           @return An unsigned 16 bit value."""
        return self._spi_raw(ATM90E32.SPI_READ, address, 0xFFFF)
        
    def _readRegister2C(self, address):
        """@brief Read a signed 16bit register.
           @param address The register address.
           @return A signed 16 bit value."""
        value = self._spi_raw(ATM90E32.SPI_READ, address, 0xFFFF)
        return value - int((value << 1) & 2**16)

    def _writeRegister(self, address, value):
        """@brief Write a 16bit register.
           @param address The register address.
           @param value The register value.
           @return 0 on success
                   -1 If rw is not ATM90E32.SPI_WRITE or ATM90E32.SPI_READ.
                   -2 If an invalid 16 bit address (0x0000 - 0xffff).
                   -3 If an invalid 16 bit value (0x0000 - 0xffff)."""
        return self._spi_raw(ATM90E32.SPI_WRITE, address, value)

    def _readLongRegister2C(self, address_high, address_low):
        """@brief Read a signed 32bit register.
           @param address_high The high part (16 bit) of the register address.
           @param address_low The low part (16 bit) of the register address.
           @return A signed 32 bit value."""
        value_h = self._spi_raw(ATM90E32.SPI_READ, address_high, 0xFFFF)
        value_l = self._spi_raw(ATM90E32.SPI_READ, address_low, 0xFFFF)
        value = (value_h << 16) | value_l
        return value - int((value << 1) & 2**32)
    
    def _init_config(self):
        """@brief Initialise the ATM90e32 registers."""
        if self._lineFreq == ATM90E32.LINE_FREQ_50HZ:
            self._lineFreqReg = 135
            FreqHiThresh = 51 * 100
            FreqLoThresh = 49 * 100
            sagV = 190
                        
        else:
            self._lineFreqReg = 4231 # North America line frequency
            FreqHiThresh = 61 * 100
            FreqLoThresh = 59 * 100
            sagV = 90
                        
        fvSagTh = (sagV * 100 * 1.41421356) / (2 * self._uGain1 / 32768) # Voltage Sag threshhold in RMS (1.41421356)
        vSagTh = ATM90E32.Floor(fvSagTh)                               # convert to int for sending to the atm90e32.

        self._writeRegister(ATM90E32.Register.SoftReset, 0x789A)       # Perform soft reset
        self._writeRegister(ATM90E32.Register.CfgRegAccEn, 0x55AA)     # enable register config access
        self._writeRegister(ATM90E32.Register.MeterEn, 0x0001)         # Enable Metering

        if self._allVoltageFromPort1:
            self._writeRegister(ATM90E32.Register.ChannelMapU, 0x0444)     # Voltage measurements all to come from V1P/V1N. By default they are read from each port.

        self._writeRegister(ATM90E32.Register.SagTh, vSagTh)           # Voltage sag threshold
        self._writeRegister(ATM90E32.Register.FreqHiTh, FreqHiThresh)  # High frequency threshold - 61.00Hz
        self._writeRegister(ATM90E32.Register.FreqLoTh, FreqLoThresh)  # Lo frequency threshold - 59.00Hz
        
        self._writeRegister(ATM90E32.Register.EMMIntEn0, 0xB76F)       # Enable interrupts
        self._writeRegister(ATM90E32.Register.EMMIntEn1, 0xDDFD)       # Enable interrupts
        self._writeRegister(ATM90E32.Register.EMMIntState0, 0x0001)    # Clear interrupt flags
        self._writeRegister(ATM90E32.Register.EMMIntState1, 0x0001)    # Clear interrupt flags
        self._writeRegister(ATM90E32.Register.ZXConfig, 0x0A55)        # ZX2, ZX1, ZX0 pin config

        # Set metering config values (CONFIG)
        self._writeRegister(ATM90E32.Register.PLconstH, 0x0861)        # PL Constant MSB (default) - Meter Constant = 3200 - PL Constant = 140625000
        self._writeRegister(ATM90E32.Register.PLconstL, 0xC468)        # PL Constant LSB (default) - this is 4C68 in the application note, which is incorrect
        self._writeRegister(ATM90E32.Register.MMode0, self._lineFreqReg)    # Mode Config (frequency set in main program)
        self._writeRegister(ATM90E32.Register.MMode1, self._pgaGain)    # PGA Gain Configuration for Current Channels - 0x002A (x4) # 0x0015 (x2) # 0x0000 (1x)
        self._writeRegister(ATM90E32.Register.PStartTh, 0x0AFC)        # Active Startup Power Threshold - 50% of startup current = 0.9/0.00032 = 2812.5
        self._writeRegister(ATM90E32.Register.QStartTh, 0x0AEC)        # Reactive Startup Power Threshold
        self._writeRegister(ATM90E32.Register.SStartTh, 0x0000)        # Apparent Startup Power Threshold
        self._writeRegister(ATM90E32.Register.PPhaseTh, 0x00BC)        # Active Phase Threshold = 10% of startup current = 0.06/0.00032 = 187.5
        self._writeRegister(ATM90E32.Register.QPhaseTh, 0x0000)        # Reactive Phase Threshold
        self._writeRegister(ATM90E32.Register.SPhaseTh, 0x0000)        # Apparent  Phase Threshold

        # Set metering calibration values (CALIBRATION)
        self._writeRegister(ATM90E32.Register.PQGainA, 0x0000)        # Line calibration gain
        self._writeRegister(ATM90E32.Register.PhiA, 0x0000)            # Line calibration angle
        self._writeRegister(ATM90E32.Register.PQGainB, 0x0000)        # Line calibration gain
        self._writeRegister(ATM90E32.Register.PhiB, 0x0000)            # Line calibration angle
        self._writeRegister(ATM90E32.Register.PQGainC, 0x0000)        # Line calibration gain
        self._writeRegister(ATM90E32.Register.PhiC, 0x0000)            # Line calibration angle
        
        self._writeRegister(ATM90E32.Register.PoffsetA, 0x0000)        # A line active power offset
        self._writeRegister(ATM90E32.Register.QoffsetA, 0x0000)        # A line reactive power offset
        self._writeRegister(ATM90E32.Register.PoffsetB, 0x0000)        # B line active power offset
        self._writeRegister(ATM90E32.Register.QoffsetB, 0x0000)        # B line reactive power offset
        self._writeRegister(ATM90E32.Register.PoffsetC, 0x0000)        # C line active power offset
        self._writeRegister(ATM90E32.Register.QoffsetC, 0x0000)        # C line reactive power offset

        # Set metering calibration values (HARMONIC)
        self._writeRegister(ATM90E32.Register.POffsetAF, 0x0000)        # A Fund. active power offset
        self._writeRegister(ATM90E32.Register.POffsetBF, 0x0000)        # B Fund. active power offset
        self._writeRegister(ATM90E32.Register.POffsetCF, 0x0000)        # C Fund. active power offset 
        self._writeRegister(ATM90E32.Register.PGainAF, 0x0000)        # A Fund. active power gain
        self._writeRegister(ATM90E32.Register.PGainBF, 0x0000)        # B Fund. active power gain
        self._writeRegister(ATM90E32.Register.PGainCF, 0x0000)        # C Fund. active power gain

        # Set measurement calibration values (ADJUST)
        self._writeRegister(ATM90E32.Register.UgainA, int(self._uGain1))       # A Voltage rms gain
        self._writeRegister(ATM90E32.Register.IgainA, int(self._iGain1))      # A line current gain
        self._writeRegister(ATM90E32.Register.UoffsetA, int(self._uOffset1))  # A Voltage offset
        self._writeRegister(ATM90E32.Register.IoffsetA, int(self._iOffset1))  # A line current offset
        
        self._writeRegister(ATM90E32.Register.UgainB, int(self._uGain2))       # B Voltage rms gain
        self._writeRegister(ATM90E32.Register.IgainB, int(self._iGain2))      # B line current gain
        self._writeRegister(ATM90E32.Register.UoffsetB, int(self._uOffset2))  # B Voltage offset
        self._writeRegister(ATM90E32.Register.IoffsetB, int(self._iOffset2))  # B line current offset
        
        self._writeRegister(ATM90E32.Register.UgainC, int(self._uGain3))       # C Voltage rms gain
        self._writeRegister(ATM90E32.Register.IgainC, int(self._iGain3))      # C line current gain
        self._writeRegister(ATM90E32.Register.UoffsetC, int(self._uOffset3))  # C Voltage offset
        self._writeRegister(ATM90E32.Register.IoffsetC, int(self._iOffset3))  # C line current offset

        self._writeRegister(ATM90E32.Register.CfgRegAccEn, 0x0000)    # end configuration
        
    # The properties do not conform to camel case because we keep the same case as
    # the registers in the data sheet.
    @property
    def LastSPIData(self):
        """@return Last Read/Write SPI Value"""
        reading =  self._readRegister(ATM90E32.Register.LastSPIData)
        return reading
    
    @property
    def EMMIntState0(self):
        """@return EMM Interrupt Status 0"""
        reading = self._readRegister(ATM90E32.Register.EMMIntState0)
        return reading

    @property
    def EMMIntState1(self):
        """@return EMM Interrupt Status 1"""
        reading = self._readRegister(ATM90E32.Register.EMMIntState1)
        return reading

    @property
    def EMMState0(self):
        """@return EMM State 0"""
        reading = self._readRegister(ATM90E32.Register.EMMState0)
        return reading

    @property
    def EMMState1(self):
        """@return EMM State 1"""
        reading = self._readRegister(ATM90E32.Register.EMMState1)
        return reading

    @property
    def UrmsA(self):
        """@return Channel A Voltage RMS"""
        reading = self._readRegister(ATM90E32.Register.UrmsA)
        return reading / 100

    @property
    def UrmsB(self):
        """@return Channel B Voltage RMS"""
        reading = self._readRegister(ATM90E32.Register.UrmsB)
        return reading / 100.0

    @property
    def UrmsC(self):
        """@return Channel C Voltage RMS"""
        reading = self._readRegister(ATM90E32.Register.UrmsC)
        return reading / 100.0

    @property
    def UPeakA(self):
        """@return Channel A Voltage Peak"""
        reading = self._readRegister2C(ATM90E32.Register.UPeakA)
        return reading * (self._uGain1 / 819200.0) # UPeak = UPeakRegValue x (Ugain / (100 x 2^13))

    @property
    def UPeakB(self):
        """@return Channel B Voltage Peak"""
        reading = self._readRegister2C(ATM90E32.Register.UPeakB)
        return reading * (self._uGain2 / 819200.0) # UPeak = UPeakRegValue x (Ugain / (100 x 2^13))

    @property
    def UPeakC(self):
        """@return Channel C Voltage Peak"""
        reading = self._readRegister2C(ATM90E32.Register.UPeakC)
        return reading * (self._uGain3 / 819200.0) # UPeak = UPeakRegValue x (Ugain / (100 x 2^13))

    @property
    def IrmsN(self):
        """@return N Line Calculated Current RMS"""
        reading = self._readRegister(ATM90E32.Register.IrmsN)
        return reading / 1000.0

    @property
    def IrmsA(self):
        """@return Phase A Current RMS"""
        reading = self._readRegister(ATM90E32.Register.IrmsA)
        return reading / 1000.0

    @property
    def IrmsB(self):
        """@return Phase B Current RMS"""
        reading = self._readRegister(ATM90E32.Register.IrmsB)
        return reading / 1000.0
    #####################################################################################
    @property
    def IrmsC(self):
        """@return Phase C Current RMS"""
        reading = self._readRegister(ATM90E32.Register.IrmsC)
        return reading / 1000.0

    @property
    def IPeakA(self):
        """@return Channel A Current Peak"""
        reading = self._readRegister2C(ATM90E32.Register.IPeakA)
        return reading * (self._iGain1 / 8192000.0) # IPeak = IPeakRegValue x (Igain / (1000 x 2^13))

    @property
    def IPeakB(self):
        """@return Channel B Current Peak"""
        reading = self._readRegister2C(ATM90E32.Register.IPeakB)
        return reading * (self._iGain2 / 8192000.0) # IPeak = IPeakRegValue x (Igain / (1000 x 2^13))

    @property
    def IPeakC(self):
        """@return Channel C Current Peak"""
        reading = self._readRegister2C(ATM90E32.Register.IPeakC)
        return reading * (self._iGain3 / 8192000.0) # IPeak = IPeakRegValue x (Igain / (1000 x 2^13))

    @property
    def Freq(self):
        """@return Frequency"""
        reading = self._readRegister(ATM90E32.Register.Freq)
        return reading / 100.0

    @property
    def PmeanT(self):
        """@return Total (All-phase-sum) Active Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.PmeanT, ATM90E32.Register.PmeanTLSB)
        return reading * 0.00032

    def _getGatedPower(self, watts):
        """@return The gated power value. If the measured power is below the 
                   gated power then 0.0 is returned."""
        if watts > self._wattsGateValue or watts < -self._wattsGateValue:
            return watts
        else:
            return 0.0
        
    @property
    def PmeanA(self):
        """@return Channel A Active Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.PmeanA, ATM90E32.Register.PmeanALSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def PmeanB(self):
        """@return Channel B Active Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.PmeanB, ATM90E32.Register.PmeanBLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def PmeanC(self):
        """@return Channel C Active Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.PmeanC, ATM90E32.Register.PmeanCLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)
    
    @property
    def QmeanT(self):
        """@return Lower Word of Total (All-phase-sum) Reactive Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.QmeanT, ATM90E32.Register.QmeanTLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def QmeanA(self):
        """@return Channel A Lower Word of Total (All-phase-sum) Reactive Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.QmeanA, ATM90E32.Register.QmeanALSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)
    
    @property
    def QmeanB(self):
        """@return Channel B Lower Word of Total (All-phase-sum) Reactive Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.QmeanB, ATM90E32.Register.QmeanBLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def QmeanC(self):
        """@return Channel B Lower Word of Total (All-phase-sum) Reactive Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.QmeanC, ATM90E32.Register.QmeanCLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def SAmeanT(self):
        """@return Lower Word of Total (Arithmetic Sum) Apparent Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.SAmeanT, ATM90E32.Register.SAmeanTLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)
    
    @property
    def SmeanA(self):
        """@return Lower Word of Phase A Apparent Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.SmeanA, ATM90E32.Register.SmeanALSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def SmeanB(self):
        """@return Lower Word of Phase B Apparent Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.SmeanB, ATM90E32.Register.SmeanBLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def SmeanC(self):
        """@return Lower Word of Phase C Apparent Power"""
        reading = self._readLongRegister2C(ATM90E32.Register.SmeanC, ATM90E32.Register.SmeanCLSB)
        watts = reading * 0.00032
        return self._getGatedPower(watts)

    @property
    def PFmeanT(self):
        """@return Total Power Factor"""
        reading = self._readRegister2C(ATM90E32.Register.PFmeanT)
        return reading * 0.001

    @property
    def PFmeanA(self):
        """@return Phase A Power Factor"""
        reading = self._readRegister2C(ATM90E32.Register.PFmeanA)
        return reading * 0.001

    @property
    def PFmeanB(self):
        """@return Phase B Power Factor"""
        reading = self._readRegister2C(ATM90E32.Register.PFmeanB)
        return reading * 0.001

    @property
    def PFmeanC(self):
        """@return Phase C Power Factor"""
        reading = self._readRegister2C(ATM90E32.Register.PFmeanC)
        return reading * 0.001

    @property
    def Temp(self):
        """@return Measured Temperature. This is the junction temperature of the device."""
        return self._readRegister2C(ATM90E32.Register.Temp)

"""
import sys

# Example code
spiClkPin = 2
spiMOSIPin = 3
spiMISOPin = 4
spi = ATM90E32.SPIFactory(spiClkPin, spiMOSIPin, spiMISOPin)
csPin = 5
csPin = 22
lineFreqHz = 50
pgaGain = 4
voltGain=49871
currentGain = 11202
chnlACurrentGain = currentGain
chnlBCurrentGain = currentGain
chnlCCurrentGain = currentGain


# CALIBRATE THE VOLTAGE OFFSET REGISTER
voltageOffset=0
offsetDelta=1000
while True:
    atm90e32 = ATM90E32(spi,
                        csPin,
                        lineFreqHz,
                        pgaGain,
                        voltGain,
                        voltGain,
                        voltGain,
                        chnlACurrentGain,
                        chnlBCurrentGain,
                        chnlCCurrentGain,
                        uOffset1=ATM90E32.FromSigned(voltageOffset,16),
                        iOffset1=0x0000,
                        iOffset2=0x0000,
                        iOffset3=0x0000)
    
    volts = atm90e32.UrmsA
    print(f"volts={volts}")
    if volts > 0:
        voltageOffset=voltageOffset-offsetDelta
    elif volts < 0:
        voltageOffset=voltageOffset-offsetDelta
    elif volts == 0.0:
        break
    print(f"voltageOffset={voltageOffset}")
    
print("!!! VOLTAGE OFFSET CALIBRATION !!!")
print(f"volts = {volts}")
VOffsetReg = ATM90E32.FromSigned(voltageOffset,16)
print(f"VOffsetReg = {VOffsetReg:04x}")

# CALIBRATE THE CURRENT (A) OFFSET REGISTER
ampsOffset=0
offsetDelta=1000
while True:
    atm90e32 = ATM90E32(spi,
                        csPin,
                        lineFreqHz,
                        pgaGain,
                        voltGain,
                        voltGain,
                        voltGain,
                        chnlACurrentGain,
                        chnlBCurrentGain,
                        chnlCCurrentGain,
                        uOffset1=0x0000,
                        iOffset1=ATM90E32.FromSigned(ampsOffset,16),
                        iOffset2=0x0000,
                        iOffset3=0x0000)
    amps = atm90e32.IrmsA
    print(f"amps={amps}")
    if amps > 0:
        ampsOffset=ampsOffset-offsetDelta
    elif amps < 0:
        ampsOffset=ampsOffset-offsetDelta
    elif amps == 0.0:
        break
    print(f"ampsOffset={ampsOffset}")
    
print("!!! AMPS (A) OFFSET CALIBRATION !!!")
print(f"amps = {amps}")
iAOffsetReg = ATM90E32.FromSigned(ampsOffset,16)
print(f"iAOffsetReg = {iAOffsetReg:04x}")


# READ VOLTAG/CURRENT/POWER
atm90e32 = ATM90E32(spi,
                    csPin,
                    lineFreqHz,
                    pgaGain,
                    voltGain,
                    voltGain,
                    voltGain,
                    chnlACurrentGain,
                    chnlBCurrentGain,
                    chnlCCurrentGain,
                    uOffset1=VOffsetReg,
                    iOffset1=iAOffsetReg,
                    iOffset2=0x0000,
                    iOffset3=0x0000)

while True:
    
    aa = atm90e32.IrmsA
    va = atm90e32.UrmsA
    apa = atm90e32.PmeanA
    pfa = atm90e32.PFmeanA
    
    ab = atm90e32.IrmsB
    vb = atm90e32.UrmsB
    apb = atm90e32.PmeanB
    pfb = atm90e32.PFmeanB
    
    ac = atm90e32.IrmsC
    vc = atm90e32.UrmsC
    apc = atm90e32.PmeanC
    pfc = atm90e32.PFmeanC
    
    ct = atm90e32.Temp
    
    print(f"A: a={aa}, v={va}, ap={apa}, pf={pfa}")
    print(f"B: a={ab}, v={vb}, ap={apb}, pf={pfb}")
    print(f"C: a={ac}, v={vc}, ap={apc}, pf={pfc}") 
    print(f"core Temp = {ct}")
   
    utime.sleep_ms(250)

"""
