from machine import SPI, Pin
import st7789
import vga2_bold_16x16 as font
import ntptime
import gc

from lib.rest_server import RestServer
from cmd_handler import CmdHandler
from constants import Constants
from mean_stats import MeanCT6StatsDict

import utime
import json
import ubinascii

from lib.umqttsimple import MQTTClient
from lib.base_machine import BaseMachine
from lib.config import MachineConfig
from lib.ydev import YDev

from time import sleep

class Display(Constants):

    # This must be an int value
    UPDATE_MILLI_SECONDS    = 1000
    ROW_HEIGHT_MARGIN       = 20
    FIRST_COL_PIXEL         = 0
    LAST_COL_PIXEL          = 239
    LAST_ROW_PIXEL          = 319
    COL0_START_PIXEL        = 3
    COL1_START_PIXEL        = 60
    FIELD_TYPE_KW           = 1
    FIELD_TYPE_AMPS         = 2
    DISPLAY_TIMEOUT_SECONDS = 60        # The number of seconds that the display will stay on after
                                        # power up or the WiFi button is pressed.

    def __init__(self, uo):
        """@brief Display constructor
           @param uo A UO instance."""
        self._uo = uo
        self._startup = True
        self._displayPowerPin = None
        self.update(None, False)
        self._preWiFiReg = True
        self._lastDisplayUpdateMS = utime.ticks_ms()
        self._lastWHUpdateMS = self._lastDisplayUpdateMS
        self._buttonPressedTime = None
        self._warningLines = None
        self._lastWarningLines = None
        self._ctFieldType = Display.FIELD_TYPE_KW
        self._lastButtonPressedMS = utime.ticks_ms()
        self._statsDict = None

    def _setText(self, row, col, text):
        self._tft.text( font, text.encode(), int(row), int(col), st7789.YELLOW, st7789.BLACK )

    def _config(self, rotation=0, buffer_size=0, options=0):
        """@brief Get the hardware confgiguration of the display."""
        return st7789.ST7789(
            SPI(1, baudrate=31250000, sck=Pin(10), mosi=Pin(11)),
            240,
            320,
            reset=Pin(21, Pin.OUT),
            cs=Pin(17, Pin.OUT),
            dc=Pin(12, Pin.OUT),
            backlight=Pin(15, Pin.OUT),
            rotation=rotation,
            options=options,
            buffer_size=buffer_size)

    def setGetIPMethod(self, getIPMethod):
        """@brief Set the method that will return the IP address of the unit on the WiFi network.
           @param getIPMethod The method to call to read the units IP address."""
        self._getIPMethod = getIPMethod

    def _setDisplayPower(self, on):
        """@brief turn the display power on/off.
           @param on If True the display power is set on."""
        if self._displayPowerPin is None:
            self._displayPowerPin = Pin(Constants.DISPLAY_ON_GPIO, Pin.OUT, value=0)
        self._displayPowerPin.value(on)
        if on:
            # We reset these so that any subsequent waring message is displayed.
            self._lastWarningLines = None
            self._warningLines = None

    def _isDisplayPowered(self):
        """@brief Determine if the display has power to it.
           @return True if the display has power."""
        return self._displayPowerPin.value()

    def _init(self):
        """@brief Init the display."""
        # Ensure the display is powered up
        self._setDisplayPower(True)

        rotation =0
        self._tft = self._config(rotation=rotation)
        self._tft.init()
        self._tft.fill(st7789.BLACK)
        #self._tft.rotation(rotation)
        self._colMax = self._tft.width() - font.WIDTH*6
        self._rowMax = self._tft.height() - font.HEIGHT
        self._rowH = font.HEIGHT+Display.ROW_HEIGHT_MARGIN
        # Draw table grid hor lines
        for row in range(0,7):
            yPos=row*self._rowH
            self._tft.line(Display.FIRST_COL_PIXEL,\
                           yPos,\
                           Display.LAST_COL_PIXEL,\
                           yPos,\
                           st7789.BLUE)
        # Draw table grid vert lines
        self._tft.line(Display.FIRST_COL_PIXEL,\
                       0,Display.FIRST_COL_PIXEL,\
                       6*self._rowH,\
                       st7789.BLUE)
        self._tft.line(Display.LAST_COL_PIXEL,\
                       0,\
                       Display.LAST_COL_PIXEL,\
                       6*self._rowH,\
                       st7789.BLUE)
        self._tft.line(Display.COL1_START_PIXEL-5,\
                       0,\
                       Display.COL1_START_PIXEL-5,\
                       6*self._rowH,\
                       st7789.BLUE)
        self._tft.line(Display.FIRST_COL_PIXEL,\
                       self._rowMax-10,\
                       Display.LAST_COL_PIXEL,\
                       self._rowMax-10,\
                       st7789.BLUE)
        self._setText(0, self._rowMax, " Connecting...")
        self._uo.info("Turned the display on.")

    def _displayOff(self):
        """@brief Turn the display off."""
        self._setDisplayPower(False)
        self._uo.info(f"{Display.DISPLAY_TIMEOUT_SECONDS} second display timeout. Powered down display.")

    def _updateParams(self, statsDict, now):
        """@brief Update the parameters read from the CT6 unit on the display.
           @param statsDict The stats dict that contains the information to display.
           @param now The time now in micro seconds. From utime.ticks_us() call."""
        vRMS = None
        if statsDict is not None:

            for ct in range(1,7):
                key = f"CT{ct}"
                if key in statsDict:
                    ctStatsDict = statsDict[key]
                    yPos = ((ct-1)*self._rowH)+(Display.ROW_HEIGHT_MARGIN/2)+1
                    self._setText(Display.COL0_START_PIXEL, yPos, f"CT{ct}")
                    if self._ctFieldType == Display.FIELD_TYPE_KW:
                        unit="kW"
                        if Constants.PRMS in ctStatsDict:
                            pWatts = ctStatsDict[Constants.PRMS]
                            pKW = pWatts/1000.0
                            self._setText(Display.COL1_START_PIXEL, yPos, f"{pKW:.3f} {unit}    ")

                    if self._ctFieldType == Display.FIELD_TYPE_AMPS:
                        unit="A"
                        if Constants.IRMS in ctStatsDict:
                            amps = ctStatsDict[Constants.IRMS]
                            self._setText(Display.COL1_START_PIXEL, yPos, f"{amps:.2f} {unit}    ")

            #We read the voltage from CT1 ATM90E32 device
            if vRMS is None and Constants.VRMS in statsDict[Constants.CT1_KEY]:
                vRMS = statsDict[Constants.CT1_KEY][Constants.VRMS]

            rssi = None
            if Constants.RSSI in statsDict:
                rssi = int(statsDict[Constants.RSSI])

            temp = None
            if Constants.BOARD_TEMPERATURE in statsDict:
                temp = statsDict[Constants.BOARD_TEMPERATURE]

            yPos = (6*self._rowH)+(Display.ROW_HEIGHT_MARGIN/2)+1
            self._setText(0, yPos, f"Volts: {vRMS:.1f}    ")
            yPos += font.HEIGHT+3
            if rssi:
                self._setText(0, yPos, f"WiFi:  {rssi} dBm   ")
            yPos += font.HEIGHT+3
            if temp:
                self._setText(0, yPos, f"Temp:  {temp:.0f} C   ")

            ipAddress = self._getIPMethod()
            if ipAddress:
                self._setText(0, self._rowMax, f"{ipAddress}    ")

    def _setButtonPressed(self, buttonPressed, now):
        """@brief Set/Reset button pressed indicator on screen
                  and toggle display power mode.
           @param pressed If True the button is pressed.
           @param now The time now in milli seconds."""
        if buttonPressed:
            self._lastButtonPressedMS = now
            # If the display is on then the user can switch between displaying kW and amps
            if self._isDisplayPowered():
                if self._ctFieldType == Display.FIELD_TYPE_KW:
                    self._ctFieldType = Display.FIELD_TYPE_AMPS

                elif self._ctFieldType == Display.FIELD_TYPE_AMPS:
                    self._ctFieldType = Display.FIELD_TYPE_KW

            self._tft.fill_rect(Display.LAST_COL_PIXEL-font.WIDTH, Display.LAST_ROW_PIXEL-font.HEIGHT+1, font.WIDTH, font.HEIGHT-1, st7789.RED)

        else:
            # If the button is not pressed and has not been pressed for the display timeout period
            delta = utime.ticks_diff(now, self._lastButtonPressedMS)
            if delta > Display.DISPLAY_TIMEOUT_SECONDS*1000 and self._isDisplayPowered():
                # Turn the display off
                self._displayOff()

    def update(self, statsDict, buttonPressed):
        """@brief Update the display.
           @param statsDict The stats dict that contains the information to display.
           @param buttonPressed If True then the WiFi button is pressed."""
        # If we have a valid statsDict save a ref to it as we may not have one when we get
        # here and it's time to update the display further down this method.
        if statsDict is not None:
            self._statsDict = statsDict

        # If the unit has just started up
        if self._startup:
            # Init the display
            self._init()
            # Ensure we don't visit this point again.
            self._startup = False

        else:
            # If the WiFi button has just been pressed and the display is not on as a display timeout has occurred.
            if buttonPressed and not self._isDisplayPowered():
                # Turn the display on.
                self._init()

            now = utime.ticks_ms()
            self._setButtonPressed(buttonPressed, now)
            delta = utime.ticks_diff(now, self._lastDisplayUpdateMS)
            # If it's time to display the stats
            if delta > Display.UPDATE_MILLI_SECONDS:
                # If a warning message is defined then display this
                # rather than the normal display.
                if self._warningLines:
                    self._showWarning()
                else:
                    self._updateParams(self._statsDict, now)
                self._lastDisplayUpdateMS = now

    def _showWarning(self):
        """@brief Show a warning message on the display."""
        if self._warningLines != self._lastWarningLines:
            # Clear the screen to make space for lines of warning text
            self._tft.init()
            self._tft.fill(st7789.BLACK)
            lines = self._warningLines.split("\n")
            row = 0
            for line in lines:
                yPos = (row*self._rowH)+(Display.ROW_HEIGHT_MARGIN/2)+1
                self._setText(Display.COL0_START_PIXEL, yPos, line)
                row = row + 1

        # We still show the IP address of the unit at the bottom of the display
        # when a waring message is displayed
        ipAddress = self._getIPMethod()
        if ipAddress:
            self._setText(0, self._rowMax, f"{ipAddress}    ")

        # Only update if we seen changes in the warning message
        self._lastWarningLines = self._warningLines

    def setWarning(self, warningLines):
        """@brief Set a warning message on the display.
           @param warningLines The lines of text to display."""
        self._warningLines = warningLines

