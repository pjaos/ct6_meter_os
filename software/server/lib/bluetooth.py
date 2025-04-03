import asyncio
import inspect
import json
from time import time
from bleak import BleakClient, BleakScanner, BleakError

class BlueTooth(object):
    """@brief Responsible for communication with a device via bluetooth.
              Bluetooth has to be enabled on the local machine and the device
              for this to work."""

    @staticmethod
    async def _IsBluetoothEnabled():
        """@brief Check if Bluetooth is available on the local machine.
           @return True is bluetooth is enabled/available."""
        try:
            await BlueTooth._Scan(0.1)
            return True
        except BleakError as ex:
            if 'No Bluetooth adapters found.' in str(ex):
                return False
            raise ex  # Re-raise if it's a different error

    @staticmethod
    def IsBluetoothEnabled():
        """@brief Check if Bluetooth is available on the local machine.
           @return True is bluetooth is enabled/available."""
        return asyncio.run(BlueTooth._IsBluetoothEnabled())

    @staticmethod
    async def _Scan(seconds):
        """@brief Scan for bluetooth devices.
           @param seconds The number of seconds to scan for.
           @return A list of bluetooth devices found."""
        return await BleakScanner.discover(timeout=seconds)

    @staticmethod
    def Scan(seconds=5, dev_filter_string=None):
        """@brief Scan for bluetooth devices.
           @param dev_filter_string If True then only bluetooth devices that
                  start with this string are included in the bluetooth device list.
           @param seconds The number of seconds to scan for.
           @return A list of bluetooth devices."""
        device_list = []
        dev_list = asyncio.run(BlueTooth._Scan(seconds))
        if dev_filter_string:
            for device in dev_list:
                if device.name.startswith(dev_filter_string):
                    device_list.append(device)
        else:
            device_list = dev_list
        return device_list

    def __init__(self, uio=None, rx_timeout_seconds=10, rx_finished_timeout_seconds=0.2):
        self._uio = uio
        self._rx_list = []
        # If we received no data over bluetooth we wait this long.
        self._rx_timeout_seconds = rx_timeout_seconds
        # Once we start receiving data over bluetooth this timeout must occur before we stop listening.
        self._rx_finished_timeout_seconds = rx_finished_timeout_seconds
        # For recording an exception generated in the async env to be reported in the sync env
        self.exception = None

    def debug(self, msg):
        """@brief display a debug message if a UIO instance was passed in the constructor.
           @param msg The text message to be displayed."""
        if self._uio:
            self._uio.debug(msg)

    async def _notification_handler(self, sender, data):
        """@brief Called when data is received over a bluetooth connection in order to record it."""
        self._rx_list.append(data.decode())

    def _raise_exception_on_error(self):
        """@brief If an error/exception has occurred in the async env raise it in the sync env."""
        ex = self.get_exception()
        if ex:
            raise ex

    def _set_exception(self, exception):
        """@brief Set an error instance.
           @param exception The error instance."""
        self._exception = exception

    def get_exception(self):
        """@return An exception instance if an error has occurred. If no error has occurred then None is returned."""
        return self.exception

    def clear_exception(self):
        """@brief May be called to clear an exception if one has occurred."""
        self.exception = None

    def _clear_rx_list(self):
        """@brief Clear the list that holds messages received over the bluetooth interface."""
        # Clear the RX data buffer
        self._rx_list.clear()

    async def _waitfor_response(self, client, clear_rx_list= True):
        """@brief Waitfor a response to a previously command previously sent over the bluetooth interface.
           @param client A connected BleakClient.
           @param clear_rx_list If True the self._rx_list is cleared before we start listening for bluetooth data."""
        if clear_rx_list:
            self._clear_rx_list()

        try:
            self.debug(f"{inspect.currentframe().f_code.co_name}: Waiting for RX data.")
            start_time = time()
            while True:
                await asyncio.sleep(0.25)
                # We have started receiving some data
                if self._rx_list:
                    self.debug(f"{inspect.currentframe().f_code.co_name}: Some data received.")
                    break

                if time() >= start_time + self._rx_timeout_seconds:
                    raise Exception(f"No data received for {self._rx_timeout_seconds} seconds.")

            self.debug(f"{inspect.currentframe().f_code.co_name}: Waiting for RX data.")
            msg_count = len(self._rx_list)
            last_msg_count = msg_count
            last_rx_time = time()
            while True:
                await asyncio.sleep(0.25)
                # We have started receiving some data
                if self._rx_list:
                    self.debug(f"{inspect.currentframe().f_code.co_name}: Some data received.")
                    break

                msg_count = len(self._rx_list)
                if msg_count > last_msg_count:
                    last_msg_count = msg_count
                    last_rx_time = time()

                # We've stopped receiving bluetooth data so exit
                elif time() > last_rx_time + self._rx_timeout_seconds:
                    break

                if time() >= start_time + self._rx_timeout_seconds:
                    raise Exception("Timeout waiting for bluetooth data reception to cease.")

        except Exception as ex:
            self.debug(f"{inspect.currentframe().f_code.co_name}: Error: {str(ex)}")
            self.exception = ex

        finally:
            await client.stop_notify(CT6BlueTooth.NOTIFY_UUID)

        return self._rx_list

