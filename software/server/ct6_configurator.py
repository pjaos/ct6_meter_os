#!/usr/bin/env python3

import sys
import argparse
import threading
import requests
import traceback
import tempfile
import os
import shutil
import json

from lib.ngt import TabbedNiceGui, YesNoDialog

from p3lib.uio import UIO
from p3lib.helper import logTraceBack
from p3lib.pconfig import ConfigManager

from lib.config import ConfigBase

from ct6_tool import YDevManager, getCT6ToolCmdOpts, CT6Config, MCULoader, CT6Base, CT6Scanner
from ct6_mfg_tool import FactorySetup, getFactorySetupCmdOpts

from nicegui import ui

class CT6ConfiguratorConfig(ConfigBase):
    DEFAULT_CONFIG_FILENAME = "ng_ct6_configurator.cfg"
    DEFAULT_CONFIG = {
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS:    "",
        ConfigBase.LOCAL_GUI_SERVER_PORT:       10000
    }

class CT6GUIServer(TabbedNiceGui):
    """@brief Responsible for starting the CT6 configurator GUI."""
    PAGE_TITLE                  = "CT6 Configurator"

    SET_CT6_IP_ADDRESS          = "SET_CT6_IP_ADDRESS"
    
    CMD_COMPLETE                = "CMD_COMPLETE"
     
    CFG_FILENAME                = ".CT6GUIServer.cfg"
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
    
    LOGFILE_PREFIX              = "ct6_configurator"
   
    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A CT6ConfiguratorConfig instance."""
        super().__init__(uio.isDebugEnabled(), FactorySetup.LOG_PATH)
        self._uio                       = uio
        self._options                   = options
        self._config                    = config
        
        self._wifiSSIDInput             = None
        self._wifiPasswordInput         = None
        self._setWiFiButton             = None
        self._log                       = None
        self._ct6IPAddressInput1        = None
        self._ct6IPAddressInput2        = None
        self._ct6DeviceList             = []
        self._dialogPrompt              = None
        self._dialogYesMethod           = None

        self._skipFactoryConfigRestore  = False
        if '--skip_factory_config_restore' in sys.argv:
            self._skipFactoryConfigRestore = True
            # We remove this arg as ct6_tool and ct6_mfg_tool do not know about this arg
            # and we may re run the cmd line args for each of these later.
            sys.argv.remove('--skip_factory_config_restore')

        self._cfgMgr                    = ConfigManager(self._uio, CT6GUIServer.CFG_FILENAME, CT6GUIServer.DEFAULT_CONFIG)
        
        self._logFile                   = os.path.join(self._logPath, CT6GUIServer.GetLogFileName(CT6GUIServer.LOGFILE_PREFIX))

    def _setCT6IPAddress(self, address):
        """@brief Set the CT6 IP address.
                  This can be called from outside the GUI thread.
           @param msg The message to be displayed."""
        if address:
            msgDict = {CT6GUIServer.SET_CT6_IP_ADDRESS: address}
        else:
            msgDict = {CT6GUIServer.ERROR_MESSAGE: "CT6 device failed to connect to WiFi network."}
        self.updateGUI(msgDict)

    def _saveConfig(self):
        """@brief Save some parameters to a local config file."""
        self._cfgMgr.addAttr(CT6GUIServer.WIFI_SSID, self._wifiSSIDInput.value)
        self._cfgMgr.addAttr(CT6GUIServer.WIFI_PASSWORD, self._wifiPasswordInput.value)
        self._cfgMgr.addAttr(CT6GUIServer.DEVICE_ADDRESS, self._ct6IPAddressInput1.value)
        self._cfgMgr.store()

    def _loadConfig(self):
        """@brief Load the config from a config file."""
        try:
            self._cfgMgr.load()
        except:
            pass
        self._wifiSSIDInput.value = self._cfgMgr.getAttr(CT6GUIServer.WIFI_SSID)
        self._wifiPasswordInput.value = self._cfgMgr.getAttr(CT6GUIServer.WIFI_PASSWORD)
        self._ct6IPAddressInput1.value = self._cfgMgr.getAttr(CT6GUIServer.DEVICE_ADDRESS)
        self._copyCT6Address()

    def _copyCT6Address(self):
        """@brief Copy same address to CT6 address on all tabs."""
        if self._ct6IPAddressInput1:
            if self._ct6IPAddressInput2:
                self._ct6IPAddressInput2.value = self._ct6IPAddressInput1.value
            if self._ct6IPAddressInput3:
                self._ct6IPAddressInput3.value = self._ct6IPAddressInput1.value
            if self._ct6IPAddressInput4:
                self._ct6IPAddressInput4.value = self._ct6IPAddressInput1.value
            if self._ct6IPAddressInput5:
                self._ct6IPAddressInput5.value = self._ct6IPAddressInput1.value
            if self._ct6IPAddressInput6:
                self._ct6IPAddressInput6.value = self._ct6IPAddressInput1.value

    def _handleGUIUpdate(self, rxDict):
        """@brief Process the dicts received from the GUI message queue that were not 
                  handled by the parent class instance.
           @param rxDict The dict received from the GUI message queue."""

        if CT6GUIServer.SET_CT6_IP_ADDRESS in rxDict:
            address = rxDict[CT6GUIServer.SET_CT6_IP_ADDRESS]
            # Set the IP address field to the CT6 address
            self._ct6IPAddressInput1.value = address
            self._copyCT6Address()
            self._saveConfig()
                
        elif CT6GUIServer.UPDATE_PORT_NAMES in rxDict:
        
            if CT6GUIServer.CT1_NAME in rxDict:
                self._ct1PortNameInput.value = str(rxDict[CT6GUIServer.CT1_NAME])
                
            if CT6GUIServer.CT2_NAME in rxDict:
                self._ct2PortNameInput.value = str(rxDict[CT6GUIServer.CT2_NAME])
                
            if CT6GUIServer.CT3_NAME in rxDict:
                self._ct3PortNameInput.value = str(rxDict[CT6GUIServer.CT3_NAME])
                
            if CT6GUIServer.CT4_NAME in rxDict:
                self._ct4PortNameInput.value = str(rxDict[CT6GUIServer.CT4_NAME])
                
            if CT6GUIServer.CT5_NAME in rxDict:
                self._ct5PortNameInput.value = str(rxDict[CT6GUIServer.CT5_NAME])
                
            if CT6GUIServer.CT6_NAME in rxDict:
                self._ct6PortNameInput.value = str(rxDict[CT6GUIServer.CT6_NAME])
                
            self._enableAllButtons(True)
            self._infoGT("Read CT6 port names from the device.")
            
        elif CT6GUIServer.PORT_NAMES_UPDATED in rxDict:
            self._enableAllButtons(True)
            self._infoGT("Set CT6 port names.")
            
        elif CT6GUIServer.DEV_NAME in rxDict:
            self._ct6DeviceNameInput.value = rxDict[CT6GUIServer.DEV_NAME]
            self._enableAllButtons(True)
                            
        elif CT6GUIServer.ACTIVE in rxDict:
            active = rxDict[CT6GUIServer.ACTIVE]
            print(f"PJA: active={active}")
            if active:
                self.activeSwitch.value = True
            else:
                self.activeSwitch.value = False
                
        elif CT6GUIServer.MQTT_SERVER_ADDRESS in rxDict and \
             CT6GUIServer.MQTT_SERVER_PORT in rxDict and \
             CT6GUIServer.MQTT_TX_PERIOD_MS in rxDict and \
             CT6GUIServer.MQTT_TOPIC in rxDict and \
             CT6GUIServer.MQTT_USERNAME in rxDict and \
             CT6GUIServer.MQTT_PASSWORD in rxDict:   
            mqttServerAddress = rxDict[CT6GUIServer.MQTT_SERVER_ADDRESS]
            mqttServerPort = rxDict[CT6GUIServer.MQTT_SERVER_PORT]
            mqttTXPeriodMS = rxDict[CT6GUIServer.MQTT_TX_PERIOD_MS]
            topic = rxDict[CT6GUIServer.MQTT_TOPIC]
            username = rxDict[CT6GUIServer.MQTT_USERNAME]
            password = rxDict[CT6GUIServer.MQTT_PASSWORD]

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

        elif CT6Base.IP_ADDRESS in rxDict and \
             CT6Base.UNIT_NAME in rxDict:
            selectText = rxDict[CT6Base.IP_ADDRESS] + '/' + rxDict[CT6Base.UNIT_NAME]
            if selectText not in self._ct6DeviceList:
                self._ct6DeviceList.append(selectText)
            self._ct6Select.set_options(self._ct6DeviceList)
            if len(self._ct6DeviceList) == 1:
                self._ct6Select.set_value(self._ct6DeviceList[0])

    def _initWiFiTab(self):
        """@brief Create the Wifi tab contents."""
        markDownText = """
        <span style="font-size:1.5em;">Set the WiFi SSID and password of your CT6 device. A USB cable must be connected to the CT6 device to setup the WiFi.
        """
        ui.markdown(markDownText)
        with ui.column():
            
            self._wifiSSIDInput = ui.input(label='WiFi SSID')
            self._wifiPasswordInput = ui.input(label='WiFi Password', password=True)
            self._setWiFiButton = ui.button('Setup WiFi', on_click=self._setWiFiNetworkButtonHandler)

            # Add to button list so that button is disabled while activity is in progress.
            self._appendButtonList(self._setWiFiButton)

    def _setWiFiNetworkButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(19,84)
        self._saveConfig()
        threading.Thread( target=self._setWiFiNetwork, args=(self._wifiSSIDInput.value, self._wifiPasswordInput.value)).start()

    def _setWiFiNetwork(self, wifiSSID, wifiPassword):
        """@brief Set the Wifi network on a CT6 device..
           @param wifiSSID The WiFi SSID to set.
           @param wifiPassword The WiFi password to set."""
        try:
            try:
                if len(wifiSSID) == 0:
                    self.error("A WiFi SSID is required.")
                
                elif len(wifiPassword) == 0:
                    self.error("A WiFi password is required.")
                    
                else:
                    self._setupWiFi(wifiSSID, wifiPassword)
                    
            except Exception as ex:
                self.error(str(ex))
                
        finally:
            self._sendEnableAllButtons(True)

                
    def _setupWiFi(self, wifiSSID, wifiPassword):
        """@brief Setup the CT6 WiFi interface. This must be called outside the GUI thread.
           @param wifiSSID The WiFi SSID to set.
           @param wifiPassword The WiFi password to set."""
        self.info("Setting the CT6 device WiFi network.")
        options = getCT6ToolCmdOpts()
        devManager = YDevManager(self, options, ssid=wifiSSID, password=wifiPassword)
        devManager.configureWiFi()
        ipAddress = devManager._runApp()
        self.info(f"The CT6 device is now connected to {wifiSSID} (IP address = {ipAddress})")
        # Send a message to set the CT6 device IP address in the GUI
        self._setCT6IPAddress(ipAddress)

    def _initUpgradeTab(self):
        """@brief Create the Wifi tab contents."""
        markDownText = f"{CT6GUIServer.DESCRIP_STYLE}Upgrade CT6 firmware over your WiFi network."
        ui.markdown(markDownText)
        self._ct6IPAddressInput1 = ui.input(label='CT6 Address')
        self._upgradeButton = ui.button('Upgrade', on_click=self._upgradeButtonButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._upgradeButton)

    def _upgradeButtonButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(107,120)
        threading.Thread( target=self._doUpgrade, args=(self._ct6IPAddressInput1.value,)).start()

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

    def _initDevNameTab(self):
        """@brief Create the set device name tab contents."""
        markDownText = f"{CT6GUIServer.DESCRIP_STYLE}Set the name for your CT6 device."
        ui.markdown(markDownText)
        self._ct6IPAddressInput2 = ui.input(label='CT6 Address')
        self._ct6DeviceNameInput = ui.input(label='Device Name')
        with ui.row():
            self._setDevNameButton = ui.button('Set', on_click=self._setDevNameButtonHandler)
            self._getDevNameButton = ui.button('Get', on_click=self._getDevNameButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._setDevNameButton)
        self._appendButtonList(self._getDevNameButton)

    def _setDevNameButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(2,3)
        self._saveConfig()
        threading.Thread( target=self._setDevName, args=(self._ct6IPAddressInput2.value,self._ct6DeviceNameInput.value)).start()
  
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
    
    def _checkResponse(self, response):
        """@brief Check we don't have an error response."""
        rDict = response.json()
        if "ERROR" in rDict:
            msg = rDict["ERROR"]
            self.error(msg)

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
    
    def _removeWhiteSpace(self, aString, replacementChar='_'):
        """@brief Get a string that has whitespace characters replaced.
           @param aString The source string to replace whitespace characters in.
           @param replacementChar The character to replace whitespace characters with.
           @return A string with the whitespace characters replaced."""
        #Ensure the string has no tab characters
        if aString.find("\t") >= 0:
           aString=aString.replace('\t', '_')
        #Ensure the string has no space characters
        if aString.find(" ") >= 0:
            aString=aString.replace(' ', '_')
        return aString
        
    def _setDevName(self, ct6IPAddress, devName):
        """@brief Set the CT6 device name.
           @param ct6IPAddress The address of the CT6 device.
           @param devName The name of the device."""
        try:
            try:
                devName = self._removeWhiteSpace(devName)
                self.info(f"Setting CT6 device ({ct6IPAddress}) name.")
                cfgDict = {}
                cfgDict[CT6GUIServer.DEV_NAME] = devName
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
        self._initTask(3,4)
        self._saveConfig()
        threading.Thread( target=self._getDevName, args=(self._ct6IPAddressInput2.value,)).start()
    
    def _getDevName(self, ct6IPAddress):
        """@brief Get the CT6 device name.
           @param ct6IPAddress The address of the CT6 device."""
        try:
            try:
                self.info(f"Getting CT6 device ({ct6IPAddress}) name.")
                cfgDict = self._getConfigDict(ct6IPAddress)
                if CT6GUIServer.DEV_NAME in cfgDict:
                    devName = cfgDict[CT6GUIServer.DEV_NAME]
                    self.info("Read CT6 device name.")
                    msgDict = {CT6GUIServer.DEV_NAME: devName}
                    self.updateGUI(msgDict)
                
                else:
                    self.error("Failed to read the CT6 device name.")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)

    def _initPortNamesTab(self):
        """@brief Create the set port names tab contents."""
        markDownText = f"{CT6GUIServer.DESCRIP_STYLE}Set the name of each port on your CT6 device."
        ui.markdown(markDownText)
        self._ct6IPAddressInput3 = ui.input(label='CT6 Address')
        with ui.row():
            self._ct1PortNameInput = ui.input(label='CT1 port name')
            self._ct2PortNameInput = ui.input(label='CT2 port name')
            self._ct3PortNameInput = ui.input(label='CT3 port name')
        with ui.row():
            self._ct4PortNameInput = ui.input(label='CT4 port name')
            self._ct5PortNameInput = ui.input(label='CT5 port name')
            self._ct6PortNameInput = ui.input(label='CT6 port name')

        with ui.row():
            self._setPortNamesButton = ui.button('Set', on_click=self._setPortNamesButtonHandler)
            self._getPortNamesButton = ui.button('Get', on_click=self._getPortNamesButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._setPortNamesButton)
        self._appendButtonList(self._getPortNamesButton)

    def _setPortNamesButtonHandler(self, event):
            """@brief Process button click.
            @param event The button event."""
            self._enableAllButtons(False)
            self._clearMessages()
            threading.Thread( target=self._setPortNames, args=(self._ct6IPAddressInput3.value, (self._ct1PortNameInput.value,
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
                cfgDict[CT6GUIServer.CT1_NAME] = self._removeWhiteSpace(portNames[0])
                cfgDict[CT6GUIServer.CT2_NAME] = self._removeWhiteSpace(portNames[1])
                cfgDict[CT6GUIServer.CT3_NAME] = self._removeWhiteSpace(portNames[2])
                cfgDict[CT6GUIServer.CT4_NAME] = self._removeWhiteSpace(portNames[3])
                cfgDict[CT6GUIServer.CT5_NAME] = self._removeWhiteSpace(portNames[4])
                cfgDict[CT6GUIServer.CT6_NAME] = self._removeWhiteSpace(portNames[5])
                response = self._saveConfigDict(ct6IPAddress, cfgDict)
                if response is not None:
                    msgDict = {CT6GUIServer.PORT_NAMES_UPDATED: True}
                    self.updateGUI(msgDict)
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)

    def _getPortNamesButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._enableAllButtons(False)
        self._clearMessages()
        threading.Thread( target=self._getPortNames, args=(self._ct6IPAddressInput3.value,)).start()
    
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
        if CT6GUIServer.CT1_NAME in cfgDict:
            ct1PortName = cfgDict[CT6GUIServer.CT1_NAME]
        
        if CT6GUIServer.CT2_NAME in cfgDict:
            ct2PortName = cfgDict[CT6GUIServer.CT2_NAME]
        
        if CT6GUIServer.CT3_NAME in cfgDict:
            ct3PortName = cfgDict[CT6GUIServer.CT3_NAME]
        
        if CT6GUIServer.CT4_NAME in cfgDict:
            ct4PortName = cfgDict[CT6GUIServer.CT4_NAME]
        
        if CT6GUIServer.CT5_NAME in cfgDict:
            ct5PortName = cfgDict[CT6GUIServer.CT5_NAME]
        
        if CT6GUIServer.CT6_NAME in cfgDict:
            ct6PortName = cfgDict[CT6GUIServer.CT6_NAME]
        
        msgDict = {CT6GUIServer.UPDATE_PORT_NAMES: True,
                   CT6GUIServer.CT1_NAME: ct1PortName,
                   CT6GUIServer.CT2_NAME: ct2PortName,
                   CT6GUIServer.CT3_NAME: ct3PortName,
                   CT6GUIServer.CT4_NAME: ct4PortName,
                   CT6GUIServer.CT5_NAME: ct5PortName,
                   CT6GUIServer.CT6_NAME: ct6PortName}
        self.updateGUI(msgDict)


    def _initMQTTServerTab(self):
        """@brief Create the MQTT Server tab contents."""
        markDownText = """For use with third party tools such as [ioBroker](https://www.iobroker.net/) you may wish the CT6 device to periodically send data to an MQTT server. 
                                     
This is not required for normal operation of the CT6 device. Therefore if you do not wish to send data to an MQTT server skip the settings on this tab.

To send JSON data to an MQTT server the 'MQTT Server Address' and 'MQTT Topic' fields must be set. You may need to enter the 'MQTT Username' and 'MQTT password' fields if your MQTT server requires credentials.

The CT6 device will not attempt to send JSON data to an MQTT server unless enabled in the 'Activate Device' tab."""
        ui.markdown(markDownText)
        self._ct6IPAddressInput4 = ui.input(label='CT6 Address')
        with ui.row():
            self._mqttServerAddressInput = ui.input(label='MQTT Server Address').style('width: 200px;')
            self._mqttServerPortInput = ui.number(label='MQTT Server Port', value=CT6GUIServer.DEFAULT_MQTT_SERVER_PORT, format='%d', min=1, max=65535).style('width: 200px;')
            self._mqttTopicInput = ui.input(label='MQTT Topic').style('width: 200px;')
        with ui.row():
            self._mqttUsernameInput = ui.input(label="MQTT Username").style('width: 200px;')  
            self._mqttPasswordInput = ui.input(label="MQTT Password").style('width: 200px;') 
            self._mqttServerTXPeriodMSInput = ui.number(label="TX Period (Milli Seconds)", value=CT6GUIServer.DEFAULT_MQTT_TX_PERIOD_MS, min= 200, max=600000).style('width: 200px;')

        with ui.row():
            self._setMQTTServerButton = ui.button('Set', on_click=self._setMQTTServerButtonHandler)
            self._getMQTTServerButton = ui.button('Get', on_click=self._getMQTTServerButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._setMQTTServerButton)
        self._appendButtonList(self._getMQTTServerButton)

    def _setMQTTServerButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(3,5)
        threading.Thread( target=self._setMQTTServer, args=(self._ct6IPAddressInput4.value, 
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
                if CT6GUIServer.MQTT_SERVER_ADDRESS in cfgDict and \
                   CT6GUIServer.MQTT_SERVER_PORT in cfgDict and \
                   CT6GUIServer.MQTT_TX_PERIOD_MS in cfgDict and \
                   CT6GUIServer.MQTT_TOPIC in cfgDict and \
                   CT6GUIServer.MQTT_USERNAME in cfgDict and \
                   CT6GUIServer.MQTT_PASSWORD in cfgDict:
                    
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

                    mqttCfgDict = {CT6GUIServer.MQTT_SERVER_ADDRESS: address,
                                   CT6GUIServer.MQTT_SERVER_PORT: port,
                                   CT6GUIServer.MQTT_TX_PERIOD_MS: txPeriodMS,
                                   CT6GUIServer.MQTT_TOPIC: topic,
                                   CT6GUIServer.MQTT_USERNAME: username,
                                   CT6GUIServer.MQTT_PASSWORD: password}
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
        self._initTask(2,3)
        threading.Thread( target=self._getMQTTServer, args=(self._ct6IPAddressInput4.value,)).start()
        
    def _getMQTTServer(self, ct6IPAddress):
        """@brief Perform an upgrade of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device."""
        try:
            try:
                self.info(f"Get CT6 device ({ct6IPAddress}) MQTT server configuration.")
                cfgDict = self._getConfigDict(ct6IPAddress)
                if CT6GUIServer.MQTT_SERVER_ADDRESS in cfgDict and \
                   CT6GUIServer.MQTT_SERVER_PORT in cfgDict and \
                   CT6GUIServer.MQTT_TX_PERIOD_MS in cfgDict and \
                   CT6GUIServer.MQTT_TOPIC in cfgDict and \
                   CT6GUIServer.MQTT_USERNAME in cfgDict and \
                   CT6GUIServer.MQTT_PASSWORD in cfgDict:
                    
                    mqttServerAddress = cfgDict[CT6GUIServer.MQTT_SERVER_ADDRESS]
                    mqttServerPort = cfgDict[CT6GUIServer.MQTT_SERVER_PORT]
                    mqttTopic = cfgDict[CT6GUIServer.MQTT_TOPIC]
                    mqttUsername = cfgDict[CT6GUIServer.MQTT_USERNAME]
                    mqttPassword = cfgDict[CT6GUIServer.MQTT_PASSWORD]
                    mqttTXPeriodMS = cfgDict[CT6GUIServer.MQTT_TX_PERIOD_MS]
                    msgDict = {CT6GUIServer.MQTT_SERVER_ADDRESS: mqttServerAddress,
                               CT6GUIServer.MQTT_SERVER_PORT: mqttServerPort,
                               CT6GUIServer.MQTT_TOPIC: mqttTopic,
                               CT6GUIServer.MQTT_USERNAME: mqttUsername,
                               CT6GUIServer.MQTT_PASSWORD: mqttPassword,
                               CT6GUIServer.MQTT_TX_PERIOD_MS: mqttTXPeriodMS}
                    self.updateGUI(msgDict)
                        
                else:
                    self.error("Upgrade the CT6 device to support MQTT server connectivity.")
                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)

    def _initActivateDeviceTab(self):
        """@brief Create the Activate device tab contents."""
        markDownText = f"""{CT6GUIServer.DESCRIP_STYLE}Activate or deactivate your CT6 device. Your CT6 device will only send data to a database or an MQTT server when it has been set to the active state."""
        ui.markdown(markDownText)
        self._ct6IPAddressInput5 = ui.input(label='CT6 Address')
        self.activeSwitch = ui.switch('Active')
        with ui.row():
            self._setEnabledStateButton = ui.button('Set', on_click=self._setEnabledStateButtonHandler)
            self._getEnabledStateButton = ui.button('Get', on_click=self._getEnabledStateButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._setEnabledStateButton)
        self._appendButtonList(self._getEnabledStateButton)

    def _setEnabledStateButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(2,3)
        threading.Thread( target=self._enableCT6, args=(self._ct6IPAddressInput5.value, self.activeSwitch.value )).start()
        
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
                cfgDict[CT6GUIServer.ACTIVE] = active
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
        self._initTask(2,3)
        threading.Thread( target=self._getEnabled, args=(self._ct6IPAddressInput5.value,)).start()
        
    def _getEnabled(self, ct6IPAddress):
        """@brief Get the enabled state of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device."""
        self.info(f"Get CT6 ({ct6IPAddress}) enabled state.")
        try:
            try:
                self.info(f"Getting CT6 device ({ct6IPAddress}) active state.")
                cfgDict = self._getConfigDict(ct6IPAddress)
                if CT6GUIServer.ACTIVE in cfgDict:
                    state = cfgDict[CT6GUIServer.ACTIVE]
                    msgDict = {CT6GUIServer.ACTIVE: state}
                    self.updateGUI(msgDict)
                        
                else:
                    self.error("Failed to read the active state of the CT6 device.")

                
            except Exception as ex:
                self.reportException(ex)
                
        finally:
            self._sendEnableAllButtons(True)

    def _initInstallTab(self):
        """@brief Create the install tab contents."""
        markDownText = """Read the factory configuration from the CT6 device, before wiping the CT6 flash. The CT6 device MicroPython<br> \
                                     and firmware will then be reloaded before reloading the CT6 device factory configuration.<br> \
                                     This option allows you to recover a CT6 unit that will not boot.<br><br> \
                                     A USB cable must be connected to the CT6 device to install CT6 software."""
        ui.markdown(markDownText)
        self._installSWButton = ui.button('Install CT6 SW', on_click=self._installSWButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._installSWButton)
        
    def _installSWButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(101,160)
        self._saveConfig()
        threading.Thread( target=self._installSW, args=(self._wifiSSIDInput.value, self._wifiPasswordInput.value)).start()

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

    def _installSW(self, wifiSSID, wifiPassword):
        """@brief Called to do the work of wiping flash and installing the system software onto
                  CT6 hardware.
           @param wifiSSID The WiFi SSID to set.
           @param wifiPassword The WiFi password to set."""
        try:
            try:
                factoryConfigFile = None
                options = getCT6ToolCmdOpts()
                devManager = YDevManager(self, options, ssid=wifiSSID, password=wifiPassword)
                try:
                    # Before erasing and loadin SW we check we have a copy of the factory config file
                    # from the CT6 device.
                    factoryConfigFile = self._getCT6FactoryConfig(devManager)
                except:
                    # If we couldn't read the factory config then we may not be able to restore it 
                    # at the endof the install process.Therefore this cmd line option should be used with care.
                    if self._skipFactoryConfigRestore:
                        self.warn("!!! Failed to read the factory config from the CT6 device !!!")
                    else:
                        # Stop the install process to ensure we are not left in a situation where the
                        # factory calibration config is lost.
                        raise

                factorySetupOptions = getFactorySetupCmdOpts()
                factorySetup = FactorySetup(self, factorySetupOptions)

                factorySetup._erasePicoWFlash()
                # We don't need to prompt the user as the above method displayed the message.
                factorySetup._loadMicroPython(showPrompt=False)

                mcuLoader = MCULoader(self, factorySetupOptions)
                mcuLoader.load()
                self.info("Running the CT6 firmware")

                self._restoreFactoryConfig(devManager, factoryConfigFile)

                devManager.restart()

                self.info("CT6 software restore complete.")
                self.info("The blue and green LED's should now be flashing on the CT6 device.")
                self.info("Install Success. You may now configure the WiFi on the CT6 device using the WiFi tab.")

            except Exception as ex:
                self.debug(traceback.format_exc())
                self.error(str(ex))
                
        finally:
            self._sendEnableAllButtons(True)   

    def _initScanTab(self):
        """@brief Create the scan tab contents."""
        markDownText = """Scan for active CT6 devices on the LAN."""
        ui.markdown(markDownText)
        self._ct6Select = ui.select(options=[], label="CT6 Device").style('width: 300px;')
        self._scanSecondsInput = ui.number(label='Scan Period (Seconds)', value=3, format='%d', min=1, max=60)
        self._scanSecondsInput.style('width: 300px')
        with ui.row():
            self._scanButton = ui.button('Scan', on_click=self._scanButtonHandler)
            self._rebootButton = ui.button('Power Cycle CT6 Device', on_click=self._rebootButtonHandler)
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._scanButton)
        self._appendButtonList(self._rebootButton)

    def _scanButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._ct6DeviceList = []
        self._initTask(0,0) # PJA update this
        self._saveConfig()
        threading.Thread( target=self._scanForCT6Devices, args=(self._scanSecondsInput.value,)).start()

    def _rebootButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask(2,2) # PJA update this
        self._saveConfig()
        inputOptions = self._ct6Select.options
        inputStr = self._ct6Select.value
        # If not selected, select the first in the list as this appears to the user
        # that it is the one selected.
        if len(inputStr) == 0 and len(inputOptions) > 0:
            inputStr = inputOptions[0]
        ipAddress = None
        ct6Name = None
        if len(inputStr):
            pos = inputStr.find('/')
            ipAddress = inputStr[:pos]
            ct6Name = inputStr[pos+1:]
        if ipAddress:
            threading.Thread( target=self._rebootDevice, args=(ipAddress,ct6Name)).start()
        else:
            self.warn("Select a CT6 device to reboot.")

    def _ct6DevFound(self, rxDict):
        self.debug(json.dumps(rxDict, indent=4))
        if CT6Base.IP_ADDRESS in rxDict and \
           CT6Base.UNIT_NAME in rxDict:
            unitName = rxDict[CT6Base.UNIT_NAME]
            ipAddress = rxDict[CT6Base.IP_ADDRESS]
            self.info("Found CT6 device: IP Address: "+ipAddress+" ("+unitName+")")
            msgDict = {CT6Base.IP_ADDRESS: ipAddress,
                       CT6Base.UNIT_NAME: unitName}
            self.updateGUI(msgDict)

        return True

    def _scanForCT6Devices(self, scanSeconds):
        """@brief Search for CT6 devices on the LAN.
           @param scanSeconds The number os seconds to spend scanning for CT6 devices."""
        try:
            ct6Scanner = CT6Scanner(None, None)
            ct6Scanner.scan(callBack=self._ct6DevFound, runSeconds=scanSeconds)
        finally:
            self._sendEnableAllButtons(True)   

    def _rebootDevice(self, ipAddress, deviceName):
        """@brief Reboot a CT6 device.
           @param ipAddress The IP address of the CT6 device.
           @param deviceName The name of the device to be rebooted."""
        try:
            # If we don't have a dev ice name use the IP address
            if deviceName is None or len(deviceName) == 0:
                deviceName = ipAddress
            options = getCT6ToolCmdOpts()
            devManager = YDevManager(self, options)
            devManager.setIPAddress(ipAddress)
            self.info(f"Checking {ipAddress} is reachable.")
            devManager.doPing(ipAddress)
            self.info(f"Power cycling {deviceName}")
            devManager._powerCycle()
            self.info(f"Waiting for {deviceName} to power off.")
            devManager._waitForWiFiDisconnect()
            self.info(f"Waiting for {deviceName} to power up and reconnect to the WiFi network.")
            devManager._waitForPingSuccess()

        finally:
            self._sendEnableAllButtons(True)

    def _calibrateTab(self):
        """@brief Create the calibrate tab contents."""
        markDownText = f"""{CT6GUIServer.DESCRIP_STYLE}The CT6 device measures the AC supply voltage in order to read accurate power values. \
                                                       This is calibrated during manufacture using the recommended AC power supply.<br>
                                                       The CT6 device should work with any AC power supply that provides 9-16 volts. \
                                                       If you use a different power supply from the one the CT6 device was calibrated with, during manufacture, you must recalibrate the unit to ensure accurate power measurements. \
                                                       This tab allows you to calibrate the CT6 device voltage measurements.<br><br>\
                                                       Measure the AC voltage, enter the measured AC voltage below and select the 'PERFORM VOLTAGE CALIBRATION' button."""
        ui.markdown(markDownText)
        self._ct6IPAddressInput6 = ui.input(label='CT6 Address').style('width: 200px;')
        self._acVoltageInput = ui.number(label="AC Voltage", format='%.2f', value=230.0, min=50, max=400).style('width: 200px;')
        self._acFreq60HzInput = widget = ui.switch("60 Hz AC Supply").style('width: 200px;')
        self._acFreq60HzInput.tooltip("Leave this off if your AC frequency is 50 Hz.")
        self._voltageCalStep1Dialog = YesNoDialog(f"Are you sure you wish to calibrate the voltage on the {self._ct6IPAddressInput6.value} CT6 device ?",
                                                    self._calVoltageStep1)
        self._calibrateVoltageButton = ui.button('Perform Voltage Calibration', on_click=lambda: self._voltageCalStep1Dialog.show() )
        # Add to button list so that button is disabled while activity is in progress.
        self._appendButtonList(self._calibrateVoltageButton)
        
    def _calVoltageStep1(self):
        """@brief Guid the user through the voltage calibration process."""
        self._initTask(0,0) # PJA update this
        self._saveConfig()
        self.info("Start CT6 voltage calibration.")
        threading.Thread( target=self._calVoltage, args=(self._ct6IPAddressInput6.value, self._acVoltageInput.value, self._acFreq60HzInput.value)).start()

    def _calVoltage(self, address, acVoltage, acFreq60Hz):
        """@brief Perform the AC voltage calibration.
           @param address The address of the CT6 device.
           @param acVoltage The measured AC voltage.
           @param acFreq60Hz True if AC main freq is 60 Hz, False if 50 Hz"""
        try:
            factorySetupOptions = getFactorySetupCmdOpts()
            factorySetupOptions.address = address
            factorySetupOptions.ac60hz = acFreq60Hz
            factorySetup = FactorySetup(self, factorySetupOptions)
            factorySetup._calVoltageGain(1, maxError=0.3, acVoltage=acVoltage)
            factorySetup._calVoltageGain(4, maxError=0.3, acVoltage=acVoltage)
            self.info("Voltage calibration completed successfully.")
        finally:
            self._sendEnableAllButtons(True)

    def start(self):
        """@Start the App server running."""
        try:
            tabNameList = ('WiFi', 
                           'Upgrade', 
                           'Device Name', 
                           'Port Names', 
                           'MQTT Server', 
                           'Activate Device', 
                           'Install', 
                           'Scan',
                           'Calibrate Voltage')
            # This must have the same number of elements as the above list
            tabMethodInitList = [self._initWiFiTab, 
                                 self._initUpgradeTab, 
                                 self._initDevNameTab, 
                                 self._initPortNamesTab, 
                                 self._initMQTTServerTab, 
                                 self._initActivateDeviceTab, 
                                 self._initInstallTab, 
                                 self._initScanTab,
                                 self._calibrateTab]
            address = self._config.getAttr(CT6ConfiguratorConfig.LOCAL_GUI_SERVER_ADDRESS)
            port = self._config.getAttr(CT6ConfiguratorConfig.LOCAL_GUI_SERVER_PORT)

            # PJA try without address port
            self.initGUI(tabNameList, 
                          tabMethodInitList, 
                          address=address, 
                          port=port, 
                          pageTitle=CT6GUIServer.PAGE_TITLE)
            self._loadConfig()

        finally:
            self.close()








def main():
    """@brief Program entry point"""
    uio = UIO()
    options = None

    try:
        parser = argparse.ArgumentParser(description="This application provides an GUI that can be used to configure CT6 units.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",  action='store_true', help="Enable debugging.")
        parser.add_argument("-f", "--config_file",  help="The configuration file for the CT6 Dash Server"\
                                    " (default={}).".format(CT6ConfiguratorConfig.GetConfigFile(CT6ConfiguratorConfig.DEFAULT_CONFIG_FILENAME)),
                                    default=CT6ConfiguratorConfig.GetConfigFile(CT6ConfiguratorConfig.DEFAULT_CONFIG_FILENAME))
        parser.add_argument("-s", "--enable_syslog",action='store_true', help="Enable syslog debug data.")
        parser.add_argument("--skip_factory_config_restore",action='store_true', help="Skip factory config restore. Use with care.")

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_dash")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        ct6ConfiguratorConfig = CT6ConfiguratorConfig(uio, options.config_file, CT6ConfiguratorConfig.DEFAULT_CONFIG)
        
        ct6Configurator = CT6GUIServer(uio, options, ct6ConfiguratorConfig)
        ct6Configurator.start()

    #If the program throws a system exit exception
    except SystemExit:
        pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if not options or options.debug:
            raise
        else:
            uio.error(str(ex))

# Note __mp_main__ is used by the nicegui module
if __name__ in {"__main__", "__mp_main__"}:
    main()
