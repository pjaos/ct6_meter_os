from lib.base_constants import BaseConstants

class Constants(BaseConstants):
    """@brief Define the constants used by this project.
              This extends BaseContants to make a more specialised configuration for this machine."""

    FIRMWARE_VERSION            = "2.3"

    # Override the BaseConstants GPIO pins to those connected on this hardware
    WIFI_SETUP_BUTTON_PIN       = 14
    BLUETOOTH_LED_PIN           = 15
    WIFI_LED_PIN                = 16
    POWER_CYCLE_GPIO            = 13

    VALID_CT_ID_LIST            = (1,2,3,4,5,6)

    TEMP_ADC_PIN                = 28        # The pin connected to the on board MCP9700 temperature sensor.
    ADC_CODES_TO_MV             = 19757.69 # Arrived at empirically by measuring the ADC voltage @ 24C
    MCP9700_VOUT_0C             = 0.5
    MCP9700_TC                  = 0.01

    ATM90E32_SPI_CLK_PIN        = 2         # The SPI clock pin used to communicate with all ATM90E32 devices
    ATM90E32_SPI_MOSI_PIN       = 3         # The SPI MOSI pin used to communicate with all ATM90E32 devices
    ATM90E32_SPI_MISO_PIN       = 4         # The SPI MISO pin used to communicate with all ATM90E32 devices
    ATM90E32_CS0_PIN            = 5         # The SPI chip select connected to the first ATM90E32 device.
    ATM90E32_CS4_PIN            = 22        # The SPI chip select connected to the second ATM90E32 device.

    ATM90E32_PGA_GAIN           = 4

    NAME                        = "NAME"
    IRMS                        = "IRMS"
    IPEAK                       = "IPEAK"
    VRMS                        = "VRMS"
    PRMS                        = 'PRMS'
    PREACT                      = "PREACT"
    PAPPARENT                   = "PAPPARENT"
    PF                          = "PF"
    TEMP                        = "TEMP"
    FREQ                        = "FREQ"

    RSSI                        = "RSSI"
    BOARD_TEMPERATURE           = "BOARD_TEMPERATURE"
    # --- START CONFIG SECTION ---

    FIRMWARE_VERSION_STR        = "FIRMWARE_VERSION"

    CT1_IGAIN_KEY               = "CT1_IGAIN"
    CT2_IGAIN_KEY               = "CT2_IGAIN"
    CT3_IGAIN_KEY               = "CT3_IGAIN"
    CT4_IGAIN_KEY               = "CT4_IGAIN"
    CT5_IGAIN_KEY               = "CT5_IGAIN"
    CT6_IGAIN_KEY               = "CT6_IGAIN"

    CT1_IOFFSET_KEY             = "CT1_IOFFSET"
    CT2_IOFFSET_KEY             = "CT2_IOFFSET"
    CT3_IOFFSET_KEY             = "CT3_IOFFSET"
    CT4_IOFFSET_KEY             = "CT4_IOFFSET"
    CT5_IOFFSET_KEY             = "CT5_IOFFSET"
    CT6_IOFFSET_KEY             = "CT6_IOFFSET"

    CT1_TYPE_KEY                = "CT1_TYPE"
    CT2_TYPE_KEY                = "CT2_TYPE"
    CT3_TYPE_KEY                = "CT3_TYPE"
    CT4_TYPE_KEY                = "CT4_TYPE"
    CT5_TYPE_KEY                = "CT5_TYPE"
    CT6_TYPE_KEY                = "CT6_TYPE"

    CT1_NAME_KEY                = "CT1_NAME"
    CT2_NAME_KEY                = "CT2_NAME"
    CT3_NAME_KEY                = "CT3_NAME"
    CT4_NAME_KEY                = "CT4_NAME"
    CT5_NAME_KEY                = "CT5_NAME"
    CT6_NAME_KEY                = "CT6_NAME"

    CT1_KEY                     = "CT1"
    CT2_KEY                     = "CT2"
    CT3_KEY                     = "CT3"
    CT4_KEY                     = "CT4"
    CT5_KEY                     = "CT5"
    CT6_KEY                     = "CT6"

    CS0_VOLTAGE_GAIN_KEY        = "CS0_VOLTAGE_GAIN"
    CS4_VOLTAGE_GAIN_KEY        = "CS4_VOLTAGE_GAIN"

    ZERO_POWER_GATE_WATTS_KEY   = "ZERO_POWER_GATE_WATTS"

    TYPE_KEY                    = "TYPE"

    SCT013_100A_SENSOR_TYPE     = "SCT013_100A"

    LINE_FREQ_HZ_KEY            = "LINE_FREQ_HZ"

    READ_TIME_NS_KEY            = "READ_TIME_NS"

    RSSI_KEY                    = "RSSI"

    BOARD_TEMPERATURE_KEY       = "BOARD_TEMPERATURE"

    CS0_VOLTAGE_OFFSET          = "CS0_VOLTAGE_OFFSET"

    CS4_VOLTAGE_OFFSET          = "CS4_VOLTAGE_OFFSET"

    ACTIVE                      = "ACTIVE"

    FACTORY_CONFIG_KEYS = [BaseConstants.ASSY_KEY,
                           
                           CS0_VOLTAGE_GAIN_KEY,
                           CS4_VOLTAGE_GAIN_KEY,
                           
                           CT1_IGAIN_KEY,
                           CT2_IGAIN_KEY,
                           CT3_IGAIN_KEY,
                           CT4_IGAIN_KEY,
                           CT5_IGAIN_KEY,
                           CT6_IGAIN_KEY,
                           
                           CT1_IOFFSET_KEY,
                           CT2_IOFFSET_KEY,
                           CT3_IOFFSET_KEY,
                           CT4_IOFFSET_KEY,
                           CT5_IOFFSET_KEY,
                           CT6_IOFFSET_KEY
                           
                           ]
        
    # Override the Constants.DEFAULT_CONFIG
    DEFAULT_CONFIG = {

        # Assy label for the product
        # ASYXXXX_VYY.YY_ZZZZZZ.
        # XXXX  = Board assembly number
        # YY.YY = The version of the assembly number.
        # ZZZZZZ = The serial number of the hardware.
        BaseConstants.ASSY_KEY:                     "ASY0197_V00.0000_SN00000000",

        BaseConstants.YDEV_UNIT_NAME_KEY:           "",
        BaseConstants.YDEV_PRODUCT_ID_KEY:          "CT6",
        BaseConstants.YDEV_DEVICE_TYPE_KEY:         "6_CHNL_CT_SENSOR",
        BaseConstants.YDEV_SERVICE_LIST_KEY:        "WEB:80",
        BaseConstants.YDEV_GROUP_NAME_KEY:          "",
        BaseConstants.YDEV_OS_KEY:                  "micropython",
        BaseConstants.YDEV_AYT_TCP_PORT_KEY:        29340,                    # We expect CT6 devices to respond to YDEV AYT messages on this port
        BaseConstants.BLUETOOTH_ON_KEY:             1,
        BaseConstants.WIFI_KEY: {
                BaseConstants.WIFI_CONFIGURED_KEY:  0,
                BaseConstants.MODE_KEY:             BaseConstants.AP_MODE,
                BaseConstants.AP_CHANNEL:           3,
                BaseConstants.SSID_KEY:             BaseConstants.BT_NAME,
                BaseConstants.PASSWORD_KEY:         "12345678"
                },

        # This is a good starting point for the calibration of current using SCT013 100A 1V sensors
        CT1_IGAIN_KEY:                  10734,
        CT2_IGAIN_KEY:                  10734,
        CT3_IGAIN_KEY:                  10734,
        CT4_IGAIN_KEY:                  10734,
        CT5_IGAIN_KEY:                  10734,
        CT6_IGAIN_KEY:                  10734,

        CT1_IOFFSET_KEY:                0,
        CT2_IOFFSET_KEY:                0,
        CT3_IOFFSET_KEY:                0,
        CT4_IOFFSET_KEY:                0,
        CT5_IOFFSET_KEY:                0,
        CT6_IOFFSET_KEY:                0,

        CT1_TYPE_KEY:                   SCT013_100A_SENSOR_TYPE,
        CT2_TYPE_KEY:                   SCT013_100A_SENSOR_TYPE,
        CT3_TYPE_KEY:                   SCT013_100A_SENSOR_TYPE,
        CT4_TYPE_KEY:                   SCT013_100A_SENSOR_TYPE,
        CT5_TYPE_KEY:                   SCT013_100A_SENSOR_TYPE,
        CT6_TYPE_KEY:                   SCT013_100A_SENSOR_TYPE,

        CT1_NAME_KEY:                   "",
        CT2_NAME_KEY:                   "",
        CT3_NAME_KEY:                   "",
        CT4_NAME_KEY:                   "",
        CT5_NAME_KEY:                   "",
        CT6_NAME_KEY:                   "",

        # This is a good starting point for the calibration of voltage
        CS0_VOLTAGE_GAIN_KEY:           49871,
        CS4_VOLTAGE_GAIN_KEY:           49871,

        # The measured power where we assume that the power is zero. The zero power gate level.
        # This can be set to 0. If so then a residual power of ~ 0.4W will be returned. This
        # can be tracked out by calibrating the voltage and current gains and offsets.
        # Currently this is not done as the ATM90E32 devices appear pretty accurate
        # without calibration.
        ZERO_POWER_GATE_WATTS_KEY:      0.5,

        LINE_FREQ_HZ_KEY:               50,

        CS0_VOLTAGE_OFFSET:             61440,
        CS4_VOLTAGE_OFFSET:             61440,

        ACTIVE:                         0           # If 1 then the unit is active and ct6_db_store.py will create a database and update
                                                    # the database with data received from this device.
                                                    # The default is set to 0. This is so that databases are not created unless the
                                                    # device has been enabled for this. This allows units to be added to a WiFi
                                                    # network but not cause database updates which is useful for development purposes.
                                                    # ct6_tool.py can be used to set the ACTIVE flag. When set this causes the databases
                                                    # to be created and updated by ct6_db_store.py.

     }

    #Define the attributes in the above configuration the you wish to be setable via the REST interface for this machine.
    SETABLE_ATTRIBUTE_LIST      = (BaseConstants.YDEV_UNIT_NAME_KEY,
                                   BaseConstants.YDEV_GROUP_NAME_KEY,

                                   BaseConstants.ASSY_KEY,

                                   CT1_IGAIN_KEY,
                                   CT2_IGAIN_KEY,
                                   CT3_IGAIN_KEY,
                                   CT4_IGAIN_KEY,
                                   CT5_IGAIN_KEY,
                                   CT6_IGAIN_KEY,

                                   CT1_IOFFSET_KEY,
                                   CT2_IOFFSET_KEY,
                                   CT3_IOFFSET_KEY,
                                   CT4_IOFFSET_KEY,
                                   CT5_IOFFSET_KEY,
                                   CT6_IOFFSET_KEY,

                                   CT1_TYPE_KEY,
                                   CT2_TYPE_KEY,
                                   CT3_TYPE_KEY,
                                   CT4_TYPE_KEY,
                                   CT5_TYPE_KEY,
                                   CT6_TYPE_KEY,

                                   CT1_NAME_KEY,
                                   CT2_NAME_KEY,
                                   CT3_NAME_KEY,
                                   CT4_NAME_KEY,
                                   CT5_NAME_KEY,
                                   CT6_NAME_KEY,

                                   CS0_VOLTAGE_GAIN_KEY,
                                   CS4_VOLTAGE_GAIN_KEY,

                                   ZERO_POWER_GATE_WATTS_KEY,

                                   CS0_VOLTAGE_OFFSET,
                                   CS4_VOLTAGE_OFFSET,
                                   ACTIVE
                                   )

    # --- END CONFIG SECTION ---
