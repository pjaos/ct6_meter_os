
class BaseConstants(object):
    """@brief define the constants that are useful across projects."""

    # Set this to False for production code as it stops messages on stdout 
    # which will reduce CPU blocking as messages are sent on the serial port.
    SHOW_MESSAGES_ON_STDOUT     = True

    FIRMWARE_VERSION            = "1.0"     # Override this in subclass for the device 

    WIFI_SETUP_BUTTON_PIN       = -1        # This should be set to a valid GPIO in a subclass
                                            # The GPIO pin that sets the WiFi parameters to unset.
                                            # The android app should be used to setup the WiFi when unset.
                                            # When the button is pressed this pin should be pulled low.
                                            # Typically GPIO 0 on an esp32 MCU.
                                            # Typically GPIO 14 on a RPi pico W MCU.

    BLUETOOTH_LED_PIN           = -1        # This should be set to a valid GPIO in a subclass
                                            # A GPIO pin to indicate bluetooth is connected (-1 = not used).
                                            # This flashes when not connected and turns solid on when connected.
                                            # Turns off when bluetooth is disabled.
                                            # Typically GPIO 26 on an esp32 MCU.
                                            # Typically GPIO 15 on a RPi pico W MCU.

    WIFI_LED_PIN                = -1        # This should be set to a valid GPIO in a subclass
                                            # The GPIO pin connected to the WiFi indicator LED (-1 = not used).
                                            # This flashes when not connected and turns solid on when connected to a WiFi network.
                                            # Typically GPIO 2 on an esp32 MCU.
                                            # Typically GPIO 16 on a RPi pico W MCU.

    POWER_CYCLE_GPIO            = -1        # This should be set to a valid GPIO in a subclass
                                            # The GPIO pin that when asserted will power down the MCU.
                                            # If set to -1 then this options is disabled.
                                            # This should only be set if your hardware has a GPIO pin connected to hardware
                                            # that will power cycle the unit.

    INITIAL_CPU_FREQ_HZ         = 160000000
    # The max CPU clock frequency. This will be during boot. Set to -1 to disable
    # and leave the CPU clock at the above frequency.
    # 240 MHz appears to work on pico W and esp32 hardware.
    MAX_CPU_FREQ_HZ             = 240000000

    MAX_STA_WAIT_REG_SECONDS     = 60       # The MAX time to wait for an STA to register.
                                            # After this time has elapsed the unit will either reboot
                                            # or if the hardware has the capability, power cycle itself.

    WIFI_ACTIVE_TIMEOUT_SECONDS = 10

    SHOW_RAM_POLL_SECS          = 5
    WDT_TIMEOUT_MSECS           = 8300 # Note that 8388 is the max WD timeout value on pico W hardware.

    # --- END CONSTANTS ---

    # --- START CONFIG ---

    ASSY_KEY                    = 'ASSY'

    YDEV_UNIT_NAME_KEY          = "YDEV_UNIT_NAME"      # The name the user wishes to give the unit
    YDEV_PRODUCT_ID_KEY         = "YDEV_PRODUCT_ID"     # The product ID. E.G the model number. This is not writable as not write code is present in cmd_handler.
    YDEV_DEVICE_TYPE_KEY        = "YDEV_DEVICE_TYPE"    # The type of device of the unit. This is not writable as not write code is present in cmd_handler.
    YDEV_SERVICE_LIST_KEY       = "YDEV_SERVICE_LIST"   # A comma separated list of <service name>:<TCPIP port> that denote the service supported (E.G WEB:80). This is not writable as not write code is present in cmd_handler.
    YDEV_GROUP_NAME_KEY         = "YDEV_GROUP_NAME"
    YDEV_AYT_TCP_PORT_KEY       = "YDEV_AYT_TCP_PORT_KEY"
    
    WIFI_KEY                    = "WIFI"
    WIFI_CONFIGURED_KEY         = "WIFI_CFG"
    MODE_KEY                    = "MODE"
    SSID_KEY                    = "SSID"
    PASSWORD_KEY                = "PASSWD"
    AP_MODE                     = "AP"
    STA_MODE                    = "STA"
    AP_CHANNEL                  = "CHANNEL"

    BT_NAME                     = "YDEV"
    YDEV_OS_KEY                 = "YDEV_OS"

    BLUETOOTH_ON_KEY            = "BLUETOOTH_ON_KEY"
    RUNNING_APP_KEY             = None # This gets set in _updateActiveApp()

     
    POLL_SECONDS                = 0.1 # How often the serviceRunningMode() method in the ThisMachine instance (project.py) is called.
    # --- START Constants used by this machine type ---
                
    # This serves as a starting point for the unit configuration
    # A machine is likely to add to this in its Constants subclass.
    DEFAULT_CONFIG = {

        # Assy label for the product
        # ASYXXXX_VYY.YY_ZZZZZZ.
        # XXXX  = Board assembly number
        # YY.YY = The version of the assembly number.
        # ZZZZZZ = The serial number of the hardware.
        ASSY_KEY:                       "ASY0197_V01.30_000000",
    
        YDEV_UNIT_NAME_KEY:             "",
        YDEV_PRODUCT_ID_KEY:            "CT6",
        YDEV_DEVICE_TYPE_KEY:           "6_CHNL_CT_SENSOR",
        YDEV_SERVICE_LIST_KEY:          "WEB:80",
        YDEV_AYT_TCP_PORT_KEY:          2934,               # The UDP port we expect to receive an AYT UDP broadcast message
        YDEV_GROUP_NAME_KEY:            "",
        YDEV_OS_KEY:                    "micropython",
        BLUETOOTH_ON_KEY:               1,
        WIFI_KEY: {
                WIFI_CONFIGURED_KEY:    0,
                MODE_KEY:               AP_MODE,
                AP_CHANNEL:             3,
                SSID_KEY:               BT_NAME,
                PASSWORD_KEY:           "12345678"
                },
     }

    #An example of the attributes in the above configuration the you wish to be setable via the REST interface.
    SETABLE_ATTRIBUTE_LIST      = (YDEV_UNIT_NAME_KEY,
                                   YDEV_GROUP_NAME_KEY,
                                   ASSY_KEY,                                   
                                  )

    # --- END CONFIG ---