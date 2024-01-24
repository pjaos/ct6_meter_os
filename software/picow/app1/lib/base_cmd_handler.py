import machine

import os

from constants import Constants

from lib.rest_server import RestServer
from lib.uo import UO
from lib.hardware import Hardware

class BaseCmdHandler(object):
    """@brief Provide a base class to Handle project commands dicts sent over the network."""
    # The following RPC's are provided by this base class. This class should be extended to 
    # provide product specific RPC's 
    # http://<IP ADDRESS>:80/get_config                              # Get the contents of the config dict 
    # http://<IP ADDRESS>:80/get_stats                               # This reports all the AC power stats for all ports
    # http://<IP ADDRESS>:80/power_cycle                             # Called to turn the power supply on/off for real power cycle
    # http://<IP ADDRESS>:80/set_config?<PARAMETER NAME>=<A VALUE>   # All the Constants attributes that are present in the DEFAULT_CONFIG dict
                                                                     # are config parameters and can be set.

    # Multiple parameters may be set in one HTTP GET using comma separated arguments
    # E,G
    # http://<IP ADDRESS>:80/set_config?ARG1=0,ARG2=1,ARG3=2
    # Commmands that can be received over the REST interface
    GET_CONFIG_CMD              = "/get_config"
    SET_CONFIG_CMD              = "/set_config"
    GET_STATS                   = "/get_stats"
    POWER_CYCLE                 = "/power_cycle"
    FW_VERSION                  = "/fw_version"
        
    def __init__(self, uo, machineConfig):
        """@brief Constructor
           @param uo A UO instance for displaying data on stdout.
           @param machineConfig The machine configuration instance."""
        self._uo = uo
        self._machineConfig = machineConfig
        self._powerCyclePin = None
        self._wifi = None
        self._savePersistentDataMethod = None
        if Constants.POWER_CYCLE_GPIO >= 0:
            self._powerCyclePin = machine.Pin(Constants.POWER_CYCLE_GPIO, machine.Pin.OUT, value=0)
        self._powerCycleTimer = Hardware.GetTimer()

    def setWiFi(self, wiFi):
        """@brief Set a reference to the WiFi object."""
        self._wifi = wiFi
        
    def _info(self, msg):
        """@brief Show an info message.
           @param msg The message to display."""
        if self._uo:
            UO.info(self._uo, msg)

    def _debug(self, msg):
        """@brief Show a debug message.
           @param msg The message to display."""
        if self._uo:
            UO.debug(self._uo, msg)

    def _error(self, msg):
        """@brief Show an error message.
           @param msg The message to display."""
        if self._uo:
            UO.error(self._uo, msg)

    def handle(self, cmdDict):
        """@brief Process the commands received as a JSON string from the client and return a response dict.
           @return A dict in response to the command."""
        handled = False
        responseDict = {RestServer.ERROR_KEY: "NO command found."}

        # Note that BuiltInCmdHandler in lib/rest_server.py has a number of built in commands
        # Look here first before adding a new command here.
        if RestServer.CMD_KEY in cmdDict:
            cmd = cmdDict[RestServer.CMD_KEY]
            # If / then default to get stats
            if cmd == '/':
                cmd = BaseCmdHandler.GET_STATS

            # Define the error response.
            responseDict = {RestServer.ERROR_KEY: "{} is an invalid command.".format(cmd)}

            if cmd.startswith( BaseCmdHandler.GET_CONFIG_CMD ):
                responseDict = self._getConfig(cmdDict)
                handled = True
                
            elif cmd.startswith( BaseCmdHandler.GET_STATS ):
                responseDict = self.getStatsDict()
                handled = True

            elif cmd.startswith( BaseCmdHandler.SET_CONFIG_CMD ):
                responseDict = self._setConfig(cmdDict)
                handled = True

            elif cmd.startswith( BaseCmdHandler.POWER_CYCLE ):
                self.powerCycle()
                responseDict = {RestServer.OK_KEY: "POWER CYCLE IN PROGRESS"}
                handled = True

            elif cmd.startswith( BaseCmdHandler.FW_VERSION ):
                responseDict = {"FIRMWARE_VERSION": Constants.FIRMWARE_VERSION}
                handled = True
                
        if not handled:
            responseDict = self._handle(cmdDict)
            
        return responseDict

    def _getConfig(self, cmdDict):
        """@brief An example command.
           @param cmdDict The command dict received."""
        return self._machineConfig

    def _getDictValue(self, key, theDict):
        """@brief Get a value from a dict with either
                  - The key value
                  - The upper case key value
                  - The lower case key value
           @param key The dict key.
           @param The value or None if not found."""
        value = None
        if key in theDict:
            value = theDict[key]

        elif key.lower() in theDict:
            value = theDict[key.lower()]

        elif key.upper() in theDict:
            value = theDict[key.upper()]

        return value

    def _getNumericValue(self, key, theDict, checkFloat=True, validRange=None):
        """@brief Get a number value from a dict.
           @param key The dict key.
           @param theDict The dict holding the value.
           @param checkFloat If True a float value is expected. f False then an int value is expected.
           @param validRange A range instance defining the min and max acceptable values.
                             This may be left as None if no range check is required.
           @return The value or None if the key is not found."""
        value = self._getDictValue(key, theDict)
        if value is not None:
            try:
                if checkFloat:
                    value = float(value)
                else:
                    value = int(value)

            except ValueError:
                if checkFloat:
                    valueType = "float"
                else:
                    valueType = "int"
                raise Exception("{}: {} is an invalid {} value.".format(key, value, valueType))

            if validRange and value not in validRange:
                raise Exception("{}: {} is not in the valid range of {}.".format(key, value, str(validRange) ))

        return value

    def _setConfig(self, cmdDict):
        """@brief Set one or more persistent config values.
           @param cmdDict The command dict received."""
        returnDict = {}
        self._debug("cmdDict={}".format(cmdDict))

        # Add your attributes to the Constants.SETABLE_ATTRIBUTE_LIST so that config options can be set
        # via the rest interface.
        
        # Itterate through the setable parameters
        for key in Constants.SETABLE_ATTRIBUTE_LIST:
            # keys are returned in lower case from the http request
            key=key.lower()
            value = None
            try:
                # Check for numeric value first
                value = self._getNumericValue(key, cmdDict)

            except:
                # Check for string value
                value = self._getDictValue(key, cmdDict)
                
            if value is not None:
                # All config parameters must be upper case.
                key=key.upper()
                self._machineConfig.set(key, value)
                self._machineConfig.store()
                self._debug("Updated persistent config {}={}".format(key, value))
                returnDict[key]=value

        # If no response define then error
        if len(list(returnDict.keys())) == 0:
            return {"ERROR": "Config parameter unset"}
        else:
            return returnDict

    def powerCycle(self):
        """@Power cycle the board by asserting a GPIO."""
        # If we have a valid GPIO pin then we assume we have the hardware to
        # power cycle the board connected to this pin.
        if self._powerCyclePin:
            # Save any persistent data before we reboot
            if self._savePersistentDataMethod:
                self._savePersistentDataMethod()
            self._info("Power cycling MCU")
            # Ensure the file system is synced before we reboot.
            os.sync()           
            delay=250
            # Start timer to set power cycle pin high and turn off the 3V3 regulator.
            self._powerCycleTimer.init(mode=machine.Timer.PERIODIC, period=delay, callback=self._powerOff)
            
    def _powerOff(self, timer):
        """@brief Called to actually perform the power cycle.
           @param timer The Timer instance that called this method."""
        if self._powerCyclePin:
            self._powerCyclePin.value(1)
                        
    def isPowerCycleSupported(self):
        """@return True if this hardware supports power cycling."""
        supported = False
        if self._powerCyclePin:
            supported = True
        return supported

    def setSavePersistentDataMethod(self, savePersistentDataMethod):
        """@brief Set the method to be called to save all persistent data on the device.
                  This method will be called before a reboot or power cycle in order to save the current system state.
           @param savePersistentDataMethod The method to be called to save all persistent data on the unit."""
        self._savePersistentDataMethod = savePersistentDataMethod
