#!/usr/bin/env python3

import sys
import argparse
import threading
import requests
import tempfile
import os
import shutil
import json

from p3lib.ngt import TabbedNiceGui, YesNoDialog

from p3lib.uio import UIO
from p3lib.helper import logTraceBack
from p3lib.pconfig import ConfigManager

from ct6.ct6_tool import YDevManager, getCT6ToolCmdOpts, CT6Config, MCULoader, CT6Base, CT6Scanner
from ct6.ct6_mfg_tool import FactorySetup, getFactorySetupCmdOpts

from nicegui import ui

class CT6GUIServer(TabbedNiceGui):
    """@brief Responsible for starting the CT6 configurator GUI."""
    PAGE_TITLE                  = "CT6 Configurator"
    DEFAULT_SERVER_ADDRESS      = "0.0.0.0"
    DEFAULT_SERVER_PORT         = 10000


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
    UI_NOTIFY_MSG               = "UI_NOTIFY_MSG"

    MIN_CAL_CURRENT             = 1
    MAX_CAL_CURRENT             = 100

    LOGFILE_PREFIX              = "ct6_configurator"

    AC_LOAD_OFF_TO_GUI_CMD      = 1
    CURRENT_CAL_COMPLETE_TO_GUI_CMD = 2

    QUIT_THREAD_FROM_GUI_CMD    = 1
    AC_LOAD_OFF_FROM_GUI_CMD    = 2

    AC_CURRENT_FIELD            = "AC Current (Amps)"

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance."""
        super().__init__(uio.isDebugEnabled(), FactorySetup.LOG_PATH)
        self._uio                       = uio
        self._options                   = options
        self._svrAddress                = options.address
        self._svrPort                   = options.port

        self._wifiSSIDInput             = None
        self._wifiPasswordInput         = None
        self._setWiFiButton             = None
        self._log                       = None
        self._ct6IPAddressInput1        = None
        self._ct6IPAddressInput2        = None
        self._ct6DeviceList             = []
        self._dialogPrompt              = None
        self._dialogYesMethod           = None
        self._loadOffDialog             = None
        self._dialog2                   = None

        self._skipFactoryConfigRestore  = False
        if '--skip_factory_config_restore' in sys.argv:
            self._skipFactoryConfigRestore = True
            # We remove this arg as ct6_tool and ct6_mfg_tool do not know about this arg
            # and we may re run the cmd line args for each of these later.
            sys.argv.remove('--skip_factory_config_restore')

        self._cfgMgr                    = ConfigManager(self._uio, CT6GUIServer.CFG_FILENAME, CT6GUIServer.DEFAULT_CONFIG)
        self._loadConfig()

        self._logFile                   = os.path.join(self._logPath, CT6GUIServer.GetLogFileName(CT6GUIServer.LOGFILE_PREFIX))

        # Add msg to let the user know the log file for this session.
        self.info("Created " + self._logFile)

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

    def _copyCT6Address(self, ipAddress):
        """@brief Copy same address to CT6 address on all tabs.
           @param ipAddress The IP address to copy to all tabs."""
        if self._ct6IPAddressInput1:
            self._ct6IPAddressInput1.value = ipAddress
        if self._ct6IPAddressInput2:
            self._ct6IPAddressInput2.value = ipAddress
        if self._ct6IPAddressInput3:
            self._ct6IPAddressInput3.value = ipAddress
        if self._ct6IPAddressInput4:
            self._ct6IPAddressInput4.value = ipAddress
        if self._ct6IPAddressInput5:
            self._ct6IPAddressInput5.value = ipAddress
        if self._ct6IPAddressInput6:
            self._ct6IPAddressInput6.value = ipAddress

    def _handleGUIUpdate(self, rxDict):
        """@brief Process the dicts received from the GUI message queue that were not
                  handled by the parent class instance.
           @param rxDict The dict received from the GUI message queue."""

        if CT6GUIServer.SET_CT6_IP_ADDRESS in rxDict:
            address = rxDict[CT6GUIServer.SET_CT6_IP_ADDRESS]
            # Set the IP address field to the CT6 address
            self._copyCT6Address(address)
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

        elif CT6GUIServer.AC_LOAD_OFF_TO_GUI_CMD in rxDict:
            self._loadOffDialog.show()

        elif CT6GUIServer.CURRENT_CAL_COMPLETE_TO_GUI_CMD in rxDict:
            ui.notify(f"Port {self._ctPortInput.value} current calibration complete.")

        elif CT6GUIServer.UI_NOTIFY_MSG in rxDict:
            msg = rxDict[CT6GUIServer.UI_NOTIFY_MSG]
            ui.notify(msg)

    def _initWiFiTab(self):
        """@brief Create the Wifi tab contents."""
        markDownText = """
        <span style="font-size:1.5em;">Set the WiFi SSID and password of your CT6 device. A USB cable must be connected to the CT6 device to setup the WiFi.
        """
        ui.markdown(markDownText)
        with ui.column():

            self._wifiSSIDInput = ui.input(label='WiFi SSID')
            ssid = self._cfgMgr.getAttr(CT6GUIServer.WIFI_SSID)
            if ssid:
                self._wifiSSIDInput.value = ssid

            self._wifiPasswordInput = ui.input(label='WiFi Password', password=True)
            passwd = self._cfgMgr.getAttr(CT6GUIServer.WIFI_PASSWORD)
            if passwd:
                self._wifiPasswordInput.value = passwd

            self._setWiFiButton = ui.button('Setup WiFi', on_click=self._setWiFiNetworkButtonHandler)

            # Add to button list so that button is disabled while activity is in progress.
            self._appendButtonList(self._setWiFiButton)

    def _setExpectedProgressMsgCount(self, nonDebugModeCount, debugModeCount):
        """@brief Set the number of log messages expected to complete a tasks progress.
           @param nonDebugModeCount The number of expected messages in non debug mode.
           @param nonDebugModeCount The number of expected messages in debug mode."""
        if self._uio.isDebugEnabled():
            self._startProgress(expectedMsgCount=debugModeCount)
        else:
            self._startProgress(expectedMsgCount=nonDebugModeCount)

    def _setWiFiNetworkButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask()
        self._saveConfig()
        self._setExpectedProgressMsgCount(22,86)
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
        devManager.configureWiFi(powerCycleHW=True)
        timeout=30
        ipAddress = devManager.waitForIP(timeout=timeout)
        if len(ipAddress) > 0:
            self.info(f"The CT6 device is now connected to {wifiSSID} (IP address = {ipAddress})")
            # Send a message to set the CT6 device IP address in the GUI
            self._setCT6IPAddress(ipAddress)
        else:
            self.error(f"{timeout} second timeout waiting for the CT6 device to get an IP address")

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
        self._upgradeChecks()

    def _upgradeChecks(self):
        """@brief perform some check on the upgrade process."""
        options = getCT6ToolCmdOpts()
        devManager = YDevManager(self, options)
        devManager.setIPAddress(self._ct6IPAddressInput1.value)
        userPrompt = devManager.upgradeChecks()
        if userPrompt is None:
            self._startUpgradeThread()
        else:
            self._showContinueUpgradeDialog(userPrompt)

    def _showContinueUpgradeDialog(self, userPrompt):
        """@brief Present a dialog to the user asking them if they with to proceed with the upgrade."""
        with ui.dialog() as self._dialog2, ui.card().style('width: 400px;'):
            ui.label(userPrompt)
            with ui.row():
                ui.button("Yes", on_click=self._startUpgradeThread)
                ui.button("No", on_click=self._dialog2_no_button_press)
        self._dialog2.open()

    def _dialog2_no_button_press(self):
        """@brief Called when dialog 2 no button is selected to close the dialog."""
        self._closeDialog2()

    def _closeDialog2(self):
        """@brief Close dialog 2 if it exists."""
        if self._dialog2:
            self._dialog2.close()

    def _startUpgradeThread(self):
        """@brief Start the thread that performs the upgrade."""
        self._closeDialog2()
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput1.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(107,120)
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

                        fwVersion = devManager.getFWVersion()
                        msgDict = {CT6GUIServer.UI_NOTIFY_MSG: f"The CT6 unit firmware has been updated to version {fwVersion}"}
                        self.updateGUI(msgDict)

                        self.info(f"CT6 firmware upgrade completed successfully to version {fwVersion}")
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput2.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(2,3)
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
        response = self._getURLResponse(url)
        if response is not None:
            self.debug("_saveConfigDict() successful.")
        else:
            self.debug("_saveConfigDict() failed.")
        self._checkResponse(response)
        return response

    def _getURLResponse(self, url):
        """@brief Get the response to an HTTP request."""
        return requests.get(url, timeout=5)

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
        response = self._getURLResponse(url)
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput2.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(3,4)
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput3.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(2,3)
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput3.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(2,3)
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput4.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(1,2)
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput4.value)
        self._saveConfig()
        self._setExpectedProgressMsgCount(3,4)
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
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput5.value)
        self._saveConfig()
        self._startProgress(10)
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
                self.info(f"Setting CT6 device ({ct6IPAddress}) to the {activeStr} state.")
                cfgDict = {}
                cfgDict[CT6GUIServer.ACTIVE] = active
                response = self._saveConfigDict(ct6IPAddress, cfgDict)
                if response is not None:
                    self.info(f"Set CT6 device ({ct6IPAddress}) to the {activeStr} state.")

            except Exception as ex:
                self.reportException(ex)

        finally:
            self._sendEnableAllButtons(True)

    def _getEnabledStateButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput5.value)
        self._saveConfig()
        self._startProgress(10)
        threading.Thread( target=self._getEnabled, args=(self._ct6IPAddressInput5.value,)).start()

    def _getEnabled(self, ct6IPAddress):
        """@brief Get the enabled state of the CT6 unit.
           @param ct6IPAddress The address of the CT6 device."""
        self.info(f"Get CT6 ({ct6IPAddress}) enabled state.")
        try:
            try:
                self.info(f"Getting CT6 device ({ct6IPAddress}) active state...")
                cfgDict = self._getConfigDict(ct6IPAddress)
                self.info("Read CT6 active state.")
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
        self._initTask()
        self._saveConfig()
        self._setExpectedProgressMsgCount(91,219)
        threading.Thread( target=self._installSW, args=(self._wifiSSIDInput.value, self._wifiPasswordInput.value)).start()

    def _correctRshellWindowsPath(self, aPath):
        """@brief Correct for a windows path in an rshell command.
           @param aPath The path to check.
           @return The corrected Windows path if on a Windows platform.
                   If not on a windows platform aPath is returned unchanged."""
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
        tempPath = tempfile.gettempdir()
        srcFile = f"/pyboard/{YDevManager.CT6_FACTORY_CONFIG_FILE}"
        destFile = os.path.join(tempPath, YDevManager.CT6_FACTORY_CONFIG_FILE)
        try:
            self.info("Connecting to CT6 device over it's serial port.")
            # Attempt to connect to the board under test python prompt
            if not devManager._checkMicroPython(closeSerialPort=True):
                raise Exception("Failed to read the CT6 MicroPython version over serial port.")
            self.info("Reading CT6 factory configuration.")
            self.debug(f"Copy {YDevManager.CT6_FACTORY_CONFIG_FILE} to {destFile}")

            # Copy the factory config to the temp folder
            devManager._runRShell((f'cp {srcFile} {self._correctRshellWindowsPath(destFile)}',))
            devManager._checkFactoryConfFile(f'{destFile}')
        except:
            self.error(f"Failed to read CT6 {YDevManager.CT6_FACTORY_CONFIG_FILE} file.")
            if not os.path.isfile(destFile):
                raise Exception(f"Unable to find the {YDevManager.CT6_FACTORY_CONFIG_FILE} file on the CT6 device or in the {tempPath} folder (cached copy).")

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
            # Use the fallback factory config file in temp if available.
            tempPath = tempfile.gettempdir()
            srcFile = os.path.join(tempPath, YDevManager.CT6_FACTORY_CONFIG_FILE)
            # If the fallback file exists let the user know as it may be the factory config file for a different unit
            # but it's probably best to try and load it and let the user know.
            if os.path.isfile(srcFile):
                self.warn(f"Using fallback factory config: {srcFile}")
            else:
                if self._skipFactoryConfigRestore:
                    self.warn("Not restoring factory config to the CT6 device.")
                else:
                    raise Exception(f"{srcFile} fallback factory config file not found.")

        if os.path.isfile(srcFile):
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
                self.reportException(ex)

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
        self._initTask()
        self._saveConfig()
        self._startProgress(self._scanSecondsInput.value+1)
        threading.Thread( target=self._scanForCT6Devices, args=(self._scanSecondsInput.value,)).start()

    def _rebootButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        # No progress on this as it's difficult to predict when the CT6 device will reconnect to the wiFi after a reboot.
        self._initTask()
        self._saveConfig()
        self._setExpectedProgressMsgCount(9,12)
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
            try:
                ct6Scanner = CT6Scanner(None, None)
                ct6Scanner.scan(callBack=self._ct6DevFound, runSeconds=scanSeconds)
            except Exception as ex:
                self.reportException(ex)
        finally:
            self._sendEnableAllButtons(True)

    def _rebootDevice(self, ipAddress, deviceName):
        """@brief Reboot a CT6 device.
           @param ipAddress The IP address of the CT6 device.
           @param deviceName The name of the device to be rebooted."""
        try:
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

            except Exception as ex:
                self.reportException(ex)

        finally:
            self._sendEnableAllButtons(True)

    def _calibrateTab(self):
        """@brief Create the calibrate tab contents."""

        self._ct6IPAddressInput6 = ui.input(label='CT6 Address').style('width: 200px;')

        with ui.tabs().classes('w-full') as tabs:
            calVoltageTab = ui.tab('Calibrate Voltage')
            calCurrentTab = ui.tab('Calibrate Current')
        with ui.tab_panels(tabs, value=calVoltageTab).classes('w-full'):
            with ui.tab_panel(calVoltageTab):
                markDownText = f"""{CT6GUIServer.DESCRIP_STYLE}The CT6 device measures the AC supply voltage in order to read accurate power values. \
                                                            This is calibrated during manufacture using the recommended AC power supply.<br>
                                                            The CT6 device should work with any AC power supply that provides 9-16 volts. \
                                                            If you use a different power supply from the one the CT6 device was calibrated with, during manufacture, you must recalibrate the unit to ensure accurate power measurements. \
                                                            This tab allows you to calibrate the CT6 device voltage measurements.<br><br>\
                                                            Measure the AC voltage, enter the measured AC voltage below and then select the button below."""
                ui.markdown(markDownText)
                self._acVoltageInput = ui.number(label="AC Voltage", format='%.2f', value=0, min=50, max=400).style('width: 200px;')
                self._acFreq60HzInput = ui.switch("60 Hz AC Supply").style('width: 200px;')
                self._acFreq60HzInput.tooltip("Leave this off if your AC frequency is 50 Hz.")
                self._voltageCalStep1Dialog = YesNoDialog("Are you sure you wish to calibrate the voltage on the CT6 device ?",
                                                            self._calVoltageStep1)
                self._calibrateVoltageButton = ui.button('Calibrate Voltage', on_click=lambda: self._voltageCalStep1Dialog.show() )
                # Add to button list so that button is disabled while activity is in progress.
                self._appendButtonList(self._calibrateVoltageButton)

            with ui.tab_panel(calCurrentTab):
                markDownText = f"""{CT6GUIServer.DESCRIP_STYLE}The CT6 device measures current on each of it's 6 ports. During manufacture \
                                                            the CT6 device ports are calibrated with a 'YHDC SCT013 100A 0-1V' CT transformer connected to each port. \
                                                            If you wish to use another type of CT transformer you must calibrate the port to which the CT transformer is connected. \
                                                            Click [this link](https://github.com/pjaos/ct6_meter_os/blob/master/software/server/README_MFG.md) for details of how this calibration is performed.<br><br> \
                                                            With an AC load, enter the measured current on the selected port and then select the button below to perform the calibration."""
                ui.markdown(markDownText)
                self._ctPortInput = ui.radio([1, 2, 3, 4, 5 ,6], value=1).props('inline')
                self._acCurrentInput = ui.number(label=CT6GUIServer.AC_CURRENT_FIELD,
                                                 format='%.2f',
                                                 value=0,
                                                 min=CT6GUIServer.MIN_CAL_CURRENT,
                                                 max=CT6GUIServer.MAX_CAL_CURRENT).style('width: 200px;')
                self._acFreq60HzInput = ui.switch("60 Hz AC Supply").style('width: 200px;')
                self._acFreq60HzInput.tooltip("Leave this off if your AC frequency is 50 Hz.")
                self._currentCalDialog = YesNoDialog("Are you sure you wish to calibrate the current on the selected port ?",
                                                            self._startPortCurrentCal)
                self._calibrateCurrentButton = ui.button('Calibrate Current', on_click=self._currentCalDialog.show)
                # Add to button list so that button is disabled while activity is in progress.
                self._appendButtonList(self._calibrateCurrentButton)

                self._loadOffDialog = YesNoDialog("Turn off the AC load on the selected port.",
                                                          self._acLoadOff,
                                                          failureMethod=self._quitThread,
                                                          successButtonText="OK",
                                                          failureButtonText="Cancel")

        # Set the IP address as this is the last tab to be loaded
        ipAddress = self._cfgMgr.getAttr(CT6GUIServer.DEVICE_ADDRESS)
        if ipAddress:
            self._copyCT6Address(ipAddress)

    def _startPortCurrentCal(self):
        """@brief Guide the user through the voltage calibration process."""
        # No progress bar for this task as it relies on user responses
        self._initTask()
        self._copyCT6Address(self._ct6IPAddressInput6.value)
        self._saveConfig()
        # Start the thread that will calibrate the current on a single port.
        threading.Thread( target=self._calCurrent, args=(self._ct6IPAddressInput6.value, self._ctPortInput.value, self._acCurrentInput.value, self._acFreq60HzInput.value)).start()

    def _calCurrent(self, address, port, amps, acFreq60Hz):
        """@brief Perform the AC voltage calibration. This is executed outside the GUI thread.
           @param address The address of the CT6 device.
           @param port The port to calibrate the current on.
           @param amps The measured current on the CT port.
           @param acFreq60Hz True if AC main freq is 60 Hz, False if 50 Hz."""
        try:
            try:
                if self._options.shelly is None and amps < 1:
                    self.error("The measured current must be at least 1 amps to calibrate the CT port.")
                    self.info("You must measure this load current and enter the AC current value.")

                else:
                    self.info(f"Start current calibration on port {port}.")
                    #If this we don't have acces to the shelly unit we use the current entered by the user.
                    if self._options.shelly is None:
                        self.info(f"Current = {amps:.2f} Amps.")
                    factorySetupOptions = getFactorySetupCmdOpts()
                    factorySetupOptions.address = address
                    factorySetupOptions.ac60hz = acFreq60Hz
                    factorySetup = FactorySetup(self, factorySetupOptions)
                    if self._options.shelly is None:
                        # Perform the port calibration and store the result in the CT6 device flash.
                        factorySetup._calCurrentGain(port, acAmps=amps, noLoadTimeoutSeconds=5)
                        cmdDict = {CT6GUIServer.AC_LOAD_OFF_TO_GUI_CMD: None}
                        responseDict = self._updateGUIAndWaitForResponse(cmdDict)
                        if CT6GUIServer.AC_LOAD_OFF_FROM_GUI_CMD in responseDict:
                            factorySetup._calCurrentOffset(port, loadOffTimeoutSeconds=5)
                            cmdDict = {CT6GUIServer.CURRENT_CAL_COMPLETE_TO_GUI_CMD: None}
                            responseDict = self._updateGUI(cmdDict)
                            self.info(f"Port {port} current calibration complete.")
                    else:
                        factorySetup._calCurrentOffset(port, loadOffTimeoutSeconds=5)
                        factorySetup._calCurrentGain(port, acAmps=amps, noLoadTimeoutSeconds=5)
                        cmdDict = {CT6GUIServer.CURRENT_CAL_COMPLETE_TO_GUI_CMD: None}
                        responseDict = self._updateGUI(cmdDict)
                        self.info(f"Port {port} current calibration complete.")

                    # Save the calibration values persistently on the CT6 unit
                    factorySetup.saveFactoryCfg()

            except Exception as ex:
                self.reportException(ex)

        finally:
            self._sendEnableAllButtons(True)

    def _quitThread(self):
        """@brief Called by the GUI thread to quit a non GUI thread."""
        # Send CMD back to thread to indicate the user wants to quit.
        cmdDict = {CT6GUIServer.QUIT_THREAD_FROM_GUI_CMD: True}
        self._updateExeThread(cmdDict)
        self.info("Calibration cancelled.")

    def _acLoadOff(self):
        """@brief Called when the user indicates they have the AC load off."""
        # Send CMD back to thread to indicate the user wants to continue.
        cmdDict = {CT6GUIServer.AC_LOAD_OFF_FROM_GUI_CMD: True}
        self._updateExeThread(cmdDict)

    def _calVoltageStep1(self):
        """@brief Guid the user through the voltage calibration process."""
        # No progress bar for this task as it relies on user responses
        self._initTask() # No progress bar for this task as it relies on user responses
        self._copyCT6Address(self._ct6IPAddressInput6.value)
        self._saveConfig()
        self.info("Start CT6 voltage calibration.")
        threading.Thread( target=self._calVoltage, args=(self._ct6IPAddressInput6.value, self._acVoltageInput.value, self._acFreq60HzInput.value)).start()

    def _calVoltage(self, address, acVoltage, acFreq60Hz):
        """@brief Perform the AC voltage calibration.
           @param address The address of the CT6 device.
           @param acVoltage The measured AC voltage.
           @param acFreq60Hz True if AC main freq is 60 Hz, False if 50 Hz"""
        try:
            try:
                if acVoltage >= 80:
                    factorySetupOptions = getFactorySetupCmdOpts()
                    factorySetupOptions.address = address
                    factorySetupOptions.ac60hz = acFreq60Hz
                    factorySetup = FactorySetup(self, factorySetupOptions)
                    factorySetup._calVoltageGain(1, maxError=0.3, acVoltage=acVoltage)
                    factorySetup._calVoltageGain(4, maxError=0.3, acVoltage=acVoltage)
                    # Save the calibration values persistently on the CT6 unit
                    factorySetup.saveFactoryCfg()
                    self.info("Voltage calibration completed successfully.")
                else:
                    self.error("The measured voltage must be at least 80 volts.")

            except Exception as ex:
                self.reportException(ex)
        finally:
            self._sendEnableAllButtons(True)

    def _checkArgs(self):
        """@brief Check command line arguments."""
        if self._options.port < 1024:
            raise Exception("The minimum TCP port that you can bind the GUI server to is 1024.")
        if self._options.port > 65535:
            raise Exception("The maximum TCP port that you can bind the GUI server to is 65535.")

    def start(self):
        """@brief Start the App server running."""
        self._uio.info("Starting GUI...")
        self._checkArgs()
        try:
            tabNameList = ('WiFi',
                           'Upgrade',
                           'Device Name',
                           'Port Names',
                           'MQTT Server',
                           'Activate Device',
                           'Install',
                           'Scan',
                           'Calibration')
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

            self.initGUI(tabNameList,
                          tabMethodInitList,
                          address=self._svrAddress,
                          port=self._svrPort,
                          pageTitle=CT6GUIServer.PAGE_TITLE,
                          reload=False)


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
        parser.add_argument("-a", "--address",help=f"Address that the GUI server is bound to (default={CT6GUIServer.DEFAULT_SERVER_ADDRESS}).", default=CT6GUIServer.DEFAULT_SERVER_ADDRESS)
        parser.add_argument("-p", "--port",   type=int, help=f"The TCP server port to which the GUI server is bound to (default={CT6GUIServer.DEFAULT_SERVER_PORT}).", default=CT6GUIServer.DEFAULT_SERVER_PORT)
        parser.add_argument("-s", "--shelly", help="The IP address of the Shelly 1PM Plus unit in the MFG test station. Use this if you are using the increased accuracy test system. If you leave this blank when calibrating the voltage or current you will be prompted to enter the values you measure from external voltage and current meters.", default=None)
        parser.add_argument("--enable_syslog",action='store_true', help="Enable syslog debug data.")
        parser.add_argument("--skip_factory_config_restore",action='store_true', help="Skip factory config restore. Use with care.")

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_dash")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        ct6Configurator = CT6GUIServer(uio, options)
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

if __name__== '__main__':
    main()

