#!/usr/bin/env python3

import json
import urllib
import socket
import paho.mqtt.client as mqtt

from time import time, sleep
from queue import Queue
from threading import Thread

from p3lib.ssh import SSH, SSHTunnelManager
from p3lib.helper import GetFreeTCPPort, printDict

from .config import ConfigBase
from .base_constants import BaseConstants

class YView(BaseConstants):
    """@brief Manage connections to the YView network."""

    def __init__(self, uio, config):
        """@brief Constructor
           @param uio A UIO instance.
           @param config A ConfigBase instance."""
        self._uio = uio
        self._config = config
        self._ssh = None
        self._sshTunnelManager = None

    def _startSSHTunnel(self):
        """@brief Start the ssh tunnel to the SSH server"""
        sshCompression = True
        iconsAddress = self._config.getAttr(ConfigBase.ICONS_ADDRESS)
        iconsPort = self._config.getAttr(ConfigBase.ICONS_PORT)
        iconsUsername = self._config.getAttr(ConfigBase.ICONS_USERNAME)
        iconsKeyFile = self._config.getAttr(ConfigBase.ICONS_SSH_KEY_FILE)

        self._uio.info("Connecting to ICONS server: {}@{}:{}".format(iconsUsername, iconsAddress, iconsPort))
        #Build an ssh connection to the ICON server
        self._ssh = SSH(iconsAddress, iconsUsername, useCompression=sshCompression, port=iconsPort, uio=self._uio, privateKeyFile=iconsKeyFile)
        self._ssh.connect(enableAutoLoginSetup=True)
        self._locaIPAddress = self._ssh.getLocalAddress()
        self._uio.info("Connected")

        self._uio.info("Setting up ssh port forwarding")
        # Get a free TCPIP port on the local machine
        localMQTTPort = GetFreeTCPPort()
        self._sshTunnelManager = SSHTunnelManager(self._uio, self._ssh, sshCompression)
        self._sshTunnelManager.startFwdSSHTunnel(localMQTTPort, YView.LOCALHOST, YView.MQTT_PORT)

        return localMQTTPort

    def getSSHTunnelManager(self):
        """@return A reference to the SSH tunnerl manager."""
        return self._sshTunnelManager

    def connect(self):
        """@brief Connect to the YView MQTT server.
           @return The local port TCP port that is connected through an ssh tunnel to the MQTT port on the ICON server."""
        return self._startSSHTunnel()

    def disconnect(self):
        """@brief disconnect from the YView MQTT server."""
        if self._sshTunnelManager:
            self._sshTunnelManager.stopAllSSHTunnels()
            self._sshTunnelManager = None

        if self._ssh:
            self._ssh.close()
            self._ssh = None

    def connected(self):
        """@brief Determine if the connection to the server is up.
           @return True if the connection is active."""
        active = False
        if self._ssh.getTransport() and self._ssh.getTransport().is_active():
            active = True
        return active

