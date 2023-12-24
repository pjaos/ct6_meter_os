import socket
import json
import uasyncio as asyncio

from lib.uo import UOBase
from lib.wifi import WiFi

from constants import Constants

class YDev(UOBase):
    """brief A Yview device implementation using micro python.
             See https://github.com/pjaos/yview for more information on the YView IoT architecture."""

    UDP_RX_BUFFER_SIZE       = 2048 # The maximum AYT message size.
    AYT_KEY                  = "AYT" # The key in the received JSON message.
    ID_STRING                = "-!#8[dkG^v\'s!dRznE}6}8sP9}QoIR#?O&pg)Qra" # The AYT key in the RX'ed JSON
                                                                           # message must hold this value in
                                                                           # order to send a response to let the
                                                                           # YView gateway know the device details.

    # These are the attributes for the AYT response message
    IP_ADDRESS_KEY           = "IP_ADDRESS"   # The IP address of this device
    OS_KEY                   = "OS"           # The operating system running on this device
    UNIT_NAME_KEY            = "UNIT_NAME"    # The name of this device.
    DEVICE_TYPE_KEY          = "DEVICE_TYPE"  # The type of this device.
    PRODUCT_ID_KEY           = "PRODUCT_ID"   # The product name for this device.
    SERVICE_LIST_KEY         = "SERVICE_LIST" # Details of the services provided by this device (E.G WEB:80)
    GROUP_NAME_KEY           = "GROUP_NAME"   # The group name for the device. Left unset if not restricted access is needed.

    POWER_WATTS_KEY          = "POWER_WATTS_KEY"

    def __init__(self, machineConfig, uo=None):
        """@brief Constructor.
           @param machineConfig The machine config that has details of the data to be returned in AYT response messages.
           @param uo A UO instance or None if no user output messages are needed."""
        super().__init__(uo=uo)
        self._machineConfig = machineConfig
        self._yDevAYTPort = self._machineConfig.get(Constants.YDEV_AYT_TCP_PORT_KEY)
        self._running = False
        self._getParamsMethod = None
        self.listen()
                    
    def _send_response(self, sock, remoteAddressPort):
        """@brief sock The UDP socket to send the response on.
           @param remoteAddressPort A tuple containing the address and port to send the response to."""
        # Ge the current WiFi interface IP address (if we have one) to send in the AYT response.
        address = WiFi.GetWifiAddress()
        jsonDict = {}
        jsonDict[YDev.IP_ADDRESS_KEY]    = address
        jsonDict[YDev.OS_KEY]            = self._machineConfig.get(Constants.YDEV_OS_KEY)
        jsonDict[YDev.UNIT_NAME_KEY]     = self._machineConfig.get(Constants.YDEV_UNIT_NAME_KEY)
        jsonDict[YDev.PRODUCT_ID_KEY]    = self._machineConfig.get(Constants.YDEV_PRODUCT_ID_KEY)
        jsonDict[YDev.DEVICE_TYPE_KEY]   = self._machineConfig.get(Constants.YDEV_DEVICE_TYPE_KEY)
        jsonDict[YDev.SERVICE_LIST_KEY]  = self._machineConfig.get(Constants.YDEV_SERVICE_LIST_KEY)
        jsonDict[YDev.GROUP_NAME_KEY]    = self._machineConfig.get(Constants.YDEV_GROUP_NAME_KEY)
        if self._getParamsMethod is not None:
            # !!! If this method blocks it will delay the AYT message response
            paramsDict = self._getParamsMethod()
            for key in paramsDict.keys():
                jsonDict[key] = paramsDict[key]
        
        jsonDictStr = json.dumps( jsonDict )
        self._debug("AYT response message: {}".format(jsonDictStr))
        sock.sendto( jsonDictStr.encode(), remoteAddressPort)
        self._debug("Sent above message to {}:{}".format(remoteAddressPort[0],remoteAddressPort[1]))

    def setGetParamsMethod(self, getParamsMethod):
        """@brief Set reference to a method that will retrieve parameters to be included in the AYT response message."""
        self._getParamsMethod = getParamsMethod
        
    async def listen(self):
        """@brief Listen for YVIEW AYT messages and send responses when received."""
        # Open UDP socket to be used for discovering devices
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self._yDevAYTPort))
        sock.setblocking(False)
        self._running = True
        while self._running:
            try:
                rxData, addressPort = sock.recvfrom(YDev.UDP_RX_BUFFER_SIZE)
                rxDict = json.loads(rxData)
                if YDev.AYT_KEY in rxDict:
                    id_str = rxDict[YDev.AYT_KEY]
                    if id_str == YDev.ID_STRING:
                        self._send_response(sock, addressPort)
            except:
                # We get here primarily when no data is present on the socket
                # when recvfrom is called.
                await asyncio.sleep(0.1)
