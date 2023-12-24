#!/usr/bin/env python3

import argparse
import requests
import urllib
import socket
import json
import os

from   time import sleep, time
from   zipfile import ZipFile
from   threading import Thread

import ping3
import hashlib

from   p3lib.uio import UIO
from   p3lib.helper import logTraceBack

from   lib.base_constants import BaseConstants

from   subprocess import check_call, DEVNULL, STDOUT

class CT6Base(BaseConstants):
    """@brief Base class for CT6 device operations."""
    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        self._uio       = uio
        self._options   = options   
        self._ipAddress = None          # The IP address for the UUT

    def _checkAddress(self):
        """@brief Check that the command line adddress option has been set."""
        if self._ipAddress == None:
            raise Exception("No address defined. Use the -a/--address command line option to define the CT6 unit address.")

    def _getConfigDict(self):
        """@brief Get the config dict from the device.
           @return The config dict."""
        self._uio.info(f"Reading configuration from {self._ipAddress}")
        url=f"http://{self._ipAddress}/get_config"
        response = requests.get(url)
        return response.json()

    def _getStatsDict(self):
        """@brief Get the stats dict from the device.
           @return The stats dict."""
        self._uio.info(f"Reading stats from {self._ipAddress}")
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
        self._ipAddress = ipAddress


    def _waitForWiFiDisconnect(self, restartTimeout=60, showMessage=True):
        """@brief Wait for the CT6 unit to disconnect from the WiFi network.
           @param restartTimeout The number of seconds before an exception is thrown if the WiFi does not disconnect.
           @param showMessage If True show a message indicating we're waiting for a reboot."""
        if showMessage:
            self._uio.info(f"Waiting for the CT6 unit  ({self._ipAddress}) to reboot.")
        startT = time()
        while True:
            pingSec = ping3.ping(self._ipAddress)
            if pingSec is None:
                break

            if time() >= startT+restartTimeout:
                raise Exception("Timeout waiting for the device to reboot.")
        
            sleep(0.25)
            
    def _waitForWiFiReconnect(self, restartTimeout=60, pingHoldSecs = 3):
        """@brief Wait for a reconnect to the WiFi network.
           @param restartTimeout The number of seconds before an exception is thrown if the WiFi does not reconnect.
           @param pingHoldSecs The number of seconds of constant pings before we determine the WiFi has reconnected.
                               This is required because the Pico W may ping and then stop pinging before pinging 
                               again when reconnecting to the Wifi."""
        self._uio.info(f"The CT6 unit ({self._ipAddress}) has rebooted. Waiting for it to re register on the WiFi network.")
        startT = time()
        pingRestartTime = None
        while True:
            pingSec = ping3.ping(self._ipAddress)
            if pingSec is not None:
                if pingRestartTime is None:
                    pingRestartTime = time()

                if time() > pingRestartTime+pingHoldSecs:
                    break

            else:
                pingRestartTime = None

            if time() >= startT+restartTimeout:
                raise Exception("Timeout waiting for the device to re register on the WiFi network.")
            
            sleep(0.25)
            
        self._uio.info("CT6 unit is now connected to the WiFi network.")
        