class CT6BlueTooth(BlueTooth):
    """@brief Responsible for communication with a CT6 device via bluetooth.
              Bluetooth has to be enabled on the local machine and CT6 device
              for this to work. To enable Bluetooth on a CT6 device hold the
              Wifi button down until the CT6 unit reboots and the blue and
              green led's flash."""

    WRITE_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Replace with actual UUID
    NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"      # Notification UUID

    WIFI_SCAN_CMD = b'{"CMD": "WIFI_SCAN"}'
    GET_IP_CMD = b'{"CMD": "GET_IP"}'
    DISABLE_BLUETOOTH = b'{"CMD": "DISABLE_BT"}'

    SSID = 'SSID'
    PASSWORD = 'PASSWD'
    SETUP_WIFI_CMD_DICT = {'CMD': 'BT_CMD_STA_CONNECT', f'{SSID}': '', f'{PASSWORD}': ''}

    IP_ADDRESS = "IP_ADDRESS"

    YDEV = "YDEV"

    @staticmethod
    def ScanCT6(seconds=5):
        """@brief Scan for bluetooth devices.
           @param dev_filter_string If True then only bluetooth devices that
                  start with this string are included in the bluetooth device list.
           @param seconds The number of seconds to scan for.
           @return A list of bluetooth devices."""
        return CT6BlueTooth.Scan(seconds=seconds, dev_filter_string=CT6BlueTooth.YDEV)

    def __init__(self, uio=None):
        super().__init__(uio=uio)

    async def _wifi_scan(self, address):
        """@brief Send a cmd to the CT6 unit to get it to scan for WiFi networks that it can see.
           @param address The bluetooth address of the device.
           @return A list of strings detailing the network parameters."""
        try:
            async with BleakClient(address) as client:
                self.debug(f"{inspect.currentframe().f_code.co_name}: Connected to {address}")

                await client.start_notify(CT6BlueTooth.NOTIFY_UUID, self._notification_handler)
                self.debug(f"{inspect.currentframe().f_code.co_name}: started RX data notifier.")

                data = CT6BlueTooth.WIFI_SCAN_CMD
                await client.write_gatt_char(CT6BlueTooth.WRITE_CHAR_UUID, data, response=True)
                self.debug(f"{inspect.currentframe().f_code.co_name}: Data written: {data}")

                await self._waitfor_response(client)

        except Exception as e:
            self._set_exception(e)

        return self._rx_list

    def wifi_scan(self, address):
        """@brief Send a cmd to the CT6 unit to get it to scan for WiFi networks that
                  it can see.
           @param address The bluetooth address of the device.
           @return A list of dicts. Each dict contains the following keys.
                  RSSI,
                  HIDDEN,
                  SSID,
                  CHANNEL,
                  BSSID
                  SECURITY
        """
        line_list = asyncio.run(self._wifi_scan(address))
        self._raise_exception_on_error()
        dict_list = []
        for line in line_list:
            try:
                dict_list.append(json.loads(line))
            except json.decoder.JSONDecodeError:
                pass
        return dict_list

    async def _setup_wifi(self, address, ssid, password):
        """@brief Set the WiFi SSID and password for the CT6 device.
           @param address The bluetooth address of the device.
           @param ssid The WiFi SSID.
           @param password The WiFi password."""
        try:
            async with BleakClient(address) as client:
                self.debug(f"{inspect.currentframe().f_code.co_name}: Connected to {address}")

                CT6BlueTooth.SETUP_WIFI_CMD_DICT[CT6BlueTooth.SSID] = ssid
                CT6BlueTooth.SETUP_WIFI_CMD_DICT[CT6BlueTooth.PASSWORD] = password
                cmd_str = json.dumps(CT6BlueTooth.SETUP_WIFI_CMD_DICT)

                data = cmd_str.encode()
                await client.write_gatt_char(CT6BlueTooth.WRITE_CHAR_UUID, data, response=True)
                self.debug(f"{inspect.currentframe().f_code.co_name}: Data written: {data}")

        except Exception as e:
            self._set_exception(e)

        return self._rx_list

    def setup_wifi(self, address, ssid, password):
        """@brief Set the WiFi SSID and password for the CT6 device.
           @param address The bluetooth address of the device.
           @param ssid The WiFi SSID.
           @param password The WiFi password."""
        response = asyncio.run(self._setup_wifi(address, ssid, password))
        self._raise_exception_on_error()
        return response

    def waitfor_device(self, address, timeout=30):
        """@brief Waitfor a CT6 device to appear.
           @param timeout The number of seconds before we give up looking.
           @return The Bluetooth device found or None if not found."""
        dev_found = None
        start_time = time()
        waiting = True
        while waiting:
            dev_list = CT6BlueTooth.Scan(seconds=3)
            for dev in dev_list:
                if dev.address == address:
                    dev_found = dev
                    waiting = False
                    break

            # Quit on timeout
            if time() >= start_time + timeout:
                break

        return dev_found

    async def _get_ip(self, address):
        """@brief Get the IP address of the CT6 device. This is only useful after setup_wifi() has been called.
           @param address The bluetooth address of the device.
           @return The IP address of the device."""
        ip_address = None
        try:
            async with BleakClient(address) as client:
                self.debug(f"{inspect.currentframe().f_code.co_name}: Connected to {address}")

                await client.start_notify(CT6BlueTooth.NOTIFY_UUID, self._notification_handler)
                self.debug(f"{inspect.currentframe().f_code.co_name}: started RX data notifier.")

                data = CT6BlueTooth.GET_IP_CMD
                await client.write_gatt_char(CT6BlueTooth.WRITE_CHAR_UUID, data, response=True)
                self.debug(f"{inspect.currentframe().f_code.co_name}: Data written: {data}")

                await self._waitfor_response(client)

                if self._rx_list:
                    line = self._rx_list[0].rstrip('\r\n')
                    rx_dict = json.loads(line)
                    if CT6BlueTooth.IP_ADDRESS in rx_dict:
                        ip_address = rx_dict[CT6BlueTooth.IP_ADDRESS]

        except Exception as e:
            self._set_exception(e)

        return ip_address

    def get_ip(self, address):
        """@brief Get the IP address of the CT6 device. This is only useful after setup_wifi() has been called.
           @param address The bluetooth address of the device.
           @return The IP address of the device."""
        response = asyncio.run(self._get_ip(address))
        self._raise_exception_on_error()
        return response

    async def _disable_bluetooth(self, address):
        """@brief Disable the bluetooth interface on the CT6 device.
                  To enable bluetooth on the CT6 device the WiFi switch
                  must be held down until the device restarts."""
        try:
            async with BleakClient(address) as client:
                self.debug(f"{inspect.currentframe().f_code.co_name}: Connected to {address}")

                data = CT6BlueTooth.DISABLE_BLUETOOTH
                await client.write_gatt_char(CT6BlueTooth.WRITE_CHAR_UUID, data, response=True)
                self.debug(f"{inspect.currentframe().f_code.co_name}: Data written: {data}")

        except Exception as e:
            self._set_exception(e)

        return self._rx_list

    def disable_bluetooth(self, address):
        """@brief Disable the bluetooth interface on the CT6 device.
                  To enable bluetooth on the CT6 device the WiFi switch
                  must be held down until the device restarts."""
        asyncio.run(self._disable_bluetooth(address))
        self._raise_exception_on_error()

"""

# Example to setup CT6 WiFi

class UIO():
    # @brief Example UIO class.
    def info(self, msg):
        print(f"INFO:  {msg}")

    def debug(self, msg):
        print(f"DEBUG: {msg}")

uio = UIO()

ct6BlueTooth = CT6BlueTooth(uio=None)

if CT6BlueTooth.IsBluetoothEnabled():

    dev_list = CT6BlueTooth.ScanCT6()
    if dev_list:
        dev = dev_list[0]
        print(f"Found: {dev}. WiFi scan in progress...")
        network_dicts = ct6BlueTooth.wifi_scan(dev.address)
        print("Setting up WiFi")
        lines = ct6BlueTooth.setup_wifi(dev.address, 'YOURSSID', 'YOURPASSWORD')
        for l in lines:
            print(l)
        print(f"Waiting for CT6 device ({dev.address}) to restart.")
        ct6BlueTooth.waitfor_device(dev.address)

        ip_address = ct6BlueTooth.get_ip(dev.address)
        print(f"ip_address={ip_address}")

        ct6BlueTooth.disable_bluetooth(dev.address)

    else:
        print("No CT6 devices detected over bluetooth.")

else:
    print("Bluetooth is not available. Please enable bluetooth.")

"""