#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import sys
import argparse
import sqlite3
import rich
import json
import threading
import psutil
import objgraph
import inspect
import copy

from datetime import datetime
from queue import Queue, Empty
from time import time, sleep
import pandas as pd

from p3lib.uio import UIO
from p3lib.boot_manager import BootManager
from p3lib.helper import logTraceBack

from lib.config import ConfigBase
from lib.base_constants import BaseConstants
from lib.yview import YViewCollector, LocalYViewCollector, YView

class AppConfig(ConfigBase):
    DEFAULT_CONFIG = {
        ConfigBase.MQTT_TOPIC:                 "#",
        ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE: "",
    }

class SQLite3DBClient(BaseConstants):
    """@brief Responsible for interfacing with the sqlite3 database."""

    DB_CONNECTION = "DB_CONNECTION"
    META_TABLE_UPDATE_TIME = "META_TABLE_UPDATE_TIME"
    HISTORY_RECORD_SET = "HISTORY_RECORD_SETS"
    RUNNING_ATTR_DICT = {DB_CONNECTION: None,
                         META_TABLE_UPDATE_TIME: None,
                         HISTORY_RECORD_SET: []}
    @staticmethod
    def GetQuotedValue(value):
        return '\"{}"'.format(str(value))

    @staticmethod
    def GetDatabaseFile(filename):
        """@brief Get the database file.
           @param filename The sqlite3 database filename.
           @return The database file."""
        homePath = os.path.expanduser("~")
        if not os.path.isdir(homePath):
            raise Exception(f"{homePath} HOME path does not exist.")

        top_level_config_folder = os.path.join(homePath, '.config')
        # Create the ~/.config folder if it does not exist
        if not os.path.isdir(top_level_config_folder):
            # Create the ~/.config folder
            os.makedirs(top_level_config_folder)

        progName = sys.argv[0]
        if progName.endswith('.py'):
            progName = progName[0:-3]
        progName = os.path.basename(progName).strip()
        config_folder = os.path.join(top_level_config_folder, progName)
        # Create the ~/.config/<app name> folder if it does not exist
        if not os.path.isdir(config_folder):
            # Create the app config folder
            os.makedirs(config_folder)

        return os.path.join(config_folder, filename)

    @staticmethod
    def GetDeviceIPAddress(rxDict):
        """@brief Get the IP address of the device.
           @return the IP address of the device or None if the dict does not contain the device IP address."""
        ipAddress = None
        if SQLite3DBClient.IP_ADDRESS in rxDict:
            ipAddress = rxDict[SQLite3DBClient.IP_ADDRESS]
        return ipAddress

    @staticmethod
    def GetValidColName(colName):
        """@brief Get a valid database column name."""

        VALID_CHAR_LIST = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_"
        for aChar in colName:
            if aChar not in VALID_CHAR_LIST:
                colName = colName.replace(aChar, '_')

        return colName

    def __init__(self, uio, options):
        """@brief Constructor"""
        self._uio = uio
        self._options = options
        self._running_att_dicts = {} # This dict contains RUNNING_ATTR_DICT's
        self._conn = None
        self._last__record_device_time = None
        self._dbLock = threading.Lock()
        self._tableSchema = SQLite3DBClient.GetTableSchema(SQLite3DBClient.CT6_DB_TABLE_SCHEMA)
        self._dev_dict_queue = Queue()
        # Thread to read data from the above queue
        threading.Thread(target=self._process_dev_dict_queue).start()

    def warn(self, msg):
        """@brief Show the user a warning level message.
           @param msg The message text."""
        if self._uio:
            self._uio.warn(msg)

    def info(self, msg):
        """@brief Show the user an info message.
           @param msg The message text."""
        if self._uio:
            self._uio.info(msg)

    def debug(self, msg):
        """@brief Show the user a debug message.
           @param msg The message text."""
        if self._uio:
            self._uio.debug(msg)

    def show_tables(self):
        """@brief List the tables."""
        try:
            cursor = self.connect()
            # Execute query to get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            if len(tables) > 0:
                for table in tables:
                    self._uio.info( table )
            else:
                self.info("No tables found.")

        finally:
            self.disconnect()

    def _report_memory_usage(self):
        """@brief Report the memory usage while running. Useful when debugging."""
        _, _, load15 = psutil.getloadavg()
        loadAvg = (load15/os.cpu_count()) * 100
        usedMB = psutil.virtual_memory()[3]/1000000
        freeMB = psutil.virtual_memory()[4]/1000000
        self.debug(f"CPU Load AVG: {loadAvg:.1f}, Used Mem (MB): {usedMB:.1f} Free Mem (MB): {freeMB:.1f}")

        objList = objgraph.most_common_types()
        for elemList in objList:
            _type = elemList[0]
            _count = elemList[1]
            self.debug(f"Found {_count: <8.0f} object of type {_type}")

    def _showdev_dict(self, dev_dict):
        """@brief Show the JSON data to the user.
           @return True if the device was shown."""
        ip_address = dev_dict[SQLite3DBClient.IP_ADDRESS]
        show_dev = False

        # If we have an include list check this device is in this list
        if self._options.include:
            include_list = self._options.include.split(",")
            if ip_address in include_list:
                show_dev = True
        else:
            show_dev = True

        # If we have an exclude list check for the device in this list.
        if self._options.exclude and show_dev:
            exclude_list = self._options.exclude.split(",")
            if ip_address in exclude_list:
                show_dev = False

        # Don't record data from CT6 units that are inactive.
        active = dev_dict[SQLite3DBClient.ACTIVE]
        if not active:
            show_dev = False

        if show_dev:
            rich.print_json(json.dumps(dev_dict))

        return show_dev

    def hear(self, dev_dict):
        """@brief Called when data is received from the device.
           @param dev_dict The CT6 device dict."""
        # We add to a queue and process the response in another thread
        # so as not to block the receipt of JSON messages from CT6 devices
        self._dev_dict_queue.put(dev_dict)

    def _process_dev_dict_queue(self):
        """@brief Called periodically to read dev_dict's received from CT6 devices from
                  the _dev_dict_queue."""
        self._read_thread_running = True
        while self._read_thread_running:
            try:
                # Process all available dev_dict's in the queue
                while True:
                    dev_dict = self._dev_dict_queue.get_nowait()
                    if dev_dict:
                        self._handle_dev_dict(dev_dict)

            except Empty:
                pass
            sleep(0.25)

    def _handle_dev_dict(self, dev_dict):
        """@brief Called when data is received from the device.
           @param dev_dict The CT6 device dict."""
        self._record_device_timestamp(dev_dict, 1)
        self._report_memory_usage()
        process_dev_dict = True
        if SQLite3DBClient.IP_ADDRESS in dev_dict:
            if self._options.show:
                process_dev_dict = self._showdev_dict(dev_dict)

            if process_dev_dict:
                self._record_device_timestamp(dev_dict, 2)
                if SQLite3DBClient.ACTIVE in dev_dict:
                    active = dev_dict[SQLite3DBClient.ACTIVE]
                    # We don't record data from units that are not active
                    if active:
                        if SQLite3DBClient.UNIT_NAME in dev_dict:
                            unit_name = dev_dict[SQLite3DBClient.UNIT_NAME]
                            unit_name = unit_name.strip()
                            # We don't record data from units that don't have a name.
                            if len(unit_name) > 0:
                                # We lock around each database store action as hear() may not always
                                # be called from the same thread.
                                with self._dbLock:
                                    self._record_device_timestamp(dev_dict, 3)
                                    self._record(dev_dict)
                                    self._record_device_timestamp(dev_dict, 4)

    def _connect(self, db_file):
        """@brief Connect to an sqlite3 database.
           @param db_file The file containing the database.
           return True If the database has juct been created."""
        self.info(f"Connecting to {db_file}")
        db_created = False
        if not os.path.isfile(db_file):
            db_created = True
        # This will create the database if it is not present
        conn = sqlite3.connect(db_file)
        self.info("Connected.")
        # Create a RUNNING_ATTR_DICT for this db and add the database connection
        # to the dict of connections.
        self._running_att_dicts[db_file] = copy.deepcopy(SQLite3DBClient.RUNNING_ATTR_DICT)
        self._running_att_dicts[db_file][SQLite3DBClient.DB_CONNECTION] = conn
        return db_created

    def disconnect(self):
        """@brief Disconnect from all the databases."""
        db_files = list(self._running_att_dicts.keys())
        for db_file in db_files:
            conn = self._running_att_dicts[db_file][SQLite3DBClient.DB_CONNECTION]
            if conn:
                conn.close()
            del self._running_att_dicts[db_file]

    def _get_db_conn(self, db_file, dev_dict):
        """@brief Get the connection to the database.
           @param db_file The database file (full path).
           @param dev_dict The CT6 device dict.
           @return A connection to the database."""
        # If we don't yet have a connection to the database file.
        if db_file not in self._running_att_dicts:
            created_db = self._connect(db_file)
            if created_db:
                # If we've just created the database ensure it contains the required tables.
                self._set_db_tables(dev_dict)
        return self._running_att_dicts[db_file][SQLite3DBClient.DB_CONNECTION]

    def _get_running_attr_dict(self, assy):
        """@brief Get the running attr dict for the given assy.
           @param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return A RUNNING_ATTR_DICT instance or None if not found"""
        running_attr_dict = None
        db_file_list = list(self._running_att_dicts.keys())
        for db_file in db_file_list:
            if assy in db_file:
                running_attr_dict = self._running_att_dicts[db_file]
        return running_attr_dict

    def _get_db_meta_table_update_time(self, assy):
        """@param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return The time that the db meta table should be updated or None if it's never been updated."""
        running_attr_dict = self._get_running_attr_dict(assy)
        return running_attr_dict[SQLite3DBClient.META_TABLE_UPDATE_TIME]

    def _set_db_meta_table_update_time(self, assy, next_update_time):
        """@brief Set the time that the meta table data should be next updated.
           @param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @param next_update_time The time it should be updated."""
        running_attr_dict = self._get_running_attr_dict(assy)
        running_attr_dict[SQLite3DBClient.META_TABLE_UPDATE_TIME] = next_update_time

    def _get_db_history_record_sets(self, assy):
        """@param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return A list containing threee lists
                   mins,
                   hours,
                   days
                   These are used to update these derived tables."""
        running_attr_dict = self._get_running_attr_dict(assy)
        record_sets = running_attr_dict[SQLite3DBClient.HISTORY_RECORD_SET]
        if len(record_sets) == 0:
            # We need lists to hold the min, hour and day records
            record_sets.append([])
            record_sets.append([])
            record_sets.append([])
        return record_sets

    def _get_db_cursor(self, dev_dict):
        """@brief Get a cursor connected to the correct database.
           @param dev_dict The CT6 device dict.
           @param db_conn_dict A dictionary that holds connection to each
                  database keyed by the database file.
           @return The cursor instance or None if no connection found."""
        cursor = None
        if SQLite3DBClient.ASSY in dev_dict:
            assy = dev_dict[SQLite3DBClient.ASSY]
            running_attr_dict = self._get_running_attr_dict(assy)
            conn = running_attr_dict[SQLite3DBClient.DB_CONNECTION]
            if conn:
                cursor = conn.cursor()
        return cursor

    def _execute_sql_cmd(self, cursor, cmd):
        """@brief Execute an SQL command."""
        self.debug(f">>>> SQL CMD: {cmd}")
        cursor.execute(cmd)

    def create_table(self, cursor, tableName, tableSchemaDict):
        """"@brief Create a table in the currently used database..
            @param cursor A cursor connected to the correct database.
            @param tableName The name of the database table.
            @param tableSchemaDict A python dictionary that defines the table schema.
                                   Each dictionary key is the name of the column in the table.
                                   Each associated value is the SQL definition of the column type (E.G VARCHAR(64), FLOAT(5,2) etc).
                                   Alternatively this may be a SQL string to create the table."""
        if isinstance(tableSchemaDict, str):
            cmd = f"CREATE TABLE {tableName} (" + tableSchemaDict + ");"
            self._execute_sql_cmd(cursor, cmd)
        else:
            sqlCmd = 'CREATE TABLE IF NOT EXISTS `{}` ('.format(tableName)
            for colName in list(tableSchemaDict.keys()):
                colDef = tableSchemaDict[colName]
                correctedColName = SQLite3DBClient.GetValidColName(colName)
                sqlCmd = sqlCmd + "`{}` {},\n".format(correctedColName, colDef)

            sqlCmd = sqlCmd[:-2]
            sqlCmd = sqlCmd + ");"
            self._execute_sql_cmd(cursor, sqlCmd)

    def _set_db_tables(self, dev_dict):
        """@brief Set the database tables. This is called after the database is created to
                  ensure the required tables are present.
           @param dev_dict The CT6 device dict."""
        self._record_device_timestamp(dev_dict, 1)
        if SQLite3DBClient.UNIT_NAME in dev_dict and SQLite3DBClient.PRODUCT_ID in dev_dict :
            unit_name = dev_dict[SQLite3DBClient.UNIT_NAME]
            if len(unit_name) == 0:
                ip_address = SQLite3DBClient.GetDeviceIPAddress(dev_dict)
                if ip_address:
                    self.warn(f"{ip_address}: Device name not set.")

                else:
                    self.warn("Found a CT6 device that does not have the device name field set.")

            # Don't record data unless the device name has been set.
            # The device name is used as the database name.
            else:
                self._record_device_timestamp(dev_dict, 2)
                cursor = self._get_db_cursor(dev_dict)
                # Create the database tables
                self.create_table(cursor, SQLite3DBClient.CT6_META_TABLE_NAME, SQLite3DBClient.CT6_DB_META_TABLE_SCHEMA_STR)
                self.create_table(cursor, SQLite3DBClient.CT6_TABLE_NAME, self._tableSchema)
                self.create_table(cursor, SQLite3DBClient.MINUTE_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                self.create_table(cursor, SQLite3DBClient.HOUR_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                self.create_table(cursor, SQLite3DBClient.DAY_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                try:
                    # Index on time stamp as most searches will be based around a date/time
                    cmd = f"CREATE INDEX {SQLite3DBClient.CT6_TABLE_NAME}_INDEX ON {SQLite3DBClient.CT6_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                    cmd = f"CREATE INDEX {SQLite3DBClient.MINUTE_RES_DB_DATA_TABLE_NAME}_INDEX ON {SQLite3DBClient.MINUTE_RES_DB_DATA_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                    cmd = f"CREATE INDEX {SQLite3DBClient.HOUR_RES_DB_DATA_TABLE_NAME}_INDEX ON {SQLite3DBClient.HOUR_RES_DB_DATA_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                    cmd = f"CREATE INDEX {SQLite3DBClient.DAY_RES_DB_DATA_TABLE_NAME}_INDEX ON {SQLite3DBClient.DAY_RES_DB_DATA_TABLE_NAME} ({SQLite3DBClient.TIMESTAMP})"
                    self._execute_sql_cmd(cursor, cmd)
                except:
                    pass

        self._record_device_timestamp(dev_dict, 3)

    def _record_device_timestamp(self, dev_dict, id):
        """@brief Record the time since device data was received from the CT6 device. This is
                  useful when debugging to see how long operations are taking.
           @param dev_dict The device dict.
           @param id A string identifying the call location."""
        start_time = dev_dict[YView.RX_TIME_SECS] # This field is not added to the database. It holds the time
                                                 # the CT6 dict was received on this machine.
        callerRef = inspect.stack()[2][4][0]
        callerRef = callerRef.strip()
        now = time()
        elapsed_ms =  int((now - start_time) * 1000)
        ms_since_last_call = -1
        if self._last__record_device_time is not None:
            ms_since_last_call = int((now - self._last__record_device_time) * 1000)

        self._uio.debug(f"DEVTS: {callerRef: >40} id={id} elapsed time = {elapsed_ms:d}/{ms_since_last_call:d} MS.")
        self._last__record_device_time = now

    def _record(self, dev_dict):
        """@brief Save the dev_dict data to a database.
           @param unit_name The name of the CT6 unit.
           @param dev_dict The CT6 device dict."""
        assy_label = dev_dict[SQLite3DBClient.ASSY]
        assy_label = assy_label.strip()
        db_file = SQLite3DBClient.GetDatabaseFile(assy_label + '.db')
        conn = self._get_db_conn(db_file, dev_dict)
        cursor = conn.cursor()
# PJA Handle exceptions adding to db ?
        # We update the meta table every 60 seconds, so fairly low CPU cost
        self._update_meta_table(cursor, dev_dict)
        # We update the CT6_SENSOR table for all CT6 stats/data received.
        self._add_device(cursor, dev_dict)
        cursor.close()
        conn.commit()

    def _add_device(self, cursor, dev_dict):
        """@brief Add device data to the database.
           @param cursor The cursor to execute the sql command.
           @param dev_dict The CT6 device dict."""
        start_time = dev_dict[YView.RX_TIME_SECS] # This field is not added to the database. It holds the time
                                             # the dict was received on this machine.

        self._record_device_timestamp(dev_dict, 1)
        sensor_data_dict = {}
        # Record the time the message was received on the TCP socket rather than the time now
        # as CPU delays may cause dither in the time we get to this point.
        sensor_data_dict[SQLite3DBClient.TIMESTAMP] = datetime.fromtimestamp(start_time)

        # active power
        sensor_data_dict[SQLite3DBClient.CT1_ACT_WATTS]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT2_ACT_WATTS]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT3_ACT_WATTS]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT4_ACT_WATTS]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT5_ACT_WATTS]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PRMS]
        sensor_data_dict[SQLite3DBClient.CT6_ACT_WATTS]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PRMS]
        # Reactive power
        sensor_data_dict[SQLite3DBClient.CT1_REACT_WATTS]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT2_REACT_WATTS]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT3_REACT_WATTS]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT4_REACT_WATTS]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT5_REACT_WATTS]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PREACT]
        sensor_data_dict[SQLite3DBClient.CT6_REACT_WATTS]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PREACT]
        # Aparent power
        sensor_data_dict[SQLite3DBClient.CT1_APP_WATTS]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT2_APP_WATTS]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT3_APP_WATTS]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT4_APP_WATTS]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT5_APP_WATTS]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PAPPARENT]
        sensor_data_dict[SQLite3DBClient.CT6_APP_WATTS]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PAPPARENT]

        # Power factor
        sensor_data_dict[SQLite3DBClient.CT1_PF]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT2_PF]=dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT3_PF]=dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT4_PF]=dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT5_PF]=dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.PF]
        sensor_data_dict[SQLite3DBClient.CT6_PF]=dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.PF]

        # Misc
        sensor_data_dict[SQLite3DBClient.VOLTAGE]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.VRMS]
        sensor_data_dict[SQLite3DBClient.FREQUENCY]=dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.FREQ]
        sensor_data_dict[SQLite3DBClient.TEMPERATURE]=dev_dict[SQLite3DBClient.TEMPERATURE]
        sensor_data_dict[SQLite3DBClient.RSSI_DBM]=dev_dict[SQLite3DBClient.RSSI]

        self._record_device_timestamp(dev_dict, 2)

        # Add sensor data to the table containing all sensor data
        self._add_to_table(cursor, SQLite3DBClient.CT6_TABLE_NAME, sensor_data_dict)

        self._record_device_timestamp(dev_dict, 3)

        assy = dev_dict[SQLite3DBClient.ASSY]

        # Update the mins, hours and days tables.
        # This may block for some time if the ct6 app is started with a large database
        # that needs mins, hours and days tables recreating. This is ok because we have
        # a queue between the receipt of CT6 JSON messages and this thread that processes them.
        self._update_derived_tables(assy, sensor_data_dict, cursor)

    def _update_meta_table(self, cursor, dev_dict):
        """@brief Update the table containing meta data. This keeps the meta table up to date.
           @param cursor A cursor for the db.
           @param devDict The device dict."""
        assy = dev_dict[SQLite3DBClient.ASSY]
        _time = self._get_db_meta_table_update_time(assy)
        #If not set yet
        if _time is None:
            _time = time()
        # If it's time to update the meta data for this CT6 unit/db
        if time() >= _time:
            # We use replace into with an id (primary key) of 1 so that we only ever have one record in the table.
            cmd = 'REPLACE INTO {} (id,{},{},{},{},{},{},{}) VALUES("1","{}","{}","{}","{}","{}","{}","{}");'.format(SQLite3DBClient.CT6_META_TABLE_NAME,
                                                                             SQLite3DBClient.HW_ASSY,
                                                                             SQLite3DBClient.CT1_NAME,
                                                                             SQLite3DBClient.CT2_NAME,
                                                                             SQLite3DBClient.CT3_NAME,
                                                                             SQLite3DBClient.CT4_NAME,
                                                                             SQLite3DBClient.CT5_NAME,
                                                                             SQLite3DBClient.CT6_NAME,
                                                                             dev_dict[SQLite3DBClient.ASSY],
                                                                             dev_dict[SQLite3DBClient.CT1][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT2][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT3][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT4][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT5][SQLite3DBClient.NAME],
                                                                             dev_dict[SQLite3DBClient.CT6][SQLite3DBClient.NAME])
            self._execute_sql_cmd(cursor, cmd)
            # We update the meta table every 60 seconds for each CT6 when we received the dev_dict
            self._set_db_meta_table_update_time(assy, time() + 60)

    def _update_derived_tables(self, db_file, sensor_data_dDict, cursor):
        """@brief Update the min, hour and day tables in the database with new data just read from a sensor.
           @param db_file The db_file to be updated.
           @param dev_dict The dict containing the device data to be added to the database.
           @param cursor The cursor to execute the sql command."""
        # PJA rename these when working
        thisRecord = sensor_data_dDict
        lowResTableList = SQLite3DBClient.LOW_RES_DATA_TABLE_LIST
        recordSets = self._get_db_history_record_sets(db_file)

        # First derived table (minute)
        tableName = lowResTableList[0]
        recordSet = recordSets[0]
        # If we've moved into the next minute
        if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].minute != recordSet[0][BaseConstants.TIMESTAMP].minute):
            # Ensure we have several records as we may get two readings in the same second (microseconds apart) but we don't want to add
            # data to the database unless it's valid. We should have 60 second values in the list but will vary as
            # poll/response and network delays to-from the CT6 device may move the sampling times.
            if len(recordSet) >= 3:
                # Use a pandas data frame to calculate the mean values for each column
                df = pd.DataFrame(recordSet)
                self._add_to_table(cursor, tableName, df.mean())
                recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                recordSet.append(thisRecord) # Add the new data to the next record set.
                self._uio.debug(f"{db_file}: Record added to {tableName} table: {datetime.now()}")

                # Second derived table (hour)
                tableName = lowResTableList[1]
                recordSet = recordSets[1]
                # If we've moved into the next hour
                if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].hour != recordSet[0][BaseConstants.TIMESTAMP].hour):
                    # Use a pandas data frame to calculate the mean values for each column
                    df = pd.DataFrame(recordSet)
                    self._add_to_table(cursor, tableName, df.mean())
                    recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                    recordSet.append(thisRecord) # Add the new data to the next record set.
                    self._uio.debug(f"{db_file}: Record added to {tableName} table: {datetime.now()}")

                    # Third derived table (day)
                    tableName = lowResTableList[2]
                    recordSet = recordSets[2]
                    # If we've moved into the next day
                    if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].day != recordSet[0][BaseConstants.TIMESTAMP].day):
                        # Use a pandas data frame to calculate the mean values for each column
                        df = pd.DataFrame(recordSet)
                        self._add_to_table(cursor, tableName, df.mean())
                        recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                        recordSet.append(thisRecord) # Add the new data to the next record set.

                        self._uio.debug(f"{db_file}: Record added to {tableName} table: {datetime.now()}")

                    else:
                        # Add to the set of record to be averaged later
                        recordSet.append(thisRecord)

                else:
                    # Add to the set of record to be averaged later
                    recordSet.append(thisRecord)

        else:
            # Add to the set of record to be averaged later
            recordSet.append(thisRecord)

