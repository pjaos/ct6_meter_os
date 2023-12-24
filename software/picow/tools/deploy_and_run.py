#!/usr/bin/env python3

import argparse
import os
import glob
import serial
import json
from   time import sleep
from   subprocess import check_call, DEVNULL, STDOUT

class MCULoader(object):
    # Convert .py files in app1 and app1/lib to .mpy files.
    # to reduce the RAM memory required to run the code.
    # The files are then loaded onto an MCU.


    REQUIRED_PYPI_MODULES = ["rshell", "mpy_cross"]

    MPY_CMDLINE_PREFIX = "python3 -m mpy_cross "

    FOLDERS = ['app1', 'app1/lib', 'app1/lib/drivers']

    CONFIG_FILE = "this.machine.cfg"
    REMOVE_CONFIG_FILE_CMD = f"rm -r /pyboard/{CONFIG_FILE}"
    START_APP_CMD = "repl pyboard import main"
    CMD_LIST = ["rm -r /pyboard/*.py",
                "rm -r /pyboard/app1",
                "rm -r /pyboard/app2",
                "mkdir /pyboard/app1",
                "mkdir /pyboard/app1/lib",
                "mkdir /pyboard/app1/lib/drivers",
                "mkdir /pyboard/app2",
#                "# Load a default config file. This should run the app from app1. If not present the previous config file will be used.",
                f"cp {CONFIG_FILE} /pyboard/",
                "cp main.py /pyboard/",
                "cp -r app1/*.mpy /pyboard/app1/",
                "cp -r app1/lib/*.mpy /pyboard/app1/lib/",
                "cp -r app1/lib/drivers/*.mpy /pyboard/app1/lib/drivers/"]

    CMD_LIST_FILE = "cmd_list.cmd"
    
    RSHELL_GET_CONFIG_CMD = f"cp /pyboard/{CONFIG_FILE} ."
    GET_CONFIG_CMD_FILE = "get_cfg.cmd"

    def __init__(self, options):
        """@brief Constructor
           @param options An instance of the OptionParser command line options."""
        self._options = options
        self._serial = None
        
    def _info(self, msg):
        """@brief display an info level message.
           @param msg The message text."""
        print("INFO:  {}".format(msg))

    def _input(self, msg):
        """@brief display a input prompt and ask user for input.
           @param msg The message text."""
        print("INPUT: {}".format(msg))
        return input()

    def _debug(self, msg):
        """@brief display an info level message.
           @param msg The message text."""
        if self._options.debug:
            print("DEBUG:  {}".format(msg))

    def _checkModulesInstalled(self):
        """@brief Check the required python modules are installed to rnu this tool."""
        for module in MCULoader.REQUIRED_PYPI_MODULES:
            self._info("Checking that the {} python module is installed.".format(module))
            cmd = "python3 -m pip install {}".format(module)
            check_call(cmd, shell=True, stdout=DEVNULL, stderr=STDOUT)

    def _getFileList(self, extension):
        """@brief Get a list of files with the given extension."""
        fileList = []
        if not extension.startswith("."):
            extension = ".{}".format(extension)

        for folder in MCULoader.FOLDERS:
            entries = os.listdir(folder)
            for entry in entries:
                if entry.endswith(extension):
                    fileList.append( os.path.join(folder, entry) )

        return fileList

    def _deleteFiles(self, fileList):
        """@brief Delete files details in the file list."""
        for aFile in fileList:
            if os.path.isfile(aFile):
                os.remove(aFile)
                self._info("Deleted {}".format(aFile))

    def deleteMPYFiles(self):
        """@brief Delete existing *.mpy files"""
        pyFileList = self._getFileList(".mpy")
        self._deleteFiles(pyFileList)

    def _convertToMPY(self):
        """@brief Generate *.mpy files for all files in app1 and app1/lib"""
        mpyFileList = []
        pyFileList = self._getFileList(".py")
        for pyFile in pyFileList:
            cmd = "{}{}".format(MCULoader.MPY_CMDLINE_PREFIX, pyFile)
            check_call(cmd, shell=True)
            mpyFile = pyFile.replace(".py", ".mpy")
            self._info("Generated {} from {}".format(mpyFile, pyFile))
            if not os.path.isfile(mpyFile):
                raise Exception("Failed to generate the {} file.".format(mpyFile))
            mpyFileList.append(mpyFile)

        return mpyFileList

    def _loadFiles(self, fileList, port):
        """@brief Load files onto the micro controller device.
           @param fileList The list of files to load.
           @param port The serial port to use."""
        # Create the list of commands to execute
        fd = open(MCULoader.CMD_LIST_FILE, 'w')
        if self._options.factory_reset:
            fd.write("{}\n".format(MCULoader.REMOVE_CONFIG_FILE_CMD))
            if os.path.isfile(MCULoader.CONFIG_FILE):
                while True:
                    self._info("{} file exists in this folder.".format(MCULoader.CONFIG_FILE))
                    response = self._input("Delete local config file y/n: ")
                    response=response.lower()
                    if response == 'y':
                        os.remove(MCULoader.CONFIG_FILE)
                        self._info("Deleted {}.".format(MCULoader.CONFIG_FILE))
                        self._info("The {} default config file will be created on the unit when it starts.".format(MCULoader.CONFIG_FILE))
                        break
                    if response == 'n':
                        self._info("Leaving {} file to be loaded onto unit.".format(MCULoader.CONFIG_FILE))
                        break
                            
        cmdList = MCULoader.CMD_LIST
        if not self._options.disable_app1_start:
            cmdList.append(MCULoader.START_APP_CMD)
        for l in cmdList:
            fd.write("{}\n".format(l))
        fd.close()
       
        self._runCmd(port, MCULoader.CMD_LIST_FILE)
        
    def _createGetConfigCmdFile(self):
        """@brief Write the command file for getting the config file from the unit."""
        with open(MCULoader.GET_CONFIG_CMD_FILE, 'w') as fd:
            fd.write("{}\n".format(MCULoader.RSHELL_GET_CONFIG_CMD))
            
    def _runCmd(self, port, cmdFile):
        """@brief Run an rshell command file.
           @param port The serial port to run the command over.
           @param cmdFile The rshell command file to execute."""
        if self._options.picow:
            rshellCmd = "rshell --rts 1 --dtr 1 --timing -p {} --buffer-size 512 -f {}".format(port, cmdFile)
        else:
            rshellCmd = "rshell --rts 0 --dtr 0 --timing -p {} --buffer-size 512 -f {}".format(port, cmdFile)
        self._debug(f"EXECUTING: {rshellCmd}")
        os.system(rshellCmd)
        
    def _checkApp1(self):
        """@brief run pyflakes3 on the app1 code."""
        self._info("Checking app1 using pyflakes3")
        cmd = "pyflakes3 app1/"
        rc = os.system(cmd)
        if rc  != 0:
            raise Exception("Fix the pyflakes3 errors and try again.")

    def _ensureApp1(self, port):
        """@brief Ensure the configuration is set to run app1.
           @param port The serial port to run the command over."""
        
        # If the user wishes to load a pre existing local config file.
        if self._options.local_config:
            if not os.path.isfile(MCULoader.CONFIG_FILE):
                raise Exception(f"Local {MCULoader.CONFIG_FILE} file not found.")
                
        # Get the config file from the unit
        else:
            self._createGetConfigCmdFile()
            # Remove local config file if it exists
            if os.path.isfile(MCULoader.CONFIG_FILE):
                os.remove(MCULoader.CONFIG_FILE)
                self._info("Deleted {}".format(MCULoader.CONFIG_FILE))
                            
            # Get the config file from the unit
            self._runCmd(port, MCULoader.GET_CONFIG_CMD_FILE)
            
        # Ensure the config file to be loaded back to the CT6 device has APP1 selected.
        if os.path.isfile(MCULoader.CONFIG_FILE):
            with open(MCULoader.CONFIG_FILE, 'r') as fd:
                data=fd.read()
            #Set active app == 1
            cfgDict = json.loads(data)
            cfgDict["APP"]=1
            # Update the local config file. This will be loaded onto the unit later.
            with open(MCULoader.CONFIG_FILE, 'w') as fd:
                json_str = json.dumps(cfgDict, indent=4) + '\n'
                fd.write(json_str)
        else:
            raise Exception(f"Unable to force APP1 execution as {MCULoader.CONFIG_FILE} file not found.")

    def load(self):
        """@brief Load the python code onto the micro controller device."""
        if not self._options.esp32 and not self._options.picow:
            raise Exception("Please define the hardware type. Either --esp32 or --picow")

        self._checkApp1()     
        
        port = self._ensurePythonPrompt()
        
        self._checkModulesInstalled()
        self.deleteMPYFiles()
        localFileList = ["main.py"]
        self.deleteMPYFiles()
        mpyFileList = self._convertToMPY()
        filesToLoad = localFileList + mpyFileList
        self._ensureApp1(port)
        self._loadFiles(filesToLoad, port)
        # Remove the *.mpy files so they are not left lying around next to the *.py files.
        #self.deleteMPYFiles()

    def _openSerialPort(self, port):
        """@brief Open the serial port with the required parameters.
           @param port The serial port to open."""
        self._serial = serial.Serial(
            port=port,
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout= 3
        )
        self._info("Opened serial port: {}".format(port))

    def _ensurePythonPrompt(self):
        """@brief Ensure we have the python prompt on a the first available serial port.
           @return The connected serial port."""
        microPythonBannerDetected = False
        try:
            port = self._openFirstAvailableSerialPort() 
            while True:
                # Send CTRL C
                self._serial.write(b'\x03')
                self._debug("Sent CTRL C")
                sleep(0.25)
                # Send CTRL B to get python prompt
                self._serial.write(b'\x02')
                self._debug("Sent CTRL B")
                bytesRead = self._serial.read_until()
                sRead = bytesRead.decode()
                self._debug(sRead)
                if sRead.startswith("MicroPython"):
                    self._info(sRead)
                    microPythonBannerDetected = True
                    
                if microPythonBannerDetected and sRead == '>>> \r\n':
                    self._info("Detected Python prompt.")
                    self._serial.write(b'\r')
                    bytesRead = self._serial.read_until()
                    sRead = bytesRead.decode()
                    self._info("MicroPython prompt returned after CR")
                    break

        finally:
            if self._serial:
                self._serial.close()
                
        return port 
            
    def _getFirstAvailableSerialPort(self):
        """@brief Attempt to get the name of the first available serial port."""
        self._info(f"Checking for serial ports")
        checking = True
        while checking:
            port = None
            ports = glob.glob('/dev/ttyACM*')
            if len(ports) > 0:
                port = ports[0]
                checking = False
                
            if port is None:
                ports = glob.glob('/dev/ttyUSB*')
                if len(ports) > 0:
                    port = ports[0]
                    checking = False
                    
            sleep(0.05)
        return port
                    
    def _openFirstAvailableSerialPort(self):
        """@brief Open the first available serial port.
           @return port The serial port opened."""
        running = True
        while running:
            port = self._getFirstAvailableSerialPort()
            if port:
                self._info(f"Detected {port}")
                while running:
                    try:
                        self._openSerialPort(port)
                        running = False
                        break
                    except KeyboardInterrupt:
                        running = False
                    except:
                        pass
            else:
                sleep(0.05)
                
        return port
                        
    def viewSerial(self):
        """@brief Connect to the first available serial port and show the data received as early as possible."""
        running = True
        while running:
            port = self._openFirstAvailableSerialPort()
            sleep(1)
            try:
                try:           
                    #self._serial.write(b'\r')         
                    while running:
                        bytesRead = self._serial.read_until()
                        sRead = bytesRead.decode()
                        sRead = sRead.rstrip('\r\n')
                        if len(sRead) > 0:
                            print(sRead)
                            
                except KeyboardInterrupt:
                    running = False
                except:
                    pass
                                                
            finally:
                if self._serial:
                    self._serial.close()
                    self._serial = None
                    self._info(f"Closed {port}")
                    
    def startApp1(self):
        """@brief Run the command to start app1 but do not load data to the microcontoller.
                  This can be used after the --disable_app1_start command line option is used to start app1."""
        port = self._ensurePythonPrompt()
        # Create the list of commands to execute
        fd = open(MCULoader.CMD_LIST_FILE, 'w')
        fd.write("{}\n".format(MCULoader.START_APP_CMD))
        fd.close()
       
        self._runCmd(port, MCULoader.CMD_LIST_FILE)
        