class YViewMQTTReader(BaseConstants):
    """@brief Responsible for reading data from the YView MQTT server."""

    @staticmethod
    def IsWebService(serviceName):
        """@brief determine if the service is a web service.
           @return True if it is."""
        webService = False
        serviceName = serviceName.upper()
        for _serviceName in YViewMQTTReader.WEB_SERVICE_NAME_LIST:
            if _serviceName == serviceName:
                webService = True
                break
        return webService

    @staticmethod
    def GetWebServicePort(devDict):
        """@return The TCP port connected (via ssh port forwarding) to the device's
                   web service or -1 if not found."""
        localHostPort = -1
        if YViewMQTTReader.LOCALHOST_SERVICE_LIST in devDict:
            localHostServiceList = devDict[YViewMQTTReader.LOCALHOST_SERVICE_LIST]
            if YViewMQTTReader.WEB_SERVICE_NAME in localHostServiceList:
                localHostPort = localHostServiceList[YViewMQTTReader.WEB_SERVICE_NAME]
        return localHostPort

    def __init__(self, uio, options, mqttPort, updateListenersMethod):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param mqttPort The TCP port on local host that is connected to the YView MQTT server.
           @param updateListenersMethod The method to call to update all device listeners."""
        self._uio                   = uio
        self._options               = options
        self._mqttPort              = mqttPort
        self._updateListenersMethod = updateListenersMethod
        self._startTime             = None
        self._sshTunnelManager      = None
        self._portForwardingDict    = {} # This dict holds
                                         # key = the device assy
                                         # value = A dict containing
                                         #     key = Service name
                                         #     value = The localhost TCP port that is forwarded to the server.  
        self._validProuctIDList     = [] # A list of YView product ID's that we're interested in hearing from.  
        
    def setSSHTunnelManager(self, sshTunnelManager):
        """@brief Set a referenece to the associated SSH tunnerl manager."""
        self._sshTunnelManager = sshTunnelManager

    def startReading(self, location, devName="192.168.0.70"):
        """@brief Start to read data from the MQTT server.
           @param port The TCP port to connect to the MQTT server.
           @return The mqtt client instance."""
        self._startTime = time()
        client = mqtt.Client(client_id="{}".format(self._startTime), clean_session=False)
        client.on_connect = self._mqttConnectedCallBack
        client.on_message = self._mqttMessageReceived
        self._uio.info("MQTT client connecting to {}:{}".format(YViewCollector.LOCALHOST, self._mqttPort))
        client.connect(YViewCollector.LOCALHOST, self._mqttPort, 60)
        topic = location
        # Subscribe to the location topic       
        self._uio.debug(topic)
        # If required to subscribe to all topics
        if self._options.all:
            topic="#"
        client.subscribe(topic, qos=0)
        return client

    def _mqttConnectedCallBack(self, client, userdata, flags, rc):
        """@brief handle a connected ICONS session"""
        self._uio.info("Connected to MQTT server")

    def _mqttMessageReceived(self, client, userdata, msg):
        """@brief Called when a message is received from the ICONS MQTT server."""
        ensureConectable = False
        rxStr = msg.payload.decode()
        rxDict = json.loads(rxStr)
        if len(self._validProuctIDList) > 0:
            if YViewMQTTReader.PRODUCT_ID in rxDict and rxDict[YViewMQTTReader.PRODUCT_ID] in self._validProuctIDList:
                ensureConectable = True
                if YView.ASSY in rxDict:
                    rxDict[YView.ASSY]=urllib.parse.unquote(rxDict[YView.ASSY])
                if YView.UNIT_NAME in rxDict:
                    rxDict[YView.UNIT_NAME]=urllib.parse.unquote(rxDict[YView.UNIT_NAME])
                if YView.LOCATION in rxDict:
                    rxDict[YView.LOCATION]=urllib.parse.unquote(rxDict[YView.LOCATION])
                for ctDev in YView.CT_DEV_LIST:
                    if ctDev in rxDict:
                        ctDevDict = rxDict[ctDev]
                        if YView.NAME in ctDevDict:
                            ctDevDict[YView.NAME]= urllib.parse.unquote(ctDevDict[YView.NAME])
        else:
            ensureConectable = True
            
        if ensureConectable:
            self._ensureConnectability(rxDict)
            
        if self._options.show:
            self._showDevData(rxDict)
        self._updateListenersMethod(rxDict)

    def _ensureConnectability(self, devDict):
        """@brief Ensure that the device can be connected to via a localhost TCP port.
                  This port is connected to an ssh tunnel that pops out on the ICON server
                  to connect to a port that is forwarded over a reverse ssh tunnel
                  to the remote device. The first time that the deive data is seen
                  the ssh port forwarding is setup. The details of the local TCP port
                  is added to the devDict to allow SW to which the devDict is passed
                  knows which local TCP port is connected to the device.
           @param devDict The device dictionary."""
        devDetailsFound = self._portForwardingSetupPreviously(devDict)
        if not devDetailsFound:
            self._setupPortForwarding(devDict)

        self._updateLocalHostServices(devDict)

    def _updateLocalHostServices(self, devDict):
        """@brief Update the devDict with the services that have been setup to connect
                  via TCP ports on localhost."""
        if YViewMQTTReader.UNIT_NAME in devDict:
            devAssy = devDict[YViewMQTTReader.ASSY]
            if devAssy in self._portForwardingDict:
                portForwardingDict = self._portForwardingDict[devAssy]
                devDict[YViewMQTTReader.LOCALHOST_SERVICE_LIST] = portForwardingDict

        else:
            self._uio.debug("_updateLocalHostServices(): Device data contains no {}: {}".format(YViewMQTTReader.UNIT_NAME, devDict))

    def _portForwardingSetupPreviously(self, devDict):
        """@brief Determine if port forwarding has already been setup for this device.
           @param devDict The device dictionary.
           @return True if the details were added to the dictionary.
                   False if we have no record of this device."""
        devDetailsFound = False
        if YViewMQTTReader.UNIT_NAME in devDict:
            devAssy = devDict[YViewMQTTReader.ASSY]
            if devAssy in self._portForwardingDict:
                devDetailsFound = True

        else:
            self._uio.debug("_portForwardingSetupPreviously(): Device data contains no {}: {}".format(YViewMQTTReader.ASSY, devDict))

        return devDetailsFound

    def _recordPortForwardingSetup(self,  devDict, localPort):
        """@brief Record the fact that device port forwarding has been setup.
           @param devDict The device dictionary.
           @param localPort The port on localhost that is forwarded to the device."""
        devAssy = devDict[YViewMQTTReader.ASSY]
        if YViewMQTTReader.SERVER_SERVICE_LIST in devDict:
            devServerServiceListString = devDict[YViewMQTTReader.SERVER_SERVICE_LIST]
            devServerServiceList = devServerServiceListString.split(',')
            for devServerService in devServerServiceList:
                serviceElems = devServerService.split(":")
                try:
                    serviceName = serviceElems[0]
                    serverServicePort = int(serviceElems[1])
                    if devAssy not in self._portForwardingDict:
                        self._portForwardingDict[devAssy] = {}
                    portForwardingDict = self._portForwardingDict[devAssy]
                    # Add to the record of the TCP forwarding setup.
                    if serviceName not in portForwardingDict:
                        portForwardingDict[serviceName] = localPort

                except:
                    self._uio.errorException()

        else:
            self._uio.warn("Device data contains no {}: {}".format(YViewMQTTReader.SERVER_SERVICE_LIST, devDict))

    def _getWebServicePort(self, devDict):
        """@brief Get the WEB service port that the device is connected to on the ICON server.
           @param devDict The device dictionary.
           @return The service port or -1 if the WEB service does not exist."""
        servicePort = -1
        if YViewMQTTReader.SERVER_SERVICE_LIST in devDict:
            serviceListString = devDict[YViewMQTTReader.SERVER_SERVICE_LIST]
            try:
                elems = serviceListString.split(":")
                serviceName = elems[0]
                if YViewMQTTReader.IsWebService(serviceName):
                    servicePort = int(elems[1])
            except:
                self._uio.errorException()

        return servicePort

    def _setupPortForwarding(self, devDict):
        """@brief Setup port forwarding for a device.
           @param devDict The device dictionary."""
        if YViewMQTTReader.UNIT_NAME in devDict:
            devName = devDict[YViewMQTTReader.UNIT_NAME]
            freeLocalTCPPort = GetFreeTCPPort()
            remoteWebServicePort = self._getWebServicePort(devDict)
            self._uio.info("Setting up WEB port forwarding for {}".format(devName))
            self._sshTunnelManager.startFwdSSHTunnel(freeLocalTCPPort, YView.LOCALHOST, remoteWebServicePort)
            if freeLocalTCPPort >= 0:
                self._recordPortForwardingSetup(devDict, freeLocalTCPPort)

        else:
            self._uio.debug("Device data contains no {}: {}".format(YViewMQTTReader.UNIT_NAME, devDict))

    def _showDevData(self, devDict):
        """@brief Show the device data received from the ICONS"""
        if "LOCATION" in devDict and "UNIT_NAME" in devDict:
            location = devDict["LOCATION"]
            unitName = devDict["UNIT_NAME"]
            self._uio.info("")
            self._uio.info("********** {}/{} DEVICE ATTRIBUTES **********".format(location, unitName))
        printDict(self._uio, devDict)
               
    def getPortForwardingDict(self):
        """@brief Get a dict that details the localhost TCP ports forwarded to the remote device.
           @return A dict that holds the 
                   key = assy of the device, 
                   value = a dict that holds
                       key = the service name, 
                       value = the local TCP port forwarded to that service on the device."""
        return self._portForwardingDict
    
    def getForwardedPort(self, deviceAssy):
        """@brief Get the first TCP port forwarded from localhost to a device.
                  If the device only presents a service on one TCP port this can be used. 
                  If the device presents services on more than one TCP port then getPortForwardingDict() should be used.
           @param deviceAssy The device assembly label of the device of interest.
           @return The TCP port forwarded from localhost to the device or -1 if no data has yet been received from 
                   the device detailing a port that the device is presenting a service on."""
        self._uio.debug("self._portForwardingDict={}".format(self._portForwardingDict))
        tcpPort = -1
        assys = list( self._portForwardingDict.keys() )
        for assy in assys:   
            if assy == deviceAssy:
                devServiceDict = self._portForwardingDict[deviceAssy]
                if 'WEB' in devServiceDict:
                    tcpPort = devServiceDict['WEB']
                    break
        return tcpPort
    
    def setValidProuctIDList(self, validProductIDList):
        """@brief Set a list of product ID's that we're interested in.
           @param validProductIDList The list we're interested in."""
        self._validProuctIDList = validProductIDList
        
