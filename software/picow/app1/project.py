from machine import SPI, Pin
import st7789
import vga2_bold_16x16 as font

from lib.rest_server import RestServer
from lib.io import IO
from cmd_handler import CmdHandler
from constants import Constants
import utime

from lib.base_machine import BaseMachine

import json

class Display(Constants):
    # Dict to store energy history in
    WH_DICT = {
        BaseMachine.CT1_KEY: {Constants.PRMS: 0.0},
        BaseMachine.CT2_KEY: {Constants.PRMS: 0.0},
        BaseMachine.CT3_KEY: {Constants.PRMS: 0.0},
        BaseMachine.CT4_KEY: {Constants.PRMS: 0.0},
        BaseMachine.CT5_KEY: {Constants.PRMS: 0.0},
        BaseMachine.CT6_KEY: {Constants.PRMS: 0.0}
    }
    # File that the above is stored in
    WH_FILE = "wh.json"

    # These must be an int values
    UPDATE_MILLI_SECONDS = 1000
    CALC_KWH_MILLI_SECONDS = 10000

    ROW_HEIGHT_MARGIN = 20

    FIRST_COL_PIXEL = 0
    LAST_COL_PIXEL = 239
    LAST_ROW_PIXEL = 319
    COL0_START_PIXEL = 3
    COL1_START_PIXEL = 60

    def __init__(self, uo):
        """@brief Display constructor
           @param uo A UO instance."""
        self._uo = uo
        self._initDisplay = False
        self.update(None, False)
        self._preWiFiReg = True
        self._lastDisplayUpdateMS = utime.ticks_ms()
        self._lastWHUpdateMS = self._lastDisplayUpdateMS
        self._whDict = self._loadWH()
        self._showKWH = False
        self._buttonPressedTime = None

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

    def _init(self):
        """@brief Init the display."""
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
        self._initDisplay = True

    def _loadWH(self):
        """@brief Load the kWh dict from flash.
           @return A dict containing the kWh read on each port."""
        kwHDict = Display.WH_DICT
        fileExists = IO.FileExists(Display.WH_FILE)
        if fileExists:
            try:
                with open(Display.WH_FILE, 'r') as fd:
                    kwHDict = json.load(fd)
            except:
                # We could loose kWh history here. This needs addressing...
                pass
        return kwHDict

    def _storeWH(self, wHDict):
        """@brief Save dict to file in flash.
           @param wHDict The kWH dict to store."""
        with open(Display.WH_FILE, 'w') as fd:
            json.dump(wHDict, fd)

    def _updateWH(self, statsDict, now):
        """@brief Update the watt hours values.
           @param statsDict The stats dict including the instantaneous watts values on each port.
           @param now The time now in micro seconds. From utime.ticks_us() call."""
        elapsedMS = utime.ticks_diff(now, self._lastWHUpdateMS)
        # If it's time to calculate the power used.
        if elapsedMS > Display.CALC_KWH_MILLI_SECONDS:
            elapsedHours = elapsedMS/3600000
            self._whDict = self._loadWH()
            for ct in range(1,7):
                ctName = f"CT{ct}"
                if ctName in statsDict:
                    ctDict = statsDict[ctName]
                    if Display.PRMS in ctDict:
                        watts = ctDict[Constants.PRMS]
                        wH = watts*elapsedHours
                        newWH = self._whDict[ctName][Constants.PRMS] + wH
                        self._whDict[ctName][Constants.PRMS]=newWH
            self._lastWHUpdateMS = now

    def _updateParams(self, statsDict, now):
        """@brief Update the parameters read from the CT6 unit on the display.
           @param statsDict The stats dict that contains the information to display.
           @param now The time now in micro seconds. From utime.ticks_us() call."""
        vRMS = None
        if statsDict:
            self._updateWH(statsDict, now)

            pwrDict = statsDict
            unit="kW"
            if self._showKWH:
                pwrDict = self._whDict
                unit=""
            if pwrDict is None:
                pwrDict = statsDict
                unit="kW"

            for ct in range(1,7):
                key = f"CT{ct}"
                if key in pwrDict:
                    ctStatsDict = pwrDict[key]
                    if Constants.PRMS in ctStatsDict:
                        pWatts = ctStatsDict[Constants.PRMS]
                        pKW = pWatts/1000.0
                        yPos = ((ct-1)*self._rowH)+(Display.ROW_HEIGHT_MARGIN/2)+1
                        self._setText(Display.COL0_START_PIXEL, yPos, f"CT{ct}")
                        self._setText(Display.COL1_START_PIXEL, yPos, f"{pKW:.3f} {unit}    ")

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
        self._updatePowerType(buttonPressed, now)
        if buttonPressed:
            self._tft.line(Display.LAST_COL_PIXEL,\
                           Display.LAST_ROW_PIXEL-10,\
                           Display.LAST_COL_PIXEL,\
                           Display.LAST_ROW_PIXEL,\
                           st7789.YELLOW)
        else:
          self._tft.line(Display.LAST_COL_PIXEL,\
                         Display.LAST_ROW_PIXEL-10,\
                         Display.LAST_COL_PIXEL,\
                         Display.LAST_ROW_PIXEL,\
                         st7789.BLACK)

    def _updatePowerType(self, buttonPressed, now):
        """@brief Update the type of power displayed, either kW or kWh
                  based on the user pressing the WiFi button to toggle
                  between the two.
           @param buttonPressed True if the button is pressed.
           @param now The time now in milli seconds."""
        # If the button is not pressed now but previously was
        if not buttonPressed and self._buttonPressedTime is not None:
                downTimeMS = utime.ticks_diff(now, self._buttonPressedTime)
                # Short button press < 0.5 seconds to toggle power mode.
                if downTimeMS < 500:
                     self._showKWH = not self._showKWH
                self._buttonPressedTime = None
        # If the button is pressed now
        elif buttonPressed:
            self._buttonPressedTime = utime.ticks_ms()


    def update(self, statsDict, buttonPressed):
        """@brief Update the display.
           @param statsDict The stats dict that contains the information to display.
           @param buttonPressed If True then the WiFi button is pressed."""
        if not self._initDisplay:
            self._init()

        else:
            now = utime.ticks_ms()
            self._setButtonPressed(buttonPressed, now)
            delta = utime.ticks_diff(now, self._lastDisplayUpdateMS)
            # If it's time to display the stats
            if delta > Display.UPDATE_MILLI_SECONDS:
                self._updateParams(statsDict, now)
                self._lastDisplayUpdateMS = now

            # If the user presses the WiFi button save the current wH history values.
            # We used to save this periodically but the flash memory would have a
            # short life (~ 70 days) if this were the case. Therefore the user
            # needs to press the WiFi SW to save the kWh values persistently.
            if buttonPressed:
                self.saveWH()
                
    def saveWH(self):
        """@brief Save the watt house dict to flash."""
        # Save the result persistently
        self._storeWH(self._whDict)
        self._uo.info("Saved watt hour data to flash.")
                
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

        #The following is required for a IOT app that needs WiFi and a REST server

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

        # Init the display again or the display update time is about 330 time slower.
        # It's unclear why this is.
        self._display = Display(uo)
        self._display.setGetIPMethod(self._wifi.getIPAddress)
        self._lastStatsUpdateMS = utime.ticks_ms()

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
        self._display.saveWH()
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

    def serviceRunningMode(self):
        """@brief Perform actions required when up and running.
                  If self._initWifi() and self._initBlueTooth() are called in the constructor
                  then WiFi should be connected by the time we get here.

                  This should be called periodically when connecting to a WiFi network.

           @return The time in seconds before this method is expected to be called again."""

        self._updateBlueTooth()
        self._updateWiFi()
        self._updateStats()

        # Show the RAM usage on the serial port. This can be useful when debugging.
        self._showRAMInfo()
        self._display.update( self._statsDict, self._wifi.isWiFiButtonPressed() )

        return Constants.POLL_SECONDS
