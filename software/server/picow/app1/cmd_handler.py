import machine

from constants import Constants

from lib.drivers.atm90e32 import ATM90E32
from lib.base_cmd_handler import BaseCmdHandler
from lib.rest_server import RestServer
from time import ticks_us, sleep_ms

class CmdHandler(BaseCmdHandler):
    """@brief Handle project commands dicts sent over the network."""

    # See BaseCmdHandler for REST RPC commands defined there.
    INIT_ATM90E32_DEVICES            = "/init_atm90e32_devs"
    SAVE_FACTORY_CONFIG_CMD          = "/save_factory_cfg"
    GET_TEMPERATURE_CMD              = "/get_temperature"
    SET_WIFI_LED                     = "/set_wifi_led"
    FLASH_BLUETOOTH_LED              = "/set_bluetooth_led"

    CT6_BOARD_TEMPERATURE            = "CT6_BOARD_TEMPERATURE"
    CMD_SUCCESS                      = "CMD_SUCCESS"

    def __init__(self, uo, machineConfig):
        """@brief Constructor
           @param uo A UO instance for displaying data on stdout.
           @param machineConfig The machine configuration instance."""
        # Call base class constructor
        super().__init__(uo, machineConfig)
        # The interface tp the on board MCP9700 temp sensor device
        self._tempADC = machine.ADC( Constants.TEMP_ADC_PIN )

        self._atm90e32Reset = machine.Pin(Constants.ATM90E32_RESET_PIN, machine.Pin.OUT, value=False) # Initially ATM90E32 devices are in reset

        # The spi interface to both ATM90E32 devices.
        self._spi = ATM90E32.SPIFactory(Constants.ATM90E32_SPI_CLK_PIN,
                                  Constants.ATM90E32_SPI_MOSI_PIN,
                                  Constants.ATM90E32_SPI_MISO_PIN)
        self._initATM90E32Devs()

    def getBoardTemp(self):
        """@brief Get The temperature of the unit."""
        adcValue = self._tempADC.read_u16()
        volts = adcValue/Constants.ADC_CODES_TO_MV
        tempC = ( volts - Constants.MCP9700_VOUT_0C ) / Constants.MCP9700_TC
        # Apply correction
        tempC = tempC * 0.86
        return tempC

    def getStatsDict(self):
        """@brief Get all the stats for all 6 channels on the device. This is mainly the current, voltage and power stats
                  but also includes the ATM90E32 core temperatures, ambient board temperature and WiFi RSSI.
           @return A dict containing te stats, E.G port power, etc."""
        retDict = {}
        ctType = "?"
        name = "?"
        iRMS = "?"
        iPeak = "?"
        vRMS = "?"
        pf = "?"
        pRMS = "?"
        temp = "?"
        freq = "?"

        sTime = ticks_us()
        for ct in Constants.VALID_CT_ID_LIST:
            if ct == 1:
                ctType = self._machineConfig.get(Constants.CT1_TYPE_KEY)
                name = self._machineConfig.get(Constants.CT1_NAME_KEY)
                iRMS = self._cs4ATM90E32.IrmsA
                iPeak = self._cs4ATM90E32.IPeakA
                vRMS = self._cs4ATM90E32.UrmsA
                pRMS = self._cs4ATM90E32.PmeanA
                pReact = self._cs4ATM90E32.QmeanA
                pApparent = self._cs4ATM90E32.SmeanA
                pf = self._cs4ATM90E32.PFmeanA
                temp = self._cs4ATM90E32.Temp
                freq = self._cs4ATM90E32.Freq

            elif ct == 2:
                ctType = self._machineConfig.get(Constants.CT2_TYPE_KEY)
                name = self._machineConfig.get(Constants.CT2_NAME_KEY)
                iRMS = self._cs4ATM90E32.IrmsB
                iPeak = self._cs4ATM90E32.IPeakB
                vRMS = self._cs4ATM90E32.UrmsB
                pRMS = self._cs4ATM90E32.PmeanB
                pReact = self._cs4ATM90E32.QmeanB
                pApparent = self._cs4ATM90E32.SmeanB
                pf = self._cs4ATM90E32.PFmeanB
                temp = self._cs4ATM90E32.Temp
                freq = self._cs4ATM90E32.Freq

            elif ct == 3:
                ctType = self._machineConfig.get(Constants.CT3_TYPE_KEY)
                name = self._machineConfig.get(Constants.CT3_NAME_KEY)
                iRMS = self._cs4ATM90E32.IrmsC
                iPeak = self._cs4ATM90E32.IPeakC
                vRMS = self._cs4ATM90E32.UrmsC
                pRMS = self._cs4ATM90E32.PmeanC
                pReact = self._cs4ATM90E32.QmeanC
                pApparent = self._cs4ATM90E32.SmeanC
                pf = self._cs4ATM90E32.PFmeanC
                temp = self._cs4ATM90E32.Temp
                freq = self._cs4ATM90E32.Freq

            elif ct == 4:
                ctType = self._machineConfig.get(Constants.CT4_TYPE_KEY)
                name = self._machineConfig.get(Constants.CT4_NAME_KEY)
                iRMS = self._cs0ATM90E32.IrmsA
                iPeak = self._cs0ATM90E32.IPeakA
                vRMS = self._cs0ATM90E32.UrmsA
                pRMS = self._cs0ATM90E32.PmeanA
                pReact = self._cs0ATM90E32.QmeanA
                pApparent = self._cs0ATM90E32.SmeanA
                pf = self._cs0ATM90E32.PFmeanA
                temp = self._cs0ATM90E32.Temp
                freq = self._cs0ATM90E32.Freq

            elif ct == 5:
                ctType = self._machineConfig.get(Constants.CT5_TYPE_KEY)
                name = self._machineConfig.get(Constants.CT5_NAME_KEY)
                iRMS = self._cs0ATM90E32.IrmsB
                iPeak = self._cs0ATM90E32.IPeakB
                vRMS = self._cs0ATM90E32.UrmsB
                pRMS = self._cs0ATM90E32.PmeanB
                pReact = self._cs0ATM90E32.QmeanB
                pApparent = self._cs0ATM90E32.SmeanB
                pf = self._cs0ATM90E32.PFmeanB
                temp = self._cs0ATM90E32.Temp
                freq = self._cs0ATM90E32.Freq

            elif ct == 6:
                ctType = self._machineConfig.get(Constants.CT6_TYPE_KEY)
                name = self._machineConfig.get(Constants.CT6_NAME_KEY)
                iRMS = self._cs0ATM90E32.IrmsC
                iPeak = self._cs0ATM90E32.IPeakC
                vRMS = self._cs0ATM90E32.UrmsC
                pRMS = self._cs0ATM90E32.PmeanC
                pReact = self._cs0ATM90E32.QmeanC
                pApparent = self._cs0ATM90E32.SmeanC
                pf = self._cs0ATM90E32.PFmeanC
                temp = self._cs0ATM90E32.Temp
                freq = self._cs0ATM90E32.Freq

            pf_watts_threshold = self._machineConfig.get(Constants.PF_WATTS_THRESHOLD)
            if abs(pRMS) < pf_watts_threshold:
                pf = 0.0

            # PJA move these names to Constants
            sensorDict = {Constants.TYPE_KEY: ctType,
                          Constants.NAME: name,
                          Constants.IRMS: iRMS,
                          Constants.IPEAK: iPeak,
                          Constants.VRMS: vRMS,
                          Constants.PRMS: pRMS,
                          Constants.PREACT: pReact,
                          Constants.PAPPARENT: pApparent,
                          Constants.PF: pf,
                          Constants.TEMP: temp,
                          Constants.FREQ: freq}
            ctName = "CT{}".format(ct)
            retDict[ctName] = sensorDict

        e_ns = ticks_us()-sTime
        retDict[Constants.READ_TIME_NS_KEY] = e_ns
        if self._wifi:
            retDict[Constants.RSSI_KEY] = self._wifi.getRSSI()
        retDict[Constants.BOARD_TEMPERATURE_KEY] = self.getBoardTemp()
        retDict[Constants.ASSY_KEY] = self._machineConfig.get(Constants.ASSY_KEY)
        retDict[Constants.YDEV_UNIT_NAME_KEY] = self._machineConfig.get(Constants.YDEV_UNIT_NAME_KEY)
        retDict[Constants.FIRMWARE_VERSION_STR] = Constants.FIRMWARE_VERSION
        retDict[Constants.ACTIVE] = self._machineConfig.get(Constants.ACTIVE)
        pf_watts_threshold = self._machineConfig.get(Constants.PF_WATTS_THRESHOLD)
        if pf_watts_threshold is not None:
            retDict[Constants.PF_WATTS_THRESHOLD] = pf_watts_threshold

        return retDict

    def _handle(self, cmdDict):
        """@brief Process the commands received and not handled by the BaseCmdHandler as a JSON string from the client and return a response dict.
           @return A dict in response to the command."""
        responseDict = {RestServer.ERROR_KEY: "NO command found."}
        # Note that BuiltInCmdHandler in lib/rest_server.py has a number of built in commands
        # Look here first before adding a new command here.
        if RestServer.CMD_KEY in cmdDict:
            cmd = cmdDict[RestServer.CMD_KEY]

            # Define the error response.
            responseDict = {RestServer.ERROR_KEY: "{} is an invalid command.".format(cmd)}

            if cmd.startswith( CmdHandler.INIT_ATM90E32_DEVICES ):
                responseDict = self._initATM90E32Devs()

            elif cmd.startswith( CmdHandler.SAVE_FACTORY_CONFIG_CMD ):
                responseDict = self.saveFactoryConfig()

            elif cmd.startswith( CmdHandler.GET_TEMPERATURE_CMD ):
                temperature = self.getBoardTemp()
                responseDict = RestServer.GetOKDict()
                # Add the board temperature to the response
                responseDict[CmdHandler.CT6_BOARD_TEMPERATURE] = temperature

            elif cmd.startswith( CmdHandler.SET_WIFI_LED ):
                self._setWifiLed(cmdDict)
                responseDict = RestServer.GetOKDict()

            elif cmd.startswith( CmdHandler.FLASH_BLUETOOTH_LED ):
                self._setBluetoothLed(cmdDict)
                responseDict = RestServer.GetOKDict()

        return responseDict

    def _setWifiLed(self, cmdDict):
        """@brief Flash the WiFi LED.
                  See WiFi.setWiFiLED() for details of the argument values that may be set."""
        if 'on' in cmdDict:
            on = cmdDict['on']
            if self._wifi:
                self._wifi.setWiFiLED(on)

    def _setBluetoothLed(self, cmdDict):
        """@brief Flash the bluetooth LED. This method allows the testing of the Bluetooth LED.
           on=1 sets LED on, on= anything else sets led off."""
        if 'on' in cmdDict:
            on = False
            if cmdDict['on'] == '1':
                on = True
            if self._wifi:
                self._wifi.setBlueToothLED(on)

    def _showConfig(self, config, paramList):
        """@brief Display debug messages detailing the contents of the config.
           @param config A MachineConfig instance.
           @param keyList A list of the config parameters."""
        for param in paramList:
            self._debug(f"{param: <25} = {config.get(param)}")

    def _initATM90E32Devs(self):
        """@brief reinit the ATM90E32 devices with the current configuration settings."""
        # Reset both ATM90E32 devices (this was added to V2.1 boards)
        # assert active low reset
        self._atm90e32Reset.value(0)
        sleep_ms(10)
        # release active low reset
        self._atm90e32Reset.value(1)
        sleep_ms(10)

        # Enabling this debug output caused the calibration to fail because
        # the serial data backs up waiting to be sent out the serial port.
        # This causes the MCU to run out of memory and the MCU restarts
        # during calibration. Therefore this has been disabled.
        # Note that the second channel (B) is CT1,2 & 3 to ease PCB layout
        self._debug("Init ATM90E32 Channel B (CT1,CT2 and CT3)")
        self._showConfig(self._machineConfig,  (Constants.LINE_FREQ_HZ_KEY,
                                                Constants.CS4_VOLTAGE_GAIN_KEY,
                                                Constants.CT1_IGAIN_KEY,
                                                Constants.CT2_IGAIN_KEY,
                                                Constants.CT3_IGAIN_KEY,
                                                Constants.CS4_VOLTAGE_OFFSET,
                                                Constants.CT1_IOFFSET_KEY,
                                                Constants.CT2_IOFFSET_KEY,
                                                Constants.CT3_IOFFSET_KEY))
        # Create an interface to the first ATM90E32 device.
        self._cs4ATM90E32 = ATM90E32(self._spi,
                            Constants.ATM90E32_CS4_PIN,
                            self._machineConfig.get(Constants.LINE_FREQ_HZ_KEY),
                            Constants.ATM90E32_PGA_GAIN,
                            self._machineConfig.get(Constants.CS4_VOLTAGE_GAIN_KEY),
                            self._machineConfig.get(Constants.CS4_VOLTAGE_GAIN_KEY),
                            self._machineConfig.get(Constants.CS4_VOLTAGE_GAIN_KEY),
                            self._machineConfig.get(Constants.CT1_IGAIN_KEY),
                            self._machineConfig.get(Constants.CT2_IGAIN_KEY),
                            self._machineConfig.get(Constants.CT3_IGAIN_KEY),
                            uOffset1=self._machineConfig.get(Constants.CS4_VOLTAGE_OFFSET),
                            iOffset1=self._machineConfig.get(Constants.CT1_IOFFSET_KEY),
                            iOffset2=self._machineConfig.get(Constants.CT2_IOFFSET_KEY),
                            iOffset3=self._machineConfig.get(Constants.CT3_IOFFSET_KEY))

        # Enabling this debug output caused the calibration to fail because
        # the serial data backs up waiting to be sent out the serial port.
        # This causes the MCU to run out of memory and the MCU restarts
        # during calibration. Therefore this has been disabled.
        # Note that the first channel (A) is CT4,5 & 6 to ease PCB layout
        self._debug("Init ATM90E32 Channel A (CT4,CT5 and CT6)")
        self._showConfig(self._machineConfig,  (Constants.LINE_FREQ_HZ_KEY,
                                                Constants.CS0_VOLTAGE_GAIN_KEY,
                                                Constants.CT4_IGAIN_KEY,
                                                Constants.CT5_IGAIN_KEY,
                                                Constants.CT6_IGAIN_KEY,
                                                Constants.CS0_VOLTAGE_OFFSET,
                                                Constants.CT4_IOFFSET_KEY,
                                                Constants.CT5_IOFFSET_KEY,
                                                Constants.CT6_IOFFSET_KEY))
        # Create an interface to the second ATM90E32 device
        self._cs0ATM90E32 = ATM90E32(self._spi,
                            Constants.ATM90E32_CS0_PIN,
                            self._machineConfig.get(Constants.LINE_FREQ_HZ_KEY),
                            Constants.ATM90E32_PGA_GAIN,
                            self._machineConfig.get(Constants.CS0_VOLTAGE_GAIN_KEY),
                            self._machineConfig.get(Constants.CS0_VOLTAGE_GAIN_KEY),
                            self._machineConfig.get(Constants.CS0_VOLTAGE_GAIN_KEY),
                            self._machineConfig.get(Constants.CT4_IGAIN_KEY),
                            self._machineConfig.get(Constants.CT5_IGAIN_KEY),
                            self._machineConfig.get(Constants.CT6_IGAIN_KEY),
                            uOffset1=self._machineConfig.get(Constants.CS0_VOLTAGE_OFFSET),
                            iOffset1=self._machineConfig.get(Constants.CT4_IOFFSET_KEY),
                            iOffset2=self._machineConfig.get(Constants.CT5_IOFFSET_KEY),
                            iOffset3=self._machineConfig.get(Constants.CT6_IOFFSET_KEY))
        self._uo.info("Initialised ATM90E32 devices.")
        return {RestServer.OK_KEY: "ATM90E32 init success."}

    def saveFactoryConfig(self):
        """@brief Save the factory configuration data to the factory config file."""
        factoryConfigFilename = self._machineConfig.saveFactoryConfig(Constants.FACTORY_CONFIG_KEYS)
        return {RestServer.OK_KEY: f"Saved factory config to {factoryConfigFilename}"}