# PJA NOT USED, del if we don't use it
    def _get_table_row_count(self, cursor, tableName):
        """@brief Get the number of rows in a table.
           @param cursor The cursor to execute the sql command.
           @param tableName The name of the table.
           @return the number of rows in the table or -1 if not found."""
        count = -1
        cmd = "SELECT COUNT(*) as count from {};".format(tableName)
        retList = self._execute_sql_cmd(cursor, cmd)
        if len(retList) > 0:
            count = retList[0]['count']
        return count

    def _add_to_table(self, cursor, tableName, dictData):
        """@brief Add data to table. We assume this is in the currently selected database.
           @param cursor The cursor to execute the sql command.
           @param tableName The name of the table to add to. If the table does not exist it will be created.
           @param dictData The dict holding the data to be added to the table.
           @param databaseIF The database interface instance."""
        keyList = list(dictData.keys())
        valueList = []
        for key in keyList:
            valueList.append(str(dictData[key]))
        sql = 'INSERT INTO `' + tableName
        sql += '` ('
        sql += ', '.join(keyList)
        sql += ') VALUES ('
        sql += ', '.join(map(SQLite3DBClient.GetQuotedValue, valueList))
        sql += ');'
        self._execute_sql_cmd(cursor, sql)


class AppServer(object):
    """@brief Responsible for
        - Starting the YViewCollector.
        - Storing data in the database.
        - Presenting the user with a web GUI to allow data to be displayed and manipulated."""

    DEFAULT_CONFIG_FILENAME = "ct6.cfg"
    LOCK_FILE_NAME = "ct6.lock"

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A ConfigBase instance."""
        self._uio = uio
        self._options = options
        self._config = config

    def start(self, db_client):
        """@Start the App server running.
            @param db_client An instance of SQLite3DBClient."""
        try:

            # Start running the local collector in a separate thread
            self._localYViewCollector = LocalYViewCollector(self._uio, self._options)
            self._localYViewCollector.setValidProductIDList(YViewCollector.VALID_PRODUCT_ID_LIST)

            # Register the dBHandler as a listener for device data so that it can be
            # stored in the database.
            self._localYViewCollector.addDevListener(db_client)
            net_if = self._config.getAttr(AppConfig.CT6_DEVICE_DISCOVERY_INTERFACE)
            self._localYViewCollector.start(net_if=net_if)

            # Start a web UI to allow the user to view the data

        finally:
            db_client.disconnect()


def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="This application is responsible for the following.\n"\
                                                     "- Detecting CT6 units on the LAN/WiFi.\n"\
                                                     "- Regularly (every second) reasdin stats from CT6 these CT6 units.\n"\
                                                     "- Saving this data to databases.\n"\
                                                     "- Presenting a use friendly web interface to view and manipulate the data.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",        action='store_true', help="Enable debugging.")
        parser.add_argument("-c", "--configure",    help="Configure this app.", action='store_true')
        parser.add_argument("--show_tables",        help="Show all the database tables.", action="store_true", default=False)

        parser.add_argument("-s", "--show",         help="Show CT6 JSON data received.", action="store_true", default=False)
        parser.add_argument("-i", "--include",      help="A comma separated list of IP addresses of CT6 units to include in the data collection. If omitted all CT6 units found are included.")
        parser.add_argument("-e", "--exclude",      help="A comma separated list of IP addresses of CT6 units to exclude from data collection.  If omitted no CT6 units are excluded.")

        parser.add_argument("--syslog",             action='store_true', help="Enable syslog debug data.")
        BootManager.AddCmdArgs(parser)

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.syslog, programName="ct6")
        if options.syslog:
            uio.info("Syslog enabled")

        app_config = AppConfig(uio, AppConfig.GetConfigFile(AppServer.DEFAULT_CONFIG_FILENAME), AppConfig.DEFAULT_CONFIG)
        db_client = SQLite3DBClient(uio, options)

        handled = BootManager.HandleOptions(uio, options, options.syslog)
        if not handled:

            if options.configure:
                app_config.configure(editConfigMethod=AppConfig.edit)

            elif options.show_tables:
                db_client.show_tables()

            else:
                app_server = AppServer(uio, options, app_config)
                app_server.start(db_client)

    #If the program throws a system exit exception
    except SystemExit:
        pass
    #Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        raise
        if options.debug:
            raise
        else:
            uio.error(str(ex))

if __name__== '__main__':
    main()