def main():
    """@brief Program entry point"""

    try:
        parser = argparse.ArgumentParser(description="Load python code onto an MCU (esp32 or pico W) device running micropython..",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",        action='store_true', help="Enable debugging.")
        parser.add_argument("-e", "--esp32",        action='store_true', help="Load ESP32 hardware.")
        parser.add_argument("-p", "--picow",        action='store_true', help="Load RPi pico W hardware.")
        parser.add_argument("-l", "--load",         action='store_true', help="Convert the app1 folder .py files to .mpy files and load onto the micro controller..")
        parser.add_argument("-r", "--remove",       action='store_true', help="Remove all local .mpy files.")
        parser.add_argument("-f", "--factory_reset",action='store_true', help="Reset the configuration to factory defaults.")
        parser.add_argument("--local_config",       action='store_true', help="Use a local this.machine.cfg config file. By default the config is pulled from the CT6 device.")
        parser.add_argument("--disable_app1_start", action='store_true', help="By default app1 is started once loaded. Use this option to disable starting app1.")    
        parser.add_argument("--start_app1",         action='store_true', help="Run the command to start app1 but do not load data to the microcontoller.")    
        parser.add_argument("-v", "--view",         action='store_true', help="View received data on first /dev/ttyUSB* or /dev/ttyACM* serial port.")

        options = parser.parse_args()

        mcuLoader = MCULoader(options)

        if options.remove:
            mcuLoader.deleteMPYFiles()
            
        elif options.view:
            mcuLoader.viewSerial()
            
        elif options.start_app1:
            mcuLoader.startApp1()
            
        else:
            mcuLoader.load()           

    #If the program throws a system exit exception
    except SystemExit:
        pass

    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass

    except Exception as ex:

        if options.debug:
            raise
        else:
            print(str(ex))

if __name__== '__main__':
    main()
