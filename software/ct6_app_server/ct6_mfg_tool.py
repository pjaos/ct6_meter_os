#!/usr/bin/env python3

# PJA TODO
# - Skip calibration then load old factory.cfg file to the CT6 unity
# - Add option to use last assy and serial number

import os
import sys
import argparse
import requests
import getpass
import shutil
import serial
import json

from   retry import retry
from   subprocess import check_call, DEVNULL, STDOUT

from   serial.tools.list_ports import comports

from   time import sleep, strftime, localtime, time

from   p3lib.uio import UIO
from   p3lib.helper import logTraceBack
from   p3lib.ate import TestCaseBase

from   ct6_tool import CT6Base

sys.path.append("../picow/tools")
from deploy_and_run import MCULoader

class FactorySetup(CT6Base):
    """@brief Allow the user to setup an calibrate a CT6 device."""

    SET_CONFIG_CMD              = "/set_config"
    ASSY_KEY                    = 'ASSY'
    CS0_VOLTAGE_OFFSET          = "CS0_VOLTAGE_OFFSET"
    CS4_VOLTAGE_OFFSET          = "CS4_VOLTAGE_OFFSET"
    VRMS                        = "VRMS"
    CT1_IOFFSET                  = "CT1_IOFFSET"
    CT2_IOFFSET                  = "CT2_IOFFSET"
    CT3_IOFFSET                  = "CT3_IOFFSET"
    CT4_IOFFSET                  = "CT4_IOFFSET"
    CT5_IOFFSET                  = "CT5_IOFFSET"
    CT6_IOFFSET                  = "CT6_IOFFSET"
    IRMS                         = "IRMS"
    CS0_VOLTAGE_GAIN_KEY        = "CS0_VOLTAGE_GAIN"
    CS4_VOLTAGE_GAIN_KEY        = "CS4_VOLTAGE_GAIN"
    CT1_IGAIN_KEY               = "CT1_IGAIN"
    CT2_IGAIN_KEY               = "CT2_IGAIN"
    CT3_IGAIN_KEY               = "CT3_IGAIN"
    CT4_IGAIN_KEY               = "CT4_IGAIN"
    CT5_IGAIN_KEY               = "CT5_IGAIN"
    CT6_IGAIN_KEY               = "CT6_IGAIN"

    CT6_BOARD_ASSY_NUMBER_STR   = "ASY0398"
    CT6_BOARD_ASSY_NUMBER       = 398
    CT6_SERIAL_NUMBER_PREFIX    = "SN"
    WIFI_CFG_KEY                = "WIFI"
    HOUSE_WIFI_CFG_FILE         = "house_wifi.cfg"
    CT6_MACHINE_CONFIG_FILE     = "this.machine.cfg"
    CT6_FACTORY_CONFIG_FILE     = "factory.cfg"
    RSHELL_CMD_LIST_FILE        = "cmd_list.cmd"
    TEMPERATURE_RESULT          = "CT6_BOARD_TEMPERATURE"
    
    # We hard code the log path so that the user does not have the option to move them.
    LOG_PATH                    = "test_logs"
    
    @staticmethod
    def FromSigned(value, bitCount) :
        """@brief Convert from a signed number to an unsigned number.
           @param value The signed value to convert.
           @param bitCount The number of bits in the conversion."""
        return int(value & (2**bitCount - 1))
    
    @staticmethod
    def GetSerialPortList():
        """@brief Get a list of the serial numbers of each serial port.
           @return A list of serial ports."""
        portList = []
        comPortList = comports()
        for port in comPortList:
            if port.vid is not None:
                portList.append(port)
        return portList
    
    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        super().__init__(uio, options)
        
        self._assyNumber   = None
        self._boardVersion = None
        self._serialNumber = None
        self._username     = getpass.getuser()
        self._logPath      = os.path.join(os. path. expanduser('~'), FactorySetup.LOG_PATH)
        self._ser          = None
        self._uioLogFile   = None
        self._serialPort   = None

        if not os.path.isfile(FactorySetup.HOUSE_WIFI_CFG_FILE):
            self._handleHouseWiFiConfigFileNotFound()
        
    def _ensureLogPathExists(self):
        """@brief Ensure that the log path exists."""
        if not os.path.isdir(self._logPath):
            os.makedirs(self._logPath)

    def _setAssyNumber(self, cfgDict):
        """@brief Allow the user to set the serial number in the assembly label.
           @param cfgDict The config dict read from the unit."""
        self._uio.info("")
        # Set the unit assembly number hardware version and serial number
        newAssy = f"ASY{self._assyNumber:0>4d}_V{self._boardVersion:0>7.3f}_SN{self._serialNumber:0>8}"
        self._uio.info(f"Setting assembly label to {newAssy}.")
        url=f"http://{self._ipAddress}{FactorySetup.SET_CONFIG_CMD}?{FactorySetup.ASSY_KEY}={newAssy}"
        response = requests.get(url)
        self._checkResponse(response)

    def _initATM90E32Devs(self):
        url=f"http://{self._ipAddress}/init_atm90e32_devs"
        response = requests.get(url)
        self._checkResponse(response)

    def _calVoltageOffset(self, ct):
        """@brief Calibrate voltage offsets. To use this the voltage level fed to the ATM90E32 devices
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

        while True:
            regValue = FactorySetup.FromSigned(ampsOffset,16)
            url=f"http://{self._ipAddress}/set_config?{cfgAttr}={regValue}"
            response = requests.get(url)
            self._checkResponse(response)

            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()

            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]

            amps = ctStatsDict[FactorySetup.IRMS]
            self._uio.info(f"Offset amps={amps}, regValue={regValue:04x}")
            if amps > 0:
                ampsOffset=ampsOffset-offsetDelta

            elif amps < 0:
                ampsOffset=ampsOffset+offsetDelta

            elif amps == 0.0:
                break


    def _calVoltageGain(self, ct, maxError=0.5):
        """@brief Calibrate the voltage gain for the CT.
           @param ct The ct number 1 or 4 as only the first port on each ATM90E32 device can measure the voltage on the CT6 hardware.
           @param maxError The maximum error. If the error drops below this value then we say the voltage is calibrated."""
        self._uio.info("")
        acVoltage = self._uio.getFloatInput("Enter the AC RMS voltage")
        while True:
            cfgDict = self._getConfigDict()
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]
            voltageMeasurement = ctStatsDict["VRMS"]
            voltageError = abs(voltageMeasurement-acVoltage)
            self._uio.info(f"Read {voltageMeasurement:.2f} Volts (error = {voltageError:.2f} Volts)")
            if voltageError < maxError:
                break

            if ct == 1:
                configKey = FactorySetup.CS4_VOLTAGE_GAIN_KEY
            elif ct == 4:
                configKey = FactorySetup.CS0_VOLTAGE_GAIN_KEY
            else:
                raise Exception(f"{ct} must be 1 or 4 to calibrate.")

            # Get the ATM90E32 voltage gain.
            voltageGain = cfgDict[configKey]
            errorFactor = acVoltage/voltageMeasurement
            newVoltgeGain = int(errorFactor * voltageGain)
            # Apply 16 bit reg limits (1000 from endstop)
            if newVoltgeGain > 65535:
                newVoltgeGain = 64535
            elif newVoltgeGain < 0:
                newVoltgeGain=1000
            url=f"http://{self._ipAddress}/set_config?{configKey}={newVoltgeGain}"
            response = requests.get(url)
            self._checkResponse(response)
            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()

        self._uio.info(f"CT{ct} voltage calibration complete.")

    def _calCurrentGain(self, ct, maxError=0.01):
        """@brief Calibrate the current gain for the CT.
           @param ct The ct number1,2,3,4,5 or 6.
           @param maxError The maximum error. If the error drops below this value then we say the voltage is calibrated."""
        self._uio.info("")
        self._uio.getInput("Ensure an AC load drawing at least 5 amps is connected and press RETURN")

        acAmps = self._uio.getFloatInput("Enter the AC RMS current in amps")
        while True:
            cfgDict = self._getConfigDict()
            statsDict = self._getStatsDict()
            ctStatsDict = statsDict[f"CT{ct}"]
            ampsMeasurement = ctStatsDict["IRMS"]
            currentError = abs(ampsMeasurement-acAmps)
            self._uio.info(f"Read {ampsMeasurement:.2f} Amps (error = {currentError:.2f} Amps)")
            if currentError < maxError:
                break

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

            # Get the ATM90E32 voltage gain.
            currentGain = cfgDict[configKey]
            errorFactor = acAmps/ampsMeasurement
            newCurrentGain = int(errorFactor * currentGain)
            # Apply 16 bit reg limits (1000 from endstop)
            if newCurrentGain > 65535:
                newCurrentGain = 64535
            elif newCurrentGain < 0:
                newCurrentGain=1000
            url=f"http://{self._ipAddress}/set_config?{configKey}={newCurrentGain}"
            response = requests.get(url)
            self._checkResponse(response)
            # Init the ATM90E32 devices from the config just updated
            self._initATM90E32Devs()

        self._uio.info("")
        self._uio.info(f"CT{ct} current calibration complete.")
        self._uio.getInput("DISCONNECT the AC load and press RETURN")

    def setCT6SerialNumber(self):
        """@brief Set the serial number of a CT6 device."""
        self._checkAddress()
        self._uio.info(f'Factory setup and calibration of CT6 unit ({self._ipAddress}).')
        cfgDict = self._getConfigDict()

        self._setAssyNumber(cfgDict)

        self._uio.info("Successfully set the unit serial number.")

    def calibrate(self):
        """@brief Perform the user configuration of a CT6 device."""
        self._checkAddress()
        self._uio.info(f'Factory setup and calibration of {self._ipAddress}')

        # Add prompt for user to connect CT to each channel as its calibrated
        for ct in range(1,7):
            self._uio.info("")
            self._uio.info("Ensure no AC load is connected.")
            self._uio.getInput(f"Connect an SCT013_100A current transformer (CT) to port {ct} and press RETURN")

            if ct == 1:
                self._uio.info("Calibrating U5 VOLTAGE gain.")
                self._calVoltageGain(ct)
                # Currently we dont plan to calibrate out the Voltage offset to reasd 0 volts.
                # As the CT6 hardware is powered by an AC adaptor which feeds the measured AC voltage.
                # self._uio.info("Calibrating U5 VOLTAGE offset.")
                # self._calVoltageOffset(1)

            if ct == 4:
                self._uio.info("Calibrating U4 VOLTAGE gain.")
                self._calVoltageGain(ct)
                # Currently we don't plan to calibrate out the Voltage offset to reasd 0 volts.
                # As the CT6 hardware is powered by an AC adaptor which feeds the measured AC voltage.
                # self._uio.info("Calibrating U4 VOLTAGE offset.")
                # self._calVoltageOffset(4)

            self._uio.info(f"Calibrating CT{ct} CURRENT gain.")
            self._calCurrentGain(ct)
            self._uio.info(f"Calibrating CT{ct} CURRENT offset.")
            self._calCurrentOffset(ct)

        self._uio.info("CT6 unit calibration successful.")
        
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
                           
    def _validateAssy(self, assyNumber):
        """@brief Validate the assembly number.
           @param The board assembly number to validate."""
        assyNumber = self._stripControlChar(assyNumber)            
        if assyNumber.startswith(FactorySetup.CT6_BOARD_ASSY_NUMBER_STR):
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
            
        else:
            raise Exception(f"The assembly label must start {FactorySetup.CT6_BOARD_ASSY_NUMBER_STR}: <{assyNumber}>")
        
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
        return f"/media/{self._username}/RPI-RP2"
    
    @retry(Exception, tries=3, delay=1)
    def _erasePicoWFlash(self):
        """@brief Erase flash on the microcontroller (Pico W)"""
        self._uio.info("Ensure the USB Pico W is connected to this PC.")
        self._uio.info("Hold the button down on the Pico W and power up the CT6 device.")
        picoPath = self._getPicoPath()
        sourcePath = "../picow/tools/picow_flash_images/flash_nuke.uf2"
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
        self._uio.info(f"Waiting for RPi Pico W to restart.")
        picoPath = self._getPicoPath()
        while True:
            if exists:
                if os.path.isdir(picoPath):
                    break
            else:
                if not os.path.isdir(picoPath):
                    break

            sleep(0.25)

    @retry(Exception, tries=3, delay=1)
    def _loadMicroPython(self):
        """@brief Load Micropython image onto the RPi Pico W."""
        self._uio.info("Ensure the USB Pico W is connected to this PC.")
        self._uio.info("Hold the button down on the Pico W and power up the CT6 device.")
        picoPath = self._getPicoPath()
        sourcePath = "../picow/tools/picow_flash_images/firmware.uf2"
        destinationPath = picoPath
    
        self._waitForPicoPath(exists=True)
            
        self._uio.info("Loading micropython image onto the RPi Pico W")
        self._uio.info(f"Copying {sourcePath} to {destinationPath}")
        shutil.copy(sourcePath, destinationPath)
        
        self._waitForPicoPath(exists=False)
        sleep(2)
        self._checkMicroPython()
        
    def _openSerialPort(self):
        """@brief Open the selected serial port."""
        self._serialPort = self._getSerialPort("/dev/ttyA")
        self._ser = serial.serial_for_url(self._serialPort, do_not_open=True, exclusive=True)
        self._ser.baudrate = 115200
        self._ser.bytesize = 8
        self._ser.parity = 'N'
        self._ser.stopbits = 1
        self._ser.rtscts = False
        self._ser.xonxoff = False
        self._ser.open()
                    
    def _getSerialPort(self, matchText):
        """@brief Get a serial port that should be connected to the RPi Pico W
           @return The serial device string."""
        matchingSerialPortList = []
        # This list of serial ports may be empty whiule the RPi pico W restarts.
        while True:
            serialPortList = FactorySetup.GetSerialPortList()
            if len(serialPortList) > 0:
                break
            
        for serialPort in serialPortList:
            if serialPort.device.find(matchText) >= 0:
                matchingSerialPortList.append(serialPort.device)
                
        if len(matchingSerialPortList) > 1:
            raise Exception(f'Multiple serial port found: {",".join(matchingSerialPortList)}')
        
        return matchingSerialPortList[0]
        
    def _checkMicroPython(self, closeSerialPort=True):
        """@brief Check micropython is loaded.
           @param closeSerialPort If True then close the serial port on exit."""
        self._uio.debug("_checkMicroPython(): START")
        try:
            self._openSerialPort()
            timeToSendCTRLC = time()

            while True:
                now = time()
                # Send CTRL C periodically
                if now >= timeToSendCTRLC:
                    # Send CTRL B
                    self._ser.write(b"\03\02")
                    self._uio.debug("Sent CTRL C/CTRL B")
                    # Send CTRL C every 3 seconds
                    timeToSendCTRLC = now+3
                if self._ser.in_waiting > 0:
                    data = self._ser.read_until()
                    if len(data) > 0:
                        data=data.decode()
                        self._uio.debug(f"Serial data = {data}")
                        if data.startswith("MicroPython"):
                            self._uio.info(f"Micropython loaded: {data}")
                            break
                else:
                    sleep(0.1)
                    
        finally:
            if closeSerialPort and self._ser:
                self._ser.close()
                
        self._uio.debug("_checkMicroPython(): STOP")
        
    def _loadCT6App(self):
        """@brief Load the CT6 code onto the CT6 hardware."""
        self._uio.debug("_loadCT6App(): START")
        ct6_mfg_tool_debug = self._uio.debug
        # Use the tool in the picow folder to load the app onto the RPi Pico W MCU
        class MCUOptions(object):
            """@brief Setup command line options for the MCULoader."""
            def __init__(self):
                self.esp32              = False
                self.picow              = True
                self.load               = True
                self.remove             = False
                self.factory_reset      = False
                self.local_config       = True
                self.disable_app1_start = True
                self.start_app1         = False
                self.view               = False
                self.debug              = ct6_mfg_tool_debug
        options = MCUOptions()
        mcuLoader = MCULoader(options)
        mcuLoader.load()
        
        ipAddress = self._runApp1()
                
        self._uio.debug("_loadCT6App(): STOP")
        return ipAddress
    
    def _runApp1(self):
        """@brief Run app1 on the CT6 unit.
           @return the IP address that the CT6 obtains when registered on the WiFi."""
        ipAddress = None
        sleep(1)
        self._uio.info("Running APP1 on the CT6 unit. Waiting for WiFi connection...")
        try:
            self._openSerialPort()
            self._ser.write(b"import main\r")
            while True:
                data = self._ser.read_until()
                if len(data) > 0:
                    data=data.decode()
                    if len(data) > 0:
                        lines = data.split("\n")
                        for line in lines:
                            line=line.rstrip("\r\n")
                            self._uio.debug(line)
                            
                    pos = data.find(", IP Address=")
                    if pos != -1:
                        elems = data.split("=")
                        if len(elems) > 0:    
                            ipAddress = elems[-1].rstrip("\r\n")
                            self._uio.info("Waiting for App to startup on CT6 device.")
                            sleep(4)
                            break
        finally:
            if self._ser:
                self._ser.close()
                
        return ipAddress

    def _initLogFile(self):
        """@brief Init the test log file to record the test an calibration of the unit."""
        timeStamp = timeStamp=strftime("%Y%m%d%H%M%S", localtime()).lower()
        
        logFileName = f"ASY{self._assyNumber:04}_V{self._boardVersion:07.4f}_SN{self._serialNumber:08d}_{timeStamp}.log"
        self._uio.logAll(True)
        self._uioLogFile = f"{self._logPath}/{logFileName}"
        self._uio.setLogFile(self._uioLogFile)
        
    def _testSwitches(self):
        """@brief Test the switches on the CT6 board."""
        self._uio.info("Hold down the WiFi switch on the CT6 board.")
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
        finally:
            if self._ser:
                self._ser.close()
        self._uio.info("The WiFi switch is working. Release the WiFi switch.")
        
        self._uio.info("Press and release the reset switch on the CT6 board.")
        self._waitForWiFiDisconnect(showMessage=False)
        self._waitForWiFiReconnect()
        
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
        self._waitForWiFiReconnect()        
            
    def scanBoardLabels(self):
        """@brief Scan the board assembly and serial number labels.
           @return A tuple containing the assembly number followed by the serial number."""
        assyNumber = self._uio.getInput("Scan the board assembly number")
        self._validateAssy(assyNumber)
        
        serialNumber = self._uio.getInput("Scan the board serial number")
        self._validateSN(serialNumber)
        
        return (assyNumber, serialNumber)
        
    def _saveFactoryConfig(self):
        """@brief Save the factor configuration. Should only be called after
           the unit serial number has been set and the unit is calibrated."""
        self._uio.info("Saving the factory configuration file to the CT6 unit.")
        url=f"http://{self._ipAddress}/save_factory_cfg"
        self._runRESTCmd(url)

    def _storeFileContents(self, filename):
        """@brief Get the contents of a file from the unit.
           @param filename The name of the file on the CT6 unit to retrieve."""
        self._uio.info(f"Get {filename} from {self._ipAddress}.")
        url=f"http://{self._ipAddress}/get_file?file={filename}"
        response = self._runRESTCmd(url)
        rDict = response.json()
        fileContents = rDict[filename]
        self._uio.info(f"Save to {filename} from {self._ipAddress}.")
        
        localFile = self._uioLogFile.replace(".log", "_")
        localFile += filename
        with open(localFile, 'w') as fd:
            fd.write(fileContents)
        self._uio.info(f"Saved to {localFile}")
                
    def _storeConfig(self):
        """@brief Store the configuration files from the unit tested in the local folder along with the test logs."""
        self._storeFileContents(FactorySetup.CT6_MACHINE_CONFIG_FILE)
        self._storeFileContents(FactorySetup.CT6_FACTORY_CONFIG_FILE)
        
    def _cleanConfig(self):
        """@brief Set the config to the state required to ship the CT6 unit from the factory.
                  The WiFi config is reset to the default value."""
        self._uio.info(f"Set factory CT6 WiFi.")
        url=f"http://{self._ipAddress}/reset_wifi_config"
        return self._runRESTCmd(url)
 
    def _initTest(self):
        """@brief Initialise the test. This includes the user inputing the assembly number and serial number of the UUT (unit under test)."""
        self._ensureLogPathExists()
        
        self.scanBoardLabels()
                
        self._initLogFile()

        self._showUUT()

    def _loadCT6Application(self):
        """@brief Load the application software onto the CT6 device."""
        ipAddress = self._loadCT6App() 
        self.setIPAddress(ipAddress)
        # The loading process should load the WiFi at the MFG site.
        # Therefore wait for the WiFi to connect.
        self._waitForWiFiReconnect() 

    def _setDefaultConf(self):
        """@brief Set the factory default configuration."""
        self._saveFactoryConfig()        
        self._cleanConfig()
        self._storeConfig()

    def _getFileContents(self, filename):
        """@brief Get the contents of a text file on the CT6 unit using the serial ports python prompt.
           @param filename The filename of the file to read.
           @return The file contents of None if we failed to read the file."""
        line = None
        fileContents = None
        startTime = time()
        while fileContents is None and time() < startTime+2:
            cmdLine = f'fd = open("{filename}") ; lines = fd.readlines() ; fd.close() ; print(lines[0])\r'
            self._ser.write(cmdLine.encode())
            sleep(0.25) # Give the MCU time to respond
            bytesAvailable = self._ser.in_waiting
            if bytesAvailable > 0:
                data = self._ser.read(bytesAvailable)
                if len(data) > 0:
                    data=data.decode()
                    lines = data.split("\n")
                    for line in lines:
                        if line.startswith('{"'):
                            fileContents = line
                            break
        return line
        
    def _storeCT6LogFile(self, filename):
        """@brief Get the contents of a text file on the CT6 unit using the serial ports python prompt and save a copy of the file locally.
                  _checkMicroPython() must have been successfully called prior to calling this method.
           @param filename The filename of the file to read.
           @return The contents of the file or None if we failed to read the file."""
        fileContents = self._getFileContents(filename)
        if fileContents:
            localFile = self._uioLogFile.replace(".log", "_")
            localFile += filename
            self._uio.info(f"Saving to {localFile}")
            with open(localFile, 'w') as fd:
                fd.write(fileContents)
            self._uio.info(f"Saved to {localFile}")
        return fileContents
        
    def _loadJSONFile(self, filename):
        """@brief Load a dict from a JSON formatted file.
           @param filename The file to read from."""
        self._uio.debug(f"Loading WiFi config from {filename}")
        with open(filename) as fd:
            fileContents = fd.read()
            return json.loads(fileContents)
            
    def _saveDictToJSONFile(self, theDict, filename):
        """@brief Save a dict to a file (JSON format)."""
        self._uio.debug(f"Saving to {filename}")
        with open(filename, 'w') as fd:
            json.dump(theDict, fd, ensure_ascii=False)
        
    def _handleHouseWiFiConfigFileNotFound(self):
        """@brief Called to handle the situation where the FactorySetup.HOUSE_WIFI_CFG_FILE file is not present."""
        HOUSE_WIFI_TEMPLATE = '{"WIFI": {"MODE": "STA", "SSID": "SSID_VALUE", "PASSWD": "PASSWORD_VALUE", "CHANNEL": 3, "WIFI_CFG": 1 } }' 
        ssid = self._uio.getInput("The house WiFi SSID: ")
        password = self._uio.getInput("The house WiFi password: ")
        HOUSE_WIFI_TEMPLATE = HOUSE_WIFI_TEMPLATE.replace('SSID_VALUE', ssid)
        HOUSE_WIFI_TEMPLATE = HOUSE_WIFI_TEMPLATE.replace('PASSWORD_VALUE', password)
        with open(FactorySetup.HOUSE_WIFI_CFG_FILE, 'w') as fd:
            fd.write(HOUSE_WIFI_TEMPLATE)
        self._uio.info(f"Created {FactorySetup.HOUSE_WIFI_CFG_FILE}")
    
    def _runRShell(self, cmdList, picow=True):
        """@brief Run an rshell command file.
           @param cmdList A list of commands to execute.
           @param picow True if loading a Pico W MSU. False for ESP32."""
        cmdFile = FactorySetup.RSHELL_CMD_LIST_FILE
        # Create the rshell cmd file.
        fd = open(cmdFile, 'w')
        for line in cmdList:
            fd.write(f"{line}\n")
        fd.close()
        if picow:
            rshellCmd = "rshell --rts 1 --dtr 1 --timing -p {} --buffer-size 512 -f {}".format(self._serialPort, cmdFile)
        else:
            rshellCmd = "rshell --rts 0 --dtr 0 --timing -p {} --buffer-size 512 -f {}".format(self._serialPort, cmdFile)
        self._uio.debug(f"EXECUTING: {rshellCmd}")
        check_call(rshellCmd, shell=True, stdout=DEVNULL, stderr=STDOUT)
        
    def _updateWiFiConfig(self):
        """@brief Update the WiFi config on the CT6 unit from the house wifi config file to
                  ensure it will connect to the wiFi network when the software is started."""
        # Attempt to connect to the board under test python prompt
        self._checkMicroPython(closeSerialPort=False)
        wifiCfgDict = self._loadJSONFile(FactorySetup.HOUSE_WIFI_CFG_FILE)
        # Save the config files from the CT6 unit to the log folder
        thisMachineFileContents = self._storeCT6LogFile(FactorySetup.CT6_MACHINE_CONFIG_FILE)
        if thisMachineFileContents is None:
            raise Exception(f"The CT6 board does not have a {FactorySetup.CT6_MACHINE_CONFIG_FILE} file. Run a MFG test to recover.")
        thisMachineDict = json.loads(thisMachineFileContents)
        fc = self._storeCT6LogFile(FactorySetup.CT6_FACTORY_CONFIG_FILE)
        if fc == None:
            self._uio.warn(f"The CT6 board does not have a {FactorySetup.CT6_FACTORY_CONFIG_FILE} file.")
        # Set the house WiFi configuration in the machine config dict
        thisMachineDict[FactorySetup.WIFI_CFG_KEY] = wifiCfgDict[FactorySetup.WIFI_CFG_KEY]
        #Save the machine config to a local file.
        self._saveDictToJSONFile(thisMachineDict, FactorySetup.CT6_MACHINE_CONFIG_FILE)
        if self._ser:
           self._ser.close()
           self._ser = None
        self._runRShell((f"cp {FactorySetup.CT6_MACHINE_CONFIG_FILE} /pyboard/",) ) 
           
    def _initTestOnly(self):
        """@brief Initialise when only testing the CT6 unit, not loading code or calibrating.
                  If not performing a MFG test process we just run the tests. 
                  In this case at this point we need to 
                  - Save the this.machine.cfg and factory.cfg files from the unit in the state they were received.
                  - Set the WiFi config to allow the unit to register on the local WiFi network.
                  - Register on the local WiFi network.
                  - Read tThe IP address the CT6 unit is registered on."""
        self._updateWiFiConfig()
        self._ipAddress = self._runApp1()
        
    def _displayTest(self):
        """@brief Check the display is working."""
        self._uio.info("Is the display showing AC voltage ?")
        displayWorking = self._uio.getBoolInput("Is the display showing AC voltage y/n")
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


    def powerCycleReliabilityTest(self, max=100):
        """@brief Perform a reliability test on the power cycle mechanism.
           @param max The maximum number of retries."""
        count = 0
        while count < max:
            self._testPowerCycle()
            count+=1
            self._uio.info(f"Power cycle passed: {count}")
            
        self._uio.info(f"Power cycle passed {count} times.")
        
    def _getFactoryConfFile(self):
        """@brief Get the name of the factory.conf file to load onto the CT6 unit.
                  _initTest must be called before calling this method.
           @return The absolute filename of the factory.cfg file."""
        factoryConfigLogFile = self._uio.getInput("The filename of the factory.cfg file to load")
        if not factoryConfigLogFile.endswith(FactorySetup.CT6_FACTORY_CONFIG_FILE):
            raise Exception(f"The log filename must end {FactorySetup.CT6_FACTORY_CONFIG_FILE}")
        # Check that the log file is for the UUT.
        filenamePrefix = f"ASY{self._assyNumber:04}_V{self._boardVersion:07.4f}_SN{self._serialNumber:08d}_"
        if not factoryConfigLogFile.startswith(filenamePrefix):
            raise Exception(f"The log filename entered does not start {filenamePrefix}")
        # Check that the file is present in the log dir 
        absLogFilename = os.path.join(self._logPath, factoryConfigLogFile)
        if not os.path.isfile(absLogFilename):
            raise Exception(f"{absLogFilename} file not found.")
        return absLogFilename
        
    def restoreFactoryConfig(self):
        """@brief Restore the last factory config file to the CT6 unit."""
        self._initTest()
        self._updateWiFiConfig()
        srcFactoryCfgFile = self._getFactoryConfFile()
        # Attempt to connect to the board under test python prompt
        self._checkMicroPython(closeSerialPort=False)
        self._runRShell((f"cp {srcFactoryCfgFile} /pyboard/{FactorySetup.CT6_FACTORY_CONFIG_FILE}",))
        self._ipAddress = self._runApp1()
        self._uio.info("Loaded the factory.cfg data to the CT6 board.")
        
    def mfgTest(self):
        """@brief Perform a manufacturing test."""
        # Create all the test cases
        ct6Testing = TestCaseBase(self._uio)
        ct6Testing.addTestCase(1000, "Enter ASSY and S.N.", self._initTest)
        
        if self._options.test:
            ct6Testing.addTestCase(1500, "RMA test initialisation.", self._initTestOnly)

        else:
            ct6Testing.addTestCase(2000, "Erase Pico W flash memory.", self._erasePicoWFlash)
            ct6Testing.addTestCase(3000, "Load MicroPython onto Pico W flash memory.", self._loadMicroPython)
            ct6Testing.addTestCase(4000, "Load the CT6 application software.", self._loadCT6Application)

        ct6Testing.addTestCase(4500, "Temperature test.", self._temperatureTest)
        ct6Testing.addTestCase(5000, "Switch test.", self._testSwitches)
        ct6Testing.addTestCase(6000, "Power cycle circuit test.", self._testPowerCycle)
        ct6Testing.addTestCase(6500, "Display test.", self._displayTest)
        
        if not self._options.test:
            ct6Testing.addTestCase(7000, "Set assembly number and serial number.", self.setCT6SerialNumber)
            if not self._options.no_cal:
                ct6Testing.addTestCase(8000, "Perform calibration process.", self.calibrate)
            ct6Testing.addTestCase(9000, "Load factory default configuration.", self._setDefaultConf)
            
        ct6Testing.executeTestCases()
                
def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="A tool to perform configuration and calibration functions on a CT6 power monitor.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",            action='store_true', help="Enable debugging.")
        parser.add_argument("-a", "--address",          help="The IP address of the unit.", default=None)
        parser.add_argument("-s", "--serialn",          action='store_true', help="Set the hardware serial number.")
        parser.add_argument("-c", "--cal",              action='store_true', help="Factory setup and calibration only.")      
        parser.add_argument("-n", "--no_cal",           action='store_true', help="Omit the calibration step from the factory test.")      
        parser.add_argument("-p", "--power_cycle",      action='store_true', help="Perform a number of power cycle tests to check the reliability of the power cycling feature.")
        parser.add_argument("-t", "--test",             action='store_true', help="Test only. This can be used on boards that are returned as faulty.")
        parser.add_argument("-r", "--restore",          action='store_true', help="Restore the factory config to the CT6 unit.")

        options = parser.parse_args()

        uio.enableDebug(options.debug)

        factorySetup = FactorySetup(uio, options)

        if options.cal:
            factorySetup.setIPAddress(options.address)
            factorySetup.calibrate()

        elif options.serialn:
            factorySetup.scanBoardLabels()
            # The user must enter the address manually.
            factorySetup.setIPAddress(options.address)
            factorySetup.setCT6SerialNumber()

        elif options.power_cycle:
            factorySetup.setIPAddress(options.address)
            factorySetup.powerCycleReliabilityTest()
            
        elif options.restore:
            factorySetup.restoreFactoryConfig()

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