class YDevManager(CT6Base):
    """@brief Responsible for providing device management functionality."""

    TCP_PORT                = 80
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
    
    EXAMPLE_CMD             = "/example_cmd"

    RAM_USED_BYTES          = "RAM_USED_BYTES"
    RAM_FREE_BYTES          = "RAM_FREE_BYTES"
    RAM_TOTAL_BYTES         = "RAM_TOTAL_BYTES"
    DISK_TOTAL_BYTES        = "DISK_TOTAL_BYTES"
    DISK_USED_BYTES         = "DISK_USED_BYTES"
    DISK_PERCENTAGE_USED    = "DISK_PERCENTAGE_USED"
    ACTIVE_APP_FOLDER_KEY   = "ACTIVE_APP_FOLDER"
    INACTIVE_APP_FOLDER_KEY = "INACTIVE_APP_FOLDER"

    REQUIRED_PYPI_MODULES = ["mpy_cross"]
    MPY_CMDLINE_PREFIX = "python3 -m mpy_cross "

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

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance for user input output.
           @param options An instance of the command line options."""
        super().__init__(uio, options)
        self._mpyFileList = []

        if self._options.check_mpy_cross:
            self._checkModulesInstalled()

        self._orgActiveAppFolder = None

    def _checkModulesInstalled(self):
        """@brief Check the required python modules are installed to rnu this tool."""
        for module in YDevManager.REQUIRED_PYPI_MODULES:
            self._uio.info("Checking that the {} python module is installed.".format(module))
            cmd = "python3 -m pip install {}".format(module)
            check_call(cmd, shell=True, stdout=DEVNULL, stderr=STDOUT)

    def _getAppZipFile(self, checkExists=False):
        """@brief Get the app zip file.
           @param checkExists If True check if the app zip file exists.
           @return The app zip file."""
        appZipFile = self._options.upgrade
        if not appZipFile:
            raise Exception("The app zip file is not defined.")

        if not appZipFile.endswith(".zip"):
            appZipFile = appZipFile + ".zip"

        if checkExists and not os.path.isfile(appZipFile):
            raise Exception("{} file not found.".format(appZipFile))

        return appZipFile

    def _ensureValidAddress(self):
        """@brief Ensure the units address is valid."""
        if not self._ipAddress:
            raise Exception("The address of the unit to be upgraded is not defined.")

    def packageApp(self):
        """@brief Package an app for OTA upgrade.
                  This involves zipping up all files in the app_path folder into a zip package file."""
        appZipFile = self._getAppZipFile()
        if os.path.isfile(appZipFile):
            self._uio.info("{} already exists.".format(appZipFile))
            if self._uio.getBoolInput("Overwrite y/n: "):
                os.remove(appZipFile)
                self._uio.info("Removed {}".format(appZipFile))
            else:
                return

        if os.path.isdir(self._options.app_path):
            opFile = appZipFile
            directory = self._options.app_path
            with ZipFile(opFile, 'w') as zip:
               for path, directories, files in os.walk(directory):
                   for file in files:
                       file_name = os.path.join(path, file)
                       archName = os.path.join(path.replace(self._options.app_path, ""), file)
                       zip.write(file_name, arcname=archName) # In archive the names are all relative to root
                       self._uio.info("Added: {}".format(file_name))
            self._uio.info('Created {}'.format(opFile))

        else:
            raise Exception("{} path not found.".format(self._options.app_path))

    def _checkRunningNewApp(self, restartTimeout=120):
        """@brief Check that the upgrade has been successful and the device is running the updated app."""
        self._waitForWiFiDisconnect()
        self._waitForWiFiReconnect()
        
        retDict = self._runCommand(YDevManager.GET_ACTIVE_APP_FOLDER, returnDict=True)
        activeApp = retDict['ACTIVE_APP_FOLDER']
        if self._orgActiveAppFolder == activeApp:
            raise Exception(f"Failed to run the updated app. Still running from {self._orgActiveAppFolder}.")
        else:
            self._uio.info(f"Upgrade successful. Switched from {self._orgActiveAppFolder} to {activeApp}")

    def upgrade(self):
        """@brief Perform an upgrade on the units SW."""
        startTime = time()
        self._ensureValidAddress()
        appSize = self._checkLocalApp()
        # We need to erase any data in the inactive partition to see if we have space for the new app
        self._runCommand(YDevManager.ERASE_OFFLINE_APP)
        self._checkDiskSpace(appSize)
        self._sendFilesToInactiveAppFolder()
        self._switchActiveAppFolder()
        self._uio.info("took {:.1f} seconds to upgrade device.".format(time()-startTime))
        # Don't leave the byte code files
        self._deleteMPYFiles()
        while True:
            response = self._uio.getInput("Upgrade complete. Do you wish to reboot the device y/n: ")
            if response.lower() == 'y':
                self._reboot()
                # Reconnect to the device and check the unit is now running the new app
                self._checkRunningNewApp()
                break

            if response.lower() == 'n':
                self._uio.info("The device will run the new software when it is manually restarted.")
                break

    def _deleteFiles(self, fileList):
        """@brief Delete files details in the file list."""
        for aFile in fileList:
            if os.path.isfile(aFile):
                os.remove(aFile)
                self._uio.info("Deleted {}".format(aFile))

    def _deleteMPYFiles(self):
        """@brief Delete existing *.mpy files"""
        self._uio.info("Cleaning up python bytecode files.")
        fileList = []
        self._getFileList(self._options.upgrade, fileList)
        mpyFileList = []
        for f in fileList:
            if f.endswith(".mpy"):
                mpyFileList.append(f)
        self._deleteFiles(mpyFileList)

    def _reboot(self):
        """@brief Issue a command to reboot the device."""
        self._runCommand(YDevManager.REBOOT_DEVICE, returnDict = True)
        self._uio.info("The device is rebooting.")

    def _powerCycle(self):
        self._runCommand(YDevManager.POWER_CYCLE_DEVICE, returnDict = True)
        self._uio.info("The device is power cycling.")

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

        self._uio.info("Converting {} to {} (bytecode).".format(os.path.basename(pythonFile), mpyFile))
        outputFile = pythonFile.replace(".py",".mpy")
        cmd = "{}{}".format(YDevManager.MPY_CMDLINE_PREFIX, pythonFile)
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

    def _checkLocalApp(self):
        """@brief Check the app on the local disk before attempting to upgrade the device.
           @return The amount of disk space required to store all the app files."""
        appZipFile = self._getAppZipFile()
        if os.path.isfile(appZipFile):
            self._upgradeAppRoot = self._inflatePackage(appZipFile)
        else:
            self._upgradeAppRoot = self._options.upgrade

        if not os.path.isdir(self._upgradeAppRoot):
            raise Exception("{} app folder not found.".format(self._upgradeAppRoot))

        mainFile = os.path.join(self._upgradeAppRoot, "app.py")
        if not os.path.isfile(mainFile):
            mainFile = os.path.join(self._upgradeAppRoot, "app.mpy")
            if not os.path.isfile(mainFile):
                raise Exception("{} app.py or app.mpy file not found.".format(mainFile))

        return self._getSize(self._upgradeAppRoot)

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
                self._uio.info("App size:            {}".format(appSize))
                self._uio.info("Max app size:        {}".format(maxAppSize))
                self._uio.info("% space left:        {:.1f}".format( ((1-(appSize/maxAppSize))*100.0) ))

        else:
            raise Exception("Unable to retrieve the disk space from the device.")

    def _sendFilesToInactiveAppFolder(self):
        """@brief Send all the files in the app folder to the remote device."""
        responseDict = self._runCommand(YDevManager.GET_INACTIVE_APP_FOLDER, returnDict=True)
        if YDevManager.INACTIVE_APP_FOLDER_KEY in responseDict:
            inactiveAppFolder = responseDict[YDevManager.INACTIVE_APP_FOLDER_KEY]
            self._uio.info("Inactive App Folder: {}".format(inactiveAppFolder))
            localAppFolder = self._options.upgrade
            fileList=[]
            self._getFileList(localAppFolder, fileList)
            for localFile in fileList:
                # Final check to ensure the local file exists.
                if os.path.isfile(localFile):
                    destPath = localFile.replace(localAppFolder, "")
                    destPath = os.path.dirname(destPath)
                    destPath = os.path.join(inactiveAppFolder, destPath)
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
                self._uio.info(line)

    def _runCommand(self, cmd, returnDict = False):
        """@brief send a command to the device and get response.
           @return A requests instance."""
        self._ensureValidAddress()
        url = 'http://{}:{}{}'.format(self._ipAddress, YDevManager.TCP_PORT, cmd)
        self._uio.debug(f"CMD: {url}")
        if returnDict:
            obj = requests.get(url).json()
            self._uio.debug(f"CMD RESPONSE: { str(obj) }")
            if isinstance(obj, dict):
                return obj
            else:
                raise Exception("'{}' failed to return a dict.".format(cmd))
        else:
            return requests.get(url)

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
        configFilename = "this.machine.cfg"
        if os.path.isfile(configFilename):
            self._uio.info("{} already exists.".format(configFilename))
            if self._uio.getBoolInput("Overwrite y/n: "):
                os.remove(configFilename)
                self._uio.info("Removed local {}".format(configFilename))
        jsonStr = json.dumps(cfgDict, indent=4)
        with open(configFilename, 'w') as fd:
            fd.write(jsonStr)
        self._uio.info("Created local {}".format(configFilename))

    def eraseInactiveApp(self):
        """@bref Erase the inactive application."""
        self._showCmdResponse(YDevManager.ERASE_OFFLINE_APP)

    def sendFile(self, localFile, destPath):
        """@brief Send a file to the device.
           @param localFile The local file to be sent.
           @param destPath The path on the device to save the file into."""
        # Ignore pre existing bytecode files
        if localFile.endswith(".mpy"):
            return

        if not os.path.isfile(localFile):
            raise Exception("{} file not found.".format(localFile))

        if destPath is None or len(destPath) == 0:
            raise Exception("Send path not defined.")

        if localFile.endswith(".py"):
            localFile = self._genByteCode(localFile)

        fn=os.path.basename(localFile)
        with open(localFile, 'rb') as fd:
            encodedData = fd.read()
            sha256=hashlib.sha256(encodedData).hexdigest()
        self._uio.info("Sending {} to {}".format(localFile, destPath))
        s = socket.socket()
        s.connect(socket.getaddrinfo(self._ipAddress, YDevManager.TCP_PORT)[0][-1])
        header = 'FILE {} {} {} {} HTTP/1.1\n'.format(fn, destPath, len(encodedData), sha256)
        s.send(header.encode() + encodedData)
        response = s.recv(1024)
        strResponse = response.decode()
        if strResponse.find("200 OK") == -1:
            raise Exception("{} file XFER failed.".format(localFile))
        self._uio.info("{} file XFER success.".format(localFile))

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

    def exampleCmd(self):
        self._showCmdResponse(YDevManager.EXAMPLE_CMD)

    def receiveFile(self, receiveFile, localPath):
        """@brief Receive a file from the device.
           @param receiveFile The file to receeive.
           @param The local path to save the file once received."""
        if not os.path.isdir(localPath):
            raise Exception(f"{localPath} local path not found.")

        self._uio.info("Receiving {} from {}".format(receiveFile, self._ipAddress))
        requestsInstance = self._runCommand(YDevManager.GET_FILE_CMD + f"?file={receiveFile}")
        cfgDict = requestsInstance.json()
        if receiveFile in cfgDict:
            if os.path.isfile(receiveFile):
                self._uio.info("The local file {} already exists.".format(receiveFile))
                if self._uio.getBoolInput("Overwrite y/n: "):
                    os.remove(receiveFile)
                    self._uio.info("Removed local {}".format(receiveFile))
            fileContents=cfgDict[receiveFile]
            absFile = os.path.join(localPath, receiveFile)
            with open(absFile, 'w') as fd:
                fd.write(fileContents)
            self._uio.info("Created local {}".format(absFile))

        else:
            if "ERROR" in cfgDict:
                raise Exception(cfgDict["ERROR"])


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

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        super().__init__(uio, options)

    def scan(self, callBack=None):
        """@brief Perform a scan for CT6 devices on the LAN.
           @param callBack If defined then this method will be called passing the dict received from each unit that responds."""

        port = CT6Scanner.CT6_UDP_SERVER_PORT

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', port))

        self._uio.info('Sending AYT messages.')
        areYouThereThread = CT6Scanner.AreYouThereThread(sock, port)
        areYouThereThread.start()

        self._uio.info("Listening on UDP port %d" % (port) )
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
                    self._uio.info("-"*30+ "DEVICE FOUND" + "-"*30)
                    for key in rx_dict:
                        self._uio.info("{: <25}={}".format(key, rx_dict[key]))

                    if callBack:
                        running = callBack(rx_dict)

                except:
                    pass

class CT6Config(CT6Base):
    """@brief Allow the user to configure a CT6 device."""

    EDITABLE_KEY_LIST = ("YDEV_UNIT_NAME", "CT1_NAME", "CT2_NAME", "CT3_NAME", "CT4_NAME", "CT5_NAME", "CT6_NAME", BaseConstants.ACTIVE)
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
        self._uio.info("Saved parameters to CT6 device.")

    def editDeviceConfig(self, cfgDict):
        """@brief Display a list of attributes to be edited, allow the user to edit them.
           @brief The device config dict.
           @return True to save the config, False to quit."""
        while True:
            boolRet = False
            id=1
            self._uio.info("ID Description    Value")
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
                self._uio.info(f"{id}  {uPrompt:15s} {value}")
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
                        self._uio.warn("Only set the CT6 device active when you wish to send data to the database.")
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
                    self._uio.error(f"{response} is an invalid ID.")

                except ValueError:
                    self._uio.error(f"{response} is an invalid CT6 parameter.")

        return boolRet

    def configure(self):
        """@brief Perform the user configuration of a CT6 device."""
        self._checkAddress()
        self._uio.info(f'Configure {self._options.address}')
        cfgDict = self._getConfigDict()
        save = self.editDeviceConfig(cfgDict)
        if save:
            self._saveConfigDict(cfgDict)


def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="A tool to perform configuration and calibration functions on a CT6 power monitor.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",            action='store_true', help="Enable debugging.")
        parser.add_argument("-a", "--address",          help="The address of the unit.", default=None)
        parser.add_argument("-c", "--config",           action='store_true', help="Configure a CT6 power monitor.")
        parser.add_argument("-f", "--find",             action='store_true', help="Find/Scan for CT6 devices on the LAN.")

        parser.add_argument("--app_path",               help="The source app path to package an app to allow OTA (over the air) upgrades.", default=None)
        parser.add_argument("--upgrade",                help="The app zip package file or app folder to upgrade a unit.")
        parser.add_argument("--get_config",             action='store_true', help="Get the machine configuration file and store it locally.")
        parser.add_argument("--create_zip",             action='store_true', help="Create an upgrade zip file.")
        parser.add_argument("--status",                 action='store_true', help="Get unit RAM/DISK usage.")
        parser.add_argument("--flist",                  action='store_true', help="Get a list of the files on the unit.")
        parser.add_argument("--mconfig",                action='store_true', help="Get the machine config.")
        parser.add_argument("--eia",                    action='store_true', help="Erase the inactive application.")
        parser.add_argument("--sf",                     help="Send a file to the device.")
        parser.add_argument("--sp",                     help="The path to place the above file on the device.", default="/")
        parser.add_argument("--rf",                     help="Receive a file from the device. Only text files are currently supported.")
        parser.add_argument("--rp",                     help="The local path to place the above file once received.")
        parser.add_argument("--mkdir",                  help="The path to create on the device.")
        parser.add_argument("--rmdir",                  help="The path to remove from the device.")
        parser.add_argument("--rmfile",                 help="The file to remove from the device.")
        parser.add_argument("--getaaf",                 help="Get the active app folder.", action='store_true')
        parser.add_argument("--getiaf",                 help="Get the inactive app folder.", action='store_true')
        parser.add_argument("--reboot",                 help="Reboot the device.", action='store_true')
        parser.add_argument("--power_cycle",            help="Power cycle the unit.", action='store_true')
        parser.add_argument("--defaults",               help="Reset a device to the default configuration.", action='store_true')
        parser.add_argument("--ex_cmd",                 help="An example command handled by project.py on the device.", action='store_true')
        parser.add_argument("--check_mpy_cross",        action='store_true', help="Check that the mpy_cross (bytecode compiler) is installed.")

        options = parser.parse_args()

        uio.enableDebug(options.debug)

        yDevManager = YDevManager(uio, options)
        yDevManager.setIPAddress(options.address)
        ct6Config = CT6Config(uio, options)
        ct6Scanner = CT6Scanner(uio, options)

        if options.config:
            ct6Config.configure()

        elif options.find:
            ct6Scanner.scan()

        elif options.create_zip:
            yDevManager.packageApp()

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

        elif options.ex_cmd:
            yDevManager.exampleCmd()

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
