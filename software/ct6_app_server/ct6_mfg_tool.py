#!/usr/bin/env python3

import os
import sys
import argparse
import requests
import getpass
import shutil
import serial
import json
import traceback
import threading
import tempfile
import string

from   retry import retry
from   queue import Queue
from   time import sleep, strftime, localtime, time

from   p3lib.uio import UIO
from   p3lib.helper import logTraceBack
from   p3lib.ate import TestCaseBase

from   ct6_tool import CT6Base, YDevManager

class FactorySetup(CT6Base):
    """@brief Allow the user to setup an calibrate a CT6 device."""

    SET_CONFIG_CMD              = "/set_config"
    CS0_VOLTAGE_OFFSET          = "CS0_VOLTAGE_OFFSET"
    CS4_VOLTAGE_OFFSET          = "CS4_VOLTAGE_OFFSET"
    VRMS                        = "VRMS"

    CT6_BOARD_ASSY_NUMBER_STR   = "ASY0398"
    CT6_BOARD_ASSY_NUMBER       = 398
    CT6_SERIAL_NUMBER_PREFIX    = "SN"
    TEMPERATURE_RESULT          = "CT6_BOARD_TEMPERATURE"
    SN_KEY                      = "SN"  
    LAST_UUT_CFG_FILE           = ".ct6_mfg_tool_last_uut.cfg"
    RPI_BOOT_BTN_DWN_FILE_LIST  = ["index.htm", "info_uf2.txt"]
    PICO_FLASH_PATHLIST         = ("../picow/tools/picow_flash_images/", "picow_flash_images/") 
    
    # We hard code the log path so that the user does not have the option to move them.
    LOG_PATH                    = "test_logs"
    
    @staticmethod
    def FromSigned(value, bitCount) :
        """@brief Convert from a signed number to an unsigned number.
           @param value The signed value to convert.
           @param bitCount The number of bits in the conversion."""
        return int(value & (2**bitCount - 1))
    
    @staticmethod
    def GetTSString():
        """@return the default timestamp string. Logfiles include the timestamp."""
        timeStamp=strftime("%Y%m%d%H%M%S", localtime()).lower()
        return timeStamp

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        super().__init__(uio, options)
        
        self._assyNumber                    = None
        self._boardVersion                  = None
        self._serialNumber                  = None
        self._username                      = getpass.getuser()
        self._logPath                       = os.path.join(os.path.expanduser('~'), FactorySetup.LOG_PATH)
        self._ser                           = None
        self._uioLogFile                    = None
        self._serialPort                    = None
        self._lineFreqHz                    = 50
        self._serialLoggingThread           = None
        self._serialLoggingThreadRunning    = None  
    
        if not os.path.isfile(FactorySetup.HOUSE_WIFI_CFG_FILE):
            self._handleHouseWiFiConfigFileNotFound()
            
        if self._options.ac60hz:
            self._lineFreqHz   = 60
            
        # If the user supplied the IP address of the CT6 unit on the cmd line then 
        # read the assy and serial number details from the unit.
        if self._options.address:
            self.setIPAddress(self._options.address)
            self._readAssyDetails()
            
    def _readAssyDetails(self):
        """@brief Read the assembly details from the unit."""
        fileContents = self._getFileContentsOverWifi(FactorySetup.CT6_MACHINE_CONFIG_FILE, self._ipAddress)
        machineCfgDict = json.loads(fileContents)
        if FactorySetup.ASSY_KEY in machineCfgDict:
            assyStr = machineCfgDict[FactorySetup.ASSY_KEY]
            elems = assyStr.split("_")
            if len(elems) == 3:
                fullAssy = elems[0]
                fullVer  = elems[1]
                fullSN   = elems[2]           
                self._validateAssy(fullAssy+fullVer, forceAssyNumber=True)
                self._validateSN(fullSN)
                self._showUUT()
                self._initLogFile()
                
            else:
                raise Exception(f"{assyStr} is an invalid assembly string.")
            
        else:
            raise Exception(f"Unable to read the assembly details from {self._ipAddress}")
                
    def _ensureLogPathExists(self):
        """@brief Ensure that the log path exists."""
        if not os.path.isdir(self._logPath):
            os.makedirs(self._logPath)
        
    def _updateAssyAndSN(self):
        """@brief Allow the user to set the assy and serial numbers in the assembly label."""
        self._uio.info("")
        # Update the unit assembly number hardware version and serial number
               
        # Delete any local factory.cfg
        localFactoryCfgFile = os.path.join(tempfile.gettempdir(), CT6Base.CT6_FACTORY_CONFIG_FILE)
        if os.path.isfile(localFactoryCfgFile):
            os.remove(localFactoryCfgFile)
            self._uio.debug(f"Removed {localFactoryCfgFile}")
            
        # Get the file from the CT6 unit
        try:
            self.receiveFile(CT6Base.CT6_FACTORY_CONFIG_FILE, tempfile.gettempdir())
        except:
            raise Exception(f"/{CT6Base.CT6_FACTORY_CONFIG_FILE} not found on CT6 unit. A full test or recal is required.")
        factoryCfgDict = self._loadJSONFile(localFactoryCfgFile)
        
        # Update the assy/sn number
        newAssy = f"ASY{self._assyNumber:0>4d}_V{self._boardVersion:0>7.3f}_SN{self._serialNumber:0>8}"
        factoryCfgDict[CT6Base.ASSY_KEY] = newAssy
        self._saveDictToJSONFile(factoryCfgDict, localFactoryCfgFile)
        
        self._sendFileOverWiFi(self._ipAddress, localFactoryCfgFile, "/")
        os.remove(localFactoryCfgFile)
        
    def _initATM90E32Devs(self):
        url=f"http://{self._ipAddress}/init_atm90e32_devs"
        response = requests.get(url)
        self._checkResponse(response)
          
    def _calVoltageGain(self, ct, maxError=0.3, acVoltage=None):
        """@brief Calibrate the voltage gain for the CT.
           @param ct The ct number 1 or 4 as only the first port on each ATM90E32 device can measure the voltage on the CT6 hardware.
           @param maxError The maximum error. If the error drops below this value then we say the voltage is calibrated.
           @param acVoltage The AC voltage as measured by an external meter. If None then the user is prompted to enter the value.
           @return The AC voltage as measured by an external meter.."""
        self._uio.info("")
        if acVoltage is None:
            # Do some bounds checking on the entered voltage
            while True:
                acVoltage = self._uio.getFloatInput("Enter the AC RMS voltage as measured by an external meter")
                if acVoltage > 100 and acVoltage < 270:
                    break
                else:
                    self._uio.warn(f"{acVoltage} is out of range (100 - 270 volts).")

        self._uio.info(f"AC Freq = {self._lineFreqHz} Hz")
        url=f"http://{self._ipAddress}/set_config?{FactorySetup.LINE_FREQ_HZ_KEY}={self._lineFreqHz}"
        response = requests.get(url)
        
        if ct == 1:
            configKey = FactorySetup.CS4_VOLTAGE_GAIN_KEY
        elif ct == 4:
            configKey = FactorySetup.CS0_VOLTAGE_GAIN_KEY
        else:
            raise Exception(f"{ct} must be 1 or 4 to calibrate.")
                    
        # Start on the low side to ensure we cal quickly and predictably.
        voltageGain = 50000
        self._uio.info(f"Voltage gain = {voltageGain}")
        url=f"http://{self._ipAddress}/set_config?{configKey}={voltageGain}"
        response = requests.get(url)
        self._checkResponse(response)
        self._initATM90E32Devs()
        
        # First check that we have enough current flowing
        self._uio.info(f"Checking that CT{ct} detects at least 100 volts.")
        while True:
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]

            volts = ctStatsDict[FactorySetup.VRMS]
            self._uio.info(f"Detected {volts} volts.")
            if volts >= 100.0:
                break
            else:
                self._uio.warn(f"Detected {volts} volts. At least 100 volts must be detected for calibration to proceed.")
                sleep(1)
                
            sleep(0.4)
            
        while True:
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]
            voltageMeasurement = ctStatsDict[FactorySetup.VRMS]
            voltageError = abs(voltageMeasurement-acVoltage)
            self._uio.info(f"Read {voltageMeasurement:.2f} Volts (error = {voltageError:.2f} Volts)")
            if voltageError < maxError:
                break

            errorFactor = acVoltage/voltageMeasurement
            newVoltgeGain = int(errorFactor * voltageGain)           
            # Apply 16 bit reg limits (1000 from endstop)
            if newVoltgeGain > 65535:
                newVoltgeGain = 64535
            elif newVoltgeGain < 0:
                newVoltgeGain=1000
            self._uio.info(f"Voltage gain = {newVoltgeGain}")
            url=f"http://{self._ipAddress}/set_config?{configKey}={newVoltgeGain}"
            self._uio.debug(f"Setting voltage gain register: URL={url}")
            response = requests.get(url)
            self._checkResponse(response)
            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()
            voltageGain = newVoltgeGain
            sleep(0.4)
        
        self._uio.info(f"CT{ct} voltage calibration complete.")
        return acVoltage

    def _calVoltageOffset(self, ct):
        """@brief !!! Unused, untested code, left in case we ever want to calibrate the voltage offset.
                  Calibrate voltage offsets. To use this the voltage level fed to the ATM90E32 devices
                  needs to be set to 0. We could add a switch to reset the voltage to 0.
           @param ct The CT port."""
        voltageOffset=0
        offsetDelta=1000
        if ct == 1:
            cfgAttr = FactorySetup.CS4_VOLTAGE_OFFSET
            ct="CT1"

        elif ct == 4:
            cfgAttr = FactorySetup.CS0_VOLTAGE_OFFSET
            ct="CT4"

        else:
            raise Exception(f"{ct} is an invalid voltage cal CT port.")

        while True:
            regValue = FactorySetup.FromSigned(voltageOffset,16)
            url=f"http://{self._ipAddress}/set_config?{cfgAttr}={regValue}"
            self._uio.debug(f"Setting voltage offset register: URL={url}")
            response = requests.get(url)
            self._checkResponse(response)

            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()

            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[ct]

            volts = ctStatsDict[FactorySetup.VRMS]
            self._uio.info(f"Offset volts={volts}, regValue={regValue:04x}")
            if volts > 0:
                voltageOffset=voltageOffset-offsetDelta

            elif volts < 0:
                voltageOffset=voltageOffset+offsetDelta

            elif volts == 0.0:
                break

            sleep(0.4)
            
    def _calCurrentGain(self, ct, maxError=0.02):
        """@brief Calibrate the current gain for the CT.
           @param ct The ct number1,2,3,4,5 or 6.
           @param maxError The maximum error. If the error drops below this value then we say the voltage is calibrated."""
        self._uio.info("")
        self._uio.getInput("Ensure an AC load drawing at least 5 amps is connected and press RETURN")

        if ct == 1:
            configKey = FactorySetup.CT1_IGAIN_KEY
        elif ct == 2:
            configKey = FactorySetup.CT2_IGAIN_KEY
        elif ct == 3:
            configKey = FactorySetup.CT3_IGAIN_KEY
        elif ct == 4:
            configKey = FactorySetup.CT4_IGAIN_KEY
        elif ct == 5:
            configKey = FactorySetup.CT5_IGAIN_KEY
        elif ct == 6:
            configKey = FactorySetup.CT6_IGAIN_KEY
        else:
            raise Exception(f"{ct} must be 1,2,3,4,5 or 6 to calibrate.")
            
        # Start on the low side to ensure we cal quickly and predictably.
        currentGain = 8000
        self._uio.info(f"Current gain = {currentGain}")
        url=f"http://{self._ipAddress}/set_config?{configKey}={currentGain}"
        response = requests.get(url)
        self._checkResponse(response)
        self._initATM90E32Devs()
                    
        # First check that we have enough current flowing
        self._uio.info(f"Checking that CT{ct} detects at least 5 amps.")
        while True:
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]

            amps = ctStatsDict[FactorySetup.IRMS]
            self._uio.info(f"Detected {amps} amps.")
            if amps >= 5.0:
                break
            else:
                self._uio.warn(f"Detected {amps} amps. A load current of at least 5 amps is required for calibration.")
                sleep(1)
            sleep(0.4)

        # Do some bounds checking on the entered voltage
        while True:
            acAmps = self._uio.getFloatInput("Enter the AC RMS current in amps as measured with an external meter")
            if acAmps >= 5 and acAmps < 100:
                break
            else:
                self._uio.warn(f"{acAmps} is out of range (5 - 100 amps).")
                
        while True:
            cfgDict = self._getConfigDict()
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]
            ampsMeasurement = ctStatsDict["IRMS"]
            currentError = abs(ampsMeasurement-acAmps)
            self._uio.info(f"Read {ampsMeasurement:.2f} Amps (error = {currentError:.2f} Amps)")
            if currentError < maxError:
                break

            # Get the ATM90E32 voltage gain.
            currentGain = cfgDict[configKey]
            # We need this to stop subsequent 0 divide errors
            if ampsMeasurement == 0:
                self._uio.warn(f'No current detected. Ensure {configKey} is connected.')
                continue
                
            errorFactor = acAmps/ampsMeasurement
            newCurrentGain = int(errorFactor * currentGain)
            # Apply 16 bit reg limits (1000 from endstop)
            if newCurrentGain > 65535:
                newCurrentGain = 64535
            elif newCurrentGain < 0:
                newCurrentGain=1000
            self._uio.info(f"Current gain = {newCurrentGain}")
            url=f"http://{self._ipAddress}/set_config?{configKey}={newCurrentGain}"
            self._uio.debug(f"Setting current gain register: URL={url}")
            response = requests.get(url)
            self._checkResponse(response)
            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()
            currentGain = newCurrentGain
            sleep(0.4)

        self._uio.info("")
        self._uio.info(f"CT{ct} current calibration complete.")
        self._uio.getInput("DISCONNECT the AC load and press RETURN")

    def _calCurrentOffset(self, ct):
        """@brief Calibrate current offsets.
           @param ct The ct port."""

        ampsOffset=0
        offsetDelta=1000

        if ct == 1:
            cfgAttr = FactorySetup.CT1_IOFFSET

        elif ct == 2:
            cfgAttr = FactorySetup.CT2_IOFFSET

        elif ct == 3:
            cfgAttr = FactorySetup.CT3_IOFFSET

        elif ct == 4:
            cfgAttr = FactorySetup.CT4_IOFFSET

        elif ct == 5:
            cfgAttr = FactorySetup.CT5_IOFFSET

        elif ct == 6:
            cfgAttr = FactorySetup.CT6_IOFFSET

        # First check that the user has turned off the load
        self._uio.info(f"Checking that CT{ct} load has been turned off.")
        while True:
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]

            amps = ctStatsDict[FactorySetup.IRMS]
            if amps > 2.0:
                self._uio.warn(f"Detected {amps} amps. Turn off the load.")
                sleep(1)
            else:
                break
            sleep(0.4)

        while True:
            regValue = FactorySetup.FromSigned(ampsOffset,16)
            self._uio.info(f"Current offset register = {regValue}")
            url=f"http://{self._ipAddress}/set_config?{cfgAttr}={regValue}"
            self._uio.debug(f"Setting current offset register: URL={url}")
            response = requests.get(url)
            self._checkResponse(response)

            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()

            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]

            amps = ctStatsDict[FactorySetup.IRMS]
            self._uio.info(f"Detected a residual current of {amps} amps.")
            if amps > 0:
                ampsOffset=ampsOffset-offsetDelta

            elif amps < 0:
                ampsOffset=ampsOffset+offsetDelta

            elif amps == 0.0:
                break
            sleep(0.4)

    def _getPortRange(self):
        """@brief Get a list of the ports to be calibrated.
           @return The port list."""
        portRange = [1,2,3,4,5,6]
        if self._options.cal_ports != "all":
            portRange = []
            elems = self._options.cal_ports.split(",")
            for elem in elems:
                try:
                    port = int(elem)
                    if port < 1 or port > 6:
                        raise ValueError("")
                    portRange.append( port )
                except ValueError:
                    raise Exception(f"{self._options.cal_ports} is not a valid port range")
                
        return portRange
    
    def _startSerialPortMonitorThread(self):
        """@brief Start a thread to log serial port data."""
        # Ensure the serial port is open before starting the thread to read serial data.
        if self._ser is None:
            self._openSerialPort()
        self._serialLoggingThread = threading.Thread(target=self.serialLoggingThread)
        self._serialLoggingThread.start()
        
    def serialLoggingThread(self):
        """@brief this method is executed to record serial data received."""
        self._serialLoggingThreadRunning = True
        while self._serialLoggingThreadRunning:
            try:
                #Wait for data to arrive
                sleep(0.25)
                if self._ser.in_waiting > 0:
                    data = self._ser.readline()
                    if len(data) > 0:
                        data=data.decode()
                        self._uio.debug(f"CT6 Serial RX: <{data}>")
            except OSError:
                self._uio.warn("The CT6 unit has rebooted !!!")
                        
        self._serialLoggingThreadRunning = False
        if self._ser:
            self._ser.close()
            self._ser = None        
                            
    def _stopSerialPortMonitorThread(self):
        """@brief Stop the thread loggin serial port data."""
        self._serialLoggingThreadRunning = False

    def calibrateAndReboot(self):
        """@brief Calibrate and reboot a CT6 unit."""
        self.calibrate()
        self._powerCycle()
        self._uio.info("Completed calibration.")
        self._uio.info("The CT6 unit is now power cycling.")
         
    def calibrate(self):
        """@brief Perform the user configuration of a CT6 device."""
        self._checkAddress()
        self._uio.info(f'Factory setup and calibration of {self._ipAddress}')

        self._waitForPingSucess(pingHoldSecs=0)
        #Calibrate the AC voltage for both devices first
        self._uio.info("Calibrating U5 VOLTAGE gain.")
        acVoltage = self._calVoltageGain(1)
        self._uio.info("Calibrating U4 VOLTAGE gain.")
        self._calVoltageGain(4, acVoltage=acVoltage)
        # Currently I don't plan to calibrate out the Voltage offset to read 0 volts.
        # As the CT6 hardware is powered by an AC adaptor which feeds the measured AC voltage.
        # We could do this by adding a jumper to the board to short out R22 but investigation
        # would be required as to the efficacy of this approach.
        # self._uio.info("Calibrating U4 VOLTAGE offset.")
        # self._calVoltageOffset(4)
            
        portRange = self._getPortRange()
        portIndex = 0
        while portIndex < len(portRange):
            ct = portRange[portIndex]
            self._waitForPingSucess(pingHoldSecs=0)
            self._uio.info("")
            self._uio.info("Ensure no AC load is connected.")
            self._uio.info("At this point you may enter 'B' to jump back to previous port calibration.")
            response = self._uio.getInput(f"Connect an SCT013_100A current transformer (CT) to port {ct} and press RETURN")
            if response.upper() == 'B' and portIndex > 0:
                    portIndex=portIndex-1
                    continue
                    
            self._uio.info(f"Calibrating CT{ct} CURRENT gain.")
            self._calCurrentGain(ct)
            self._uio.info(f"Calibrating CT{ct} CURRENT offset.")
            self._calCurrentOffset(ct)
            
            portIndex+=1
    
        # This creates the factory.cfg file on the CT6 unit
        self._saveFactoryConfig()
        
        # If we've completed calibration of all ports.
        if self._options.cal_ports == 'all':
            # Save the CT6 calibration file (factory.cfg) locally to a unique filename
            self._storeFileContents(FactorySetup.CT6_FACTORY_CONFIG_FILE)
            self._uio.info("CT6 unit calibration successful.")
        else:
            self._uio.warn("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            self._uio.warn("!!! Calibration data not saved locally as you   !!!")
            self._uio.warn("!!! did not calibrate all ports.                !!!")
            self._uio.warn("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    def calibrateVoltage(self):
        """@brief Perform the voltage calibration of the CT6 unit.
                  Both the ATM90E32 devices are calibrated.
                  """
        self._checkAddress()
        self._uio.info(f'{self._ipAddress}: CT6 voltage calibration.')

        self._uio.info("Calibrating U5 VOLTAGE gain.")
        acVoltage = self._calVoltageGain(1)
        self._uio.info("Calibrating U4 VOLTAGE gain.")
        self._calVoltageGain(4, acVoltage=acVoltage)
        # This creates the factory.cfg file on the CT6 unit
        self._saveFactoryConfig()
        # We don't save the contents of the CT6 unit factory.cfg file locally because we
        # don't know if the port current calibration is correct on the unit. We only want
        # the local (E.G ~/test_logs/ASY0398_V01.6000_SN00001823_20240111063130_factory.cfg)
        # factory config files to contain data when all calibration has been completed
        # successfully.
                
    def calibrateVoltageAndReboot(self):
        """@brief Perform voltage calibration and reboot afterwards."""
        self.calibrateVoltage()
        self._powerCycle()
        self._uio.info("Completed calibration.")
        self._uio.info("The CT6 unit is now power cycling.")
        
    def _saveFactoryConfig(self):
        """@brief Save the factory configuration. Should only be called after
           the unit serial number has been set and the unit is calibrated."""
        self._uio.info("Saving the factory configuration file to the CT6 unit.")

        # Set ASSY/SN value in this.machine.cfg on the CT6 unit
        newAssy = f"ASY{self._assyNumber:0>4d}_V{self._boardVersion:0>7.3f}_SN{self._serialNumber:0>8}"
        self._uio.info(f"Setting assembly label to {newAssy}.")
        url=f"http://{self._ipAddress}{FactorySetup.SET_CONFIG_CMD}?{FactorySetup.ASSY_KEY}={newAssy}"
        response = requests.get(url)
        self._checkResponse(response)
        
        url=f"http://{self._ipAddress}/save_factory_cfg"
        self._runRESTCmd(url)

    def _stripControlChar(self, enteredText):
        """@brief Strip the control character if present in the entered text.
           @param enteredText The text entered by the user.
           @return The text without the first control character (if present)"""
        # If a non printable character then strip the first character
        # This may occur if the scanned by a bar code scanner and a control character is present at the start of the bar code.
        if len(enteredText) > 0:
            firstChar = ord(enteredText[0])
            if firstChar <= 0x20 or firstChar >= 0x7f:
                enteredText=enteredText[1:]
        return enteredText
                           
    def _validateAssy(self, assyNumber, forceAssyNumber=False):
        """@brief Validate the assembly number.
           @param assyNumber The board assembly number to validate.
           @param forceAssyNumber If True then set the correct assembly number."""
        assyNumber = self._stripControlChar(assyNumber)
        if forceAssyNumber:
            self._assyNumber = FactorySetup.CT6_BOARD_ASSY_NUMBER
        else:
            if not assyNumber.startswith(FactorySetup.CT6_BOARD_ASSY_NUMBER_STR):
                raise Exception(f"{assyNumber} is not correct. The assembly label must start {FactorySetup.CT6_BOARD_ASSY_NUMBER_STR}")
            self._assyNumber = FactorySetup.CT6_BOARD_ASSY_NUMBER
            
        versionPos = assyNumber.find("V")
        if versionPos > 0:
            boardVersionStr = assyNumber[versionPos+1:]
            try:
                # Save the board version to be used later
                self._boardVersion = float(boardVersionStr)

            except ValueError:
                raise Exception(f"{boardVersionStr} is not a valid board version in {assyNumber}")
                
        else:
            raise Exception(f"No version number found in the board assembly number: {assyNumber}")
        
    def _validateSN(self, serialNumber):
        """@brief Validate the board serial number.
           @param serialNumber The serial number to validate."""
        serialNumber = self._stripControlChar(serialNumber)
        if serialNumber.startswith(FactorySetup.CT6_SERIAL_NUMBER_PREFIX):
             self._serialNumber = int(serialNumber[2:])
             
        else:
            raise Exception(f"The serial number label does not start {FactorySetup.CT6_SERIAL_NUMBER_PREFIX}: {serialNumber}")    
         
    def _showUUT(self):
        """@param Show details of the unit under test."""
        table = [("UNIT UNDER TEST", "")]
        table.append(["Assembly Number",    f"{self._assyNumber}"])
        table.append(["CT6 hardware version",            f"{self._boardVersion}"])
        table.append(["CT6 board serial Number",      f"{self._serialNumber}"])
        self._uio.showTable(table)

    def _getPicoPath(self):
        """@brief Get the path of the RPi Pico W device.
           @return The path on this machine where RPi Pico W images can be copied to load them into flash."""
        if self._windowsPlatform:
            picoDrive = None
            # Wait for the drive mounted from the RPi over the serial interface. 
            while not picoDrive:           
                drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
                for drive in drives:
                    # Skip the main HDD/SSD
                    if drive.startswith("C:"):
                        continue
                    fileList = os.listdir(drive)
                    fileCount = 0
                    for rootFile in fileList:
                        if rootFile.lower() in FactorySetup.RPI_BOOT_BTN_DWN_FILE_LIST:
                            fileCount+=1
                    # If the expected files are in the root of the drive assume it's a RPi in the correct mode.
                    if fileCount == len(FactorySetup.RPI_BOOT_BTN_DWN_FILE_LIST):
                        picoDrive = drive
                        break
                sleep(0.2)
                
            return picoDrive
        else:
            return f"/media/{self._username}/RPI-RP2"
              
    def _getPicoFlashPath(self):
        """@brief Get the path in which the RPi Pico W flash images are held.
                  The path may be in differnet locations relatve to the CWD 
                  depending upon whether youre running on a Windows or Linux platform.
           @return the above as a string."""
        picoFlashPath = None
        for flashP in FactorySetup.PICO_FLASH_PATHLIST:
            if os.path.isdir(flashP):
                picoFlashPath = flashP
                break
                
        if not picoFlashPath:
            raise Exception("Unable to find the path in which the RPi Pico W flash images are held.")
            
        return picoFlashPath
        
    def _getPicoFlashNukeImage(self):
        """@return The image used to wipe the flash on the RPi."""
        flashP = self._getPicoFlashPath()
        nukeImage = os.path.join(flashP, "flash_nuke.uf2")
        if not os.path.isfile(nukeImage):
            raise Exception(f"{nukeImage} file not found.")
        return nukeImage
    
    @retry(Exception, tries=3, delay=1)
    def _erasePicoWFlash(self):
        """@brief Erase flash on the microcontroller (Pico W)"""
        self._uio.info("Ensure the USB Pico W is connected to this PC.")
        self._uio.info("Hold the button down on the Pico W and power up the CT6 device.")
        picoPath = self._getPicoPath()
        sourcePath = self._getPicoFlashNukeImage()
        destinationPath = picoPath
    
        self._waitForPicoPath(exists=True)
            
        self._uio.info("")
        self._uio.info("Release the button on the Pico W.")
        self._uio.info("")
        
        self._uio.info(f"Copying {sourcePath} to {destinationPath}")
        shutil.copy(sourcePath, destinationPath)

        self._waitForPicoPath(exists=False)
            
        self._uio.info(f"Checking {picoPath}")
        while True:
            if os.path.isdir(picoPath):
                break
            sleep(0.25)
                    
    def _waitForPicoPath(self, exists=True):
        """@brief wait for the path that appears when the RPi Pico button is held down
           and the RPi Pico is powered up to no longer be present."""
        picoPath = self._getPicoPath()
        while True:
            if exists:
                if os.path.isdir(picoPath):
                    break
            else:
                if not os.path.isdir(picoPath):
                    break

            sleep(0.25)

    
    def _getPicoMicroPythonImage(self):
        """@return The image containing the Micropython for the RPi."""
        flashP = self._getPicoFlashPath()
        microPythonImage = os.path.join(flashP, "firmware.uf2")
        if not os.path.isfile(microPythonImage):
            raise Exception(f"{microPythonImage} file not found.")
        return microPythonImage
            
    @retry(Exception, tries=3, delay=1)
    def _loadMicroPython(self):
        """@brief Load Micropython image onto the RPi Pico W."""
        self._uio.info("Ensure the USB Pico W is connected to this PC.")
        self._uio.info("Hold the button down on the Pico W and power up the CT6 device.")
        picoPath = self._getPicoPath()
        sourcePath = self._getPicoMicroPythonImage()
        destinationPath = picoPath
    
        self._waitForPicoPath(exists=True)
            
        self._uio.info("Loading micropython image onto the RPi Pico W")
        self._uio.info(f"Copying {sourcePath} to {destinationPath}")
        shutil.copy(sourcePath, destinationPath)
        
        self._waitForPicoPath(exists=False)
        sleep(2)
        self._checkMicroPython()

    def _initLogFile(self):
        """@brief Init the test log file to record the test an calibration of the unit."""
        timeStamp = FactorySetup.GetTSString()

        logFileName = f"ASY{self._assyNumber:04}_V{self._boardVersion:07.4f}_SN{self._serialNumber:08d}_{timeStamp}.log"
        self._uio.logAll(True)
        self._uioLogFile = f"{self._logPath}/{logFileName}"
        self._uio.setLogFile(self._uioLogFile)
        
    def _testSwitches(self):
        """@brief Test the switches on the CT6 board."""
        self._uio.info("Hold down the WiFi switch on the CT6 board.")
        try:
            try:
                self._openSerialPort()
                while True:
                    data = self._ser.read_until()
                    if len(data) > 0:
                        data=data.decode()
                        if len(data) > 0:
                            lines = data.split("\n")
                            for line in lines:
                                line=line.rstrip("\r\n")
                                self._uio.debug(line)
                                
                        pos = data.find("Button pressed for")
                        if pos != -1:
                            break
                    
            except serial.SerialException:
                self._uio.debug(f"SerialException: {traceback.format_exc()}")
    
            except OSError:
                self._uio.debug(f"SerialException: {traceback.format_exc()}")
                
        finally:
            if self._ser:
                self._ser.close()
                self._ser = None
        self._uio.info("The WiFi switch is working. Release the WiFi switch.")
        
        # No longer test the reset switch as it is not exposed outside the case 
        # and therefore if the unit is tested with the case on it can't be pressed 
        # to check it. In future this may not be fitted.
        # self._uio.info("Press and release the reset switch on the CT6 board.")
        # self._waitForWiFiDisconnect(showMessage=False)
        # self._waitForUnitPingable()
        
    def _waitForUnitPingable(self):
        """@brief Wait for unit to be pingable."""
        self._uio.info(f"Checking for CT6 unit on {self._ipAddress}")
        self._waitForPingSucess()
        
    def _powerCycle(self):
        url=f"http://{self._ipAddress}/power_cycle"
        self._runRESTCmd(url)
        
    def _runRESTCmd(self, cmd):
        """@brief Run a CT6 rest command.
           @param cmd The REST cmd to execute.
           @return The response dict from the unit"""
        self._uio.debug(f"URL={cmd}")
        response = requests.get(cmd)
        self._checkResponse(response)
        return response
        
    def _testPowerCycle(self):
        """@brief Check that the power cycle circuit works."""
        self._uio.info("Checking the power cycle feature on the CT6 board.")
        self._powerCycle()
        self._waitForWiFiDisconnect()
        self._waitForUnitPingable()        
    
    def _saveLastUnitTested(self, assyNumber, serialNumber):
        """@brief Save details of the last unit tested.
           @param assyNumber The unit assembly number.
           @param serialNumber The serial number entered."""
        uutDict = {FactorySetup.ASSY_KEY: assyNumber, FactorySetup.SN_KEY: serialNumber}
        lastUUTFile = os.path.join(os.path.expanduser('~'), FactorySetup.LAST_UUT_CFG_FILE)
        self._saveDictToJSONFile(uutDict, lastUUTFile)
        
    def _loadLastUnitTested(self):
        """@brief Load details of the last unit tested."""
        lastUUTFile = os.path.join(os.path.expanduser('~'), FactorySetup.LAST_UUT_CFG_FILE)
        try:
            uutDict = self._loadJSONFile(lastUUTFile)
            return (uutDict[FactorySetup.ASSY_KEY], uutDict[FactorySetup.SN_KEY])
        except:
            raise Exception("Unable to load details of the last UUT.")
        
    def scanBoardLabels(self):
        """@brief Scan the board assembly and serial number labels.
           @return A tuple containing the assembly number followed by the serial number."""
        assyNumber = self._uio.getInput("Enter the board assembly number or 'r' to repeat last test")
        assyNumber = assyNumber.upper()
        if assyNumber.lower() == 'r':
            assyNumber, serialNumber = self._loadLastUnitTested()
            self._validateAssy(assyNumber)
            self._validateSN(serialNumber)
            
        else:
            self._validateAssy(assyNumber)
            
            serialNumber = self._uio.getInput("Enter the board serial number")
            serialNumber = serialNumber.upper()
            self._validateSN(serialNumber)
            
            self._saveLastUnitTested(assyNumber, serialNumber)

        return (assyNumber, serialNumber)
        
    def _storeFileContents(self, filename):
        """@brief Get the contents of a file from the unit and save the contents to a local file.
           @param filename The name of the file on the CT6 unit to retrieve."""
        fileContents = self._getFileContentsOverWifi(filename, self._ipAddress)
        self._uio.info(f"Save to {filename} from {self._ipAddress}.")
        localFile = self._uioLogFile.replace(".log", "_")
        localFile += filename
        with open(localFile, 'w') as fd:
            fd.write(fileContents)
        self._uio.info(f"Saved to {localFile}")
                
    def _storeConfig(self):
        """@brief Store the configuration files from the unit tested in the local folder along with the test logs."""
        self._storeFileContents(FactorySetup.CT6_MACHINE_CONFIG_FILE)
        # check if factory.cfg file is present
        try:
            url=f"http://{self._ipAddress}/get_file?file={FactorySetup.CT6_FACTORY_CONFIG_FILE}"
            self._runRESTCmd(url)

        except:
            self._uio.warn("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            self._uio.warn("!!! The CT6 unit is NOT CALIBRATED.             !!!")
            self._uio.warn("!!! To resolve this issue                       !!!")
            self._uio.warn("!!! 1: Run this tool with '--setup_wifi' to     !!!")
            self._uio.warn("!!!    connect the WiFi to your network.        !!!")
            self._uio.warn("!!! 2: Run this tool with either '--cal_only'   !!!")
            self._uio.warn("!!!    or '--restore'                           !!!")
            self._uio.warn("!!!    --cal_only takes you through the CT6     !!!")
            self._uio.warn("!!!      calibration process.                   !!!")
            self._uio.warn("!!!    --restore allows you to load an old      !!!")
            self._uio.warn("!!!      calibration (factory config) file      !!!")
            self._uio.warn("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
    def _cleanConfig(self):
        """@brief Set the config to the state required to ship the CT6 unit from the factory.
                  The WiFi config is reset to the default value."""
        self._uio.info("Set factory CT6 WiFi.")
        url=f"http://{self._ipAddress}/reset_wifi_config"
        return self._runRESTCmd(url)
 
    def _initTest(self):
        """@brief Initialise the test. This includes the user entering the assembly number and serial number of the UUT (unit under test)."""
        self._ensureLogPathExists()
        
        self.scanBoardLabels()
                
        self._initLogFile()

        self._recordGitHash()
                
        self._showUUT()

    def _loadCT6Application(self):
        """@brief Load the application software onto the CT6 device."""
        ipAddress = self.loadCT6Firmware() 
        self.setIPAddress(ipAddress)
        # The loading process should load the WiFi at the MFG site.
        # Therefore wait for the WiFi to connect.
        self._waitForUnitPingable()

    def _waitForAppStart(self, closeSerialPort=True, timeout=60):
        """@brief Wait for App to startup after reboot.
           @param closeSerialPort If True then close the serial port on exit.
           @param timeout The timeout value, in seconds, when waiting for the CT6 app to startup."""
        self._uio.debug("_waitForAppStart(): START")
        startTime = time()
        lastCtrlCTime = time()
        lastCtrlDTime = time()+3
        try:
            while True:
                try:
                    self._openSerialPort()                   
                    #Wait for data to arrive
                    sleep(0.25)
                    now = time()
                    if self._ser.in_waiting > 0:
                        data = self._ser.readline()
                        if len(data) > 0:
                            data=data.decode()
                            self._uio.debug(f"Serial data = {data}")
                            if data.find("Activating WiFi") != -1:
                                self._uio.info("CT6 App running.")
                                break
                            
                    if now > lastCtrlCTime+5:
                        # Send CTRL C
                        self._ser.write(b"\03")
                        self._uio.debug("Sent CTRL C")                        
                        lastCtrlCTime = now

                    if now > lastCtrlDTime+5:
                        # Send CTRL C
                        self._ser.write(b"\04")
                        self._uio.debug("Sent CTRL 4")                        
                        lastCtrlDTime = now
                        
                except serial.SerialException:
                    self._uio.debug(f"SerialException: {traceback.format_exc()}")

                except OSError:
                    self._uio.debug(f"SerialException: {traceback.format_exc()}")

                if self._ser:
                    self._ser.close()
                    self._ser = None
                    
                if time() > startTime+timeout:
                    raise Exception(f"{timeout} second timeout waiting for CT6 app to startup.")
                    
        finally:
            if closeSerialPort and self._ser:
                self._ser.close()
                self._ser = None
                
        self._uio.debug("_waitForAppStart(): STOP")

    def _testLEDs(self):
        """@brief test the LED's on the board."""
        self._testLED(True)
        self._testLED(False)

    def _flashLED(self, cmd, states):
        """@brief Flash an LED.
           @param cmd The command to set/reset the LED state.
           @param states The states of the LED."""
        while self._stopQueue.empty():
            url=f"http://{self._ipAddress}/{cmd}?on={states[0]}"
            self._runRESTCmd(url)
            sleep(0.25)
            url=f"http://{self._ipAddress}/{cmd}?on={states[1]}"
            self._runRESTCmd(url)
            sleep(0.25)
        # Remove stop cmd from queue
        self._stopQueue.get()

    def _testLED(self, wifi):
        """@brief Test an LED.
           @param wifi If True test the WiFi LED. If False test the Bluetooth LED."""
        if wifi:
            prompt = "Is the green LED next to the WiFi switch flashing ? y/n"
            cmd = 'set_wifi_led'
            states = ["force_on","force_off"]
        else:
            prompt = "Is the blue LED next to the reset switch flashing ? y/n"
            cmd = 'set_bluetooth_led'
            states = [1, 0]
            
        self._stopQueue = Queue()
        flashLedThread = threading.Thread(target=self._flashLED, args=(cmd,states))
        flashLedThread.start()

        yesEntered = self._uio.getBoolInput(prompt)
        self._stopQueue.put(True)
        # Wait for flash thread to stop
        flashLedThread.join()
        if yesEntered:
            passed = True
        else:
            passed = False
                    
        if not passed:
            if wifi:
                raise Exception("WiFi LED fault.")
            
            else:
                raise Exception("Bluetooth LED fault.")
            
        if wifi:
            # Release the Wifi LED forced state
            url=f"http://{self._ipAddress}/{cmd}?on=release"
            self._runRESTCmd(url)
            
    def _setDefaultConf(self):
        """@brief Set the factory default configuration."""
        self._cleanConfig()
           
    def _initTestOnly(self):
        """@brief Initialise when only testing the CT6 unit, not loading code or calibrating.
                  If not performing a MFG test process we just run the tests. 
                  In this case at this point we need to 
                  - Save the this.machine.cfg and factory.cfg files from the unit in the state they were received.
                  - Set the WiFi config to allow the unit to register on the local WiFi network.
                  - Register on the local WiFi network.
                  - Read tThe IP address the CT6 unit is registered on."""
        self._updateWiFiConfig()
        self._ipAddress = self._runApp()
        
    def _displayTest(self):
        """@brief Check the display is working."""
        displayWorking = self._uio.getBoolInput("Is the display showing the CT6 IP address y/n")
        if not displayWorking:
            raise Exception("The CT6 display is faulty.")
        
    def _temperatureTest(self, minTemp=15, maxTemp=40):
        """@brief Check that the CT6 can read the board temperature."""
        self._uio.info("Checking the CT6 board temperature.")
        url = f"http://{self._ipAddress}/get_temperature"
        response = self._runRESTCmd(url)
        rDict = response.json()
        if FactorySetup.TEMPERATURE_RESULT in rDict:
            tempC = rDict[FactorySetup.TEMPERATURE_RESULT]
            if tempC < minTemp or tempC > maxTemp:
                raise Exception(f"CT6 board temperature = {tempC:.1f} °C (min={minTemp:.1f} °C, max={maxTemp:.1f} °C).")
            self._uio.info(f"CT6 board temperature = {tempC:.1f} °C")
            
        else:
            raise Exception("Failed to read the CT6 board temperature.")

    def configureWiFi(self):
        """@brief configure the CT6 WiFi interface from the house_wifi.cfg file."""
        self._uio.info("Setting up CT6 WiFi interface.")
        ssid = self._updateWiFiConfig()
        self._uio.info(f"WiFi SSID: {ssid}")
        self._uio.info("The CT6 WiFi interface is now configured.")
        
    def powerCycleReliabilityTest(self, max=20):
        """@brief Perform a reliability test on the power cycle mechanism.
           @param max The maximum number of retries."""
        count = 0
        while count < max:
            self._testPowerCycle()
            count+=1
            self._uio.info(f"Power cycle passed: {count}")
            
        self._uio.info(f"Power cycle passed {count} times.")
                
    def _recordGitHash(self):
        """@brief Record the git hash of the test software in the log file."""
        # Get currently executing file
        exeFile = sys.argv[0]
        # Get it's path.
        pathname = os.path.dirname(exeFile)
        # Get the git_hash.txt file created when build.sh was executed to create the deb file.
        assetsFolder = os.path.join(pathname, "assets")
        gitHashFile = os.path.join(assetsFolder, "git_hash.txt")
        if os.path.isfile(gitHashFile):
            lines = []
            with open(gitHashFile, 'r') as fd:
                lines = fd.readlines()
            if len(lines) > 0:
                gitHash = lines[0].rstrip("\r\n")
                self._uio.info(f"Test SW git hash: {gitHash}")
            else:
                self._uio.error("Failed to read test SW git hash")
        else:
            self._uio.error(f"{gitHashFile} file not found.")
                
    def setLabelData(self):
        """@brief Set the CT6 unit label data (ASSY and serial number). This is useful if the board is modified."""
        self._ensureLogPathExists()
        
        self.scanBoardLabels()
                
        self._updateAssyAndSN()
        
        self._powerCycle()
        self._uio.info("Completed setting the CT6 unit ASSY and SN numbers.")
        self._uio.info("The CT6 unit is now power cycling.")
            
    def upgradeAndCal(self):
        """@brief Upgrade and calibrate a CT6 unit. This only requires WiFi access to the unit."""
        class YDevManagerOptions(object):
            def __init__(self, address):
                self.check_mpy_cross = False
                self.address = address
                self.upgrade_src = "app1"
        opts = YDevManagerOptions(self._ipAddress)
                
        yDevManager = YDevManager(self._uio, opts)
        self._initTest()
        self._updateAssyAndSN()
        yDevManager.upgrade(promptReboot=False)
        sleep(1)
        self._powerCycle()
        self._uio.info("CT6 unit is now power cycling.")
        self._waitForPingSucess(pingHoldSecs=4)
        
        self.calibrateAndReboot()
        
    def mfgTest(self):
        """@brief Perform a manufacturing test."""
         # Create all the test cases
        ct6Testing = TestCaseBase(self._uio)
        ct6Testing.addTestCase(1000, "Enter ASSY and S.N.", self._initTest)
        
        if self._options.test:
            ct6Testing.addTestCase(2000, "RMA test initialisation.", self._initTestOnly)

        else:
            ct6Testing.addTestCase(3000, "Erase Pico W flash memory.", self._erasePicoWFlash)
            ct6Testing.addTestCase(4000, "Load MicroPython onto Pico W flash memory.", self._loadMicroPython)
            ct6Testing.addTestCase(5000, "Load the CT6 firmware.", self._loadCT6Application)
        
        if not self._options.test:
            if not self._options.no_cal:
                # The calibration process tests all the CT interface ports.
                # We do this first as this is the most important part of the test.
                ct6Testing.addTestCase(6000, "Perform calibration process.", self.calibrate)
                
        ct6Testing.addTestCase(7000, "Temperature test.", self._temperatureTest)
        
        ct6Testing.addTestCase(8000, "LED test.", self._testLEDs)
        ct6Testing.addTestCase(9000, "Switch test.", self._testSwitches)
        ct6Testing.addTestCase(10000, "Power cycle circuit test.", self._testPowerCycle)
        ct6Testing.addTestCase(11000, "Display test.", self._displayTest)

        # 12000 used to be the step that sets the unit assy/serial number. This is now 
        # done as part of the calibration process.

        #This ensures we have a local copy of the CT6 config files.
        ct6Testing.addTestCase(13000, "Store CT6 configuration files.", self._storeConfig)
            
        if not self._options.no_default:
            ct6Testing.addTestCase(14000, "Load factory default configuration.", self._setDefaultConf)
            
        ct6Testing.executeTestCases()
                
def getFactorySetupCmdOpts():
    """@brief Get a reference to the command line options.
       @return The options instance."""
    parser = argparse.ArgumentParser(description="A tool to perform configuration and calibration functions on a CT6 power monitor.",
                                        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no_cal",                 action='store_true', help="By default a full MFG test is performed. If this option is used code is loaded but CT6 ports are not calibrated/tested.")
    parser.add_argument("--no_default",             action='store_true', help="By default a full MFG test is performed. If this options is used the factory defaults will not be loaded leaving the WiFi config present when testing is complete..")
    parser.add_argument("-t", "--test",             action='store_true', help="By default a full MFG test is performed. This option will not load code onto the CT6 device but will run some test cases. This options does not test the CT ports.")
    parser.add_argument("-o", "--cal_only",         action='store_true', help="Only perform the CT port calibration.")
    parser.add_argument("-u", "--upcal",            action='store_true', help="Upgrade the CT6 firmware and recal.")
    parser.add_argument("-v", "--voltage_cal_only", action='store_true', help="Only perform the CT voltage calibration.")
    parser.add_argument("-r", "--restore",          help="The filename of the CT6 factory config file to load onto the CT6 unit.")
    parser.add_argument("-p", "--power_cycle",      action='store_true', help="Perform a number of power cycle tests to check the reliability of the power cycling feature.")
    parser.add_argument("-w", "--setup_wifi",       action='store_true', help="Alternative to using the Android App to setup the CT6 WiFi interface.")
    parser.add_argument("-a", "--address",          help="The IP address of the unit. This is required for --restore and --power_cycle.", default=None)
    parser.add_argument("-c", "--cal_ports",        help="Ports to calibrate. Default = all. The port number or comma separated list of ports (E.G 1,2,3,4,5,6) may be entered.", default="all")
    parser.add_argument("-l", "--labels",           action='store_true', help="Set the assembly and serial number label data in the CT6 unit.")
    parser.add_argument("--ac60hz",                 action='store_true', help="Set the AC freq to 60 Hz. The default is 50 Hz.")
    parser.add_argument("-d", "--debug",            action='store_true', help="Enable debugging.")

    options = parser.parse_args()
    return options

def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        options = getFactorySetupCmdOpts()

        uio.enableDebug(options.debug)

        factorySetup = FactorySetup(uio, options)

        if options.power_cycle:
            factorySetup.setIPAddress(options.address)
            factorySetup.powerCycleReliabilityTest()
            
        elif options.restore:
            factorySetup.setIPAddress(options.address)
            factorySetup.restoreFactoryConfig(options.restore, serialCon=False)
            
        elif options.cal_only:
            factorySetup.setIPAddress(options.address)
            factorySetup.calibrateAndReboot()
            
        elif options.voltage_cal_only:
            factorySetup.setIPAddress(options.address)
            factorySetup.calibrateVoltageAndReboot()
                       
        elif options.setup_wifi:
            factorySetup.configureWiFi()

        elif options.labels:
            factorySetup.setIPAddress(options.address)
            factorySetup.setLabelData()

        elif options.upcal:
            factorySetup.setIPAddress(options.address)
            factorySetup.upgradeAndCal()
                        
        else:
            factorySetup.mfgTest()

    #If the program throws a system exit exception
    except SystemExit:
        pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if options.debug:
            raise
        else:
            uio.error(str(ex))

if __name__== '__main__':
    main()
