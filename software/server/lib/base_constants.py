class BaseConstants(object):
    """@brief Responsible for defining contants"""
    LOCATION                = "LOCATION"
    MQTT_TOPIC              = "MQTT_TOPIC"
    UNIT_NAME               = "UNIT_NAME"
    PRODUCT_ID              = "PRODUCT_ID"
    IP_ADDRESS              = "IP_ADDRESS"
    ASSY                    = "ASSY"
    SERVER_SERVICE_LIST     = "SERVER_SERVICE_LIST"
    LOCALHOST_SERVICE_LIST  = "LOCALHOST_SERVICE_LIST"
    WEB_SERVICE_NAME        = "WEB"
    HTTP_SERVICE_NAME       = "HTTP"
    WEB_SERVICE_NAME_LIST   = (WEB_SERVICE_NAME, HTTP_SERVICE_NAME)
    VALID_PRODUCT_ID_LIST   = ("CT6",)

    MQTT_LOOP_BLOCK_SECONDS = 1

    LOCALHOST               = "127.0.0.1"
    MQTT_PORT               = 1883

    RECONNECT_DELAY_SECS    = 10

    DATABASE_KEY            = 'Database'

    SHOW_DATABASES_SQL_CMD  = 'SHOW DATABASES;'

    TIMESTAMP               = "TIMESTAMP"

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
                    if colName == BaseConstants.TIMESTAMP:
                        timestampFound=True
                    colType = subElems[1]
                    tableSchemaDict[colName] = colType
                else:
                    raise Exception("{} is an invalid table schema column.".format(elem))
            return tableSchemaDict

        else:
            raise Exception("Invalid Table schema. No elements found.")

    CT6_META_TABLE_NAME     = "CT6_META"
    CT6_TABLE_NAME          = "CT6_SENSOR"

    # Dev dict params
    ASSY = "ASSY"
    CT1 = "CT1"
    CT2 = "CT2"
    CT3 = "CT3"
    CT4 = "CT4"
    CT5 = "CT5"
    CT6 = "CT6"
    CT_DEV_LIST = (CT1, CT2, CT3, CT4, CT5, CT6)
    NAME = "NAME"
    WATTS = 'WATTS'
    PRMS = "PRMS"
    PREACT = "PREACT"
    PAPPARENT = "PAPPARENT"
    VRMS = "VRMS"
    FREQ = "FREQ"
    PREACT = "PREACT"
    PF = "PF"
    TEMPERATURE = 'BOARD_TEMPERATURE' # The same name is used in the database for this param
    TEMP = 'TEMP'
    RSSI_DBM = 'RSSI_DBM'       # The name in the database
    RSSI = 'RSSI'       # The name in the dict received from the device

    # Database table params
    HW_ASSY = "HW_ASSY"
    CT1_NAME = "CT1_NAME"
    CT2_NAME = "CT2_NAME"
    CT3_NAME = "CT3_NAME"
    CT4_NAME = "CT4_NAME"
    CT5_NAME = "CT5_NAME"
    CT6_NAME = "CT6_NAME"

    CT1_ACT_WATTS = "CT1_ACT_WATTS"
    CT2_ACT_WATTS = "CT2_ACT_WATTS"
    CT3_ACT_WATTS = "CT3_ACT_WATTS"
    CT4_ACT_WATTS = "CT4_ACT_WATTS"
    CT5_ACT_WATTS = "CT5_ACT_WATTS"
    CT6_ACT_WATTS = "CT6_ACT_WATTS"

    CT1_REACT_WATTS = "CT1_REACT_WATTS"
    CT2_REACT_WATTS = "CT2_REACT_WATTS"
    CT3_REACT_WATTS = "CT3_REACT_WATTS"
    CT4_REACT_WATTS = "CT4_REACT_WATTS"
    CT5_REACT_WATTS = "CT5_REACT_WATTS"
    CT6_REACT_WATTS = "CT6_REACT_WATTS"

    CT1_APP_WATTS = "CT1_APP_WATTS"
    CT2_APP_WATTS = "CT2_APP_WATTS"
    CT3_APP_WATTS = "CT3_APP_WATTS"
    CT4_APP_WATTS = "CT4_APP_WATTS"
    CT5_APP_WATTS = "CT5_APP_WATTS"
    CT6_APP_WATTS = "CT6_APP_WATTS"

    CT1_PF = "CT1_PF"
    CT2_PF = "CT2_PF"
    CT3_PF = "CT3_PF"
    CT4_PF = "CT4_PF"
    CT5_PF = "CT5_PF"
    CT6_PF = "CT6_PF"
    VOLTAGE   = "VOLTAGE"
    FREQUENCY = "FREQUENCY"
    ACTIVE = 'ACTIVE'
    FIELD_LIST_A = [CT1_ACT_WATTS,
                    CT2_ACT_WATTS,
                    CT3_ACT_WATTS,
                    CT4_ACT_WATTS,
                    CT5_ACT_WATTS,
                    CT6_ACT_WATTS,
                    CT1_REACT_WATTS,
                    CT2_REACT_WATTS,
                    CT3_REACT_WATTS,
                    CT4_REACT_WATTS,
                    CT5_REACT_WATTS,
                    CT6_REACT_WATTS,
                    CT1_APP_WATTS,
                    CT2_APP_WATTS,
                    CT3_APP_WATTS,
                    CT4_APP_WATTS,
                    CT5_APP_WATTS,
                    CT6_APP_WATTS,
                    CT1_PF,
                    CT2_PF,
                    CT3_PF,
                    CT4_PF,
                    CT5_PF,
                    CT6_PF,
                    VOLTAGE,
                    FREQUENCY,
                    TEMPERATURE,
                    RSSI_DBM]

    # Used by ct6_db_store to save to mysql databases.
    CT6_DB_META_TABLE_SCHEMA     =  "{}:VARCHAR(64) " \
                                    "{}:VARCHAR(64) " \
                                    "{}:VARCHAR(64) " \
                                    "{}:VARCHAR(64) " \
                                    "{}:VARCHAR(64) " \
                                    "{}:VARCHAR(64) " \
                                    "{}:VARCHAR(64)".format(HW_ASSY,
                                                            CT1_NAME,
                                                            CT2_NAME,
                                                            CT3_NAME,
                                                            CT4_NAME,
                                                            CT5_NAME,
                                                            CT6_NAME)

    # Used by ct6_db_store to save to mysql databases.
    CT6_DB_TABLE_SCHEMA          = "TIMESTAMP:TIMESTAMP " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(6,1) " \
                                   "{}:FLOAT(4,3) " \
                                   "{}:FLOAT(4,3) " \
                                   "{}:FLOAT(4,3) " \
                                   "{}:FLOAT(4,3) " \
                                   "{}:FLOAT(4,3) " \
                                   "{}:FLOAT(4,3) " \
                                   "{}:FLOAT(4,1) " \
                                   "{}:FLOAT(3,1) " \
                                   "{}:FLOAT(4,1) " \
                                   "{}:FLOAT(3,1)".format(CT1_ACT_WATTS,
                                                          CT2_ACT_WATTS,
                                                          CT3_ACT_WATTS,
                                                          CT4_ACT_WATTS,
                                                          CT5_ACT_WATTS,
                                                          CT6_ACT_WATTS,
                                                          CT1_REACT_WATTS,
                                                          CT2_REACT_WATTS,
                                                          CT3_REACT_WATTS,
                                                          CT4_REACT_WATTS,
                                                          CT5_REACT_WATTS,
                                                          CT6_REACT_WATTS,
                                                          CT1_APP_WATTS,
                                                          CT2_APP_WATTS,
                                                          CT3_APP_WATTS,
                                                          CT4_APP_WATTS,
                                                          CT5_APP_WATTS,
                                                          CT6_APP_WATTS,
                                                          CT1_PF,
                                                          CT2_PF,
                                                          CT3_PF,
                                                          CT4_PF,
                                                          CT5_PF,
                                                          CT6_PF,
                                                          VOLTAGE,
                                                          FREQUENCY,
                                                          TEMPERATURE,
                                                          RSSI_DBM)

    MAX_RES_DB_DATA_TABLE_NAME          = CT6_TABLE_NAME
    MINUTE_RES_DB_DATA_TABLE_NAME       = 'CT6_SENSOR_MINUTE'
    HOUR_RES_DB_DATA_TABLE_NAME         = 'CT6_SENSOR_HOUR'
    DAY_RES_DB_DATA_TABLE_NAME          = 'CT6_SENSOR_DAY'
    LOW_RES_DATA_TABLE_LIST = [MINUTE_RES_DB_DATA_TABLE_NAME,
                               HOUR_RES_DB_DATA_TABLE_NAME,
                               DAY_RES_DB_DATA_TABLE_NAME]

    # Used by ct6_app to save to sqlite databases.
    CT6_DB_META_TABLE_SCHEMA_SQLITE  = "ID INTEGER PRIMARY KEY, " \
                                      f"{HW_ASSY} VARCHAR(64), " \
                                      f"{UNIT_NAME} VARCHAR(64), " \
                                      f"{CT1_NAME} VARCHAR(64), " \
                                      f"{CT2_NAME} VARCHAR(64), " \
                                      f"{CT3_NAME} VARCHAR(64), " \
                                      f"{CT4_NAME} VARCHAR(64), " \
                                      f"{CT5_NAME} VARCHAR(64), " \
                                      f"{CT6_NAME} VARCHAR(64)"

    # Used by ct6_app to save to sqlite databases.
    CT6_DB_TABLE_SCHEMA_SQLITE   = "TIMESTAMP:TEXT " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(9,2) " \
                                   "{}:NUMERIC(6,4) " \
                                   "{}:NUMERIC(6,4) " \
                                   "{}:NUMERIC(6,4) " \
                                   "{}:NUMERIC(6,4) " \
                                   "{}:NUMERIC(6,4) " \
                                   "{}:NUMERIC(6,4) " \
                                   "{}:NUMERIC(6,2) " \
                                   "{}:NUMERIC(4,1) " \
                                   "{}:NUMERIC(6,2) " \
                                   "{}:NUMERIC(6,3)".format(CT1_ACT_WATTS,
                                                          CT2_ACT_WATTS,
                                                          CT3_ACT_WATTS,
                                                          CT4_ACT_WATTS,
                                                          CT5_ACT_WATTS,
                                                          CT6_ACT_WATTS,
                                                          CT1_REACT_WATTS,
                                                          CT2_REACT_WATTS,
                                                          CT3_REACT_WATTS,
                                                          CT4_REACT_WATTS,
                                                          CT5_REACT_WATTS,
                                                          CT6_REACT_WATTS,
                                                          CT1_APP_WATTS,
                                                          CT2_APP_WATTS,
                                                          CT3_APP_WATTS,
                                                          CT4_APP_WATTS,
                                                          CT5_APP_WATTS,
                                                          CT6_APP_WATTS,
                                                          CT1_PF,
                                                          CT2_PF,
                                                          CT3_PF,
                                                          CT4_PF,
                                                          CT5_PF,
                                                          CT6_PF,
                                                          VOLTAGE,
                                                          FREQUENCY,
                                                          TEMPERATURE,
                                                          RSSI_DBM)

    # Used by ct6_app to read from sqlite databases.
    TIMESTAMP_INDEX = 0

    CT1_ACT_WATTS_INDEX = 1
    CT2_ACT_WATTS_INDEX = 2
    CT3_ACT_WATTS_INDEX = 3
    CT4_ACT_WATTS_INDEX = 4
    CT5_ACT_WATTS_INDEX = 5
    CT6_ACT_WATTS_INDEX = 6

    CT1_REACT_WATTS_INDEX = 7
    CT2_REACT_WATTS_INDEX = 8
    CT3_REACT_WATTS_INDEX = 9
    CT4_REACT_WATTS_INDEX = 10
    CT5_REACT_WATTS_INDEX = 11
    CT6_REACT_WATTS_INDEX = 12

    CT1_APP_WATTS_INDEX = 13
    CT2_APP_WATTS_INDEX = 14
    CT3_APP_WATTS_INDEX = 15
    CT4_APP_WATTS_INDEX = 16
    CT5_APP_WATTS_INDEX = 17
    CT6_APP_WATTS_INDEX = 18

    CT1_PF_INDEX = 19
    CT2_PF_INDEX = 20
    CT3_PF_INDEX = 21
    CT4_PF_INDEX = 22
    CT5_PF_INDEX = 23
    CT6_PF_INDEX = 24

    VOLTAGE_INDEX = 25
    FREQUENCY_INDEX = 26
    TEMPERATURE_INDEX = 27
    RSSI_DBM_INDEX = 28



