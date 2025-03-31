from machine import Pin
from machine import Timer

import ubluetooth

from lib.hardware import Hardware

class BlueTooth():
    """@brief Thanks to the original author of this class which has been modified from the original.
              https://techtotinker.blogspot.com/2021/08/025-esp32-micropython-esp32-bluetooth.html"""

    MAX_RX_MESSAGE_SIZE = 256

    def __init__(self, name, ledGPIO=-1, debug=False):
        """@brief Constructor
           @param name The name of this bluetooth device.
           @param ledGPIO The GPIO ping to set to indicate bluetooth connected status.
           @param debug It True show some debug data."""
        self._led = None
        self._timer1 = None
        if ledGPIO >= 0:
            # Create internal objects for the onboard LED
            # blinking when no BLE device is connected
            # stable ON when connected
            self._led = Pin(ledGPIO, Pin.OUT)
            self._timer1 = Hardware.GetTimer()
        self._ble_connected = False
        self._rx_message = None
        self._debug = debug
        self._conn_handle = None

        self._name = name
        self._ble = ubluetooth.BLE()
        self._ble.active(True)
        self._disconnected()
        self._ble.irq(self._bleIRQ)
        self._register()
        self._advertiser()

    def setLED(self, on):
        """@brief Set the bluetooth status indicator LED if a GPIO pin was allocated for it.
           @param on LED on if True."""
        if self._led:
            self._led.value(on)

    def toggleLED(self):
        "@brief Toggle the state of the LED  if a GPIO pin was allocated for it."
        if self._led:
            self._led.value(not self._led.value())

    def _connected(self):
        """@bried Set the internal state as connected."""
        self._ble_connected = True
        self.setLED(True)
        if self._timer1 and self._led:
            self._timer1.deinit()

    def _disconnected(self):
        """@bried Set the internal state as disconnected."""
        self._ble_connected = False
        if self._timer1 and self._led:
            self._timer1.init(period=100, mode=Timer.PERIODIC, callback=lambda t: self._led.value(not self._led.value()))
        self._conn_handle = None

    def shutdown(self):
        """@brief Shutdown the bluetooth interface. After this has been called this
                  BlueTooth instance can not be used again. Another must be created
                  to use BlueTooth."""
        self._ble_connected = False
        if self._timer1:
            self._timer1.deinit()
            self._timer1 = None
        self._ble.active(False)
        self.setLED(False)

    def isEnabled(self):
        """@brief Determine if bluetooth is enabled.
           @return False if bluetooth is not enabled."""
        return self._ble.active()

    def isConnected(self):
        """@brief Get the connected state. True = connected."""
        return self._ble_connected

    def _bleIRQ(self, event, data):
        """@brief The bluetooth IRQ handler."""
        if event == 1: #_IRQ_CENTRAL_CONNECT:
                       # A central has connected to this peripheral
            self._conn_handle, addr_type, addr = data
            self._connected()

        elif event == 2: #_IRQ_CENTRAL_DISCONNECT:
                         # A central has _disconnected from this peripheral.
            self._disconnected()
            self._advertiser()

        elif event == 3: #_IRQ_GATTS_WRITE:
                         # A client has written to this characteristic or descriptor.
            buffer = self._ble.gatts_read(self.rx)
             self._rx_message = buffer.decode('UTF-8').strip()
            if self._debug:
                print(f"self._rx_message = {self._rx_message}")

        else:
            if self._debug:
                print("Unknown event")

    def getRxMessage(self):
        """@return The message received or None if no message received."""
        msg = self._rx_message
        self._rx_message = None
        return msg

    def _register(self):
        """@brief Register the bluetooth service as a UART."""
        # Nordic UART Service (NUS)
        NUS_UUID = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
        RX_UUID = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'
        TX_UUID = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'

        BLE_NUS = ubluetooth.UUID(NUS_UUID)
        BLE_RX = (ubluetooth.UUID(RX_UUID), ubluetooth.FLAG_WRITE)
        BLE_TX = (ubluetooth.UUID(TX_UUID), ubluetooth.FLAG_NOTIFY)

        BLE_UART = (BLE_NUS, (BLE_TX, BLE_RX,))
        SERVICES = (BLE_UART, )
        ((self.tx, self.rx,), ) = self._ble.gatts_register_services(SERVICES)
        self._ble.gatts_set_buffer(self.rx, BlueTooth.MAX_RX_MESSAGE_SIZE)

    def send(self, data):
        """@brief Send data to a connected bluetooth device."""
        self._ble.gatts_notify(self._conn_handle, self.tx, data + '\n')

    def _advertiser(self):
        name = bytes(self._name, 'UTF-8')
        adv_data = bytearray('\x02\x01\x06', 'UTF-8') + bytearray((len(name) + 1, 0x09)) + name
        try:
            self._ble.gap_advertise(100000, adv_data)
            if self._debug:
                print(adv_data)
                print("\r\n")
                        # adv_data
                        # raw: 0x02010209094553503332424C45
                        # b'\x02\x01\x02\t\tESP32BLE'
                        #
                        # 0x02 - General discoverable mode
                        # 0x01 - AD Type = 0x01
                        # 0x02 - value = 0x02

                        # https://jimmywongiot.com/2019/08/13/advertising-payload-format-on-ble/
                        # https://docs.silabs.com/bluetooth/latest/general/adv-and-scanning/bluetooth-adv-data-basics

        # When the bluetooth interface is disabled an 'OSError: [Errno 19] ENODEV' error will occur.
        except OSError:
            pass
