#!/usr/bin/env python3

import  os
import  ifaddr
from    p3lib.ssh import SSH
from    p3lib.pconfig import ConfigManager
from    p3lib.netif import NetIF

class ConfigBase(ConfigManager):
    """@brief Responsible for managing configuration used by all apps."""
    ICONS_ADDRESS               = "ICONS_ADDRESS"
    ICONS_PORT                  = "ICONS_PORT"
    ICONS_USERNAME              = "ICONS_USERNAME"
    ICONS_SSH_KEY_FILE          = "ICONS_SSH_KEY_FILE"
    MQTT_TOPIC                  = "MQTT_TOPIC"
    TIMESTAMP                   = "TIMESTAMP"
    DB_HOST                     = "DB_HOST"
    DB_PORT                     = "DB_PORT"
    DB_USERNAME                 = "DB_USERNAME"
    DB_PASSWORD                 = "DB_PASSWORD"
    LOCAL_GUI_SERVER_ADDRESS    = "LOCAL_GUI_SERVER_ADDRESS"
    LOCAL_GUI_SERVER_PORT       = "LOCAL_GUI_SERVER_PORT"
    SERVER_LOGIN                = "SERVER_LOGIN"
    SERVER_ACCESS_LOG_FILE      = "SERVER_ACCESS_LOG_FILE"
    CT6_DEVICE_DISCOVERY_INTERFACE = "CT6_DEVICE_DISCOVERY_INTERFACE"

    @staticmethod
    def GetTableSchema(tableSchemaString):
        """@brief Get the table schema
           @param tableSchemaString The string defining the database table schema.
           @return A dictionary containing a database table schema."""
        timestampFound=False
        tableSchemaDict = {}
        elems = tableSchemaString.split(" ")
        if len(elems) > 0:
            for elem in elems:
                subElems = elem.split(":")
                if len(subElems) == 2:
                    colName = subElems[0]
                    if colName == ConfigBase.TIMESTAMP:
                        timestampFound=True
                    colType = subElems[1]
                    tableSchemaDict[colName] = colType
                else:
                    raise Exception("{} is an invalid table schema column.".format(elem))
            return tableSchemaDict
        else:
            raise Exception("Invalid Table schema. No elements found.")

        if not timestampFound:
            raise Exception("No {} table column defined.".format(ConfigBase.TIMESTAMP))

    def __init__(self, uio, configFile, defaultConfig):
        """@brief Constructor.
           @param uio UIO instance.
           @param configFile Config file instance.
           @param defaultConfig The default configuration."""
        super().__init__(uio, configFile, defaultConfig, addDotToFilename=False, encrypt=False)
        self._uio     = uio
        try:
            self.load()
        except:
            self._configDict = self._defaultConfig
        self.store()

    def _showLocalIPAddressList(self):
        """@brief Show the user a list of local IP addresses that they may want to use to present the GUI/Bokeh server on.
           @return A List of local IP addresses."""
        localIPList = []
        adapters = ifaddr.get_adapters()
        self._uio.info("Local Interface List")
        self._uio.info("-"*62)
        self._uio.info("| Interface Name            | IP Address                     |")
        self._uio.info("-"*62)
        for adapter in adapters:
            for ip in adapter.ips:
                if isinstance(ip.ip, str):
                    self._uio.info("| {: <25s} | {: <25s}      |".format(adapter.nice_name, ip.ip))
                    localIPList.append(ip.ip)
        self._uio.info("-"*62)
        return localIPList

    def _enterServerAccessLogFile(self):
        """@brief Allow the user to enter the server access log file."""
        # Ensure the user enters the path and name of the server access log file.
        while True:
            self.inputStr(ConfigBase.SERVER_ACCESS_LOG_FILE, "Enter the file (full path) to record server access.", False)
            logFile = self.getAttr(ConfigBase.SERVER_ACCESS_LOG_FILE)
            logFile = os.path.abspath(logFile)
            logPath = os.path.dirname(logFile)
            if os.path.isdir(logPath):
                # Try creating the file to check write access
                try:
                    # Check if file is already present
                    if os.path.isfile(logFile):
                        delete = self._uio.getBoolInput(f"OK to overwrite {logFile} ? y/n")
                        if not delete:
                            continue
                    # Create empty file.
                    with open(logFile, 'w'):
                        pass
                    break
                except IOError as ex:
                    self._uio.error(f"{str(ex)} folder not found.")
            else:
                self._uio.error(f"{logPath} folder not found.")

    def _showAvailableNetworkInterfaces(self):
        """@param Show the use the available network interfaces.
           @return A list of network interface names in the order in which they
                   appear in the displayed list."""
        self._uio.info("Available network interfaces.")
        self._uio.info("ID    Name            Address")
        netIF = NetIF()
        ifDict = netIF.getIFDict()
        nameList = []
        ifNameID = 1
        self._uio.info("{: <2d}    {}".format(ifNameID, "All Interfaces"))
        ifNameID = ifNameID + 1
        for ifName in list(ifDict.keys()):
            ipsStr = ",".join(ifDict[ifName])
            if ifName == "lo":
                continue
            self._uio.info("{: <2d}    {: <10s}      {}".format(ifNameID, ifName, ipsStr))
            nameList.append(ifName)
            ifNameID = ifNameID + 1
        return nameList

    def _enterDiscoveryInterface(self):
        """@brief Allow the user to enter a network interface name to discover YView devices on.
                  This is optional. If the user enters none then AYT broadcast messages are sent
                  over all network interfaces."""
        self._uio.info("Select the interface/s to find YView devices over.")
        self._uio.info("")
        ifNameList = self._showAvailableNetworkInterfaces()
        idSelected = ConfigManager.GetDecInt(self._uio, "Enter the ID from the above list", minValue=1, maxValue=len(ifNameList)+1)
        if idSelected == 1:
             self.addAttr(ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE, None)
        else:
            selectedIndex = idSelected-2
            if selectedIndex < len(ifNameList):
                self.addAttr(ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE, ifNameList[selectedIndex])
            else:
                raise Exception("{} ID is not valid for {} interface list.".format(idSelected, ",".join(ifNameList)))

    def edit(self, key):
        """@brief Provide the functionality to allow the user to enter any ct4 config parameter
                  regardless of the config type.
           @param key The dict key to be edited.
           @return True if the config parameter was handled/updated"""
        handled = False

        if key == ConfigBase.ICONS_ADDRESS:
            self.inputStr(ConfigBase.ICONS_ADDRESS, "Enter the ICON server address", False)
            handled = True

        elif key == ConfigBase.ICONS_PORT:
            self.inputDecInt(ConfigBase.ICONS_PORT, "Enter the ICON server port (default = 22)", minValue=1024, maxValue=65535)
            handled = True

        elif key == ConfigBase.ICONS_USERNAME:
            self.inputStr(ConfigBase.ICONS_USERNAME, "Enter ICON server username", False)
            handled = True

        elif key == ConfigBase.ICONS_SSH_KEY_FILE:
            self.inputStr(ConfigBase.ICONS_SSH_KEY_FILE, "Enter the ICON server ssh key file", False)
            handled = True

        elif key == ConfigBase.MQTT_TOPIC:
            self._uio.info("The MQTT topic can be # to receive data on all YView devices.")
            self._uio.info("To limit the data received to all devices at a location (E.G HOME/#).")
            self._uio.info("To limit the data received to a single device at a location enter HOME/QUAD_CT_SENSOR_A")
            self.inputStr(ConfigBase.MQTT_TOPIC, "Enter the location of the device", False)
            handled = True

        elif key == ConfigBase.DB_HOST:
            self.inputStr(ConfigBase.DB_HOST, "Enter the address of the MYSQL database server", False)
            handled = True

        elif key == ConfigBase.DB_PORT:
            self.inputDecInt(ConfigBase.DB_PORT, "Enter TCP port to connect to the MYSQL database server", minValue=1024, maxValue=65535)
            handled = True

        elif key == ConfigBase.DB_USERNAME:
            self.inputStr(ConfigBase.DB_USERNAME, "Enter the database username", False)
            handled = True

        elif key == ConfigBase.DB_PASSWORD:
            self.inputStr(ConfigBase.DB_PASSWORD, "Enter the database password", False)
            handled = True

        elif key == ConfigBase.LOCAL_GUI_SERVER_ADDRESS:
            localIPList = self._showLocalIPAddressList()
            # Ensure the user enters an IP address of an interface on this machine.
            while True:
                self.inputStr(ConfigBase.LOCAL_GUI_SERVER_ADDRESS, "Enter the local IP address to serve the GUI/Bokeh web interface from", False)
                ipAddr = self.getAttr(ConfigBase.LOCAL_GUI_SERVER_ADDRESS)
                if ipAddr in localIPList:
                    break
                else:
                    self._uio.error("{} is not a IP address of an interface on this machine.".format(ipAddr))
            handled = True

        elif key == ConfigBase.LOCAL_GUI_SERVER_PORT:
            self.inputBool(ConfigBase.LOCAL_GUI_SERVER_PORT, "Enter the TCP port to serve the GUI/Bokeh web interface from", minValue=1024, maxValue=65535)
            handled = True

        elif key == ConfigBase.SERVER_LOGIN:
            self.inputBool(ConfigBase.SERVER_LOGIN, "Enable server login")
            handled = True

        elif key == ConfigBase.SERVER_ACCESS_LOG_FILE:
            self._enterServerAccessLogFile()

        elif key == ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE:
            self._enterDiscoveryInterface()

        if handled:
            self.store()

        return handled