import network
import time
import binascii
import json

from time import sleep
from machine import Pin
from lib.uo import UO
from constants import Constants

class WiFi(object):
    """@brief Responsible for accessing the WiFi interface."""

    AP_IP_ADDRESS               = '192.168.4.1'   # The IP address to access the unit when configuring the WiFi from the web server interface.
    AP_SUBNET_MASK              = '255.255.255.0' # The netmask of the above interface.
    WIFI_SETUP_BUTTON_HOLD_SECS = 5               # The number of seconds the WiFi button must be held down by the user to move to WiFi setup mode.
    AP_CHANNEL                  = 3               # The WiFi channel used in setup mode.

    WIFI_CONFIGURED_KEY         = "WIFI_CFG"
    MODE_KEY                    = "MODE"
    AP_CHANNEL                  = "CHANNEL"
    PASSWORD_KEY                = "PASSWD"

    MODE_AP                     = 'AP'
    MODE_STA                    = 'STA'

    SSID_KEY                    = "SSID"
    BSSID_KEY                   = "BSSID"
    CHANNEL_KEY                 = "CHANNEL"
    RSSI_KEY                    = "RSSI"
    SECURITY_KEY                = "SECURITY"
    HIDDEN_KEY                  = "HIDDEN"

    SECURITY_OPEN               = 0
    SECURITY_WEP                = 1
    SECURITY_WPA_PSK            = 2
    SECURITY_WPA2_PSK           = 3
    SECURITY_WPA_WPA2_PSK       = 4

    BT_CMD                      = "CMD"
    BT_CMD_WIFI_SCAN            = "WIFI_SCAN"
    WIFI_SCAN_COMPLETE          = "WIFI_SCAN_COMPLETE"
    BT_CMD_STA_CONNECT          = "BT_CMD_STA_CONNECT"
    STA_CONNECTED               = ""
    BT_CMD_PCP_CONNECT          = "BT_CMD_PCP_CONNECT"
    WIFI_CONFIGURED             = "WIFI_CONFIGURED"
    BT_CMD_GET_IP               = "GET_IP"
    IP_ADDRESS                  = "IP_ADDRESS"
    DISABLE_BT                  = "DISABLE_BT"

    @staticmethod
    def Get_Wifi_Networks(uo=None):
        """@brief Get details of all the detectable WiFi networks.
           @param uo A UO instance if debugging is required. Default=None.
           @return A list of Wifi networks. Each WiFi network is a dict of parameters
                    SSID_KEY        The network ssid
                    BSSID_KEY       bssid is returned as a string of 6 hex characters each one separated by a '0x' characters
                    CHANNEL_KEY     The channel as an integer
                    RSSI_KEY        The RSSI as a float
                    SECURITY_KEY    The security as an int
                    HIDDEN_KEY      An int, 1=hidden, 0=visible
        """
        wifi_network_list = []
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if uo:
            uo.debug("Starting WiFi network scan.")
        # Returns a tuple each element of which contains
        # (ssid, bssid, channel, RSSI, security, hidden)
        # bssid = MAC address of AP
        # There are five values for security:
        # 0 – open
        # 1 – WEP
        # 2 – WPA-PSK
        # 3 – WPA2-PSK
        # 4 – WPA/WPA2-PSK
        # and two for hidden:
        # 0 – visible
        # 1 – hidden
        networks = wlan.scan()
        for n in networks:
            if n[0] != b'\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                ssid      = n[0].decode()
                bssid     = binascii.hexlify(n[1],'0x').decode()
                try:
                    channel   = int(n[2])
                    rssi      = float(n[3])
                    security  = int(n[4])
                    hidden    = int(n[5])
                    wifiNetworkDict = { WiFi.SSID_KEY: ssid,
                                        WiFi.BSSID_KEY: bssid,
                                        WiFi.CHANNEL_KEY: channel,
                                        WiFi.RSSI_KEY: rssi,
                                        WiFi.SECURITY_KEY: security,
                                        WiFi.HIDDEN_KEY: hidden}
                    wifi_network_list.append( wifiNetworkDict )
                    if uo:
                        uo.debug("Detected WiFi network: {}".format(wifiNetworkDict))

                except ValueError:
                    pass

        return wifi_network_list

    @staticmethod
    def GetWifiAddress():
        """@brief Get the WiFi IP address.
           @return The IP address of the WiFi interface in STA mode or an empty string."""
        ipAddress = ""
        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            status = sta.ifconfig()
            if status:
                ipAddress = status[0]
        return ipAddress

    def __init__(self,
                 uo,
                 wifiButtonGPIO,
                 wdt,
                 useOnBoardLED=False,
                 wifiLEDPin=-1,
                 maxRegWaitSecs=60):
        """@brief Constructor
           @param uo A UO instance.
           @param wifiButtonGPIO The GPIO pin with a button to GND that is used to setup the WiFi.
           @param wdt A WDT instance.
           @param useOnBoardLED Use the picow on board LED to indicate the WiFi state.
           @param wifiLEDPin If an external LED is connected to indicate WiFi state
                             this should be set to the GPIO pin number with the LED
                             connected or left at -1 if only using the on board LED.
           @param maxRegWaitSecs The maximum time (seconds) to wait to register on the WiFi network.
            """
        self._uo = uo
        self._wifiButtonGPIO = wifiButtonGPIO
        self._wdt = wdt
        self._wifiLEDPin = wifiLEDPin
        self._wifiLed = None
        self._wifiButtonPressedTime = None
        self._maxRegWaitSecs = maxRegWaitSecs
        self._initButton()
        self._initLED()
        self._wifiConnected = False
        self._staMode = False
        self._wlan = None
        self._ipAddress = ""
        self._nextCheckSetupTime = time.time() + 1
        self._blueTooth = None
        self._wifiMode = None
        self._wifiSSID = None
        self._wifiPassword = None
        self._resetWiFiSettings = False
        self._forceWiFiLEDState = False

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

    def setWiFiConfigDict(self, wifiConfigDict):
        """@brief Set the WiFi Config dict. This must be set before calling self.setup().
           @param wifiConfigDict The WiFi config dict."""
        # Ensure the dict contains the required keys
        if WiFi.WIFI_CONFIGURED_KEY in wifiConfigDict and\
           WiFi.SSID_KEY in wifiConfigDict and\
           WiFi.MODE_KEY in wifiConfigDict and\
           WiFi.AP_CHANNEL in wifiConfigDict and\
           WiFi.PASSWORD_KEY in wifiConfigDict:

           self._wifiConfigDict = wifiConfigDict

    def setBlueTooth(self, blueTooth):
        """@brief Set the bluetooth instance that can be used to configure the WiFi."""
        self._blueTooth = blueTooth

    def _initButton(self):
        """@brief Init the WiFi setup button."""
        if self._wifiButtonGPIO >= 0:
            self._wifiButton = Pin(self._wifiButtonGPIO, Pin.IN, Pin.PULL_UP)
        else:
            raise Exception("WiFi setup button GPIO pin not set.")

    def _initLED(self):
        """@brief Init the WiFi status LED if set."""
        if self._wifiLEDPin >= 0:
            self._wifiLed = Pin(self._wifiLEDPin, Pin.OUT, value=0)

    def getMAC(self):
        """@return The MAC address of the WiFi interface on this device."""
        mode = network.STA_IF
        if self._wifiConfigDict[WiFi.MODE_KEY] == WiFi.MODE_AP:
            mode = network.AP_IF
        ap = network.WLAN(mode)
        if not ap.active():
            ap.active(True)
        ap_mac = ap.config('mac')
        return "{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}".format(ap_mac[0], ap_mac[1], ap_mac[2], ap_mac[3], ap_mac[4], ap_mac[5])

    def getDefaultSSID(self):
        """@brief Get the SSID of the unit is in setup mode.
                  I.E The user needs to configure the WiFi."""
        defaultSSIDPrefix = self._wifiConfigDict[WiFi.SSID_KEY]
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap_mac = ap.config('mac')
        full_ssid = "{}{:02x}{:02x}{:02x}".format(defaultSSIDPrefix, ap_mac[0], ap_mac[1], ap_mac[2])
        return full_ssid

    def _configAP(self, ssid, password, powerSaveMode=False):
        """@brief configure the WiFi in AP mode.
           @paraam ssid The AP's SSID.
           @param password The password for the network.
           @param powerSaveMode If True then run the wiFi in power save mode (PICOW only).
           @return A WLAN instance."""
        # When in AP mode we set a fixed AP address
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        if powerSaveMode:
            ap.config(pm = 0xa11140) # Disable power-save mode (PICOW only).
        ap.ifconfig((WiFi.AP_IP_ADDRESS, WiFi.AP_SUBNET_MASK, WiFi.AP_IP_ADDRESS, '1.1.1.1'))
        channel = self._wifiConfigDict[WiFi.AP_CHANNEL]
        ap.config(essid=ssid, channel=channel, password=password)
        self._info("Activating WiFi.")
        # Wait to go active
        startT = time.time()
        while ap.active() == False:
          if time.time() > startT+Constants.WIFI_ACTIVE_TIMEOUT_SECONDS:
              raise Exception("Hardware Issue: {} timeout waiting for WiFi to go active.".format(Constants.WIFI_ACTIVE_TIMEOUT_SECONDS))
          sleep(0.25)

        status = ap.ifconfig()
        self._ipAddress = status[0]
        self._debug("Set AP mode ({}/{}).".format(self._ipAddress, WiFi.AP_SUBNET_MASK))
        self.setWiFiLED(True)
        self._wifiConnected = True
        self._staMode = False
        return ap

    def userWiFiReset(self):
        """@brief Determine if the user wishes to reset the WiFi settings.
           @return True if the user wishes to reset the WiFi settings."""
        return self._resetWiFiSettings

    def _configSTA(self, ssid, password, powerSaveMode=False):
        """@brief Configure the WiFi in STA mode.
           @paraam ssid The AP's SSID.
           @param password The password for the network.
           @param powerSaveMode If True then run the wiFi in power save mode (PICOW only).
           @return A WLAN instance if connected. None if not connected."""
        if self._wifiLed:
            # Set WiFi LED off before we start
            self._wifiLed.value(False)

        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if powerSaveMode:
            sta.config(pm = 0xa11140) # Disable power-save mode (PICOW only).
        sta.connect(ssid, password)
        startT = time.time()
        while True:
            wifi_status = sta.status()
            self._debug("wifi_status={}".format(wifi_status))
            if sta.isconnected():
                break

            # If we were not able to connect to a WiFi network return None
            elif time.time() >= startT+self._maxRegWaitSecs:
                return None

            resetWiFiConfig = self.checkWiFiSetupMode()
            if resetWiFiConfig:
                self._resetWiFiSettings = True
                return None

            sleep(0.5)
            self._patWDT()

        self._debug('connected')
        status = sta.ifconfig()
        self._ipAddress = status[0]
        self._debug('ip = ' + self._ipAddress)
        self.setWiFiLED(True)
        self._wifiConnected = True
        self._staMode = True

        return sta

    def _patWDT(self):
        if self._wdt:
           self._wdt.feed()

    def getRSSI(self):
        """@brief Get the RSSI of the network/SSID to which we are connected."""
        sta = network.WLAN(network.STA_IF)
        return sta.status('rssi')

    def _configWifi(self, wifiCfgDict):
        """@brief Setup the Wifi as per the configuration.
           @param wifiCfgDict A Dict containing in the WiFi configuration.
           @return An instance of network.WLAN. None if not connected."""
        mode = wifiCfgDict[WiFi.MODE_KEY]
        ssid = wifiCfgDict[WiFi.SSID_KEY]
        password = wifiCfgDict[WiFi.PASSWORD_KEY]

        if mode == WiFi.MODE_AP:
            wlan = self._configAP(ssid, password)
            if wlan:
                self._debug("Setup AP with SSID={}, IP Address={}".format(ssid, self.getIPAddress()))
                self.setWiFiLED(True)

        elif mode == WiFi.MODE_STA:
            wlan = self._configSTA(ssid, password)
            if wlan:
                self._debug("Setup STA and connected to {}, IP Address={}".format(ssid, self.getIPAddress()))
                self.setWiFiLED(True)

        else:
            raise Exception("{} is an invalid WiFi mode.".format(mode))

        self._wlan = wlan
        return self._wlan

    def setup(self):
        """@brief Setup the WiFi networking.
           @return An instance of the WiFi network or None if not connected."""
        if self.isSetupModeActive():
            # The WiFi has not been setup therefore we set AP mode and allow
            # the user to configure the WiFi settings via the android app.
            ssid = self.getDefaultSSID()
            password = self._wifiConfigDict[WiFi.PASSWORD_KEY]
            wlan = self._configAP(ssid, password)

        else:
            wlan = self._configWifi(self._wifiConfigDict)
        return wlan

    def isSetupModeActive(self):
        """@brief Determine if the Wifi setting are currently being setup.
           @return True if setup mode is active."""
        return not self._wifiConfigDict[WiFi.WIFI_CONFIGURED_KEY]

    def isWiFiButtonPressed(self):
        """@brief Determine if the WiFi button is currently pressed.
           @return True if the WiFi button is pressed."""
        pressed = False
        if self._wifiButton.value() == 0:
            pressed = True

        if not pressed:
            self._wifiButtonPressedTime = None
            self.setWiFiLED(self._wifiConnected)

        return pressed

    def checkWiFiSetupMode(self):
        """@brief Check for WiFi setup mode.
                  This must be called periodically to see if the user is holding down the WiFi setup button.
           @return True if we should reset the WiFi config to the defaults."""
        defaultWiFiConfig = False
        if time.time() < self._nextCheckSetupTime:
            return
        if self._wifiButtonPressedTime is None:
            if self.isWiFiButtonPressed():
                # Record the initial button press time
                self._wifiButtonPressedTime = time.time()
        else:
            if self.isWiFiButtonPressed():
                # Toggle the WiFi LED slowly to indicate the button is pressed
                self.toggleWiFiLED()
                eleapseSeconds = time.time() - self._wifiButtonPressedTime
                self._debug('Button pressed for {} of {} seconds.'.format(eleapseSeconds, WiFi.WIFI_SETUP_BUTTON_HOLD_SECS))
                if eleapseSeconds >= WiFi.WIFI_SETUP_BUTTON_HOLD_SECS:
                    defaultWiFiConfig = True

            # If WiFi button is no longer pressed
            else:
                # If user has held WiFi button then the WiFi button should be set back on if currently connected.
                self.setWiFiLED(self._wifiConnected)

        return defaultWiFiConfig

    def toggleWiFiLED(self):
        """@brief Change the state of the WiFi LED."""
        if self._wifiLed:
            self._wifiLed.value( not self._wifiLed.value() )

    def setWiFiLED(self, on):
        """@brief Set the LED state to WiFi indicator LED.
           @param on This may be
                     "force_on" to set the LED on until set to "release".
                     "force_off" to set the LED on until set to "release".
                     "release" to allow the LED state to be set to a boolean value.
                     True set LED on if in a not in a forced state.
                     False set LED off if not in a forced state.

                     The forced states are used when testing the WiFi LED.
                      """
        if self._wifiLed:
            if on == 'force_on':
                self._forceWiFiLEDState = True
                self._wifiLed.value(True)

            elif on == 'force_off':
                self._forceWiFiLEDState = True
                self._wifiLed.value(False)

            elif on == 'release':
                self._forceWiFiLEDState = False

            else:
                if not self._forceWiFiLEDState:
                    self._wifiLed.value(on)

    def toggleBlueToothLED(self):
        """@brief Set the LED state to BlueTooth indicator LED. if associated with a BlueTooth instance."""
        if self._blueTooth:
            self._blueTooth.toggleLED()

    def setBlueToothLED(self, on):
        """@brief Set the LED state to indicate the BlueTooth is connected (LED on).
           @param on True to set the LED on."""
        if self._blueTooth:
            self._blueTooth.setLED(on)

    def getIPAddress(self):
        """@brief Get the IP address we have on the network.
           @return The IP address of None if WiFi is not setup."""
        return self._ipAddress

    def getDict(self, throwError=False):
        """@brief Get a message from a connected bluetooth client. This message should be a
                  JSON string. This is converted to a python dictionary.
           @param throwError If True an exception is thrown if the data is received but it
                  is not JSON formatted.
           @return A python dictionary or None if no message is received or the
                   message received is not a valid JSON string."""
        jsonDict = None
        if self._blueTooth is not None:
            if self._blueTooth.isConnected():
                rxString = self._blueTooth.getRxMessage()
                if rxString is not None:
                    try:
                        jsonDict = json.loads(rxString)
                    except:
                        if throwError:
                            raise

        return jsonDict

    def isWifiConnected(self):
        """@brief Return True if the Wifi is connected."""
        return self._wifiConnected

    def processBTCommands(self):
        """@brief Process bluetooth commands.
           @return True if a command to shutdown the bluetooth interface is received."""
        shutDownBlueTooth = False

        rxDict = self.getDict()
        if rxDict:
            self._debug("BT rxDict={}".format(rxDict))
            if WiFi.BT_CMD in rxDict:
                cmd = rxDict[WiFi.BT_CMD]

                # Perform a Wifi network scan
                if cmd == WiFi.BT_CMD_WIFI_SCAN:
                    wiFiNetworksDict = WiFi.Get_Wifi_Networks(self._uo)
                    if self._blueTooth is not None and self._blueTooth.isConnected():
                        for wifiNetwork in wiFiNetworksDict:
                            # Send one network at a time as the bluetooth LE packet size is not large
                            self._blueTooth.send(json.dumps(wifiNetwork))
                        self._blueTooth.send(json.dumps( {WiFi.WIFI_SCAN_COMPLETE: 1} ))

                # Connect as an STA to a WiFi network
                elif cmd == WiFi.BT_CMD_STA_CONNECT:
                        # If the WiFi network and password have been supplied.
                        if WiFi.SSID_KEY in rxDict and WiFi.PASSWORD_KEY in rxDict:
                            self._wifiMode = WiFi.MODE_STA
                            self._wifiSSID = rxDict[WiFi.SSID_KEY]
                            self._wifiPassword = rxDict[WiFi.PASSWORD_KEY]
                            if self._blueTooth is not None:
                                self._blueTooth.send(json.dumps( {WiFi.WIFI_CONFIGURED: 1} ))

                # Setup as an AP WiFi network
                elif cmd == WiFi.BT_CMD_PCP_CONNECT:
                        # If the WiFi network and password have been supplied.
                        if WiFi.SSID_KEY in rxDict and WiFi.PASSWORD_KEY in rxDict:
                            self._wifiMode = WiFi.MODE_AP
                            self._wifiSSID = rxDict[WiFi.SSID_KEY]
                            self._wifiPassword = rxDict[WiFi.PASSWORD_KEY]
                            if self._blueTooth is not None:
                                self._blueTooth.send(json.dumps( {WiFi.WIFI_CONFIGURED: 1} ))

                # Setup as an AP WiFi network
                elif cmd == WiFi.BT_CMD_GET_IP:
                    if self._blueTooth is not None:
                        self._blueTooth.send(json.dumps( {WiFi.IP_ADDRESS: self.getIPAddress()} ))

                # The app has sent a message instructing the device to disable it's bluetooth interface.
                elif cmd == WiFi.DISABLE_BT:
                    if self._blueTooth is not None:
                        self._blueTooth.shutdown()
                        shutDownBlueTooth = True

        return shutDownBlueTooth

    def getMode(self):
        """@return Return the mode of the WiFi interface set over the bluetooth connection."""
        return self._wifiMode

    def getSSID(self):
        """@return Return the SSID of the WiFi interface set over the bluetooth connection."""
        return self._wifiSSID

    def getPassword(self):
        """@return Return the password of the WiFi interface set over the bluetooth connection."""
        return self._wifiPassword

    def isConfigured(self):
        """@brief Determine if the Wifi config parameters have been set via the bluetooth interface.
           @return True if the WiFi config has been set."""
        configured = False
        if self.getMode() is not None and\
           self.getSSID() is not None and\
           self.getPassword() is not None:
           configured = True
        return configured

    def connected(self):
        """@return True if WiFi is connected."""
        connected = False
        if self._wlan:
            connected = self._wlan.isconnected()
        return connected
