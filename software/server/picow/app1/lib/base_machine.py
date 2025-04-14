import machine
import gc

import uasyncio as asyncio
from time import time, sleep

from constants import Constants

from lib.wifi import WiFi
from lib.bluetooth import BlueTooth
from lib.ydev import YDev
from lib.config import MachineConfig

from lib.fs import VFS
from lib.uo import UO

class BaseMachine(Constants):
    """A base class for implementation of a machine.
       This contains many useful methods when building IoT products."""
    def __init__(self, uo, configFile, activeAppKey, activeApp, wdt):
        """@brief Constructor.
           @param uo A UO instance.
           @param configFile The config file that holds all machine config including the active application ID.
           @param activeAppKey The key in the config dict that details which app (1 or 2) we are running from.
           @param activeApp The active app. Either 1 or 2.
           @param wdt A WDT instance."""
        self._uo = uo
        self._configFile=configFile
        self._activeAppKey=activeAppKey
        self._activeApp = activeApp
        self._wdt = wdt
        self._wifi = None
        self._blueTooth = None
        self._wifiConnectTime = None
        self._machineConfig = None
        self._yDev = None
        self._paramDict = {}
        self._startTime = time()
        self._restServer = None
        self._projectCmdHandler = None
        self._macAddress = ""
        self._statsDict = {}

        # If the max speed value is set in constants then bump the CPU speed.
        if Constants.MAX_CPU_FREQ_HZ > 0:
            machine.freq(Constants.MAX_CPU_FREQ_HZ)
            self._debug("Set CPU freq to {} MHz (MAX)".format(machine.freq()/1000000))

        VFS.ShowFSInfo(self._uo)

        self._updateActiveApp()

        # Define the time we show the system ram usage on stdout
        self._showRamTime = time() + Constants.SHOW_RAM_POLL_SECS

    def _info(self, msg):
        """@brief Show an info message.
           @param msg The message to display."""
        if self._uo:
            UO.info(self._uo, msg)

    def _error(self, msg):
        """@brief Show an error message.
           @param msg The message to display."""
        if self._uo:
            UO.error(self._uo, msg)

    def _debug(self, msg):
        """@brief Show a debug message.
           @param msg The message to display."""
        if self._uo:
            UO.debug(self._uo, msg)

    def _updateActiveApp(self):
        """@brief Update the active app in the default config and the persistent config."""
        defaultConfigDict = Constants.DEFAULT_CONFIG
        # Add the currently running app to the default config. This is only used
        # when unit stats without a machine config to create the initial config file.
        Constants.RUNNING_APP_KEY = self._activeAppKey
        # The default is to use app 1
        defaultConfigDict[self._activeAppKey]=1
        # We need to ensure that the active app passed to us is what is set in the config file.
        self._machineConfig = MachineConfig(defaultConfigDict)
        self._machineConfig.set(self._activeAppKey, self._activeApp)
        self._machineConfig.store()

    def _initWifi(self):
        """@brief Perform WiFi interface initialisation."""
        # Init the WiFi interface
        self._wifi = WiFi(self._uo,
                          Constants.WIFI_SETUP_BUTTON_PIN,
                          self._wdt,
                          maxRegWaitSecs = Constants.MAX_STA_WAIT_REG_SECONDS,
                          wifiLEDPin = Constants.WIFI_LED_PIN)
        wifiConfigDict = self._getWiFiConfigDict()
        self._debug("wifiConfigDict: {}".format(wifiConfigDict))
        self._wifi.setWiFiConfigDict(wifiConfigDict)
        # Returns a network.WLAN instance or None if we failed to connect to the WiFi
        wlan = self._wifi.setup()
        # If the user wishes to reset the WiFi settings
        if self._wifi.userWiFiReset():
            self._setDefaultConfig()
            self._wifi.reboot()
        # If the WiFi STA (this unit) failed to register with an AP.
        # If we're setup as an AP we should have a network.WLAN instance
        if wlan is None:
            # If this hardware has the ability to power cycle itself.
            if self._projectCmdHandler and self._projectCmdHandler.isPowerCycleSupported():
                self._debug("WiFi failed to register, power cycling unit.")
                sleep(0.25)
                self._projectCmdHandler.powerCycle()
            else:
                self._debug("WiFi failed to register, rebooting unit.")
                sleep(0.25)
                self.reboot()

        self._setMACAddress(self._wifi.getMAC())

    def _initBlueTooth(self):
        """@brief Perform BlueTooth interface initialisation."""
        self._blueTooth = BlueTooth(self._getBTDevName(), ledGPIO=Constants.BLUETOOTH_LED_PIN)
        # Pass ref of the BT interface to the WiFi instance as BT is used to setup the WiFi interface.
        self._wifi.setBlueTooth(self._blueTooth)

    def serviceWiFiSetupMode(self):
        """@brief Perform actions required when WiFi is in setup mode.
                  This should be called periodically (E.G every 0.1 seconds) when WiFi is in setup mode."""
        # Toggle the LED fast to indicate that we are in WiFi setup mode.
        self._wifi.toggleWiFiLED()
        self._wifi.processBTCommands()
        if self._wifi.isConfigured():
            mode = self._wifi.getMode()
            ssid = self._wifi.getSSID()
            password = self._wifi.getPassword()
            self._debug("WiFi settings mode: {}, ssid={}, password={}".format(mode, ssid, password))
            self._setWiFiConfig(mode, ssid, password)
            self.reboot()

    def serviceWiFiConnecting(self):
        """@brief Perform actions required when attempting to connect to a WiFi network.
                  This should be called periodically (E.G once a second) when connecting to a WiFi network.
           @return The IP address of the WiFi interface if connected or None if not connected."""
        # Read the IP address we have on the WiFi network.
        ipAddress = self._wifi.getIPAddress()
        self._debug("WiFi interface IP address: {}".format(ipAddress))
        if ipAddress and len(ipAddress) > 0:
            self._machineConfig.store()
            self._wifiConnectTime = time()

            # As we now have an IP address we can start the servers

            # Start the JSON REST server.
            self._startRestServer()

            # Start the server that responds to YView AYT messages
            self._startYDevServer()

        else:

            # Toggle the LED to indicate that we are attempting to connect to a WiFi network.
            self._wifi.toggleWiFiLED()
            resetWiFiConfig = self._wifi.checkWiFiSetupMode()
            if resetWiFiConfig:
                self._setDefaultConfig()
                self.reboot()

        return ipAddress

    def _showRAMInfo(self):
        """@brief show the RAM usage info."""
        # If it's time to show the ram info
        if time() >= self._showRamTime:
            usedBytes = gc.mem_alloc()
            freeBytes = gc.mem_free()
            totalBytes = usedBytes + freeBytes
            self._info("Total RAM (bytes) {}, Free {}, Used {}, uptime {}".format(totalBytes, freeBytes, usedBytes, time()-self._startTime))
            self._showRamTime = time()++ Constants.SHOW_RAM_POLL_SECS

    def isWifiSetupModeActive(self):
        """@brief Determine if WiFi setup mode is active.
           @return True if WiFi setup mode is active."""
        wifiDict = self._getWiFiConfigDict()
        wifiConfigured = wifiDict[Constants.WIFI_CONFIGURED_KEY]
        return not wifiConfigured

    def _startRestServer(self):
        """@brief Start the REST server running. Must be called after
                  the WiFi network is up."""
        if self._restServer and not self._restServer.isServerRunning():
            self._restServer.startServer()

    def _startYDevServer(self):
        """@brief Start the YDev are you there server."""
        if self._yDev is None:
            # start Yview device listener using uasyncio
            self._yDev = YDev(self._machineConfig)
            self._yDev.setGetParamsMethod(self._getParams)
            asyncio.create_task(self._yDev.listen())

    def _getParams(self):
        """@brief Get the parameters (in a dict) we wish to include in the AYT response message."""
        if self._projectCmdHandler:
            self._statsDic = self._projectCmdHandler.getStatsDict()
        return self._statsDic

    def _getWiFiConfigDict(self):
        """@return Get the WiFi config dict."""
        return self._machineConfig.get( Constants.WIFI_KEY )

    def _setDefaultConfig(self):
        """@brief Set WiFi Defaults."""
        # We actually set all machine config to the default values.
        self._machineConfig.setDefaults()
        # Ensure the WiFi LED is off when the default config is set
        self._wifi.setWiFiLED(False)
        self._debug("Reset Wifi config to setup mode.")

    def _setWiFiConfig(self, mode, ssid, password):
        """@brief Set the WiFi cnfiguration.
           @param mode The WiFi mode (AP/STA)
           @param ssid The WiFi SSID
           @param password The WiFi password."""
        self._machineConfig.set( (Constants.WIFI_KEY, Constants.WIFI_CONFIGURED_KEY), 1 )
        self._machineConfig.set( (Constants.WIFI_KEY, Constants.MODE_KEY), mode )
        self._machineConfig.set( (Constants.WIFI_KEY, Constants.SSID_KEY), ssid )
        self._machineConfig.set( (Constants.WIFI_KEY, Constants.PASSWORD_KEY), password )
        self._machineConfig.store()

    def _setMACAddress(self, macAddress):
        """@brief Let the machine know the MAC address of the WiFi interface."""
        self._macAddress = macAddress

    def _getBTDevName(self):
        """@brief Get the Bluetooth device name."""
        return Constants.BT_NAME + self._macAddress

    def reboot(self, preRestartDelay=0.25):
        """@brief Reboot machine."""
        self._debug("Rebooting in {:.2f} seconds.".format(preRestartDelay))
        if preRestartDelay > 0.0:
            sleep(preRestartDelay)
        machine.reset()

    def _updateBlueTooth(self):
        """@brief Update the state of the bluetooth radio.
                  The app that sets up the WiFi turns off bluetooth by sending a command over bluetooth to
                  instruct this unit to turn off its bluetooth interface."""
        shutDownBlueTooth = self._wifi.processBTCommands()
        if shutDownBlueTooth:
            self._machineConfig.set(Constants.BLUETOOTH_ON_KEY, 0)
            self._machineConfig.store()
            self._info("Bluetooth shutdown now the unit has an IP address via DHCP.")

    def _updateWiFi(self):
        """@brief Check if the user wishes to reset the WiFi config
           @return True if the Wifi is connected."""
        resetWiFiConfig = self._wifi.checkWiFiSetupMode()
        if resetWiFiConfig:
            self._setDefaultConfig()
            self.reboot()
        return self._wifi.connected()
