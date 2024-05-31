#!/usr/bin/env python3

import argparse
import threading
import requests
import traceback
import tempfile
import os
import shutil
import platform

from queue import Queue
from time import time

from p3lib.uio import UIO
from p3lib.bokeh_gui import MultiAppServer
from p3lib.helper import logTraceBack
from p3lib.pconfig import ConfigManager

from lib.config import ConfigBase

from bokeh.layouts import column, row
from bokeh.models.css import Styles
from bokeh.models import TabPanel, Tabs, Div
from bokeh.models import Button, NumericInput
from bokeh.models import TextInput, PasswordInput, TextAreaInput
from bokeh.layouts import layout
from bokeh.models.widgets import Select

from ct6_tool import YDevManager, getCT6ToolCmdOpts, CT6Config, MCULoader
from ct6_mfg_tool import FactorySetup, getFactorySetupCmdOpts

class CT6ConfiguratorConfig(ConfigBase):
    DEFAULT_CONFIG_FILENAME = "ct6_configurator.cfg"
    DEFAULT_CONFIG = {
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS:    "",
        ConfigBase.LOCAL_GUI_SERVER_PORT:       10000
    }

class CT6ConfiguratorGUI(MultiAppServer):
    """@brief Responsible for providing an GUI interface that allows the user to configure
              some parameters on CT6 units."""
    PAGE_TITLE                  = "CT6 Configurator"
    BUTTON_TYPE                 = "success"
    INFO_MESSAGE                = "INFO:  "
    WARN_MESSAGE                = "WARN:  "
    ERROR_MESSAGE               = "ERROR: "
    DEBUG_MESSAGE               = "DEBUG: "
    ENABLE_BUTTONS              = "ENABLE_BUTTONS"
    SET_CT6_IP_ADDRESS          = "SET_CT6_IP_ADDRESS"
    
    CMD_COMPLETE                = "CMD_COMPLETE"
    UPDATE_SECONDS              = "UPDATE_SECONDS"
    
    CFG_FILENAME                = ".ct6ConfiguratorGUI.cfg"
    WIFI_SSID                   = "WIFI_SSID" 
    WIFI_PASSWORD               = "WIFI_PASSWORD" 
    DEVICE_ADDRESS              = "DEVICE_ADDRESS"
    DEFAULT_CONFIG              = {WIFI_SSID: "",
                                   WIFI_PASSWORD: "",
                                   DEVICE_ADDRESS: ""}
    
    UPDATE_PORT_NAMES           = "UPDATE_PORT_NAMES"
    CT1_NAME                    = "CT1_NAME"
    CT2_NAME                    = "CT2_NAME"
    CT3_NAME                    = "CT3_NAME"
    CT4_NAME                    = "CT4_NAME"
    CT5_NAME                    = "CT5_NAME"
    CT6_NAME                    = "CT6_NAME"
    PORT_NAMES_UPDATED          = "PORT_NAMES_UPDATED"
    DEV_NAME                    = "YDEV_UNIT_NAME"
    ACTIVE                      = "ACTIVE"
    MQTT_SERVER_ADDRESS         = "MQTT_SERVER_ADDRESS"
    MQTT_SERVER_PORT            = "MQTT_SERVER_PORT"
    MQTT_TX_PERIOD_MS           = "MQTT_TX_PERIOD_MS"
    DEFAULT_MQTT_SERVER_PORT    = 1883    
    DEFAULT_MQTT_TX_PERIOD_MS   = 2000
    MQTT_TOPIC                  = "MQTT_TOPIC"
    MQTT_USERNAME               = "MQTT_USERNAME"
    MQTT_PASSWORD               = "MQTT_PASSWORD"

    def __init__(self, uio, options, config):
        """@brief Constructor.
           @param uio A UIO instance responsible for stdout/stdin input output.
           @param options The command line argparse options instance.
           @param config The dash app config.
           @param loginCredentialsFile A file containing the login credentials or None if no server authentication is required."""
        super().__init__(address=config.getAttr(CT6ConfiguratorConfig.LOCAL_GUI_SERVER_ADDRESS),
                         bokehPort=config.getAttr(CT6ConfiguratorConfig.LOCAL_GUI_SERVER_PORT) )
        self._uio               = uio
        self._options           = options
        self._config            = config
    
        self._doc               = None
        self._server            = None
        self._tabList           = None
        self._startUpdateTime   = None
        self._logPath           = os.path.join(os.path.expanduser('~'), FactorySetup.LOG_PATH)
        self._isWindows         = platform.system() == "Windows"

        self._ensureLogPathExists()

        self._cfgMgr = ConfigManager(self._uio, CT6ConfiguratorGUI.CFG_FILENAME, CT6ConfiguratorGUI.DEFAULT_CONFIG)
        # this queue is used to send commands from the GUI thread and read responses received from outside the GUI thread.
        self._commsQueue = Queue()
        
    def _ensureLogPathExists(self):
        """@brief Ensure that the log path exists."""
        if not os.path.isdir(self._logPath):
            os.makedirs(self._logPath)

    def getAppMethodDict(self):
        """@return The server app method dict."""
        appMethodDict = {}
        appMethodDict['/']=self._mainApp
        return appMethodDict

    def _getInstallPanel(self):
        """@brief Return the panel used to wipe the Pico W flash and re install the software."""
        #Add HTML to the page.
        descriptionDiv = Div(text="""Erase the all CT6 firmware and configuration and then re load firmware.<br><br>A USB cable must be connected to the CT6 device to install CT6 software.""")
        
        self._installSWButton = Button(label="Install CT6 SW", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._installSWButton.on_click(self._installSWButtonHandler)

        buttonRow = row(children=[self._installSWButton])
        
        
        panel = column(children=[descriptionDiv,
                                 buttonRow])
        return TabPanel(child=panel,  title="Install")

    def _installSWButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        self._saveConfig()
        threading.Thread( target=self._installSW).start()

    def _correctRshellWindowsPath(self, aPath):
        """@brief Correct for a windows path in an rshell command.
           @param aPath The path to check.
           @return The corrected Windows path if on a Windows platform.
                   If not on a windwos platform aPath is returned unchanged."""
        mPath = aPath
        if self._isWindows:
            # Remove drive
            if len(mPath) > 2 and mPath[1] == ':':
                mPath = mPath[1:]
                mPath=mPath.replace(":\\", "/")
            # Close in quotes in case of spaces in path.
            mPath = '"'+mPath+'"'
        return mPath
    
    def _getCT6FactoryConfig(self, devManager):
        """@brief Read the factory config from the CT6 unit.
           @param devManager A YDevManager instance.
           @return The path to a local copy of the factory config file read from the CT6 device."""
        self.info("Connecting to CT6 device over it's serial port.")
        # Attempt to connect to the board under test python prompt
        if not devManager._checkMicroPython(closeSerialPort=True):
            raise Exception("Failed to read the CT6 MicroPython version over serial port.")
        tempPath = tempfile.gettempdir()
        srcFile = f"/pyboard/{YDevManager.CT6_FACTORY_CONFIG_FILE}"
        destFile = os.path.join(tempPath, YDevManager.CT6_FACTORY_CONFIG_FILE)
        self.info("Reading CT6 factory configuration.")
        self.debug(f"Copy {YDevManager.CT6_FACTORY_CONFIG_FILE} to {destFile}")
        # Copy the factory config to the temp folder
        devManager._runRShell((f'cp {srcFile} {self._correctRshellWindowsPath(destFile)}',))
        devManager._checkFactoryConfFile(f'{destFile}')
        factoryDict = devManager._loadJSONFile(destFile)
        assyLabel = factoryDict[YDevManager.ASSY_KEY]
        tsString = FactorySetup.GetTSString()
        savedFactoryConfFile = os.path.join(self._logPath, assyLabel + "_" + tsString + "_" + YDevManager.CT6_FACTORY_CONFIG_FILE)
        shutil.copy(destFile ,savedFactoryConfFile)
        self.info(f"Created {savedFactoryConfFile}")
        return savedFactoryConfFile

    def _restoreFactoryConfig(self, devManager, factoryConfigFile):
        """@brief restore the factory config file to the CT6 device.
           @param devManager A YDevManager instance.
           @param factoryConfigFile The factory config file to copy."""
        self.info("Restoring factory config to the CT6 device.")
        if factoryConfigFile and os.path.isfile(factoryConfigFile):
            srcFile = factoryConfigFile
        else:
            # Use the fallback factory config file if available.
            tempPath = tempfile.gettempdir()
            srcFile = os.path.join(tempPath, YDevManager.CT6_FACTORY_CONFIG_FILE)
            if not os.path.isfile(srcFile):
                raise Exception(f"{srcFile} fallback factory config file not found.")

        # Copy the factory config to the temp folder
        destFile = f"/pyboard/{YDevManager.CT6_FACTORY_CONFIG_FILE}"
        devManager._runRShell((f"cp {self._correctRshellWindowsPath(srcFile)} {destFile}",))
        self.info("Restored factory config to the CT6 device.")

    def _installSW(self):
        """@brief Called to do the work of wiping flash and installing the system software onto
                  CT6 hardware."""
        try:
            try:
                factoryConfigFile = None
                options = getCT6ToolCmdOpts()
                devManager = YDevManager(self, options)
                try:
                    # Before erasing and loadin SW we check we have a copy of the factory config file
                    # from the CT6 device.
                    factoryConfigFile = self._getCT6FactoryConfig(devManager)
                except:
                    # If we couldn't read the factory config then we may not be able to restore it 
                    # at the endof the install process.Therefore this cmd line option should be used with care.
                    if self._options.skip_factory_config_restore:
                        self.warn("!!! Failed to read the factory config from the CT6 device !!!")
                    else:
                        # Stop the install process to ensure we are not left in a situation where the
                        # factory calibration config is lost.
                        raise

                factorySetupOptions = getFactorySetupCmdOpts()
                factorySetup = FactorySetup(self, factorySetupOptions)

                factorySetup._erasePicoWFlash()
                factorySetup._loadMicroPython()

                mcuLoader = MCULoader(self, factorySetupOptions)
                mcuLoader.load()
                self.info("Running the CT6 firmware")

                self._restoreFactoryConfig(devManager, factoryConfigFile)

                devManager.restart()

                self.info("CT6 software restore complete.")
                self.info("The blue and green LED's should now be flashing on the CT6 device.")
                self.info("You may now configure the WiFi on the CT6 device.")

            except Exception as ex:
                self.error(str(ex))
                
        finally:
            self._sendEnableAllButtons(True)   

    def _getSetWifiPanel(self):
        """@brief Return the panel used to configure the CT6 devices WiFi network parameters."""
                #Add HTML to the page.
        descriptionDiv = Div(text="""Set the WiFi SSID and password of your CT6 device.<br><br>A USB cable must be connected to the CT6 device to setup the WiFi.""")
        
        self._wifiSSIDInput = TextInput(title="WiFi SSID", placeholder="WiFi SSID")
        ssidRow = row(children=[self._wifiSSIDInput])
            
        self._wifiPasswordInput = PasswordInput(title="WiFi password",placeholder="WiFi password")
        passwordRow = row(children=[self._wifiPasswordInput])
            
        self._setWiFiNetworkButton = Button(label="Setup WiFi", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._setWiFiNetworkButton.on_click(self._setWiFiNetworkButtonHandler)

        buttonRow = row(children=[self._setWiFiNetworkButton])
        
        
        panel = column(children=[descriptionDiv,
                                 ssidRow,
                                 passwordRow, 
                                 buttonRow])
        return TabPanel(child=panel,  title="WiFi")
        
    def _setWiFiNetworkButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        self._saveConfig()
        threading.Thread( target=self._setWiFiNetwork, args=(self._wifiSSIDInput.value, self._wifiPasswordInput.value)).start()
                
    def _setWiFiNetwork(self, wifiSSID, wifiPassword):
        """@brief Set the Wifi network.
           @param wifiSSID The WiFi SSID to set.
           @param wifiPassword The WiFi password to set."""
        try:
            try:
                if len(wifiSSID) == 0:
                    self.info("A WiFi SSID is required.")
                
                elif len(wifiPassword) == 0:
                    self.info("A WiFi password is required.")
                    
                else:
                    self.info("Setting the CT6 device WiFi network.")
                    options = getCT6ToolCmdOpts()
                    devManager = YDevManager(self, options, ssid=wifiSSID, password=wifiPassword)
                    devManager.configureWiFi()
                    ipAddress = devManager._runApp()
                    self.info(f"The CT6 device is now connected to {wifiSSID} (IP address = {ipAddress})")
                    # Send a message to set the CT6 device IP address in the GUI
                    self._setCT6IPAddress(ipAddress)
                    
            except Exception as ex:
                self.error(str(ex))
                
        finally:
            self._sendEnableAllButtons(True)
                
    def _setCT6IPAddress(self, address):
        """@brief Send a warning message to be displayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {CT6ConfiguratorGUI.SET_CT6_IP_ADDRESS: address}
        self.updateGUI(msgDict)
        
    def updateGUI(self, msgDict):
        """@brief Send a message to the GUI so that it updates itself.
           @param msgDict A dict containing details of how to update the GUI."""
        # Record the seconds when we received the message
        msgDict[CT6ConfiguratorGUI.UPDATE_SECONDS]=time()
        self._commsQueue.put(msgDict)
        
    def _getUpgradePanel(self):
        """@brief Return the panel used to upgrade CT6 devices."""
        descriptionDiv = Div(text="""Upgrade CT6 firmware over your WiFi network.""")
        
        ipAddresssRow = row(children=[self._ct6IPAddressInput])
                        
        self._upgradeButton = Button(label="Upgrade CT6 device", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._upgradeButton.on_click(self._upgradeButtonButtonHandler)

        buttonRow = row(children=[self._upgradeButton])
        
        panel = column(children=[descriptionDiv,
                                 ipAddresssRow,
                                 buttonRow])
        return TabPanel(child=panel,  title="Upgrade")

    def _upgradeButtonButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._doUpgrade, args=(self._ct6IPAddressInput.value,)).start()
        
    def _doUpgrade(self, ct6IPAddress):
        """@brief Perform an upgrade of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device."""
        try:
            try:
                if len(ct6IPAddress) == 0:
                    self.info("The address of the CT6 device is required.")
                    
                else:
                    self.info(f"Checking {ct6IPAddress} is reachable.")
                    
                    options = getCT6ToolCmdOpts()
                    devManager = YDevManager(self, options)
                    pingT = devManager.doPing(ct6IPAddress)
                    if pingT is not None:
                        self.info(f"Attempting to upgrade CT6 device at {ct6IPAddress}")
                        devManager.setIPAddress(ct6IPAddress)
                        devManager.upgrade(promptReboot=False)
                        devManager._powerCycle()
                        devManager._checkRunningNewApp()
                        self.info("CT6 upgrade completed successfully.")
                        
                    else:
                        self.error(f"Unable to ping {ct6IPAddress}")
                                          
            except Exception as ex:
                self.error(str(ex))
                
        finally:
            self._sendEnableAllButtons(True)
        
    def _getDeviceNamePanel(self):
        """@brief Return the panel used to configure the CT6 device name."""
        descriptionDiv = Div(text="""Set the name for your CT6 device.""")
        
        ipAddresssRow = row(children=[self._ct6IPAddressInput])
        
        self._ct6DeviceNameInput = TextInput(title="Device Name", placeholder="Device Name")
        devNameRow = row(children=[self._ct6DeviceNameInput])
        
        self._setDevNameButton = Button(label="Set", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._setDevNameButton.on_click(self._setDevNameButtonHandler)

        self._getDevNameButton = Button(label="Get", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._getDevNameButton.on_click(self._getDevNameButtonHandler)

        buttonRow = row(children=[self._getDevNameButton, self._setDevNameButton])

        panel = column(children=[descriptionDiv,
                                 ipAddresssRow,
                                 devNameRow,
                                 buttonRow])
        return TabPanel(child=panel,  title="Device Name")
            
    def _setDevNameButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        self._saveConfig()
        threading.Thread( target=self._setDevName, args=(self._ct6IPAddressInput.value,self._ct6DeviceNameInput.value)).start()
        
    def _setDevName(self, ct6IPAddress, devName):
        """@brief Set the CT6 device name.
           @param ct6IPAddress The address of the CT6 device.
           @param devName The name of the device."""
        try:
            try:
                self.info(f"Setting CT6 device ({ct6IPAddress}) name.")
                cfgDict = {}
                cfgDict[CT6ConfiguratorGUI.DEV_NAME] = devName
                response = self._saveConfigDict(ct6IPAddress, cfgDict)
                if response is not None:
                    self.info(f"Set CT6 device name to {devName}")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)
    
    def _getDevNameButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        self._saveConfig()
        threading.Thread( target=self._getDevName, args=(self._ct6IPAddressInput.value,)).start()
    
    def _getDevName(self, ct6IPAddress):
        """@brief Get the CT6 device name.
           @param ct6IPAddress The address of the CT6 device."""
        try:
            try:
                self.info(f"Getting CT6 device ({ct6IPAddress}) name.")
                cfgDict = self._getConfigDict(ct6IPAddress)
                if CT6ConfiguratorGUI.DEV_NAME in cfgDict:
                    devName = cfgDict[CT6ConfiguratorGUI.DEV_NAME]
                    self.info("Read CT6 device name.")
                    msgDict = {CT6ConfiguratorGUI.DEV_NAME: devName}
                    self.updateGUI(msgDict)
                
                else:
                    self.error("Failed to read the CT6 device name.")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)
            
    def _getPortNamePanel(self):
        """@brief Return the panel used to configure the CT6 port names."""
        descriptionDiv = Div(text="""Set the name of each port on your CT6 device.""")
        
        ipAddresssRow = row(children=[self._ct6IPAddressInput])
        
        self._ct1PortNameInput = TextInput(title="CT1 port name", placeholder="CT1 port name")
        port1Row = row(children=[self._ct1PortNameInput])
            
        self._ct2PortNameInput = TextInput(title="CT2 port name", placeholder="CT2 port name")
        port2Row = row(children=[self._ct2PortNameInput])
            
        self._ct3PortNameInput = TextInput(title="CT3 port name", placeholder="CT3 port name")
        port3Row = row(children=[self._ct3PortNameInput])
            
        self._ct4PortNameInput = TextInput(title="CT4 port name", placeholder="CT4 port name")
        port4Row = row(children=[self._ct4PortNameInput])
            
        self._ct5PortNameInput = TextInput(title="CT5 port name", placeholder="CT5 port name")
        port5Row = row(children=[self._ct5PortNameInput])
            
        self._ct6PortNameInput = TextInput(title="CT6 port name", placeholder="CT6 port name")
        port6Row = row(children=[self._ct6PortNameInput])
            
        self._setPortNamesButton = Button(label="Set", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._setPortNamesButton.on_click(self._setPortNamesButtonHandler)

        self._getPortNamesButton = Button(label="Get", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._getPortNamesButton.on_click(self._getPortNamesButtonHandler)
        
        buttonRow = row(children=[self._getPortNamesButton, self._setPortNamesButton])

        col1 = row(port1Row,
                      port2Row,
                      port3Row)
        col2 = row(port4Row,
                      port5Row,
                      port6Row)
        
        panel = column(children=[descriptionDiv,
                                 ipAddresssRow,
                                 col1,
                                 col2,
                                 buttonRow])
        
        return TabPanel(child=panel,  title="Port Names")
    
    def _setPortNamesButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._setPortNames, args=(self._ct6IPAddressInput.value, (self._ct1PortNameInput.value,
                                                                                           self._ct2PortNameInput.value,
                                                                                           self._ct3PortNameInput.value,
                                                                                           self._ct4PortNameInput.value,
                                                                                           self._ct5PortNameInput.value,
                                                                                           self._ct6PortNameInput.value) )).start()
                                                                                           
    def _setPortNames(self, ct6IPAddress, portNames):
        """@brief Set the CT6 port names.
           @param ct6IPAddress The address of the CT6 device.
           @param portNames The names of each port."""
        try:
            try:
                self.info(f"Setting CT6 device ({ct6IPAddress}) port names.")
                cfgDict = {}
                cfgDict[CT6ConfiguratorGUI.CT1_NAME] = portNames[0]
                cfgDict[CT6ConfiguratorGUI.CT2_NAME] = portNames[1]
                cfgDict[CT6ConfiguratorGUI.CT3_NAME] = portNames[2]
                cfgDict[CT6ConfiguratorGUI.CT4_NAME] = portNames[3]
                cfgDict[CT6ConfiguratorGUI.CT5_NAME] = portNames[4]
                cfgDict[CT6ConfiguratorGUI.CT6_NAME] = portNames[5]
                response = self._saveConfigDict(ct6IPAddress, cfgDict)
                if response is not None:
                    msgDict = {CT6ConfiguratorGUI.PORT_NAMES_UPDATED: True}
                    self.updateGUI(msgDict)
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)
        
    def _checkResponse(self, response):
        """@brief Check we don't have an error response."""
        rDict = response.json()
        if "ERROR" in rDict:
            msg = rDict["ERROR"]
            self.error(msg)
        
    def _saveConfigDict(self, ct6IPAddress, cfgDict):
        """@brief Save the config dict back to the CT6 device.
           @brief The device config dict."""
        url=f"http://{ct6IPAddress}/set_config"
        index=0
        url=url+"?"
        index = 0
        for key in cfgDict:
            if key not in CT6Config.EDITABLE_KEY_LIST:
                self.error(f"{key} in not an editable parameter on CT6 devices.")
                continue
            value=cfgDict[key]
            # First arg is added without , separator
            if index == 0:
                url=url+key+"="+str(value)
            # All other args are added with a , separator
            else:
                url=url+","+key+"="+str(value)
            index+=1
        response = requests.get(url)
        if response is not None:
            self.debug("_saveConfigDict() successful.")
        else:
            self.debug("_saveConfigDict() failed.")
        self._checkResponse(response)
        return response
        
    def _getPortNamesButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._getPortNames, args=(self._ct6IPAddressInput.value,)).start()
    
    def _getPortNames(self, ct6IPAddress):
        """@brief Get the CT6 port names.
           @param ct6IPAddress The address of the CT6 device."""
        cfgDict = self._getConfigDict(ct6IPAddress)
        ct1PortName = ""
        ct2PortName = ""
        ct3PortName = ""
        ct4PortName = ""
        ct5PortName = ""
        ct6PortName = ""
        if CT6ConfiguratorGUI.CT1_NAME in cfgDict:
            ct1PortName = cfgDict[CT6ConfiguratorGUI.CT1_NAME]
        
        if CT6ConfiguratorGUI.CT2_NAME in cfgDict:
            ct2PortName = cfgDict[CT6ConfiguratorGUI.CT2_NAME]
        
        if CT6ConfiguratorGUI.CT3_NAME in cfgDict:
            ct3PortName = cfgDict[CT6ConfiguratorGUI.CT3_NAME]
        
        if CT6ConfiguratorGUI.CT4_NAME in cfgDict:
            ct4PortName = cfgDict[CT6ConfiguratorGUI.CT4_NAME]
        
        if CT6ConfiguratorGUI.CT5_NAME in cfgDict:
            ct5PortName = cfgDict[CT6ConfiguratorGUI.CT5_NAME]
        
        if CT6ConfiguratorGUI.CT6_NAME in cfgDict:
            ct6PortName = cfgDict[CT6ConfiguratorGUI.CT6_NAME]
        
        msgDict = {CT6ConfiguratorGUI.UPDATE_PORT_NAMES: True,
                   CT6ConfiguratorGUI.CT1_NAME: ct1PortName,
                   CT6ConfiguratorGUI.CT2_NAME: ct2PortName,
                   CT6ConfiguratorGUI.CT3_NAME: ct3PortName,
                   CT6ConfiguratorGUI.CT4_NAME: ct4PortName,
                   CT6ConfiguratorGUI.CT5_NAME: ct5PortName,
                   CT6ConfiguratorGUI.CT6_NAME: ct6PortName,}
        self.updateGUI(msgDict)
           
    def _getConfigDict(self, ct6IPAddress):
        """@brief Get the config dict from the device.
           @param ct6IPAddress The address of the CT6 device.
           @return The config dict."""
        self.info(f"Reading configuration from {ct6IPAddress}.")
        url=f"http://{ct6IPAddress}/get_config"
        response = requests.get(url)
        cfgDict = response.json()
        self.debug(f"Config read from CT6 device: cfgDict={cfgDict}")
        return cfgDict
               
    def _getMQTTPanel(self):
        """@brief Return the panel used to configure the MQTT server."""
        descriptionDiv = Div(text="""For use with third party tools such as ioBroker you may wish the CT6 device to<br>
                                     periodically send data to an MQTT server. This is not required for normal operation<br>
                                     of the CT6 device and so you may skip the settings on this page if you do not wish<br>
                                     to send data to an MQTT server.<br>
                                     To send JSON data to an MQTT server the 'MQTT Server Address' or 'MQTT Topic' fields must<br>
                                     be set. You may need to complete the 'MQTT Username' and 'MQTT password' fields if your MQTT<br>
                                     server requires this.<br>
                                     The CT6 device will not attempt to send JSON data to an MQTT server unless enabled in<br>
                                     the 'Activate Device' tab.""")

        ipAddresssRow = row(children=[self._ct6IPAddressInput])
        
        self._mqttServerAddressInput = TextInput(title="MQTT Server Address", placeholder="MQTT Server Address")
        self._mqttServerPortInput = NumericInput(title="MQTT Server Port", value=CT6ConfiguratorGUI.DEFAULT_MQTT_SERVER_PORT, low= 1, high=65535, mode='int')
        self._mqttTopicInput = TextInput(title="MQTT Topic", placeholder="MQTT Topic")  
        row1 = row(children=[self._mqttServerAddressInput, self._mqttServerPortInput, self._mqttTopicInput])

        self._mqttUsernameInput = TextInput(title="MQTT Username", placeholder="MQTT Username")  
        self._mqttPasswordInput = TextInput(title="MQTT Password", placeholder="MQTT Password") 
        self._mqttServerTXPeriodMSInput = NumericInput(title="TX Period (Milli Seconds)", placeholder="TX Period (Milli Seconds)", value=CT6ConfiguratorGUI.DEFAULT_MQTT_TX_PERIOD_MS, low= 200, high=600000, mode='int')
        row2 = row(children=[self._mqttUsernameInput, self._mqttPasswordInput, self._mqttServerTXPeriodMSInput])

        self._setMQTTServerButton = Button(label="Set", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._setMQTTServerButton.on_click(self._setMQTTServerButtonHandler)

        self._getMQTTServerButton = Button(label="Get", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._getMQTTServerButton.on_click(self._getMQTTServerButtonHandler)

        buttonRow = row(children=[self._getMQTTServerButton, self._setMQTTServerButton])

        panel = column(children=[descriptionDiv,
                                 ipAddresssRow,
                                 row1,
                                 row2,
                                 buttonRow])
        return TabPanel(child=panel,  title="MQTT Server")
        
    def _setMQTTServerButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._setMQTTServer, args=(self._ct6IPAddressInput.value, 
                                                        self._mqttServerAddressInput.value ,
                                                        self._mqttServerPortInput.value,
                                                        self._mqttTopicInput.value,
                                                        self._mqttUsernameInput.value,
                                                        self._mqttPasswordInput.value,
                                                        self._mqttServerTXPeriodMSInput.value )).start()
        
    def _setMQTTServer(self, ct6IPAddress, address, port, topic, username, password, txPeriodMS):
        """@brief Perform an upgrade of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device.
           @param address The address of the MQTT server.
           @param port The port number of the MQTT server.
           @param topic The MQTT topic that the CT6 device MQTT client will subsribe to.
           @param username The MQTT username. Maybe empty for anonymous connection.
           @param password The MQTT password. Maybe empty fro anonymous connection.
           @param txPeriodMS The period of the data sent to the MQTT server in milli seconds."""
        try:
            try:
                self.info(f"Set CT6 device ({ct6IPAddress}) MQTT server configuration.")
                # First check that the firmware on the CT6 device contains the MQTT server configuration
                cfgDict = self._getConfigDict(ct6IPAddress) 
                if CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_SERVER_PORT in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_TOPIC in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_USERNAME in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_PASSWORD in cfgDict:
                    
                    #PAJ TODO self._checkReacable(address, port)
                    
                    # Remove leading and trailing whitespace characters
                    address=address.strip()
                    topic=topic.strip()
                    username=username.strip()
                    password=password.strip()

                    # Replace spaces with underscores
                    address=address.replace(" ", "_")
                    topic=topic.replace(" ", "_")
                    username=username.replace(" ", "_")
                    password=password.replace(" ", "_")

                    mqttCfgDict = {CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS: address,
                                   CT6ConfiguratorGUI.MQTT_SERVER_PORT: port,
                                   CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS: txPeriodMS,
                                   CT6ConfiguratorGUI.MQTT_TOPIC: topic,
                                   CT6ConfiguratorGUI.MQTT_USERNAME: username,
                                   CT6ConfiguratorGUI.MQTT_PASSWORD: password}
                    response = self._saveConfigDict(ct6IPAddress, mqttCfgDict)
                    if response is not None:
                        self.info("Set CT6 device MQTT server configuration.")
                       
                else:
                    self.error("Upgrade the CT6 device to support MQTT server connectivity.")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)

    def _getMQTTServerButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._getMQTTServer, args=(self._ct6IPAddressInput.value,)).start()
        
    def _getMQTTServer(self, ct6IPAddress):
        """@brief Perform an upgrade of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device."""
        try:
            try:
                self.info(f"Get CT6 device ({ct6IPAddress}) MQTT server configuration.")
                cfgDict = self._getConfigDict(ct6IPAddress)
                if CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_SERVER_PORT in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_TOPIC in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_USERNAME in cfgDict and \
                   CT6ConfiguratorGUI.MQTT_PASSWORD in cfgDict:
                    
                    mqttServerAddress = cfgDict[CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS]
                    mqttServerPort = cfgDict[CT6ConfiguratorGUI.MQTT_SERVER_PORT]
                    mqttTopic = cfgDict[CT6ConfiguratorGUI.MQTT_TOPIC]
                    mqttUsername = cfgDict[CT6ConfiguratorGUI.MQTT_USERNAME]
                    mqttPassword = cfgDict[CT6ConfiguratorGUI.MQTT_PASSWORD]
                    mqttTXPeriodMS = cfgDict[CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS]
                    msgDict = {CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS: mqttServerAddress,
                               CT6ConfiguratorGUI.MQTT_SERVER_PORT: mqttServerPort,
                               CT6ConfiguratorGUI.MQTT_TOPIC: mqttTopic,
                               CT6ConfiguratorGUI.MQTT_USERNAME: mqttUsername,
                               CT6ConfiguratorGUI.MQTT_PASSWORD: mqttPassword,
                               CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS: mqttTXPeriodMS}
                    self.updateGUI(msgDict)
                        
                else:
                    self.error("Upgrade the CT6 device to support MQTT server connectivity.")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)

    def _getEnableDevicePanel(self):
        """@brief Return the panel used to configure the CT6 devices WiFi network parameters."""
        descriptionDiv = Div(text="""Activate or deactivate your CT6 device. Your CT6 device will only send data to a database or an MQTT<br>server when it has been set to the active state.""")
                
        ipAddresssRow = row(children=[self._ct6IPAddressInput])
        
        self._enabledStates = ["enabled", "disabled"]
        # Select the first serial port in the list
        self._enabledStateSelect = Select(title="CT6 Device Active", value=self._enabledStates[1], options=self._enabledStates)
        enabledStateRow = row(children=[self._enabledStateSelect])
            
        self._setEnabledStateButton = Button(label="Set", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._setEnabledStateButton.on_click(self._setEnabledStateButtonHandler)

        self._getEnabledStateButton = Button(label="Get", button_type=CT6ConfiguratorGUI.BUTTON_TYPE)
        self._getEnabledStateButton.on_click(self._getEnabledStateButtonHandler)

        buttonRow = row(children=[self._getEnabledStateButton, self._setEnabledStateButton])
        
        panel = column(children=[descriptionDiv,
                                 ipAddresssRow,
                                 enabledStateRow,
                                 buttonRow])
        return TabPanel(child=panel,  title="Activate Device")
    
    def _setEnabledStateButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        if self._enabledStateSelect.value == 'enabled':
            state=1
        else:
            state=0
        threading.Thread( target=self._enableCT6, args=(self._ct6IPAddressInput.value, state )).start()
        
    def _enableCT6(self, ct6IPAddress, enabled):
        """@brief Enable/Disable the CT6 unit.
           @param ct6IPAddress The address of the CT6 device.
           @param enabled True if the CT6 should send data."""
        try:
            try:
                active=0
                activeStr = "inactive"
                if enabled:
                    active=1
                    activeStr = "active"
                cfgDict = {}
                cfgDict[CT6ConfiguratorGUI.ACTIVE] = active
                response = self._saveConfigDict(ct6IPAddress, cfgDict)
                if response is not None:         
                    self.info(f"Set CT6 device ({ct6IPAddress}) the {activeStr} state.")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)
            
    def _getEnabledStateButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._getEnabled, args=(self._ct6IPAddressInput.value,)).start()
        
    def _getEnabled(self, ct6IPAddress):
        """@brief Get the enabled state of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device."""
        self.info(f"Get CT6 ({ct6IPAddress}) enabled state.")
        try:
            try:
                self.info(f"Getting CT6 device ({ct6IPAddress}) active state.")
                cfgDict = self._getConfigDict(ct6IPAddress)
                if CT6ConfiguratorGUI.ACTIVE in cfgDict:
                    state = cfgDict[CT6ConfiguratorGUI.ACTIVE]
                    msgDict = {CT6ConfiguratorGUI.ACTIVE: state}
                    self.updateGUI(msgDict)
                        
                else:
                    self.error("Failed to read the active state of the CT6 device.")

                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)
             
    def _enableAllButtons(self, enabled):
        """@brief Enable/Disable all buttons.
           @param enabled True if button is enabled."""
        self._installSWButton.disabled = not enabled
        self._setWiFiNetworkButton.disabled = not enabled
        self._upgradeButton.disabled = not enabled
        self._setPortNamesButton.disabled = not enabled
        self._setEnabledStateButton.disabled = not enabled
        self._setMQTTServerButton.disabled = not enabled
        self._getPortNamesButton.disabled = not enabled
        self._getEnabledStateButton.disabled = not enabled
        self._getMQTTServerButton.disabled = not enabled
        
    def _clearMessages(self):
        """@brief Reset the messages in the status area."""
        self._statusAreaInput.value = ""
        
    def _mainApp(self, doc):
        """@brief create the GUI page.
           @param doc The document to add the plot to."""
        self._startupShow = True
        # Clear the queue once we have the lock to ensure it's
        # not being read inside the _update() method.
        while not self._commsQueue.empty():
            self._commsQueue.get(block=False)

        doc.clear()
        self._doc = doc
        # Set the Web page title
        self._doc.title = CT6ConfiguratorGUI.PAGE_TITLE
        self._tabList = []
        # 1 rem generally = 16px
        # Using rem rather than px can help ensure consistency of font size and spacing throughout your UI.
        fontSize='1rem'
        theme = "dark_minimal"
        tabTextSizeSS = [{'.bk-tab': Styles(font_size='{}'.format(fontSize))}, {'.bk-tab': Styles(background='{}'.format('grey'))}]
        
        self._lastStatusMsgTextInput = TextInput(title="Message", value="", disabled=True)
        self._statusAreaInput = TextAreaInput(title="Message Log", value="", disabled=True, rows=10)

        # Create address input field. Defined here because we use it on multiple tabs.
        self._ct6IPAddressInput = TextInput(title="CT6 IP Address", placeholder="CT6 IP Address")

        self._tabList.append( self._getInstallPanel() )
        self._tabList.append( self._getSetWifiPanel() )
        self._tabList.append( self._getUpgradePanel() )
        self._tabList.append( self._getDeviceNamePanel() )
        self._tabList.append( self._getPortNamePanel() )
        self._tabList.append( self._getMQTTPanel() )
        self._tabList.append( self._getEnableDevicePanel() )
      
        self._allTabsPanel = Tabs(tabs=self._tabList, sizing_mode="stretch_both", stylesheets=tabTextSizeSS)
            
        pageWidthPanel = column(children=[self._allTabsPanel], sizing_mode="stretch_both")
        statusPanel1 = layout([[self._lastStatusMsgTextInput]], sizing_mode='scale_width')
        statusPanel2 = layout([[self._statusAreaInput]], sizing_mode='scale_width')
        mainPanel = column(children=[pageWidthPanel, statusPanel1, statusPanel2], sizing_mode="stretch_both")
        
        self._doc.add_root( mainPanel )

        self._doc.theme = theme
        self._doc.add_periodic_callback(self._updateCallBack, 100)
        
        self._loadConfig()
        
    def _updateCallBack(self):
        # Call the update method so that to ensure it's safe to update the document.
        # This ensures an exception won't be thrown.
        self._doc.add_next_tick_callback(self._update)

    def _update(self, maxDwellMS=1000):
        """@brief Called periodically to update the Web GUI."""
        while not self._commsQueue.empty():
            rxMessage = self._commsQueue.get()
            if isinstance(rxMessage, dict):
                self._processRXDict(rxMessage)
        
    def _saveConfig(self):
        """@brief Save some parameters to a local config file."""
        self._cfgMgr.addAttr(CT6ConfiguratorGUI.WIFI_SSID, self._wifiSSIDInput.value)
        self._cfgMgr.addAttr(CT6ConfiguratorGUI.WIFI_PASSWORD, self._wifiPasswordInput.value)
        self._cfgMgr.addAttr(CT6ConfiguratorGUI.DEVICE_ADDRESS, self._ct6IPAddressInput.value)
        self._cfgMgr.store()
        
    def _loadConfig(self):
        """@brief Load the config from a config file."""
        try:
            self._cfgMgr.load()
        except:
            pass
        self._wifiSSIDInput.value = self._cfgMgr.getAttr(CT6ConfiguratorGUI.WIFI_SSID)
        self._wifiPasswordInput.value = self._cfgMgr.getAttr(CT6ConfiguratorGUI.WIFI_PASSWORD)
        self._ct6IPAddressInput.value = self._cfgMgr.getAttr(CT6ConfiguratorGUI.DEVICE_ADDRESS)
        
    def __info(self, msg):
        """@brief Update an info level message. This must be called from the GUI thread.
           @param msg The message to display."""
        self._statusAreaInput.value = self._statusAreaInput.value + "\n" + CT6ConfiguratorGUI.INFO_MESSAGE + " " + str(msg)
        self._lastStatusMsgTextInput.value = CT6ConfiguratorGUI.INFO_MESSAGE + " " + str(msg)

    def __warn(self, msg):
        """@brief Update an warning level message. This must be called from the GUI thread.
           @param msg The message to display."""
        self._statusAreaInput.value = self._statusAreaInput.value + "\n" + CT6ConfiguratorGUI.WARN_MESSAGE + " " + str(msg)
        self._lastStatusMsgTextInput.value = CT6ConfiguratorGUI.INFO_MESSAGE + " " + str(msg)

    def __error(self, msg):
        """@brief Update an error level message. This must be called from the GUI thread.
           @param msg The message to display."""
        self._statusAreaInput.value = self._statusAreaInput.value + "\n" + CT6ConfiguratorGUI.ERROR_MESSAGE + " " + str(msg)
        self._lastStatusMsgTextInput.value = CT6ConfiguratorGUI.INFO_MESSAGE + " " + str(msg)

    def __debug(self, msg):
        """@brief Update an debug level message. This must be called from the GUI thread.
           @param msg The message to display."""
        self._statusAreaInput.value = self._statusAreaInput.value + "\n" + CT6ConfiguratorGUI.DEBUG_MESSAGE + " " + str(msg)
        self._lastStatusMsgTextInput.value = CT6ConfiguratorGUI.INFO_MESSAGE + " " + str(msg)

    def _processRXDict(self, rxDict):
        """@brief Process the dicts received from the GUI message queue.
           @param rxDict The dict received from the GUI message queue."""
        if CT6ConfiguratorGUI.INFO_MESSAGE in rxDict:
            msg = rxDict[CT6ConfiguratorGUI.INFO_MESSAGE]
            self.__info(msg)

        elif CT6ConfiguratorGUI.WARN_MESSAGE in rxDict:
            msg = rxDict[CT6ConfiguratorGUI.WARN_MESSAGE]
            self.__warn(msg)

        elif CT6ConfiguratorGUI.ERROR_MESSAGE in rxDict:
            msg = rxDict[CT6ConfiguratorGUI.ERROR_MESSAGE]
            self.__error(msg)

        elif CT6ConfiguratorGUI.DEBUG_MESSAGE in rxDict:
            msg = rxDict[CT6ConfiguratorGUI.DEBUG_MESSAGE]
            self.__debug(msg)
            
        elif CT6ConfiguratorGUI.ENABLE_BUTTONS in rxDict:
            state = rxDict[CT6ConfiguratorGUI.ENABLE_BUTTONS]
            self._enableAllButtons(state)

        elif CT6ConfiguratorGUI.SET_CT6_IP_ADDRESS in rxDict:
            address = rxDict[CT6ConfiguratorGUI.SET_CT6_IP_ADDRESS]
            # Set the IP address field to the CT6 address
            self._ct6IPAddressInput.value = address
            self._saveConfig()
                
        elif CT6ConfiguratorGUI.UPDATE_PORT_NAMES in rxDict:
        
            if CT6ConfiguratorGUI.CT1_NAME in rxDict:
                self._ct1PortNameInput.value = str(rxDict[CT6ConfiguratorGUI.CT1_NAME])
                
            if CT6ConfiguratorGUI.CT2_NAME in rxDict:
                self._ct2PortNameInput.value = str(rxDict[CT6ConfiguratorGUI.CT2_NAME])
                
            if CT6ConfiguratorGUI.CT3_NAME in rxDict:
                self._ct3PortNameInput.value = str(rxDict[CT6ConfiguratorGUI.CT3_NAME])
                
            if CT6ConfiguratorGUI.CT4_NAME in rxDict:
                self._ct4PortNameInput.value = str(rxDict[CT6ConfiguratorGUI.CT4_NAME])
                
            if CT6ConfiguratorGUI.CT5_NAME in rxDict:
                self._ct5PortNameInput.value = str(rxDict[CT6ConfiguratorGUI.CT5_NAME])
                
            if CT6ConfiguratorGUI.CT6_NAME in rxDict:
                self._ct6PortNameInput.value = str(rxDict[CT6ConfiguratorGUI.CT6_NAME])
                
            self._enableAllButtons(True)
            self.__info("Read CT6 port names from the device.")
            
        elif CT6ConfiguratorGUI.PORT_NAMES_UPDATED in rxDict:
            self._enableAllButtons(True)
            self.__info("Set CT6 port names.")
            
        elif CT6ConfiguratorGUI.DEV_NAME in rxDict:
            self._ct6DeviceNameInput.value = rxDict[CT6ConfiguratorGUI.DEV_NAME]
            self._enableAllButtons(True)
                            
        elif CT6ConfiguratorGUI.ACTIVE in rxDict:
            active = rxDict[CT6ConfiguratorGUI.ACTIVE]
            if active:
                self._enabledStateSelect.value="enabled"
            else:
                self._enabledStateSelect.value="disabled"
                
        elif CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS in rxDict and \
             CT6ConfiguratorGUI.MQTT_SERVER_PORT in rxDict and \
             CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS in rxDict and \
             CT6ConfiguratorGUI.MQTT_TOPIC in rxDict and \
             CT6ConfiguratorGUI.MQTT_USERNAME in rxDict and \
             CT6ConfiguratorGUI.MQTT_PASSWORD in rxDict:   
            mqttServerAddress = rxDict[CT6ConfiguratorGUI.MQTT_SERVER_ADDRESS]
            mqttServerPort = rxDict[CT6ConfiguratorGUI.MQTT_SERVER_PORT]
            mqttTXPeriodMS = rxDict[CT6ConfiguratorGUI.MQTT_TX_PERIOD_MS]
            topic = rxDict[CT6ConfiguratorGUI.MQTT_TOPIC]
            username = rxDict[CT6ConfiguratorGUI.MQTT_USERNAME]
            password = rxDict[CT6ConfiguratorGUI.MQTT_PASSWORD]

            # Remove any whitespace leading or trailing characters
            mqttServerAddress = mqttServerAddress.strip()
            topic = topic.strip()
            username = username.strip()
            password = password.strip()

            self._mqttServerAddressInput.value = mqttServerAddress
            self._mqttServerPortInput.value = mqttServerPort
            self._mqttTopicInput.value = topic
            self._mqttUsernameInput.value = username
            self._mqttPasswordInput.value = password
            self._mqttServerTXPeriodMSInput.value = mqttTXPeriodMS

    def _sendEnableAllButtons(self, state):
        """@brief Send a message to the GUI to enable/disable all the command buttons.
           @param msg The message to be displayed."""
        msgDict = {CT6ConfiguratorGUI.ENABLE_BUTTONS: state}
        self.updateGUI(msgDict)
            
    # Start ------------------------------
    # Methods that allow the GUI to display standard UIO messages
    #
    def info(self, msg):
        """@brief Send a info message to be displayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {CT6ConfiguratorGUI.INFO_MESSAGE: msg}
        self.updateGUI(msgDict)

    def warn(self, msg):
        """@brief Send a warning message to be displayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {CT6ConfiguratorGUI.WARN_MESSAGE: msg}
        self.updateGUI(msgDict)
        
    def error(self, msg):
        """@brief Send a error message to be displayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {CT6ConfiguratorGUI.ERROR_MESSAGE: msg}
        self.updateGUI(msgDict)
        
    def debug(self, msg):
        """@brief Send a debug message to be displayed in the GUI.
           @param msg The message to be displayed."""
        if self._uio.isDebugEnabled():
            msgDict = {CT6ConfiguratorGUI.DEBUG_MESSAGE: msg}
            self.updateGUI(msgDict)

    def getInput(self, prompt):
        raise Exception("Set the WiFi SSId and password in the WiFi tab and try again.")
            
    def reportException(self, exception):
        """@brief Report an exception."""
        if self._uio.isDebugEnabled():
            self.error(traceback.format_exc())
            
        else:
            self.error( exception.args[0] )
            
    # End ------------------------------   
        
class CT6ConfiguratorServer(object):
    """@brief Responsible for starting the CT6 configurator GUI."""

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A GUIConfigBase instance."""
        self._uio                   = uio
        self._options               = options
        self._config                = config
        self._dbHandler             = None

    def close(self):
        """@brief Close down the app server."""
        pass

    def start(self):
        """@Start the App server running."""
        try:
            gui = CT6ConfiguratorGUI(self._uio, self._options, self._config)
            gui.runBlockingBokehServer(gui.getAppMethodDict(), openBrowser=True)

        finally:
            self.close()
            
def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="This application provides an GUI that can be used to configure CT6 units.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",  action='store_true', help="Enable debugging.")
        parser.add_argument("-f", "--config_file",  help="The configuration file for the CT6 Dash Server"\
                                    " (default={}).".format(CT6ConfiguratorConfig.GetConfigFile(CT6ConfiguratorConfig.DEFAULT_CONFIG_FILENAME)),
                                    default=CT6ConfiguratorConfig.GetConfigFile(CT6ConfiguratorConfig.DEFAULT_CONFIG_FILENAME))
        parser.add_argument("-s", "--enable_syslog",action='store_true', help="Enable syslog debug data.")
        parser.add_argument("-s", "--skip_factory_config_restore",action='store_true', help="Skip factory config restore. Use with care.")

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_dash")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        ct6ConfiguratorConfig = CT6ConfiguratorConfig(uio, options.config_file, CT6ConfiguratorConfig.DEFAULT_CONFIG)
        
        ct6Configurator = CT6ConfiguratorServer(uio, options, ct6ConfiguratorConfig)
        ct6Configurator.start()

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
