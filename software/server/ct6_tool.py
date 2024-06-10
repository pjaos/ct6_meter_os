#!/usr/bin/env python3

import argparse
import requests
import urllib
import socket
import json
import os
import serial
import tempfile
import shutil
import traceback
import platform

from    copy import copy
from   pyflakes import reporter as modReporter
from   pyflakes.api import checkRecursive

from   serial.tools.list_ports import comports
from   time import sleep, time
from   zipfile import ZipFile
from   threading import Thread

import ping3
import hashlib

from   p3lib.uio import UIO
from   p3lib.helper import logTraceBack

from   lib.base_constants import BaseConstants

from   subprocess import check_output, check_call, DEVNULL, STDOUT

class CT6Base(BaseConstants):
    """@brief Base class for CT6 device operations."""

    
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
    
    @staticmethod
    def GetInstallFolder():
        """@return The folder where the apps are installed."""
        installFolder = os.path.dirname(__file__)
        if not os.path.isdir(installFolder):
            raise Exception(f"{installFolder} folder not found.")
        return installFolder
    
    @staticmethod
    def GetSrcPicoWFolder():
        """@return The folder where the MCU code is held."""
        installFolder = CT6Base.GetInstallFolder()
        picowFolder = os.path.join(installFolder, "picow")
        if not os.path.isdir(picowFolder):
            raise Exception(f"{picowFolder} folder not found.")
        return picowFolder

    @staticmethod
    def GetApp1Folder():
        """@return the picow/app1 folder/"""
        picowFolder = CT6Base.GetSrcPicoWFolder()
        app1Folder = os.path.join(picowFolder, 'app1')
        if not os.path.isdir(app1Folder):
            raise Exception(f"{app1Folder} folder not found.")
        return app1Folder

    @staticmethod
    def GetTempFolder():
        """@return The temp storage folder."""
        tempFolder = tempfile.gettempdir()
        if any(platform.win32_ver()):
            # On Windows we use the install folder as it should be writable
            tempFolder = os.path.dirname(__file__)
        return tempFolder
    
    HOUSE_WIFI_CFG_FILE         = os.path.join(os.path.join(os.path.expanduser('~')), "ct6_house_wifi.cfg" )
    WIFI_CFG_KEY                = "WIFI"
    CT6_MACHINE_CONFIG_FILE     = "this.machine.cfg"
    CT6_FACTORY_CONFIG_FILE     = "factory.cfg"
    RSHELL_CMD_LIST_FILE        = os.path.join( GetTempFolder(), "cmd_list.cmd")
    BLUETOOTH_ON_KEY            = 'BLUETOOTH_ON_KEY'
    GET_FILE_CMD                = "/get_file"
    SEND_FILE_CMD               = "/send_file"
    ASSY_KEY                    = 'ASSY'

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
    LINE_FREQ_HZ_KEY            = "LINE_FREQ_HZ"
    FACTORY_CONFIG_KEYS         = [CT1_IGAIN_KEY,
                                   CT2_IGAIN_KEY,
                                   CT3_IGAIN_KEY,
                                   CT4_IGAIN_KEY,
                                   CT5_IGAIN_KEY,
                                   CT6_IGAIN_KEY,
                                   CT1_IOFFSET,
                                   CT2_IOFFSET,
                                   CT3_IOFFSET,
                                   CT4_IOFFSET,
                                   CT5_IOFFSET,
                                   CT6_IOFFSET,
                                   ASSY_KEY,
                                   CS0_VOLTAGE_GAIN_KEY,
                                   CS4_VOLTAGE_GAIN_KEY,
                                   LINE_FREQ_HZ_KEY]
    TCP_PORT                    = 80
    LINUX_MPY_CMDLINE_PREFIX = "python3 -m mpy_cross "
    # When pipenv is executed on windows the python comand must be executed to ensure the 
    # env is loaded.
    WINDOWS_MPY_CMDLINE_PREFIX = "python -m mpy_cross "

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        self._uio       = uio
        self._options   = options   
        self._ipAddress = None          # The IP address for the UUT
        self._ser       = None      
        self._windowsPlatform = any(platform.win32_ver())
        # Define the prefix for using the micro python X compiler
        if self._windowsPlatform:
            self._mpyCmdLinePrefix = MCULoader.WINDOWS_MPY_CMDLINE_PREFIX
        else:
            self._mpyCmdLinePrefix = MCULoader.LINUX_MPY_CMDLINE_PREFIX
        self._initFolders()
        self._ensureMCUCodeAvailable()

    def _info(self, msg):
        """@brief Display an info level message.
           @param msg The message to display."""
        if self._uio:
            self._uio.info(msg)

    def _warn(self, msg):
        """@brief Display a warning level message.
           @param msg The message to display."""
        if self._uio:
            self._uio.warn(msg)

    def _error(self, msg):
        """@brief Display an error level message.
           @param msg The message to display."""
        if self._uio:
            self._uio.error(msg)

    def _debug(self, msg):
        """@brief Display a debug level message.
           @param msg The message to display."""
        if self._uio:
            self._uio.debug(msg)

    def _initFolders(self):
        """@brief Init the folders used by various tools."""
        self._tempFolder = CT6Base.GetTempFolder()
        self._installFolder = CT6Base.GetInstallFolder()
        srcPicoWFolder = CT6Base.GetSrcPicoWFolder()
        if not os.path.isdir(srcPicoWFolder):
            raise Exception(f"{srcPicoWFolder} folder not found.")
     
        if self._windowsPlatform:
            # On windows platforms the src folder should be writable.
            # Therefore just remove the drive as if this is left in rshell commands fail.
            self._tempFolder = '/' + self._tempFolder[3:]
            destPicoWFolder = '/' + srcPicoWFolder[3:]
            self._picowFolder = destPicoWFolder
        else:
            # The picow folder must be writable as we create .mpy files alongside the .py MCU files.
            # On Linux platform this may not be writable so we use a temp folder.
            destPicoWFolder = os.path.join(self._tempFolder, "picow")
            if os.path.isdir(destPicoWFolder):
                shutil.rmtree(destPicoWFolder)
            shutil.copytree(srcPicoWFolder, destPicoWFolder)
            self._picowFolder = destPicoWFolder
            
        self._app1Folder =  os.path.join(destPicoWFolder, "app1")
        self._upgradeAppRoot = self._app1Folder
        if not os.path.isdir(self._app1Folder):
            raise Exception(f"{self._app1Folder} folder not found.")
        
        tPath = os.path.join(destPicoWFolder, "tools")
        self._uf2ImagePath = os.path.join(tPath, "picow_flash_images")
        if not os.path.isdir(self._uf2ImagePath):
            raise Exception(f"{self._uf2ImagePath} folder not found.")

        self._info(f"Install Folder:  {self._installFolder}")
        self._info(f"MCU Code Folder: {self._picowFolder}")

        if not os.path.isdir(self._picowFolder):
            raise Exception(f"{self._picowFolder} folder not found.")
        
        if not os.path.isdir(self._app1Folder):
            raise Exception(f"{self._app1Folder} folder not found.")
        
    def _ensureMCUCodeAvailable(self):
        """@brief Ensure we have access to the RPI Pico W code."""           
        requiredFolder = self._picowFolder
        if not os.path.isdir(requiredFolder):
            srcFolder = requiredFolder
            if not os.path.isdir(srcFolder):
                raise Exception(f"{srcFolder} folder not found. This contains the RPi Pico W MCU code.")

            # The git picow linux link on windows appears as a file
            if os.path.isfile(requiredFolder):
                # Move it out of the way
                backupFolder = requiredFolder + ".link"
                if os.path.isfile(backupFolder):
                    os.remove(backupFolder)
                os.rename(requiredFolder, backupFolder)

            shutil.copytree(srcFolder, requiredFolder)

    def _checkAddress(self):
        """@brief Check that the command line adddress option has been set."""
        if self._ipAddress == None:
            if self._options.address == None:
                raise Exception("No address defined. Use the -a/--address command line option to define the CT6 unit address.")
            else:
                self._ipAddress = self._options.address

    def _getConfigDict(self):
        """@brief Get the config dict from the device.
           @return The config dict."""
        self._info(f"Reading configuration from {self._ipAddress}")
        url=f"http://{self._ipAddress}/get_config"
        response = requests.get(url)
        return response.json()

    def _getStatsDict(self):
        """@brief Get the stats dict from the device.
           @return The stats dict."""
        self._info(f"Reading stats from {self._ipAddress}")
        url=f"http://{self._ipAddress}/get_stats"
        response = requests.get(url)
        return response.json()

    def _checkResponse(self, response):
        """@brief Check we don't have an error response."""
        rDict = response.json()
        if "ERROR" in rDict:
            msg = rDict["ERROR"]
            raise Exception(msg)
        
    def setIPAddress(self, ipAddress):
        """@brief Set the IP address of the CT6 unit being tested."""
        if ipAddress is None:
            raise Exception("Use the -a/--address argument to define the CT6 IP address.")
        self._ipAddress = ipAddress
        self._debug(f"self._ipAddress={self._ipAddress}")

    def doPing(self, address):
        """@brief Attempt to ping the address.
           @return The time number of seconds it took for the ping packet to be returned or None if no ping packet returned."""
        pingSec = None
        if self._windowsPlatform:
            # On windows we can use the python ping3 module
            pingSec = ping3.ping(address)
        else:
            # On Linux the ping3 module gives 'Permission denied' errors for non root users
            # so we use the command line ping instead.
            try:
                startT = time()
                cmd = f"/usr/bin/ping -W 1 -c 1 {address} 2>&1 > /dev/null"
                check_call(cmd, shell=True)
                pingSec = time()-startT
            except:
                pass
        return pingSec
            
    def _waitForWiFiDisconnect(self, restartTimeout=60, showMessage=True):
        """@brief Wait for the CT6 unit to disconnect from the WiFi network.
           @param restartTimeout The number of seconds before an exception is thrown if the WiFi does not disconnect.
           @param showMessage If True show a message indicating we're waiting for a reboot."""
        if showMessage:
            self._info(f"Waiting for the CT6 unit  ({self._ipAddress}) to reboot.")
        startT = time()
        while True:
            pingSec = self.doPing(self._ipAddress)
            if pingSec is None:
                break

            if time() >= startT+restartTimeout:
                raise Exception("Timeout waiting for the device to reboot.")
        
            sleep(0.25)
            
    def _waitForPingSuccess(self, restartTimeout=60, pingHoldSecs = 3):
        """@brief Wait for a reconnect to the WiFi network.
           @param restartTimeout The number of seconds before an exception is thrown if the WiFi does not reconnect.
           @param pingHoldSecs The number of seconds of constant pings before we determine the WiFi has reconnected.
                               This is required because the Pico W may ping and then stop pinging before pinging 
                               again when reconnecting to the Wifi."""
        startT = time()
        pingRestartTime = None
        while True:
            pingSec = self.doPing(self._ipAddress)
            if pingSec is not None:
                if pingRestartTime is None:
                    pingRestartTime = time()

                if time() > pingRestartTime+pingHoldSecs:
                    break

            else:
                pingRestartTime = None

            if time() >= startT+restartTimeout:
                raise Exception(f"Timeout waiting for {self._ipAddress} to become pingable.")
            
            sleep(0.25)
            
        self._info(f"{self._ipAddress} ping success.")
        

    def _loadJSONFile(self, filename):
        """@brief Load a dict from a JSON formatted file.
           @param filename The file to read from."""
        self._debug(f"Loading WiFi config from {filename}")
        with open(filename) as fd:
            fileContents = fd.read()
            return json.loads(fileContents)
        
    def _saveDictToJSONFile(self, theDict, filename):
        """@brief Save a dict to a file (JSON format)."""
        self._debug(f"Saving to {filename}")
        with open(filename, 'w') as fd:
            json.dump(theDict, fd, ensure_ascii=False)
        
    def _getRShellCmd(self, port, cmdFile, picow=True):
        """@brief Get the RSHell command line.
           @param port The serial port to use.
           @param cmdFile The rshell command to execute.
           @param picow True if loading a Pico W MSU. False for ESP32."""
        if picow:
            rshellCmd = f'rshell --rts 1 --dtr 1 --timing -p {port} --buffer-size 512 -f "{cmdFile}"'
        else:
            rshellCmd = f'rshell --rts 0 --dtr 0 --timing -p {port} --buffer-size 512 -f "{cmdFile}"'
        return rshellCmd

    def _runRShell(self, cmdList):
        """@brief Run an rshell command file.
           @param cmdList A list of commands to execute."""
        cmdFile = CT6Base.RSHELL_CMD_LIST_FILE
        self._debug(f"Creating {cmdFile}")
        # Create the rshell cmd file.
        fd = open(cmdFile, 'w')
        for line in cmdList:
            fd.write(f"{line}\n")
        fd.close()
        rshellCmd = self._getRShellCmd(self._serialPort, cmdFile)
        self._debug(f"EXECUTING: {rshellCmd}")
        check_call(rshellCmd, shell=True, stdout=DEVNULL, stderr=STDOUT)
        
    def _openSerialPort(self, matchStr="/dev/ttyA"):
        """@brief Open the selected serial port.
           @param matchStr A string to match for any serial port found."""
        self._serialPort = self._getSerialPort(matchStr)
        self._debug(f"Attempting to open serial port {self._serialPort}")
        self._ser = serial.serial_for_url(self._serialPort, do_not_open=True, exclusive=True)
        self._ser.baudrate = 115200
        self._ser.bytesize = 8
        self._ser.parity = 'N'
        self._ser.stopbits = 1
        self._ser.rtscts = False
        self._ser.xonxoff = False
        self._ser.open()
        self._debug(f"Opened serial port {self._serialPort}")
                    
    def _getSerialPort(self, matchText, timeout=30):
        """@brief Get a serial port that should be connected to the RPi Pico W
           @param matchText The text to match the serial ports.
           @param timeout The timeout in seconds to wait for a serial port to appear.
           @return The serial device string."""
        self._info(f"Checking serial connections for CT6 device (timeout = {timeout} seconds).")
        # If windows then force a COM port
        if self._windowsPlatform:
            matchText = "COM"
        matchingSerialPortList = []
        # This list of serial ports may be empty while the RPi pico W restarts.
        startT = time()
        while True:
            serialPortList = CT6Base.GetSerialPortList()
            if len(serialPortList) > 0:
                break
            if time() > startT+timeout:
                raise Exception(f"{timeout} second timeout waiting for a serial port to appear.")
            # Don't spin to fast here
            sleep(0.1)
            
        for serialPort in serialPortList:
            if serialPort.device.find(matchText) >= 0:
                matchingSerialPortList.append(serialPort.device)

        if len(matchingSerialPortList) == 0:
            raise Exception('No RPi Pico W serial port detected.')
                        
        self._info("Checking that only one serial port is connected to this machine.")
        
        if len(matchingSerialPortList) > 1:
            raise Exception(f'Multiple serial ports detected: {",".join(matchingSerialPortList)}')
        
        self._info(f"Found {matchingSerialPortList[0]}")
        return matchingSerialPortList[0]
        
    def _checkMicroPython(self, closeSerialPort=True):
        """@brief Check micropython is loaded.
           @param closeSerialPort If True then close the serial port on exit.
           @return True on success."""
        success = False
        self._debug("_checkMicroPython(): START")
        try:
            try:
                self._openSerialPort()
                timeToSendCTRLC = time()
    
                while True:
                    now = time()
                    # Send CTRL C periodically
                    if now >= timeToSendCTRLC:
                        # Send CTRL B
                        self._ser.write(b"\03\02")
                        self._debug("Sent CTRL C/CTRL B")
                        # Send CTRL C every 3 seconds
                        timeToSendCTRLC = now+3
                    if self._ser.in_waiting > 0:
                        data = self._ser.read_until()
                        if len(data) > 0:
                            data=data.decode()
                            self._debug(f"Serial data = {data}")
                            if data.startswith("MicroPython"):
                                line = data.rstrip("\r\n")
                                self._info(f"CT6 Unit:  {line}")
                                success = True
                                break
                    else:
                        sleep(0.1)

            except serial.SerialException:
                self._debug(f"SerialException: {traceback.format_exc()}")
    
            except OSError:
                self._debug(f"SerialException: {traceback.format_exc()}")

        finally:
            if closeSerialPort and self._ser:
                self._ser.close()
                self._ser = None
                
        self._debug("_checkMicroPython(): STOP")
        return success
        
    def restart(self):
        """@brief Restart the CT6 unit via a machine.reset()"""
        try:
            self._checkMicroPython(closeSerialPort=False)
            self._ser.write(b"import machine ; machine.reset()\r")
        
        finally:
            if self._ser:
                self._ser.close()
                self._ser = None

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
    
    def _updateWiFiConfig(self):
        """@brief Update the WiFi config on the CT6 unit from the house wifi config file to
                  ensure it will connect to the wiFi network when the software is started.
           @return the configured SSID"""
        # Attempt to connect to the board under test python prompt
        self._checkMicroPython(closeSerialPort=False)
        wifiCfgDict = self._loadJSONFile(CT6Base.HOUSE_WIFI_CFG_FILE)
        thisMachineFileContents = self._getFileContents(CT6Base.CT6_MACHINE_CONFIG_FILE)
        if thisMachineFileContents is None:
            raise Exception(f"The CT6 board does not have a {CT6Base.CT6_MACHINE_CONFIG_FILE} file. Run a MFG test to recover.")
        self._debug(f"thisMachineFileContents=<{thisMachineFileContents}>")
        thisMachineDict = json.loads(thisMachineFileContents)
        fc = self._getFileContents(CT6Base.CT6_FACTORY_CONFIG_FILE)
        if fc == None:
            self._warn(f"The CT6 board does not have a {CT6Base.CT6_FACTORY_CONFIG_FILE} file.")
        # Set the house WiFi configuration in the machine config dict
        thisMachineDict[CT6Base.WIFI_CFG_KEY] = wifiCfgDict[CT6Base.WIFI_CFG_KEY]
        # Ensure bluetooth is turned off now we have configured the WiFi.
        thisMachineDict[CT6Base.BLUETOOTH_ON_KEY] = 0
        #Save the machine config to a local file.
        localMachineCfgFile = os.path.join(self._tempFolder, CT6Base.CT6_MACHINE_CONFIG_FILE)
        self._saveDictToJSONFile(thisMachineDict, localMachineCfgFile)
        if self._ser:
           self._ser.close()
           self._ser = None
        self._runRShell((f'cp "{localMachineCfgFile}" /pyboard/',) )
        return thisMachineDict[CT6Base.WIFI_CFG_KEY]['SSID']
        
    def _rebootUnit(self):
        """@brief reboot a CT6 unit."""
        self._info("Rebooting the MCU")
        # Attempt to connect to the board under test python prompt
        self._checkMicroPython(closeSerialPort=False)
        try:
            # Send the python code to reboot the MCU
            self._ser.write(b"import machine ; machine.reset()\r")
            self._info("Rebooted the MCU")
        except:
            pass
        if self._ser:
           self._ser.close()
           self._ser = None
           
    def _handleHouseWiFiConfigFileNotFound(self):
        """@brief Called to handle the situation where the CT6Base.HOUSE_WIFI_CFG_FILE file is not present."""
        ssid = self._uio.getInput("The local WiFi SSID: ")
        password = self._uio.getInput("The local WiFi password: ")
        self._storeWiFiCredentials(ssid, password)
         
    def _storeWiFiCredentials(self, ssid, password):
        """@brief Stroe the WiFi credentials locally.
           @param ssid The Wifi SSID/network.
           @param password The WiFi password."""
        HOUSE_WIFI_TEMPLATE = '{"WIFI": {"MODE": "STA", "SSID": "SSID_VALUE", "PASSWD": "PASSWORD_VALUE", "CHANNEL": 3, "WIFI_CFG": 1 } }'
        HOUSE_WIFI_TEMPLATE = HOUSE_WIFI_TEMPLATE.replace('SSID_VALUE', ssid)
        HOUSE_WIFI_TEMPLATE = HOUSE_WIFI_TEMPLATE.replace('PASSWORD_VALUE', password)
        with open(CT6Base.HOUSE_WIFI_CFG_FILE, 'w') as fd:
            fd.write(HOUSE_WIFI_TEMPLATE)
        self._info(f"Created {CT6Base.HOUSE_WIFI_CFG_FILE}")

    def _runApp(self, waitForIPAddress=True):
        """@brief Run the CT6 firmware on the CT6 unit.
           @param waitForIPAddress If True wait for an IP address to be allocated to the unit.
           @return The IP address that the CT6 obtains when registered on the WiFi if waitForIPAddress == True or None if not."""
        ipAddress = None
        sleep(1)
        self._info("Running APP1 on the CT6 unit. Waiting for WiFi connection...")
        try:
            try:
                self._openSerialPort()
                self._ser.write(b"import main\r")
                while True:
                    availableByteCount = self._ser.in_waiting
                    if availableByteCount == 0:
                        sleep(0.05)
                        continue
                    data = self._ser.read(availableByteCount)
                    if len(data) > 0:
                        data=data.decode()
                        if len(data) > 0:
                            lines = data.split("\n")
                            for line in lines:
                                line=line.rstrip("\r\n")
                                self._debug(line)

                        if waitForIPAddress:                                
                            pos = data.find(", IP Address=")
                            if pos != -1:
                                elems = data.split("=")
                                if len(elems) > 0:    
                                    ipAddress = elems[-1].rstrip("\r\n")
                                    self._info(f"CT6 IP address = {ipAddress}")
                                    self._info("Waiting for firmware to startup on CT6 device.")
                                    sleep(4)
                                    self._info("Firmware is now running on the CT6 device.")
                                    break
                        else:
                            # Wait for the app to get to a running state.
                            # It will get to this state regardless of whether the Wifi is configured.
                            pos = data.find("Activating WiFi")
                            if pos != -1:
                                break
                                
            except serial.SerialException:
                self._debug(f"SerialException: {traceback.format_exc()}")

            except OSError:
                self._debug(f"SerialException: {traceback.format_exc()}")
            
        finally:
            if self._ser:
                self._ser.close()
                self._ser = None
                
        return ipAddress

    def loadCT6Firmware(self, factoryConfigFile=None):
        """@brief Load the CT6 code onto the CT6 hardware.
           @param factoryConfigFile If set this is the factory.cfg file to load onto the CT6 unit."""
        self._debug("loadCT6Firmware(): START")
        # If factory config defined check the contents of the file.
        if factoryConfigFile:
            self._checkFactoryConfFile(factoryConfigFile)
            
        # This will clean all the files including all config from the MCU flash memory 
        mcuLoader = MCULoader(self._uio, self._options)
        mcuLoader.load()
        self._info("Running the CT6 firmware")
        # Start the app. This will create the this.machine.cfg file
        self._runApp(waitForIPAddress=False)
        if factoryConfigFile:
            self.restoreFactoryConfig(factoryConfigFile)
            
        self._info("Updating the MCU WiFi configuration.")
        # Now the this.machine.cfg file is present we can setup the configuration.
        self._updateWiFiConfig()
        self._rebootUnit()
        self._info("Starting MCU to register on the WiFi network.")
        ipAddress = self._runApp()
        self._debug("loadCT6Firmware(): STOP")
        return ipAddress

    def _getFileContentsOverWifi(self, filename, address):
        """@brief Get the file contents via the network (WiFi).
           @param filename The text filename to read.
           @brief address The unit IP address."""
        self._info(f"Get {filename} from {address}.")
        url=f"http://{address}{CT6Base.GET_FILE_CMD}?file={filename}"
        response = self._runRESTCmd(url)
        rDict = response.json()
        return rDict[filename]
    
    def _checkFactoryConfFile(self, factoryConfigLogFile):
        """@brief Get the name of the factory.conf file to load onto the CT6 unit.
                  _initTest must be called before calling this method.
           @param factoryConfigLogFile The file to check.
           @return The factory conf file."""
        if not os.path.isfile(factoryConfigLogFile):
            raise Exception(f"{factoryConfigLogFile} file not found.")
        factoryCfgDict = None
        try:
            with open(factoryConfigLogFile) as fd:
                fileContents = fd.read()
                factoryCfgDict = json.loads(fileContents)
        except:
            pass
        if factoryCfgDict is None:
            raise Exception(f"{factoryConfigLogFile} is not a JSON formatted file.")
        
        # Ensure the file has all the required keys
        for key in CT6Base.FACTORY_CONFIG_KEYS:
            if key not in factoryCfgDict:
                raise Exception(f"The {key} parameter is not defined in the {factoryConfigLogFile} file.")
            
        assyStr = factoryCfgDict[CT6Base.ASSY_KEY]
        # If the ASSY is not set
        if assyStr.startswith("ASY0197"):
            # Correct the assembly number from the filename data
            filename = os.path.basename(factoryConfigLogFile)
            elems = filename.split("_")
            if len(elems) > 3:
                assyStr = elems[0] + "_" + elems[1] + "_" + elems[2]
                factoryCfgDict[CT6Base.ASSY_KEY] = assyStr
                self._saveDictToJSONFile(factoryCfgDict, factoryConfigLogFile)
                self._warn(f"Corrected assembly number in the {factoryConfigLogFile} file.")
            else:
                raise Exception(f"{filename} invalid. Should have 'ASY0398_V03.2000_SN00001834_20240211094915_factory.cfg' form.")
            
        # We've completed the checks required on the contents of the config file.
        return factoryConfigLogFile
        
    def _sendFileOverWiFi(self, address, localFile, destPath):
        """@brief Send a file to the device.
           @param address The IP address of the CT6 device.
           @param localFile The local file to be sent.
           @param destPath The path on the device to save the file into."""
        #If on a windows platform then we need to correct the destination file path
        if self._windowsPlatform and destPath.find("\\"):
            destPath=destPath.replace('\\','/')

        fn=os.path.basename(localFile)
        with open(localFile, 'rb') as fd:
            encodedData = fd.read()
            sha256=hashlib.sha256(encodedData).hexdigest()
        self._info("Sending {} to {}".format(localFile, destPath))
        s = socket.socket()
        s.connect(socket.getaddrinfo(address, YDevManager.TCP_PORT)[0][-1])
        header = 'FILE {} {} {} {} HTTP/1.1\n'.format(fn, destPath, len(encodedData), sha256)
        s.send(header.encode() + encodedData)
        response = s.recv(1024)
        strResponse = response.decode()
        if strResponse.find("200 OK") == -1:
            raise Exception("{} file XFER failed.".format(localFile))
        self._info("{} file XFER success.".format(localFile))

    def restoreFactoryConfig(self, factoryConfigFile, serialCon = True):
        """@brief Restore the last factory config file to the CT6 unit via it's serial port.
           @param factoryConfigFile The factory config file.
           @param serialCon If True then the factory config file is loaded to the unit over the CT6 serial port.
                            If False then it is loaded over the WiFi interface."""
        srcFactoryCfgFile = self._checkFactoryConfFile(factoryConfigFile)
        
        if serialCon:
            # Attempt to connect to the board under test python prompt
            self._checkMicroPython(closeSerialPort=False)
            self._runRShell((f'cp "{srcFactoryCfgFile}" /pyboard/{CT6Base.CT6_FACTORY_CONFIG_FILE}',))
        else:
            tmpLocalFile = os.path.join(self._tempFolder, CT6Base.CT6_FACTORY_CONFIG_FILE)
            shutil.copyfile(srcFactoryCfgFile, tmpLocalFile)
            self._sendFileOverWiFi(self._ipAddress, tmpLocalFile, "/")
            os.remove(tmpLocalFile)
            
        self._info("Loaded the factory.cfg data to the CT6 board.")
        

    def _runCommand(self, cmd, returnDict = False):
        """@brief send a command to the device and get response.
           @return A requests instance."""
        self._checkAddress()
        url = 'http://{}:{}{}'.format(self._ipAddress, CT6Base.TCP_PORT, cmd)
        self._debug(f"CMD: {url}")
        if returnDict:
            obj = requests.get(url).json()
            self._debug(f"CMD RESPONSE: { str(obj) }")
            if isinstance(obj, dict):
                return obj
            else:
                raise Exception("'{}' failed to return a dict.".format(cmd))
        else:
            return requests.get(url)
        
    def receiveFile(self, receiveFile, localPath):
        """@brief Receive a file from the device.
           @param receiveFile The file to receive.
           @param The local path to save the file once received."""
        self._checkAddress()
        if not os.path.isdir(localPath):
            raise Exception(f"{localPath} local path not found.")

        self._info("Receiving {} from {}".format(receiveFile, self._ipAddress))
        requestsInstance = self._runCommand(YDevManager.GET_FILE_CMD + f"?file={receiveFile}")
        cfgDict = requestsInstance.json()
        if receiveFile in cfgDict:
            if os.path.isfile(receiveFile):
                self._info("The local file {} already exists.".format(receiveFile))
                if self._uio.getBoolInput("Overwrite y/n: "):
                    os.remove(receiveFile)
                    self._info("Removed local {}".format(receiveFile))
            fileContents=cfgDict[receiveFile]
            absFile = os.path.join(localPath, receiveFile)
            with open(absFile, 'w') as fd:
                fd.write(fileContents)
            self._info("Created local {}".format(absFile))

        else:
            if "ERROR" in cfgDict:
                raise Exception(cfgDict["ERROR"])