class ThisMachine(BaseMachine):
    """@brief Implement functionality required by this project."""

    STATS_UPDATE_PERIOD_MSECS = 200

    NUMERIC_CT_FIELD_LIST = (Constants.PRMS,
                             Constants.PAPPARENT,
                             Constants.PF,
                             Constants.PREACT,
                             Constants.VRMS,
                             Constants.TEMP,
                             Constants.FREQ,
                             Constants.IRMS,
                             Constants.IPEAK)

    NON_NUMERIC_CT_FIELD_LIST = (Constants.TYPE_KEY,
                                 Constants.NAME )

    NUMERIC_FIELD_LIST = (Constants.RSSI,
                          Constants.BOARD_TEMPERATURE_KEY,
                          Constants.READ_TIME_NS_KEY)

    NON_NUMERIC_FIELD_LIST = (Constants.ASSY_KEY,
                              Constants.YDEV_UNIT_NAME_KEY,
                              Constants.FIRMWARE_VERSION_STR,
                              Constants.ACTIVE,
                              YDev.IP_ADDRESS_KEY,
                              YDev.OS_KEY,
                              YDev.UNIT_NAME_KEY,
                              YDev.DEVICE_TYPE_KEY,
                              YDev.PRODUCT_ID_KEY,
                              YDev.SERVICE_LIST_KEY,
                              YDev.GROUP_NAME_KEY)

    def __init__(self, uo, configFile, activeAppKey, activeApp, wdt):
        """@brief Constuctor.
           @param uo A UO instance.
           @param configFile The config file that holds all machine config including the active application ID.
           @param activeAppKey The key in the config dict that details which app (1 or 2) we are running from.
           @param activeApp The active app. Either 1 or 2.
           @param wdt A WDT instance."""
        # Call base class constructor
        super().__init__(uo, configFile, activeAppKey, activeApp, wdt)

        gc.enable()
        self._ntp = None
        self._uo.info(f"Firmware Version = {Constants.FIRMWARE_VERSION}")
        # Init the display to display the booting message as early as possible.
        self._display = Display(uo)

        #The following is required for an IOT app that needs WiFi and a REST server

        # Start a server to provide a REST interface.
        # Update cmd_handler.py as required by your project.
        self._projectCmdHandler = CmdHandler(self._uo, self._machineConfig)
        # This server will be started later when the WiFi connects
        self._restServer = RestServer(self._machineConfig, self._activeAppKey, self._projectCmdHandler, uo=uo)
        self._restServer.setSavePersistentDataMethod(self._savePersistentData)
        self._restServer.setStartTime(self._startTime)
        self._initWifi()
        self._initBlueTooth()
        # Pass a reference to the WiFi so that the RSSI can be included in the stats dict if required
        self._projectCmdHandler.setWiFi(self._wifi)

        # Init the display again or the display update time is about 330 times slower.
        # Further investigation required.
        self._display = Display(uo)
        self._display.setGetIPMethod(self._wifi.getIPAddress)

        # The client interface to an MQTT server.
        self._mqttInterface = MQTTInterface(self._machineConfig, uo=self._uo)

        self._lastStatsUpdateMS = utime.ticks_ms()

        self._startWiFiDisconnectTime = None

        # statsDict's sent in response to received AYT messages are sent from this instance.
        self._aytStatsDict = MeanCT6StatsDict(ThisMachine.NUMERIC_CT_FIELD_LIST,
                                              ThisMachine.NON_NUMERIC_CT_FIELD_LIST,
                                              ThisMachine.NUMERIC_FIELD_LIST,
                                              ThisMachine.NON_NUMERIC_FIELD_LIST)
        # statsDict's sent to MQTT servers are sent from this instance.
        self._mqttStatsDict = MeanCT6StatsDict(ThisMachine.NUMERIC_CT_FIELD_LIST,
                                               ThisMachine.NON_NUMERIC_CT_FIELD_LIST,
                                               ThisMachine.NUMERIC_FIELD_LIST,
                                               ThisMachine.NON_NUMERIC_FIELD_LIST)
        # statsDict's used to update the display values.
        self._displayStatsDict = MeanCT6StatsDict(ThisMachine.NUMERIC_CT_FIELD_LIST,
                                                  ThisMachine.NON_NUMERIC_CT_FIELD_LIST,
                                                  ThisMachine.NUMERIC_FIELD_LIST,
                                                  ThisMachine.NON_NUMERIC_FIELD_LIST)

        self._ntp_sync_success_once = False
        self._savedUpTime = 0

    def _isFactoryConfigPresent(self):
        """@brief Check if the factory config file is present.
           @return True if the factory config file is present in flash."""
        factoryConfPresent = False
        try:
            fd = open("/"+MachineConfig.FACTORY_CONFIG_FILENAME)
            fd.close()
            factoryConfPresent = True
        except OSError:
            pass
        return factoryConfPresent

    def _isReadPwrStatsTime(self):
        """@brief Determine if it's time to read the ATM90E32 device stats.
           @return True if it's time."""
        updateStats = False
        now = utime.ticks_ms()
        delta = utime.ticks_diff(now, self._lastStatsUpdateMS)
        if delta >= ThisMachine.STATS_UPDATE_PERIOD_MSECS:
            updateStats=True
            self._lastStatsUpdateMS = now
        return updateStats

    def _savePersistentData(self):
        """@brief a single method to save all persistent data on the device."""
        self._machineConfig.store()
        self._uo.info("Saved all persistent data on unit.")

    def _getParams(self):
        """@brief Get the parameters (in a dict) we wish to include in the AYT response message."""
        statsDict = None
        active = self._machineConfig.get(Constants.ACTIVE)
        # We don't send a response if not active
        if active:
            statsDict = self._aytStatsDict.getStatsDict()
        return statsDict

    def _updateStats(self):
        """@brief Periodically update the stats we read from the ATM90E32 devices.
           @return True if stats updated."""
        updated = False
        if self._isReadPwrStatsTime():
            statsDict = self._projectCmdHandler.getStatsDict()
            self._aytStatsDict.addStatsDict(statsDict)
            self._mqttStatsDict.addStatsDict(statsDict)
            self._displayStatsDict.addStatsDict(statsDict)
            updated = True
        return updated

    def _wifiDownRestart(self, wifiConnected, timeoutMS=10000):
        """@brief If the WiFi goes down for a period of time then power cycle the CT6 unit
                  to keep the CT6 unit active. Without this it may go into a dormant state.
           @param wifiConnected True if the WiFi is currently connected.
           @param timeoutMS If the WiFi stays down for this period of time we power cycle the CT6 device."""
        # If WiFi is connected then reset disconnected time.
        if wifiConnected:
            self._startWiFiDisconnectTime = None

        # If WiFi is disconnected but this is the first time here since
        # it dropped record the time it dropped.
        elif self._startWiFiDisconnectTime is None:
            self._startWiFiDisconnectTime = utime.ticks_ms()

        else:
            now_ms = utime.ticks_ms()
            elapsed_ms = now_ms - self._startWiFiDisconnectTime
            self._debug(f"WiFi has been down for {elapsed_ms} milliseconds.")
            if elapsed_ms > timeoutMS:
                self._debug(f"WiFi down timeout ({timeoutMS} ms). Power cycling CT6 device.")
                sleep(0.25)
                self._projectCmdHandler.powerCycle()

    def serviceRunningMode(self):
        """@brief Perform actions required when up and running.
                  If self._initWifi() and self._initBlueTooth() are called in the constructor
                  then WiFi should be connected by the time we get here.

                  This should be called periodically when connecting to a WiFi network.

           @return The time in seconds before this method is expected to be called again."""
        self._updateBlueTooth()
        wifiConnected = self._updateWiFi()
        # We only get here if the WiFi comes up, so we check if it goes down
        # and reboot if it stays down for a period of time.
        self._wifiDownRestart(wifiConnected)
        # Get power stats to be sent to the display, in response to an AYT msg or to sn MQTT server.
        self._updateStats()
        # Send data to an MQTT server if required.
        self._mqttInterface.update(self._mqttStatsDict)

        # Show the RAM usage on the serial port. This can be useful when debugging.
        self._showRAMInfo()
        if not self._isFactoryConfigPresent():
            self._display.setWarning("Uncalibrated\nCT6 device.")
        statsDict = self._displayStatsDict.getStatsDict()
        if statsDict is not None:
            self._display.update( statsDict, self._wifi.isWiFiButtonPressed() )

        # If we have not yet created an NTP instance. We create this here
        # because know the WiFi is connected if serviceRunningMode() is called.
        if self._ntp is None:
            # Update the MCU time via NTP every 2 hours.
            self._ntp = NTP(self._uo, 3600*2)

        else:
            # If we have not yet had an NTP sync
            if not self._ntp_sync_success_once:
                # Save the current uptime in order to deduct it from the post NTP sync start time
                # to ensure the uptime is valid either side of an NTP sync.
                self._savedUpTime = utime.time() - self._startTime

            # handle() won't update NTP every time it's called.
            ntp_sync_success = self._ntp.handle()
            # If this is the first time NTP sync occurred.
            if not self._ntp_sync_success_once and ntp_sync_success:
                # Reset the startTime as the previous start time will be incorrect
                # because the NTP sync adjusts the MCU time.
                self._startTime = utime.time() - self._savedUpTime
                # Update the start time held by the rest servers BuiltInCmdHandler.
                # so that the /get_uptime REST cmd returns the correct uptime.
                self._restServer.setStartTime(self._startTime)
                self._ntp_sync_success_once = True
                # We feed the WDT or the NTP sync may cause a reboot due to a sudden large shift in
                # the MCU time.
                if self._wdt:
                    self._wdt.feed()

        # Attempt to force garbage collector to run.
        gc.collect()
        return Constants.POLL_SECONDS