class YViewCollector(BaseConstants):
    """@brief Responsible for
        - Connecting to and receiving data from the YView ICON server.
        - Forwarding device data to listeners."""

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A ConfigBase instance."""
        self._uio                   = uio
        self._options               = options
        self._config                = config
        self._mqttTopic             = self._config.getAttr(ConfigBase.MQTT_TOPIC)
        self._yview                 = None
        self._yViewMQTTReader       = None
        self._running               = False
        self._devListenerList       = []       # A list of all the parties interested in receiving device data messages
        self._validProuctIDList     = []
        
    def close(self, halt=False):
        """@brief Close down the collector.
           @param halt If True When closed the collector will not restart."""
        if self._yview:
            self._yview.disconnect()
            self._yview = None

        if halt:
            self._running = False

    def start(self):
        """@brief Start the App server."""
        self._running = True
        while self._running:
            self._yview = YView(self._uio, self._config)
            try:
                mqttPort = self._yview.connect()
                self._yViewMQTTReader = YViewMQTTReader(self._uio, self._options, mqttPort, self._updateListeners)
                self._yViewMQTTReader.setValidProuctIDList(self._validProuctIDList)
                self._yViewMQTTReader.setSSHTunnelManager(self._yview.getSSHTunnelManager())
                mqttClient = self._yViewMQTTReader.startReading(self._mqttTopic)

                # Block here while we are connected to the YView ICONS MQTT server.
                while self._yview and self._yview.connected():
                    # Loop and block here for a period of time
                    mqttClient.loop(YViewMQTTReader.MQTT_LOOP_BLOCK_SECONDS)

            except KeyboardInterrupt:
                self.close()
                break

            except Exception as ex:
                self.close()
                self._uio.error(str(ex))
                self._uio.info("Waiting {} seconds before attempting to ICONS reconnect.".format(YViewCollector.RECONNECT_DELAY_SECS))
                sleep(YViewCollector.RECONNECT_DELAY_SECS)
                
    def addDevListener(self, devListener):
        """@brief Add to the list of entities that are interested in the device data.
           @param devListener The device listener (must implement the hear(devDict) method."""
        self._devListenerList.append(devListener)
        
    def removeAllListeners(self):
        """@brief Remove all listeners for device data."""
        self._devListenerList = []

    def _updateListeners(self, devData):
        """@brief Update all listeners with the device data."""
        for devListener in self._devListenerList:
            devListener.hear(devData)
            
    def getPortForwardingDict(self):
        """@brief Get a dict that details the localhost TCP ports forwarded to the remote device.
           @return A dict a dict that holds the Service Name = TCP port list for all the TCP ports forwarded from localhost to the remote device."""
        return self._yViewMQTTReader.getPortForwardingDict()
    
    def getForwardedPort(self, deviceName):
        """@brief Get the first TCP port forwarded from localhost to the device.
                  If the device only presents a service on one TCP port this can be used. 
                  If the device presents services on more than one TCP port then getPortForwardingDict() should be used.       
           @param deviceName The name of the device of interest.
           @return The TCP port forwarded from localhost to the device or -1 if no data has yet been received from 
                   the device detailing a port that the device is presenting a service on."""
        return self._yViewMQTTReader.getForwardedPort(deviceName)
    
    def setValidProuctIDList(self, validProductIDList):
        """@brief Set a list of product ID's that we're interested in.
           @param validProductIDList The list we're interested in."""
        self._validProuctIDList = validProductIDList
              
class LocalYViewCollector(BaseConstants):
    """@brief This collects data from YView devices on the local LAN only as opposed to connecting to the
              ICONS server and collecting data from there.
        - Sending out AYT messages
        - Forwarding device data to listeners."""

    UDP_SERVER_PORT = 29340
    
    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance."""
        self._uio                   = uio
        self._options               = options
        self._running               = False
        self._devListenerList       = []       # A list of all the parties interested in receiving device data messages
        self._validProuctIDList     = []
        self._areYouThereThread     = None
        self._deviceIPAddressList   = []

    def close(self, halt=False):
        """@brief Close down the collector.
           @param halt If True When closed the collector will not restart."""
        if self._areYouThereThread:
            self._areYouThereThread.stop()
            self._areYouThereThread = None

        if halt:
            self._running = False

    def start(self):
        """@brief Start the App server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', LocalYViewCollector.UDP_SERVER_PORT))
    
        self._uio.info('Sending AYT messages.')
        self._areYouThereThread = AreYouThereThread(sock)
        self._areYouThereThread.start()
    
        self._uio.info("Listening on UDP port %d" % (LocalYViewCollector.UDP_SERVER_PORT) )
        self._running = True
        while self._running:
            data = sock.recv(65536)
            #Ignore the message we sent
            if data != AreYouThereThread.AreYouThereMessage:
                try:
                    dataStr = data.decode()
                    rx_dict = json.loads(dataStr)
                    if BaseConstants.PRODUCT_ID in rx_dict:
                        prodID = rx_dict[BaseConstants.PRODUCT_ID]
                        if prodID in self._validProuctIDList:
                            self._updateListeners(rx_dict)
                            
                        if BaseConstants.IP_ADDRESS in rx_dict:
                            ipAddress = rx_dict[BaseConstants.IP_ADDRESS]
                            if ipAddress not in self._deviceIPAddressList:
                                self._uio.info(f"Found device on {ipAddress}")
                                self._deviceIPAddressList.append(ipAddress)

                except KeyboardInterrupt:
                    self.close()
                    break
    
                except Exception as ex:
                    raise
                
    def addDevListener(self, devListener):
        """@brief Add to the list of entities that are interested in the device data.
           @param devListener The device listener (must implement the hear(devDict) method."""
        self._devListenerList.append(devListener)
        
    def removeAllListeners(self):
        """@brief Remove all listeners for device data."""
        self._devListenerList = []

    def _updateListeners(self, devData):
        """@brief Update all listeners with the device data."""
        for devListener in self._devListenerList:
            devListener.hear(devData)
                
    def setValidProuctIDList(self, validProductIDList):
        """@brief Set a list of product ID's that we're interested in.
           @param validProductIDList The list we're interested in."""
        self._validProuctIDList = validProductIDList
        
class AreYouThereThread(Thread):
    """Class to are you there messages to devices"""

    AreYouThereMessage = "{\"AYT\":\"-!#8[dkG^v's!dRznE}6}8sP9}QoIR#?O&pg)Qra\"}"
    PERIODICITY_SECONDS = 1.0
    MULTICAST_ADDRESS   = "255.255.255.255"

    def __init__(self, sock):
        Thread.__init__(self)
        self._running = None
        self.setDaemon(True)

        self._sock = sock

    def run(self):
        self._running = True
        while self._running:
            try:
                self._sock.sendto(AreYouThereThread.AreYouThereMessage.encode(), (AreYouThereThread.MULTICAST_ADDRESS, LocalYViewCollector.UDP_SERVER_PORT))
            # If the local interface goes down this error will be generated. In this situation we want to keep trying to
            # send an AYT message in order to hear from Yview devices when the interface comes back up. This ensures the 
            # AYT messages continue to be sent if the house power drops for a short while as occurred recently.
            except OSError as ex:
                pass
            sleep(AreYouThereThread.PERIODICITY_SECONDS)
            
    def stop(self):
        """@brief Stop the server running."""
        self._running = False
              
    