class MCULoader(CT6Base):
    """@brief Responsible for converting .py files in app1 and app1/lib
              to .mpy files and loading them onto the MCU."""

    VALID_MCU_LIST = ['picow', 'esp32']
    CMD_LIST = ["mkdir /pyboard/app1",
                "mkdir /pyboard/app1/lib",
                "mkdir /pyboard/app1/lib/drivers",
                "mkdir /pyboard/app2",
                "mkdir /pyboard/app2/lib",
                "mkdir /pyboard/app2/lib/drivers"]
    DEL_ALL_FILES_CMD_LIST = ["rm -r /pyboard/*"]
    MCU_MP_CACHE_FOLDER = "mcu_app.cache"
        
    def __init__(self, uio, 
                       options,
                       mcu = VALID_MCU_LIST[0]):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options.
           @param mcu The MCU type. Either 'picow' or 'esp32'. esp32 is not supported on the CT6 HW.
                      However this class supports loading code onto an esp32."""
        super().__init__(uio, options)
        if mcu not in MCULoader.VALID_MCU_LIST:
            raise Exception(f"{mcu} is an unsupported MCU ({','.join(MCULoader.VALID_MCU_LIST)} are valid).")
        self._mcu = mcu
        self._mcuCodeFolders = [self._app1Folder, os.path.join(self._app1Folder, 'lib'), os.path.join(self._app1Folder, 'lib/drivers')]
        
    def _checkApp1(self):
        """@brief Run pyflakes3 on the app1 folder code to check for errors before loading it."""
        self._info("Checking python code in the app1 folder using pyflakes")
        reporter = modReporter._makeDefaultReporter()
        warnings = checkRecursive((self._mcuCodeFolders[0],), reporter)
        if warnings > 0:
            raise Exception("Fix issues with the code in the app1 folder and then try again.")
        self._info("pyflakes found no issues with the app1 folder code.")
        
    def _getFileList(self, extension):
        """@brief Get a list of files with the given extension."""
        fileList = []
        if not extension.startswith("."):
            extension = ".{}".format(extension)

        for folder in self._mcuCodeFolders:
            entries = os.listdir(folder)
            for entry in entries:
                if entry.endswith(extension):
                    _file = os.path.join(folder, entry)
                    _file = _file.replace("\\", "/")
                    fileList.append( _file )

        return fileList
    
    def _deleteFiles(self, fileList):
        """@brief Delete files details in the file list."""
        for aFile in fileList:
            if os.path.isfile(aFile):
                os.remove(aFile)
                self._info("Deleted local {}".format(aFile))
                
    def deleteMPYFiles(self):
        """@brief Delete existing *.mpy files"""
        # Be careful with this code !!!
        # Don't change .mpy to .py or you could your python source code before checking it in to git.
        pyFileList = self._getFileList(".mpy")
        self._deleteFiles(pyFileList)

    def _convertToMPY(self):
        """@brief Generate *.mpy files for all files in app1 and app1/lib"""
        mpyFileList = []
        pyFileList = self._getFileList(".py")
        for pyFile in pyFileList:
            cmd = f'{self._mpyCmdLinePrefix} "{pyFile}"'
            check_call(cmd, shell=True)
            mpyFile = pyFile.replace(".py", ".mpy")
            self._info("Generated {} from {}".format(mpyFile, pyFile))
            if not os.path.isfile(mpyFile):
                raise Exception("Failed to generate the {} file.".format(mpyFile))
            mpyFileList.append(mpyFile)

        return mpyFileList
            
    def _runCmd(self, port, cmdFile):
        """@brief Run an rshell command file.
           @param port The serial port to run the command over.
           @param cmdFile The rshell command file to execute.
           @return the output from the command executed as a string."""
        rshellCmd = self._getRShellCmd(port, cmdFile)
        self._debug(f"EXECUTING: {rshellCmd}")   
        return check_output(rshellCmd, shell=True).decode()

    def _loadFiles(self, fileList, port):
        """@brief Load files onto the micro controller device.
           @param fileList The list of files to load.
           @param port The serial port to use."""      
        self._info("Loading CT6 firmware. This may take several minutes...")                 
        cmdList = copy(MCULoader.CMD_LIST)
        for srcFile in fileList:
            picoWPos = srcFile.find("picow")
            if picoWPos >= 0:
                destFile = "/pyboard" + srcFile[picoWPos+5:]
                # The dest path must use unix file sep characters
                destFile=destFile.replace('\\','/')
                cpCmd = f'cp "{srcFile}" {destFile}'
                cmdList.append(cpCmd)
            else:
                raise Exception(f"picow not found in {srcFile}")

        fd = open(MCULoader.RSHELL_CMD_LIST_FILE, 'w')
        for l in cmdList:
            fd.write("{}\n".format(l))
        fd.close()
        cmdOutput = self._runCmd(port, MCULoader.RSHELL_CMD_LIST_FILE)
        for _file in fileList:
            if cmdOutput.find(_file) == -1:
                lines = cmdOutput.split("\n")
                for l in lines:
                    self._info(l)
                raise Exception(f"Failed to load the {_file} file onto the CT6 device.") 
        self._info(f"Loaded all {len(fileList)} python files.")    
    
    def _deleteAllCT6Files(self, port):
        """@brief Delete all files from the CT6 device.
           @param port The serial port to use."""
        cmdList = MCULoader.DEL_ALL_FILES_CMD_LIST
        fd = open(MCULoader.RSHELL_CMD_LIST_FILE, 'w')
        for l in cmdList:
            fd.write("{}\n".format(l))
        fd.close()
        self._runCmd(port, MCULoader.RSHELL_CMD_LIST_FILE)
        self._info("Deleted all files from CT6 unit.")
        
    def load(self):
        """@brief Load the python code onto the micro controller device."""
        self._checkApp1()
        self._checkMicroPython()
        self.deleteMPYFiles()
        # Delete all files from the CT6 device
        self._deleteAllCT6Files(self._serialPort)
        # We now need to reboot the device in order to ensure the WDT is disabled
        # as there is no way to disable the WDT once enabled and the WDT runs 
        # on a CT6 device.
        self._rebootUnit()
        # Regain the python prompt from the CT6 unit.
        self._checkMicroPython()
        localFileList = [os.path.join(self._picowFolder, "main.py")]
        mpyFileList = self._convertToMPY()
        filesToLoad = localFileList + mpyFileList
        self._loadFiles(filesToLoad, self._serialPort)
        self.deleteMPYFiles()

class YDevManager(CT6Base):
    """@brief Responsible for providing device management functionality."""

    GET_SYS_STATS           = "/get_sys_stats"
    GET_FILE_LIST           = "/get_file_list"
    GET_MACHINE_CONFIG      = "/get_machine_config"
    ERASE_OFFLINE_APP       = "/erase_offline_app"
    MKDIR                   = "/mkdir"
    RMDIR                   = "/rmdir"
    RMFILE                  = "/rmfile"
    GET_ACTIVE_APP_FOLDER   = "/get_active_app_folder"
    GET_INACTIVE_APP_FOLDER = "/get_inactive_app_folder"
    SWAP_ACTIVE_APP         = "/swap_active_app"
    REBOOT_DEVICE           = "/reboot"
    POWER_CYCLE_DEVICE      = "/power_cycle"
    RESET_TODEFAULT_CONFIG  = "/reset_to_default_config"
    GET_FILE_CMD            = "/get_file"

    RAM_USED_BYTES          = "RAM_USED_BYTES"
    RAM_FREE_BYTES          = "RAM_FREE_BYTES"
    RAM_TOTAL_BYTES         = "RAM_TOTAL_BYTES"
    DISK_TOTAL_BYTES        = "DISK_TOTAL_BYTES"
    DISK_USED_BYTES         = "DISK_USED_BYTES"
    DISK_PERCENTAGE_USED    = "DISK_PERCENTAGE_USED"
    ACTIVE_APP_FOLDER_KEY   = "ACTIVE_APP_FOLDER"
    INACTIVE_APP_FOLDER_KEY = "INACTIVE_APP_FOLDER"

    REQUIRED_PYPI_MODULES = ["mpy_cross"]

    @staticmethod
    def GetColWidths(theDict, maxWidth0, maxWidth1, keyPrefix):
        """@brief Get the col 0 & 1 widths to set when showing dict table.
           @param theDict The dict that may contain other dicts.
           @param maxWidth0
           @param maxWidth1
           @param keyPrefix
           @return A tuple
                   0 = col 0 width
                   1 = col 1 width"""
        for key in theDict:
            if len(keyPrefix) > 0:
                col0Text = keyPrefix+':'+str(key)
            else:
                col0Text = str(key)
            col0Len = len(col0Text)
            if col0Len > maxWidth0:
                maxWidth0 = col0Len

            value = theDict[key]

            if isinstance(value, dict):
                maxWidth0, maxWidth1 = YDevManager.GetColWidths(value, maxWidth0, maxWidth1, keyPrefix=col0Text)
            else:
                col1Len = len(str(value))
                if col1Len > maxWidth1:
                    maxWidth1 = col1Len

        return(maxWidth0, maxWidth1)

    @staticmethod
    def PrintDict(uio, theDict, width0, width1, keyPrefix=""):
        """@brief Show the details of a dictionary contents
           @param theDict The dictionary
           @param indent Number of tab indents"""
        uio.info('-'*(width0+width1+7))
        for key in theDict:
            if len(keyPrefix) > 0:
                col0Text = keyPrefix+':'+str(key)
            else:
                col0Text = str(key)
            value = theDict[key]
            if isinstance(value, dict):
                YDevManager.PrintDict(uio, value, width0, width1, keyPrefix=col0Text)
            else:
                col1Text = theDict[key]
                l = '| {: <{width0}} | {: <{width1}} |'.format(col0Text, col1Text, width0=width0, width1=width1)
                uio.info(l)

        if len(keyPrefix) == 0:
            uio.info('-'*(width0+width1+7))

    def __init__(self, uio, options, ssid=None, password=None):
        """@brief Constructor
           @param uio A UIO instance for user input output.
           @param options An instance of the command line options.
           @param ssid The WiFi SSID. If left as None the user is prompted to enter it if not previously set.
           @param password The Wifi password.  If left as None the user is prompted to enter it if not previously set."""
        super().__init__(uio, options)
        self._mpyFileList = []

        if self._options.check_mpy_cross:
            self._checkModulesInstalled()

        if ssid and password:
            self._storeWiFiCredentials(ssid, password)

        elif not os.path.isfile(CT6Base.HOUSE_WIFI_CFG_FILE):
            self._handleHouseWiFiConfigFileNotFound()
            
        self._orgActiveAppFolder = None

    def _checkModulesInstalled(self):
        """@brief Check the required python modules are installed to rnu this tool."""
        for module in YDevManager.REQUIRED_PYPI_MODULES:
            self._info(f"Checking that the {module} python module is installed.")
            cmd = f"python3 -m pip install {module}"
            check_call(cmd, shell=True, stdout=DEVNULL, stderr=STDOUT)
            self._info(f"The {module} python module is installed.")

    def _ensureValidAddress(self):
        """@brief Ensure the units address is valid."""
        self._checkAddress()

    def packageApp(self):
        """@brief Package an app for OTA upgrade.
                  This involves zipping up all files in the self._app1Folder folder into a zip package file."""
        appZipFile = self._getAppZipFile()
        if os.path.isfile(appZipFile):
            self._info("{} already exists.".format(appZipFile))
            if self._uio.getBoolInput("Overwrite y/n: "):
                os.remove(appZipFile)
                self._info("Removed {}".format(appZipFile))
            else:
                return

        if os.path.isdir(self._app1Folder):
            opFile = appZipFile
            directory = self._app1Folder
            with ZipFile(opFile, 'w') as zip:
               for path, directories, files in os.walk(directory):
                   for file in files:
                       file_name = os.path.join(path, file)
                       archName = os.path.join(path.replace(self._app1Folder, ""), file)
                       zip.write(file_name, arcname=archName) # In archive the names are all relative to root
                       self._info("Added: {}".format(file_name))
            self._info('Created {}'.format(opFile))

        else:
            raise Exception("{} path not found.".format(self._app1Folder))

    def _checkRunningNewApp(self, restartTimeout=120):
        """@brief Check that the upgrade has been successful and the device is running the updated app."""
        self._waitForWiFiDisconnect()
        self._info(f"The CT6 unit ({self._ipAddress}) has rebooted.")
        self._info("Waiting for the CT6 device to connect to the WiFi network.")
        self._waitForPingSuccess()
        
        retDict = self._runCommand(YDevManager.GET_ACTIVE_APP_FOLDER, returnDict=True)
        activeApp = retDict['ACTIVE_APP_FOLDER']
        if self._orgActiveAppFolder == activeApp:
            raise Exception(f"Failed to run the updated app. Still running from {self._orgActiveAppFolder}.")
        else:
            self._info(f"Upgrade successful. Switched from {self._orgActiveAppFolder} to {activeApp}")

    def upgrade(self, promptReboot=True):
        """@brief Perform an upgrade on the units SW.
           @param promptReboot If True prompt the user to enter 'y' to reboot the unit."""
        startTime = time()
        self._ensureValidAddress()
        appSize = self._getSize(self._picowFolder)
        self._info(f"Peforming an OTA upgrade of {self._ipAddress}")

        # We need to erase any data in the inactive partition to see if we have space for the new app
        self._runCommand(YDevManager.ERASE_OFFLINE_APP)
        self._checkDiskSpace(appSize)
        self._sendFilesToInactiveAppFolder()
        self._switchActiveAppFolder()
        self._info("took {:.1f} seconds to upgrade device.".format(time()-startTime))
        # Don't leave the byte code files
        self._deleteMPYFiles()
        if promptReboot:
            while True:
                response = self._uio.getInput("Upgrade complete. Do you wish to reboot the device y/n: ")
                if response.lower() == 'y':
                    self._reboot()
                    # Reconnect to the device and check the unit is now running the new app
                    self._checkRunningNewApp()
                    break
    
                if response.lower() == 'n':
                    self._info("The device will run the new software when it is manually restarted.")
                    break

    def _deleteFiles(self, fileList):
        """@brief Delete files details in the file list."""
        for aFile in fileList:
            if os.path.isfile(aFile):
                os.remove(aFile)
                self._info("Deleted local {}".format(aFile))

    def _deleteMPYFiles(self):
        """@brief Delete existing *.mpy files"""
        self._info("Cleaning up python bytecode files.")
        fileList = []
        self._getFileList(self._upgradeAppRoot, fileList)
        mpyFileList = []
        for f in fileList:
            if f.endswith(".mpy"):
                mpyFileList.append(f)
        self._deleteFiles(mpyFileList)

    def _reboot(self):
        """@brief Issue a command to reboot the device."""
        self._runCommand(YDevManager.REBOOT_DEVICE, returnDict = True)
        self._info("The device is rebooting.")

    def _powerCycle(self):
        self._runCommand(YDevManager.POWER_CYCLE_DEVICE, returnDict = True)
        self._info("The device is power cycling.")

    def _getSize(self, folder, byteCount=0):
        """@brief Get the size of all the files in and below the folder.
           @param byteCount The running byte count."""
        entries = os.listdir(folder)
        for entry in entries:
            absEntry = os.path.join(folder, entry)
            if os.path.isfile(absEntry):
                fileSize = os.path.getsize(absEntry)
                byteCount += fileSize

            elif os.path.isdir(absEntry):
                byteCount = self._getSize(absEntry, byteCount=byteCount)

        return byteCount

    def _genByteCode(self, pythonFile):
        """@brief Convert the python file to a python bytecode file (.mpy suffix).
           @return The bytecode (*.mpy) file"""
        mpyFile = os.path.basename(pythonFile)
        mpyFile = mpyFile.replace(".py",".mpy")

        self._info("Converting {} to {} (bytecode).".format(os.path.basename(pythonFile), mpyFile))
        outputFile = pythonFile.replace(".py",".mpy")
        cmd = f'{self._mpyCmdLinePrefix} "{pythonFile}"'
        check_call(cmd, shell=True, stdout=DEVNULL, stderr=STDOUT)
        if not os.path.isfile(outputFile):
            raise Exception("Failed to create {} python bytecode file.".format(outputFile))
        self._mpyFileList.append(outputFile)
        return outputFile

    def _getFileList(self, folder, fileList=[]):
        """@brief Get a list of all the files at or below the given folder.
           @param fileList The list of files to be added to."""
        entries = os.listdir(folder)
        for entry in entries:
            absEntry = os.path.join(folder, entry)
            if os.path.isfile(absEntry):
                fileList.append(absEntry)

            elif os.path.isdir(absEntry):
                self._getFileList(absEntry, fileList)

    def _unzipPackage(self, zipFile):
        """@brief Decompress a zip file and return the folder it was decompressed into."""
        packagePath = os.path.join(self._tempFolder, "ct6_lool_package")
        if os.path.isdir(packagePath):
            shutil.rmtree(packagePath)
        os.mkdir(packagePath)
        self._info(f"Unzipping {zipFile} to {packagePath}")

        with ZipFile(zipFile, 'r') as zip_ref:
            zip_ref.extractall(packagePath)
        return packagePath
    
    def _checkDiskSpace(self, appSize):
        """@brief Check that there is sufficient space to store the new app. This should
           take a maximum of 1/2 the available disk space."""
        url = 'http://{}:{}{}'.format(self._ipAddress, YDevManager.TCP_PORT, YDevManager.GET_SYS_STATS)
        r = requests.get(url)
        obj = r.json()
        if isinstance(obj, dict):
            if YDevManager.DISK_TOTAL_BYTES in obj:
                diskSize = obj[YDevManager.DISK_TOTAL_BYTES]
                #usedSpace = obj[YDevManager.DISK_USED_BYTES]
                # App should not take more than 1/2 the available space so that we always have the ability
                # to upgrade.
                maxAppSize = int(diskSize /2)
                if appSize > maxAppSize:
                    raise Exception("The app is too large ({} bytes, max {} bytes).".format(appSize, maxAppSize))
                self._info("App size:            {}".format(appSize))
                self._info("Max app size:        {}".format(maxAppSize))
                self._info("% space left:        {:.1f}".format( ((1-(appSize/maxAppSize))*100.0) ))

        else:
            raise Exception("Unable to retrieve the disk space from the device.")

    def _sendFilesToInactiveAppFolder(self):
        """@brief Send all the files in the app folder to the remote device."""
        responseDict = self._runCommand(YDevManager.GET_INACTIVE_APP_FOLDER, returnDict=True)
        if YDevManager.INACTIVE_APP_FOLDER_KEY in responseDict:
            inactiveAppFolder = responseDict[YDevManager.INACTIVE_APP_FOLDER_KEY]
            self._info("Inactive App Folder: {}".format(inactiveAppFolder))
            localAppFolder = self._upgradeAppRoot
            fileList=[]
            self._getFileList(localAppFolder, fileList)
            for localFile in fileList:
                # Final check to ensure the local file exists.
                if os.path.isfile(localFile):
                    destPath = localFile.replace(localAppFolder, "")
                    destPath = os.path.dirname(destPath)
                    destPath = inactiveAppFolder + destPath
                    self.sendFile(localFile, destPath)
            
        else:
            raise Exception("Failed to determine the devices inactive app folder.")

    def _switchActiveAppFolder(self):
        """@brief Switch the active app, /app1 -> /app2 or /app2 -> /app1 depending upon
                  which is the currently active app."""
        beforeDict = self._runCommand(YDevManager.GET_ACTIVE_APP_FOLDER, returnDict=True)
        self._runCommand(YDevManager.SWAP_ACTIVE_APP)
        afterDict = self._runCommand(YDevManager.GET_ACTIVE_APP_FOLDER, returnDict=True)
        if beforeDict[YDevManager.ACTIVE_APP_FOLDER_KEY] == afterDict[YDevManager.ACTIVE_APP_FOLDER_KEY]:
            raise Exception("Failed to switch active app folder from: {}".format(beforeDict[YDevManager.ACTIVE_APP_FOLDER_KEY]))
        self._orgActiveAppFolder = beforeDict[YDevManager.ACTIVE_APP_FOLDER_KEY]

    def _showJSON(self, requestsInstance):
        """@brief show the contents of a JSON response.
           @param requestsInstance The requests that contains the RX JSON data."""
        obj = requestsInstance.json()
        if isinstance(obj, dict):
            width0, width1 = YDevManager.GetColWidths(obj, 0, 0, "")
            YDevManager.PrintDict(self._uio, obj, width0, width1)

        elif isinstance(obj, list):
            for line in obj:
                self._info(line)

    def _showCmdResponse(self, cmd):
        """@brief Show the response to a command."""
        r = self._runCommand(cmd)
        self._showJSON(r)

    def showStatus(self):
        """@brief Get the unit status."""
        self._showCmdResponse(YDevManager.GET_SYS_STATS)

    def showFileList(self):
        """@brief Show the files on the unit."""
        self._showCmdResponse(YDevManager.GET_FILE_LIST)

    def showMachineConfig(self):
        """@brief Show the machine config."""
        self._showCmdResponse(YDevManager.GET_MACHINE_CONFIG)

    def getMachineConfig(self):
        """@brief Get the machine configuration from the unit."""
        requestsInstance = self._runCommand(YDevManager.GET_MACHINE_CONFIG)
        cfgDict = requestsInstance.json()
        configFilename = os.path.join(self._tempFolder, "this.machine.cfg")
        if os.path.isfile(configFilename):
            self._info("{} already exists.".format(configFilename))
            if self._uio.getBoolInput("Overwrite y/n: "):
                os.remove(configFilename)
                self._info("Removed local {}".format(configFilename))
        jsonStr = json.dumps(cfgDict, indent=4)
        with open(configFilename, 'w') as fd:
            fd.write(jsonStr)
        self._info("Created local {}".format(configFilename))

    def eraseInactiveApp(self):
        """@bref Erase the inactive application."""
        self._info("Erasing inactive app.")
        self._showCmdResponse(YDevManager.ERASE_OFFLINE_APP)

    def sendFile(self, localFile, destPath):
        """@brief Send a file to the device.
           @param localFile The local file to be sent.
           @param destPath The path on the device to save the file into."""
        self._checkAddress()
        # Ignore pre existing bytecode files
        if localFile.endswith(".mpy"):
            return

        if not os.path.isfile(localFile):
            raise Exception("{} file not found.".format(localFile))

        if destPath is None or len(destPath) == 0:
            raise Exception("Send path not defined.")

        if localFile.endswith(".py"):
            localFile = self._genByteCode(localFile)

        self._sendFileOverWiFi(self._ipAddress, localFile, destPath)
        
    def makeDir(self):
        """@brief Make a dir on the devices file system."""
        dirToMake = self._options.mkdir
        self._ensureValidAddress()
        url = 'http://{}:{}{}?dir={}'.format(self._ipAddress, YDevManager.TCP_PORT, YDevManager.MKDIR, dirToMake)
        r = requests.get(url)
        self._showJSON(r)

    def rmDir(self):
        """@brief Remove a dir from the devices file system."""
        dirToRemove = self._options.rmdir
        self._ensureValidAddress()
        url = 'http://{}:{}{}?dir={}'.format(self._ipAddress, YDevManager.TCP_PORT, YDevManager.RMDIR, dirToRemove)
        r = requests.get(url)
        self._showJSON(r)

    def rmFile(self):
        """@brief Remove a file from the devices file system."""
        rmFile = self._options.rmfile
        self._ensureValidAddress()
        url = 'http://{}:{}{}?file={}'.format(self._ipAddress, YDevManager.TCP_PORT, YDevManager.RMFILE, rmFile)
        r = requests.get(url)
        self._showJSON(r)

    def getActiveAppFolder(self):
        """@brief Get the active app folder."""
        self._showCmdResponse(YDevManager.GET_ACTIVE_APP_FOLDER)

    def getInactiveAppFolder(self):
        """@brief Get the inactive app folder."""
        self._showCmdResponse(YDevManager.GET_INACTIVE_APP_FOLDER)

    def reboot(self):
        """@brief reboot the device."""
        self._reboot()

    def powerCycle(self):
        """@brief Power cycle the unit."""
        self._powerCycle()

    def setDefaults(self):
        """@brief Set default config."""
        self._showCmdResponse(YDevManager.RESET_TODEFAULT_CONFIG)
        # Ask user if they wish to reboot the unit now its set to default configuration.
        if self._uio.getBoolInput("Reboot unit y/n"):
            self._reboot()

    def configureWiFi(self):
        """@brief configure the CT6 WiFi interface from the house_wifi.cfg file."""
        self._info("Setting up CT6 WiFi interface.")
        ssid = self._updateWiFiConfig()
        self._info(f"WiFi SSID: {ssid}")
        self._info("The CT6 WiFi interface is now configured.")
        
    def _openFirstAvailableSerialPort(self):
        """@brief Attempt to get the name of the first available serial port."""
        checking = True
        self._serialPort = None
        while checking:
            try:
                self._openSerialPort(matchStr="/dev/ttyA")
                checking = False
            except:
                try:
                    self._openSerialPort(matchStr="/dev/ttyUSB")
                    checking = False
                except:
                    pass

            # Spin, not too quickly if no serial port found.
            if self._serialPort is None:
                sleep(0.1)
    
    def viewSerialOut(self):
        """@brief View serial port output quickly after a Pico W reset.
                  This is useful when debugging Pico W firmware issues."""
        running = True
        while running:
            self._openFirstAvailableSerialPort()
            try:
                try:           
                    while running:
                        bytesRead = self._ser.read_until()
                        sRead = bytesRead.decode()
                        sRead = sRead.rstrip('\r\n')
                        if len(sRead) > 0:
                            self._info(sRead)
                            
                except KeyboardInterrupt:
                    running = False
                except:
                    sleep(0.1)
                                                
            finally:
                if self._ser:
                    self._ser.close()
                    self._ser = None
                    self._info(f"Closed {self._serialPort}")
                
class CT6Scanner(CT6Base):
    """@brief Responsible for scanning for CT6 devices."""

    CT6_UDP_SERVER_PORT = 29340

    class AreYouThereThread(Thread):
        """An inner class to send are you there (AYT) messages to devices"""

        AreYouThereMessage = "{\"AYT\":\"-!#8[dkG^v's!dRznE}6}8sP9}QoIR#?O&pg)Qra\"}"
        PERIODICITY_SECONDS = 1.0
        MULTICAST_ADDRESS   = "255.255.255.255"

        def __init__(self, sock, port):
            Thread.__init__(self)
            self._running = None
            self.setDaemon(True)

            self._sock = sock
            self._port = port

        def run(self):
            self._running = True
            while self._running:
                self._sock.sendto(CT6Scanner.AreYouThereThread.AreYouThereMessage.encode(), (CT6Scanner.AreYouThereThread.MULTICAST_ADDRESS, self._port))
                sleep(CT6Scanner.AreYouThereThread.PERIODICITY_SECONDS)

        def shutDown(self):
            """@brief Shutdown the are you there thread."""
            self._running = False

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        super().__init__(uio, options)

    def scan(self, callBack=None, runSeconds=None):
        """@brief Perform a scan for CT6 devices on the LAN.
           @param callBack If defined then this method will be called passing the dict received from each unit that responds.
           @param runSeconds If defined then this is the number of seconds to scan for."""

        port = CT6Scanner.CT6_UDP_SERVER_PORT

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', port))

        self._info('Sending AYT messages.')
        areYouThereThread = CT6Scanner.AreYouThereThread(sock, port)
        areYouThereThread.start()

        self._info("Listening on UDP port %d" % (port) )
        stopTime = None
        if runSeconds:
            stopTime = time() + runSeconds
        running = True
        while running:
            data = sock.recv(65536)
            #Ignore the messaage we sent
            if data != CT6Scanner.AreYouThereThread.AreYouThereMessage:
                try:
                    dataStr = data.decode()
                    rx_dict = json.loads(dataStr)
                    # Ignore the reflected broadcast message.
                    if 'AYT' in rx_dict:
                        continue
                    self._info("-"*30+ "DEVICE FOUND" + "-"*30)
                    for key in rx_dict:
                        self._info("{: <25}={}".format(key, rx_dict[key]))

                    if callBack:
                        running = callBack(rx_dict)

                except:
                    pass

            #If we need to stop after a given time period.
            if stopTime and time() >= stopTime:
                areYouThereThread.shutDown()
                areYouThereThread.join()
                sock.close()
                break

class CT6Config(CT6Base):
    """@brief Allow the user to configure a CT6 device."""

    EDITABLE_KEY_LIST = ("YDEV_UNIT_NAME", "CT1_NAME", "CT2_NAME", "CT3_NAME", "CT4_NAME", "CT5_NAME", "CT6_NAME", BaseConstants.ACTIVE, "MQTT_SERVER_ADDRESS", "MQTT_SERVER_PORT", "MQTT_TX_PERIOD_MS", "MQTT_TOPIC", "MQTT_USERNAME", "MQTT_PASSWORD")
    USER_PROMPT_LIST  = ("Device name", "Port 1 name", "Port 2 name", "Port 3 name", "Port 4 name", "Port 5 name", "Port 6 name", "Device Active")

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        super().__init__(uio, options)

    def _saveConfigDict(self, cfgDict):
        """@brief Save the config dict back to the CT6 device.
           @brief The device config dict."""
        url=f"http://{self._options.address}/set_config"
        index=0
        url=url+"?"
        while index < len(CT6Config.EDITABLE_KEY_LIST):
            key = CT6Config.EDITABLE_KEY_LIST[index]
            value=cfgDict[key]
            # First arg is added without , separator
            if index == 0:
                url=url+key+"="+str(value)
            # All other args are added with a , separator
            else:
                url=url+","+key+"="+str(value)
            index+=1
        response = requests.get(url)
        self._checkResponse(response)
        self._info("Saved parameters to CT6 device.")

    def editDeviceConfig(self, cfgDict):
        """@brief Display a list of attributes to be edited, allow the user to edit them.
           @brief The device config dict.
           @return True to save the config, False to quit."""
        while True:
            boolRet = False
            id=1
            self._info("ID Description    Value")
            for uPrompt in CT6Config.USER_PROMPT_LIST:
                key = CT6Config.EDITABLE_KEY_LIST[id-1]
                if key == CT6Config.ACTIVE:
                    if key in cfgDict:
                        value = cfgDict[key]
                    else:
                        # Prior to adding the active key all units were active
                        value = True
                        cfgDict[key]=value
                else:
                    value = urllib.parse.unquote(cfgDict[key])
                self._info(f"{id}  {uPrompt:15s} {value}")
                id+=1
            response = self._uio.getInput("Enter the ID to change, S to store or Q to quit")
            if response.upper() == 'S':
                boolRet = True
                break

            elif response.upper() == 'Q':
                break

            else:
                try:
                    intVal = int(response)
                    key = CT6Config.EDITABLE_KEY_LIST[intVal-1]
                    prompt = CT6Config.USER_PROMPT_LIST[intVal-1]
                    if key == CT6Config.ACTIVE:
                        self._warn("Only set the CT6 device active when you wish to send data to the database.")
                        attrValue = self._uio.getBoolInput("Activate the CT6 device ? y/n")
                        if attrValue == True:
                            attrValue = '1'
                        else:
                            attrValue = '0'
                    else:
                        attrValue = self._uio.getInput(f"Enter the {prompt} value")
                        # Don't allow spaces, tabs or . in the database table names
                        attrValue=attrValue.replace(" ","_")
                        attrValue=attrValue.replace("\t","_")
                        attrValue=attrValue.replace(".","_")
                    cfgDict[key] = attrValue

                except IndexError:
                    self._error(f"{response} is an invalid ID.")

                except ValueError:
                    self._error(f"{response} is an invalid CT6 parameter.")

        return boolRet

    def configure(self):
        """@brief Perform the user configuration of a CT6 device."""
        self._checkAddress()
        self._info(f'Configure {self._options.address}')
        cfgDict = self._getConfigDict()
        save = self.editDeviceConfig(cfgDict)
        if save:
            self._saveConfigDict(cfgDict)

def getCT6ToolCmdOpts():
    """@brief Get a reference to the command line options.
       @return The options instance."""
    parser = argparse.ArgumentParser(description="A tool to perform configuration and calibration functions on a CT6 power monitor.",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-w", "--setup_wifi",       action='store_true', help="Alternative to using the Android App to setup the CT6 WiFi interface.")
    parser.add_argument("-c", "--config",           action='store_true', help="Configure a CT6 unit.")
    parser.add_argument("-f", "--find",             action='store_true', help="Find/Scan for CT6 devices on the LAN.")
    parser.add_argument("--upgrade",                action='store_true', help="Perform an upgrade of a CT6 unit over the air (OTA) via it's WiFi interface.")
    parser.add_argument("--clean",                  help="Delete all files and reload the firmware onto a CT6 device over the Pico W serial port. The factory.cfg file must be reloaded when this is complete to restore assy/serial number and calibration configuration.", action='store_true')
    parser.add_argument("--status",                 action='store_true', help="Get unit RAM/DISK usage.")
    parser.add_argument("--flist",                  action='store_true', help="Get a list of the files on the unit.")
    parser.add_argument("--mconfig",                action='store_true', help="Get the machine config.")
    parser.add_argument("--get_config",             action='store_true', help="Get the machine configuration file and store it locally.")
    parser.add_argument("--eia",                    action='store_true', help="Erase the inactive application.")
    parser.add_argument("--sf",                     help="Send a file to the device.")
    parser.add_argument("--sp",                     help="The path to place the above file on the device.", default="/")
    parser.add_argument("--rf",                     help="Receive a file from the device. Only text files are currently supported.")
    parser.add_argument("--rp",                     help=f"The local path to place the above file once received (default={CT6Base.GetTempFolder()}).", default=CT6Base.GetTempFolder())
    parser.add_argument("--mkdir",                  help="The path to create on the device.")
    parser.add_argument("--rmdir",                  help="The path to remove from the device.")
    parser.add_argument("--rmfile",                 help="The file to remove from the device.")
    parser.add_argument("--getaaf",                 help="Get the active app folder.", action='store_true')
    parser.add_argument("--getiaf",                 help="Get the inactive app folder.", action='store_true')
    parser.add_argument("--reboot",                 help="Reboot the device.", action='store_true')
    parser.add_argument("--power_cycle",            help="Power cycle the unit.", action='store_true')
    parser.add_argument("--defaults",               help="Reset a device to the default configuration.", action='store_true')
    parser.add_argument("--check_mpy_cross",        action='store_true', help="Check that the mpy_cross (bytecode compiler) is installed.")
    parser.add_argument("-v", "--view",             action='store_true', help="View received data on first /dev/ttyUSB* or /dev/ttyACM* serial port quickly after a Pico W reset.")
    parser.add_argument("-a", "--address",          help="The address of the CT6 unit.", default=None)
    parser.add_argument("-d", "--debug",            action='store_true', help="Enable debugging.")

    options = parser.parse_args()
    return options
    
def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        options = getCT6ToolCmdOpts()

        uio.enableDebug(options.debug)

        yDevManager = YDevManager(uio, options)
        ct6Config = CT6Config(uio, options)
        ct6Scanner = CT6Scanner(uio, options)

        if options.setup_wifi:
            yDevManager.configureWiFi()
            
        elif options.config:
            ct6Config.configure()

        elif options.find:
            ct6Scanner.scan()

        elif options.clean:
            yDevManager.loadCT6Firmware(False)

        elif options.upgrade:
            yDevManager.upgrade()

        elif options.status:
            yDevManager.showStatus()

        elif options.flist:
            yDevManager.showFileList()

        elif options.mconfig:
            yDevManager.showMachineConfig()

        elif options.get_config:
            yDevManager.getMachineConfig()

        elif options.eia:
            yDevManager.eraseInactiveApp()

        elif options.sf:
            yDevManager.sendFile(options.sf, options.sp)

        elif options.rf:
            yDevManager.receiveFile(options.rf, options.rp)

        elif options.mkdir:
            yDevManager.makeDir()

        elif options.rmdir:
            yDevManager.rmDir()

        elif options.rmfile:
            yDevManager.rmFile()

        elif options.getaaf:
            yDevManager.getActiveAppFolder()

        elif options.getiaf:
            yDevManager.getInactiveAppFolder()

        elif options.reboot:
            yDevManager.reboot()

        elif options.power_cycle:
            yDevManager.powerCycle()

        elif options.defaults:
            yDevManager.setDefaults()

        elif options.view:
            yDevManager.viewSerialOut()

        else:
            raise Exception("Please define the action you wish to perform on the command line.")

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