class MQTTInterface(object):
    """@brief Responsible for connecting to and sending stats to an MQTT server."""

    STATE_UNCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECT_TIMEOUT = 2
    STATE_CONNECTED = 3

    def __init__(self, config, uo=None):
        self._config = config
        self._uo = uo

        self._connectedMQTTAddress = None
        self._connectedMQTTPort = None
        self._mqttClient = None
        self._poller = None
        self._startConnectingMS = None
        self._connectTimeoutMS = int(Constants.WDT_TIMEOUT_MSECS/2)

        self._assyStr = self._config.get(Constants.ASSY_KEY)

        self._conState = MQTTInterface.STATE_UNCONNECTED
        self._loadConfig()

        self._lastMQTTTxMS = utime.ticks_ms()

    def _info(self, msg):
        """@brief Display an info message on the serial port if
                  uo provided in the Constructor."""
        if self._uo:
            self._uo.info(msg)

    def _debug(self, msg):
        """@brief Display a debug message on the serial port if
                  uo provided in the Constructor."""
        if self._uo:
            self._uo.debug(msg)

    def _error(self, msg):
        """@brief Display an error message on the serial port if
                  uo provided in the Constructor."""
        if self._uo:
            self._uo.error(msg)

    def isUnconnected(self):
        """@return True if connected to an MQTT server."""
        return self._conState == MQTTInterface.STATE_UNCONNECTED

    def isConnected(self):
        """@return True if connected to an MQTT server."""
        return self._conState == MQTTInterface.STATE_CONNECTED

    def isConnecting(self):
        """@return True if connected to an MQTT server."""
        return self._conState == MQTTInterface.STATE_CONNECTING

    def _loadConfig(self):
        """@brief Load the MQTT config parameters."""
        self._mqttServerAddress = self._config.get(Constants.MQTT_SERVER_ADDRESS)
        self._mqttServerPort = int(self._config.get(Constants.MQTT_SERVER_PORT))
        self._mqttTopic = self._config.get(Constants.MQTT_TOPIC)
        self._mqttUsername = self._config.get(Constants.MQTT_USERNAME)
        self._mqttPassword = self._config.get(Constants.MQTT_PASSWORD)

    def isConfigured(self):
        """@brief Determine if the CT6 unit is configured to connect to a MQTT server.
           @return True if configured."""
        self._loadConfig()
        configured = False
        # If we have the required arguments to connect to an MQTT server
        if self._mqttServerAddress and \
           len(self._mqttServerAddress) > 0 and \
           self._mqttServerPort >= 1 and self._mqttServerPort < 65536 and \
           self._mqttTopic and \
           len(self._mqttTopic) > 0:
            configured = True
        return configured

    def startConnecting(self, keepAlive=60):
        """@brief Initiate an attempt to connect to an MQTT server."""
        # Only initiate a connection in the unconnected state
        if self._conState == MQTTInterface.STATE_UNCONNECTED:
            mqttClientID = ubinascii.hexlify(self._assyStr)

            if len(self._mqttUsername) > 0 and len(self._mqttPassword) > 0:
                self._info(f"Connecting to MQTT server {self._mqttServerAddress}:{self._mqttServerPort} username={self._mqttUsername}, password={self._mqttPassword}")
                self._mqttClient = MQTTClient(mqttClientID,
                                            self._mqttServerAddress,
                                            port=self._mqttServerPort,
                                            user=self._mqttUsername,
                                            password=self._mqttPassword,
                                            keepalive=keepAlive,
                                            connect_timeout_ms=self._connectTimeoutMS)
            else:
                self._info(f"Connecting to MQTT server {self._mqttServerAddress}:{self._mqttServerPort}")
                self._mqttClient = MQTTClient(mqttClientID,
                                            self._mqttServerAddress,
                                            port=self._mqttServerPort,
                                            keepalive=keepAlive,
                                            connect_timeout_ms=self._connectTimeoutMS)
            self._mqttClient.set_callback(self.mqttCallBack)
            self._conState = MQTTInterface.STATE_CONNECTING
            self._poller = self._mqttClient.start_connecting()

    def updateState(self):
        """@brief Called to update the connection status during a connection
                  attempt. Should only be called while connecting to an MQTT server.
           @return The connection state."""
        if self._mqttClient.is_connected():
            self._conState = MQTTInterface.STATE_CONNECTED
            # Record the address and port so that if they are changed we disconnect.
            self._connectedMQTTAddress = self._mqttServerAddress
            self._connectedMQTTPort = self._mqttServerPort

        elif self._mqttClient._connect_attempt_timed_out():
            self._conState = MQTTInterface.STATE_UNCONNECTED

        return self._conState

    def sendToMQTT(self, statsDict):
        """@brief Send data to the MQTT server. The connection must be built before this
                  method is called. This method may throw an Exception if an error occurs.
           @param statsDict This dict is sent to the MQTT server as JSON formatted text."""
        self._loadConfig()
        #If connected to the server and the MQTT server address or port has changed
        if self._mqttServerAddress != self._connectedMQTTAddress or \
           self._mqttServerPort != self._connectedMQTTPort:
            #Drop the connection ready for a reconnect attempt next time round.
            self.disconnectMQTT()

        #If we have a connection to the MQTT server
        if self._mqttClient:
            # Send json string to the MQTT server
            jsonStr = json.dumps( statsDict )
            self._mqttClient.publish(self._mqttTopic, jsonStr)

            # Attempt to read from the MQTT server in case data has been received so that the
            # input buffers do not fill up.
            self._mqttClient.check_msg()

    def disconnectMQTT(self):
        """@brief Disconnect from the MQTT server."""
        try:
            if self._mqttClient:
                self._mqttClient.disconnect()
        except Exception as ex:
            self._uo.error('Error shutting down MQTT connection: ' + str(ex))
        self._mqttClient = None
        self._connectedMQTTAddress = None
        self._connectedMQTTPort = None
        self._conState = MQTTInterface.STATE_UNCONNECTED

    def mqttCallBack(self, topic, msg):
        """@brief show the MQTT callback message."""
        self._debug(f"{topic}: {msg}")

    def _isNextMQTTTXTime(self):
        """@brief Determine if it's time to send the stats to the MQTT server.
           @return True if it's time."""
        mqttTX = False
        active = self._config.get(Constants.ACTIVE)
        # We don't send if not active
        if active:
            txPeriodMS = self._config.get(Constants.MQTT_TX_PERIOD_MS)
            # Every 200 milliseconds is as fast as we will send stats to an MQTT server.
            if txPeriodMS >= 200:
                now = utime.ticks_ms()
                delta = utime.ticks_diff(now, self._lastMQTTTxMS)
                if delta >= txPeriodMS:
                    mqttTX=True
                    self._lastMQTTTxMS = now
        return mqttTX

    def update(self, mqttStatsDict):
        """@brief Handle connecting to and sending messages to an MQTT server.
           @param mqttStatsDict The MeanCT6StatsDict instance that provides power usage
                                data to be sent to the MQTT server."""
        try:
            if self.isConfigured():

                if self.isUnconnected():
                    self.startConnecting()

                elif self.isConnecting():
                    self.updateState()

                elif self.isConnected():
                    if self._isNextMQTTTXTime():
                        statsDict = mqttStatsDict.getStatsDict()
                        self.sendToMQTT(statsDict)

            # If we are no longer configured but are connected drop the connection
            elif self.isConnected():
                self.disconnectMQTT()

        except Exception as ex:
            self._error(f"MQTT error: {str(ex)}")
            self.disconnectMQTT()


