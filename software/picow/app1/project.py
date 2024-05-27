from machine import SPI, Pin
import st7789
import vga2_bold_16x16 as font

from lib.rest_server import RestServer
from cmd_handler import CmdHandler
from constants import Constants
import utime
import json
import socket

from lib.base_machine import BaseMachine
from lib.config import MachineConfig

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
        if statsDict:

            pwrDict = statsDict
            
            for ct in range(1,7):
                key = f"CT{ct}"
                if key in pwrDict:
                    ctStatsDict = pwrDict[key]
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
        
        # If the unit has just started up
        if self._startup:
            # Init the display
            self._init()
            # Ensure we don't visit this point again.
            self._startup = False

        else:
            # If the WiFi button has just been pressed and the display is not on as a display timeout has occured.
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
                    self._showWarning(statsDict)
                else:
                    self._updateParams(statsDict, now)
                self._lastDisplayUpdateMS = now
                
    def _showWarning(self, statsDict):
        """@brief Show a warning message on the display."""
        if self._warningLines != self._lastWarningLines:
            # Clear the screen to make space for lines of waring text
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

    STATS_UPDATE_PERIOD_MSECS = 400

    def __init__(self, uo, configFile, activeAppKey, activeApp, wdt):
        """@brief Constuctor
           @param uo A UO instance.
           @param configFile The config file that holds all machine config including the active application ID.
           @param activeAppKey The key in the config dict that details which app (1 or 2) we are running from.
           @param activeApp The active app. Either 1 or 2.
           @param wdt A WDT instance."""
        # Call base class constructor
        super().__init__(uo, configFile, activeAppKey, activeApp, wdt)
        self._statsDict = None
        
        # Init the display to display the booting message as early as possible.
        self._display = Display(uo)

        #The following is required for an IOT app that needs WiFi and a REST server

        # Start a server to provide a REST interface.
        # Update cmd_handler.py as required by your project.
        self._projectCmdHandler = CmdHandler(self._uo, self._machineConfig)
        # This server will be started later when the WiFi connects
        self._restServer = RestServer(self._machineConfig, self._activeAppKey, self._projectCmdHandler, uo=uo)
        self._restServer.setSavePersistentDataMethod(self._savePersistentData)
        self._initWifi()
        self._initBlueTooth()
        # Pass a reference to the WiFi so that the RSSI can be included in the stats dict if required
        self._projectCmdHandler.setWiFi(self._wifi)

        # Init the display again or the display update time is about 330 times slower.
        # Further investigation required.
        self._display = Display(uo)
        self._display.setGetIPMethod(self._wifi.getIPAddress)
        self._lastStatsUpdateMS = utime.ticks_ms()
        self._lastMQTTtxMS = utime.ticks_ms()
        self._mqttServerTCPConnection = None
        self._connectedMQTTAddress = None
        self._connectedMQTTPort = None
            
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
    
    def _isNextStatsUpdateTime(self):
        """@brief Determine if it's time to update the stats.
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
        return self._statsDict

    def _updateStats(self):
        """@brief Periodically update the stats we read from the ATM90E32 devices.
           @return True if stats updated."""
        updated = False
        if self._isNextStatsUpdateTime():
            self._statsDict = self._projectCmdHandler.getStatsDict()
            updated = True
        return updated

    def _connectToMQTTServer(self, address, port):
        """@brief Connect to the MQTT server.
           @param address The address of the server.
           @param port The TCP port number of the server."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._uo.info(f"Connecting to MQTT server at {address}:{port}")
            s.settimeout(2)
            self._wdt.feed()
            s.connect((address, port))
            self._uo.info("Connecting to MQTT server")
            self._mqttServerTCPConnection = s
            self._connectedMQTTAddress = address
            self._connectedMQTTPort = port
            
        except Exception as ex:
            self._uo.error( str(ex) )
        
    def _sendOnTCPSocket(self):
        """@brief Connect to a TCP server and send power usage data to it."""
        mqttServerAddress = self._machineConfig.get(Constants.MQTT_SERVER_ADDRESS)
        mqttServerPort = int(self._machineConfig.get(Constants.MQTT_SERVER_PORT))
        txPeriodMS = self._machineConfig.get(Constants.MQTT_TX_PERIOD_MS)
        # If we have the required arguments to connect to an MQTT server
        if mqttServerAddress and \
           len(mqttServerAddress) > 0 and \
           mqttServerPort >= 1 and mqttServerPort < 65536 and \
           txPeriodMS >= 200:
            self._thisMQTTtxMS = utime.ticks_ms()
            self._elapsedMS = self._thisMQTTtxMS-self._lastMQTTtxMS
            if self._elapsedMS >= txPeriodMS:
                if self._mqttServerTCPConnection is None:
                    # PJA how often should we attempt to connect to MQTT server as it will block
                    # for up to the connection timeout period
                    self._connectToMQTTServer(mqttServerAddress, mqttServerPort)
                
                #If connected to the server but the address or port has been changed
                elif mqttServerAddress != self._connectedMQTTAddress or \
                     mqttServerPort != self._connectedMQTTPort:
                    #Drop the connection ready for a reconnect attempt next time round.
                    self._mqttServerTCPConnection.close()
                    self._mqttServerTCPConnection = None
                     
                #If we have a connection to the MQTT server
                if self._mqttServerTCPConnection:
                    try:
                        # Send json string to the MQTT server
                        jsonStr = json.dumps( self._statsDict )
                        self._mqttServerTCPConnection.sendall(jsonStr.encode())
                        self._uo.info(f"Sent stats to MQTT server ({self._connectedMQTTAddress}:{self._connectedMQTTPort})")
                        
                    except:
                        #If an error occurred sending to the MQTT server drop the connection ready for a reconnect attempt next time round.
                        self._mqttServerTCPConnection.close()
                        self._mqttServerTCPConnection = None
                        
                if self._mqttServerTCPConnection:
                    self._uo.info(f"Time since last MQTT TX = {self._elapsedMS} ms.")
                else:
                    self._uo.info(f"{mqttServerAddress}:{mqttServerPort}: {self._elapsedMS} ms connection timeout.")
                    
                self._lastMQTTtxMS = self._thisMQTTtxMS
                
                # PJA Do we need to read from socket to make sure data doesn't fill input buffers ???


    def _sendToMQTT(self):
        """@brief Send data to the MQTT server."""
        mqttServerAddress = self._machineConfig.get(Constants.MQTT_SERVER_ADDRESS)
        mqttServerPort = int(self._machineConfig.get(Constants.MQTT_SERVER_PORT))
        txPeriodMS = self._machineConfig.get(Constants.MQTT_TX_PERIOD_MS)
        # If we have the required arguments to connect to an MQTT server
        if mqttServerAddress and \
           len(mqttServerAddress) > 0 and \
           mqttServerPort >= 1 and mqttServerPort < 65536 and \
           txPeriodMS >= 200:
            self._thisMQTTtxMS = utime.ticks_ms()
            self._elapsedMS = self._thisMQTTtxMS-self._lastMQTTtxMS
            if self._elapsedMS >= txPeriodMS:
                if self._mqttServerTCPConnection is None:
                    # PJA how often should we attempt to connect to MQTT server as it will block
                    # for up to the connection timeout period
                    self._connectToMQTTServer(mqttServerAddress, mqttServerPort)
                
                #If connected to the server but the address or port has been changed
                elif mqttServerAddress != self._connectedMQTTAddress or \
                     mqttServerPort != self._connectedMQTTPort:
                    #Drop the connection ready for a reconnect attempt next time round.
                    self._mqttServerTCPConnection.close()
                    self._mqttServerTCPConnection = None
                     
                #If we have a connection to the MQTT server
                if self._mqttServerTCPConnection:
                    try:
                        # Send json string to the MQTT server
                        jsonStr = json.dumps( self._statsDict )
                        self._mqttServerTCPConnection.sendall(jsonStr.encode())
                        self._uo.info(f"Sent stats to MQTT server ({self._connectedMQTTAddress}:{self._connectedMQTTPort})")
                        
                    except:
                        #If an error occurred sending to the MQTT server drop the connection ready for a reconnect attempt next time round.
                        self._mqttServerTCPConnection.close()
                        self._mqttServerTCPConnection = None
                        
                if self._mqttServerTCPConnection:
                    self._uo.info(f"Time since last MQTT TX = {self._elapsedMS} ms.")
                else:
                    self._uo.info(f"{mqttServerAddress}:{mqttServerPort}: {self._elapsedMS} ms connection timeout.")
                    
                self._lastMQTTtxMS = self._thisMQTTtxMS
                
                # PJA Do we need to read from socket to make sure data doesn't fill input buffers ???

    def serviceRunningMode(self):
        """@brief Perform actions required when up and running.
                  If self._initWifi() and self._initBlueTooth() are called in the constructor
                  then WiFi should be connected by the time we get here.

                  This should be called periodically when connecting to a WiFi network.

           @return The time in seconds before this method is expected to be called again."""

        self._updateBlueTooth()
        self._updateWiFi()
        self._updateStats()
        active = self._machineConfig.get(Constants.ACTIVE)
        if active:
            self._sendOnTCPSocket()
            #self._sendToMQTT()

        # Show the RAM usage on the serial port. This can be useful when debugging.
        self._showRAMInfo()
        if not self._isFactoryConfigPresent():
            self._display.setWarning("Uncalibrated\nCT6 device.")
        self._display.update( self._statsDict, self._wifi.isWiFiButtonPressed() )

        return Constants.POLL_SECONDS