class NTP(object):
    """@brief Responsible for setting the MCU time with time received from an NTP server."""

    NTP_HOST                    = "pool.ntp.org"

    def __init__(self, uo, interval_seconds):
        """@brief Constructor.
           @param uo A UO instance for msg output."""
        self._uo = uo
        self._interval_seconds = interval_seconds
        # Try to ensure we update the NTP time soon after (~ 1 second) after the WiFi is connected.
        self._next_update_seconds = utime.time() + 1
        # Set the NTP server to use.
        ntptime.host = NTP.NTP_HOST

    def handle(self):
        """@brief Called periodically in order to update the MCU time via NTP.
                  This may block for up to 1 second if the server is unreachable.
                  However as it's not called often we can live with this.
                  Generally this method executes (when an NTP sync is required)
                  in ~ 30 to 90 milli seconds although this is dependant upon
                  the internet connection RTT.
                  Tried executing this in a background _thread but this made the CT6
                  platform unstable.
            @param True if an NTP sync was performed and succeeded."""
        ntp_sync_success = False
        # If it's time to set the time via NTP
        if utime.time() >= self._next_update_seconds:
            ntp_sync_success = self._sync_time()
            self._next_update_seconds = utime.time() + self._interval_seconds
        return ntp_sync_success

    def _sync_time(self):
        """@brief Attempt to sync the system time usiong an NTP server.
                  This method may block for some time if the NTP server is not reachable.
           @return interval_seconds The number of seconds to elapse between each ntp sync attempt."""
        # We don't want to output to much data on the serial port here to ensure
        # we don't use to much time sending data over the serial port compared to the time
        # taken to update the NTP time.
        success = False
        start_t = utime.ticks_us()
        try:
            ntptime.settime()
            success = True
        except:
            pass
        elapsed_us = utime.ticks_us() - start_t
        if success:
            self._uo.info(f"NTP sync success. Took {elapsed_us} microseconds.")
        else:
            self._uo.error(f"NTP sync failure. Took {elapsed_us} microseconds.")
        return success
