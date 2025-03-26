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
import itertools
import re
import calendar

from datetime import datetime, timedelta, date
from queue import Queue, Empty
from time import time, sleep

import mysql.connector
import pandas as pd

from p3lib.uio import UIO
from p3lib.boot_manager import BootManager
from p3lib.helper import logTraceBack
from p3lib.bokeh_gui import MultiAppServer

from lib.config import ConfigBase
from lib.base_constants import BaseConstants
from lib.yview import YViewCollector, LocalYViewCollector, YView

from bokeh.layouts import column, row
from bokeh.models import Div, Button, HoverTool, CustomJS
from bokeh.models import TabPanel, Tabs
from bokeh.models.css import Styles
from bokeh.plotting import figure, ColumnDataSource
from bokeh.models import DatetimePicker
from bokeh.palettes import Category20_20
from bokeh.models import RadioButtonGroup, DataTable, \
                         TableColumn, InlineStyleSheet, Tooltip, HelpButton
from bokeh.models.widgets import HTMLTemplateFormatter

from ct6.ct6_dash_mgr import CRED_JSON_FILE
from ct6.ct6_tool import CT6Base

class AppConfig(ConfigBase):

    @staticmethod
    def GetAppConfigPath():
        """@brief Get the config path.
           @return The config path."""
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
        return config_folder

    DB_STORAGE_PATH = "DB_STORAGE_PATH"

    DEFAULT_CONFIG = {
        DB_STORAGE_PATH: GetAppConfigPath(), # By default the db's are stored in the same folder as the config files, but the user can re configure this.
        ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE: "",
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS: "0.0.0.0",
        ConfigBase.LOCAL_GUI_SERVER_PORT: 10000,
        ConfigBase.SERVER_LOGIN: False,
        ConfigBase.SERVER_ACCESS_LOG_FILE: ""
    }

    def _enter_storage_path(self):
        """@brief Allow the user to enter the storage path."""
        # Ensure the user enters an IP address of an interface on this machine.
        while True:
            self.inputStr(AppConfig.DB_STORAGE_PATH, "Enter path to store database and config files (enter d for the default value).", False)
            config_path = self.getAttr(AppConfig.DB_STORAGE_PATH)
            if config_path.lower() == 'd':
                config_path = AppConfig.GetAppConfigPath()
                if not os.path.isdir(config_path):
                    os.makedirs(config_path)
                self.addAttr(AppConfig.DB_STORAGE_PATH, config_path)
            if os.path.isdir(config_path):
                break

            else:
                self._uio.error(f"{config_path} path not found.")

    def edit(self, key):
        """@brief Provide the functionality to allow the user to enter any ct4 config parameter
                  regardless of the config type.
           @param key The dict key to be edited.
           @return True if the config parameter was handled/updated"""
        if key == ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE:
            self._enterDiscoveryInterface()

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

        elif key == ConfigBase.LOCAL_GUI_SERVER_PORT:
            self.inputBool(ConfigBase.LOCAL_GUI_SERVER_PORT, "Enter the TCP port to serve the GUI/Bokeh web interface from", minValue=1024, maxValue=65535)

        elif key == ConfigBase.SERVER_LOGIN:
            self.inputBool(ConfigBase.SERVER_LOGIN, "Enable server login")

        elif key == ConfigBase.SERVER_ACCESS_LOG_FILE:
            self._enterServerAccessLogFile()

        elif key == AppConfig.DB_STORAGE_PATH:
            self._enter_storage_path()

        elif key == ConfigBase.DB_HOST:
            self.inputStr(ConfigBase.DB_HOST, "Enter the address of the MYSQL database server", False)

        elif key == ConfigBase.DB_PORT:
            self.inputDecInt(ConfigBase.DB_PORT, "Enter TCP port to connect to the MYSQL database server", minValue=1024, maxValue=65535)

        elif key == ConfigBase.DB_USERNAME:
            self.inputStr(ConfigBase.DB_USERNAME, "Enter the database username", False)

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
    def GetConfigPathFile(filename):
        """@brief Get the abs path to a file in the config path.
           @param filename The filename to reside in the config path.
           @return The abs file."""
        config_folder = AppConfig.GetAppConfigPath()
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

    @staticmethod
    def GetDBFileList(db_storage_path):
        """@return A list of all the available db files."""
        db_file_list = []
        entry_list = os.listdir(db_storage_path)
        for entry in entry_list:
            abs_path = os.path.join(db_storage_path, entry)
            if abs_path.endswith(".db"):
                db_file_list.append(abs_path)
        return db_file_list

    def __init__(self, uio, options, app_config):
        """@brief Constructor
           @param uio A UIO instance.
           @param options The command line options instance.
           @param config A ConfigBase instance."""
        self._uio = uio
        self._options = options
        self._config = app_config
        self._running_attr_dicts = {} # This dict contains RUNNING_ATTR_DICT's
        self._conn = None
        self._last__record_device_time = None
        self._dbLock = threading.Lock()
        self._tableSchema = SQLite3DBClient.GetTableSchema(SQLite3DBClient.CT6_DB_TABLE_SCHEMA_SQLITE)
        self._dev_dict_queue = Queue()
        # Thread to read data from the above queue
        pthread = threading.Thread(target=self._process_dev_dict_queue)
        pthread.daemon = True
        pthread.start()

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
            db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
            db_file_list = SQLite3DBClient.GetDBFileList(db_storage_folder)
            for db_file in db_file_list:
                self._connect(db_file)
                conn = self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION]
                cursor = conn.cursor()
                # Execute query to get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                if len(tables) > 0:
                    for table in tables:
                        self._uio.info( table[0] )
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

            except Exception:
                self._uio.errorException()

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
        self._running_attr_dicts[db_file] = copy.deepcopy(SQLite3DBClient.RUNNING_ATTR_DICT)
        self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION] = conn
        return db_created

# PJA this must be called from the db thread !!!
    def disconnect(self):
        """@brief Disconnect from all the databases."""
        db_files = list(self._running_attr_dicts.keys())
        for db_file in db_files:
            conn = self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION]
            if conn:
                conn.close()
            del self._running_attr_dicts[db_file]

    def _get_db_conn(self, db_file, dev_dict):
        """@brief Get the connection to the database.
           @param db_file The database file (full path).
           @param dev_dict The CT6 device dict.
           @return A connection to the database."""
        # If we don't yet have a connection to the database file.
        if db_file not in self._running_attr_dicts:
            created_db = self._connect(db_file)
            if created_db:
                # If we've just created the database ensure it contains the required tables.
                self._set_db_tables(dev_dict)
        return self._running_attr_dicts[db_file][SQLite3DBClient.DB_CONNECTION]

    def _get_running_attr_dict(self, assy):
        """@brief Get the running attr dict for the given assy.
           @param assy This may be the device assembly number as contained
                       in a dev_dict or the db file (this contains the assy text).
           @return A RUNNING_ATTR_DICT instance or None if not found"""
        running_attr_dict = None
        db_file_list = list(self._running_attr_dicts.keys())
        for db_file in db_file_list:
            if assy in db_file:
                running_attr_dict = self._running_attr_dicts[db_file]
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
                self.create_table(cursor, SQLite3DBClient.CT6_META_TABLE_NAME, SQLite3DBClient.CT6_DB_META_TABLE_SCHEMA_SQLITE)
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
        db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
        db_file = os.path.join(db_storage_folder, assy_label + '.db')
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
            cmd = 'REPLACE INTO {} (id,{},{},{},{},{},{},{},{}) VALUES("1","{}","{}","{}","{}","{}","{}","{}","{}");'.format(SQLite3DBClient.CT6_META_TABLE_NAME,
                                                                             SQLite3DBClient.HW_ASSY,
                                                                             SQLite3DBClient.UNIT_NAME,
                                                                             SQLite3DBClient.CT1_NAME,
                                                                             SQLite3DBClient.CT2_NAME,
                                                                             SQLite3DBClient.CT3_NAME,
                                                                             SQLite3DBClient.CT4_NAME,
                                                                             SQLite3DBClient.CT5_NAME,
                                                                             SQLite3DBClient.CT6_NAME,
                                                                             dev_dict[SQLite3DBClient.ASSY],
                                                                             dev_dict[SQLite3DBClient.UNIT_NAME],
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


class MYSQLImporter(object):
    """@brief Responsible for the conversion of CT6 mysql databases to CT6 sqlite databases."""

    MYSQL_CONFIG_FILENAME = "mysql.cfg"

    DEFAULT_MYSQL_CONFIG = {
        ConfigBase.DB_HOST: "",
        ConfigBase.DB_PORT: 3306,
        ConfigBase.DB_USERNAME: ""
    }

    VALID_CT6_DB_TABLE_NAMES = ('CT6_META',
                                'CT6_SENSOR',
                                'CT6_SENSOR_MINUTE',
                                'CT6_SENSOR_HOUR',
                                'CT6_SENSOR_DAY')

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config An AppConfig instance."""
        self._uio = uio
        self._options = options
        self._config = config

    def _get_ct6_db_list(self, mysql_cursor):
        """@return A list of CT6 databases on the mysql server."""
        ct6_db_list = []
        cmd = 'SHOW DATABASES;'
        mysql_cursor.execute(cmd)
        db_list = mysql_cursor.fetchall()
        for db in db_list:
            db_name = db[0]
            cmd = f'USE {db_name};'
            mysql_cursor.execute(cmd)

            cmd = 'SHOW TABLES;'
            mysql_cursor.execute(cmd)
            table_list = mysql_cursor.fetchall()
            valid_table_names = True
            for table in table_list:
                table_name = table[0]
                if table_name not in MYSQLImporter.VALID_CT6_DB_TABLE_NAMES:
                    valid_table_names = False
                    break
            if valid_table_names:
                ct6_db_list.append(db_name)
        return ct6_db_list

    def _get_mysql_attr(self):
        """@brief Get a list of the my sql database attributes required.
           @return A tuple containing.
                   0 = host
                   1 = port
                   2 = username
                   4 = password"""
        # The host, port and username are saved persistently
        mysql_config = AppConfig(self._uio, SQLite3DBClient.GetConfigPathFile(MYSQLImporter.MYSQL_CONFIG_FILENAME) , MYSQLImporter.DEFAULT_MYSQL_CONFIG)
        mysql_config.configure(editConfigMethod=mysql_config.edit,
                               prompt="Enter 'E' to edit a parameter, or 'C' to continue",
                               quitCharacters= 'C')
        host = mysql_config.getAttr(ConfigBase.DB_HOST)
        port = mysql_config.getAttr(ConfigBase.DB_PORT)
        username = mysql_config.getAttr(ConfigBase.DB_USERNAME)
        # But the user must enter the MYSQL server password every time.
        password = self._uio.getInput("Enter the password for the MYSQL server")
        return (host, port, username, password)

    def _get_sqlite_database_file(self, mysql_db_name, mysql_cursor):
        """@brief Get a list of the sqlite database files.
           @param mysql_database_files A list of the mysql database files.
           @param mysql_cursor A cursor connected to the mysql database.
           @return The sqlite database file or None if not found."""
        db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
        sqlite_db_file = None
        cmd = f'USE {mysql_db_name};'
        mysql_cursor.execute(cmd)
        cmd = f'SELECT HW_ASSY FROM {MYSQLImporter.VALID_CT6_DB_TABLE_NAMES[0]};'
        mysql_cursor.execute(cmd)
        response = mysql_cursor.fetchall()
        if len(response) > 0:
            hw_assy = response[0][0]
            sqlite_db_name = hw_assy + ".db"
            sqlite_db_file = os.path.join(db_storage_folder,
                                          sqlite_db_name)
        return sqlite_db_file

    def convert_mysql_to_sqlite(self):
        """@brief Connect to a my database and import all CT6 databases into sqlite"""
        self._uio.info("- Enter the mysql configuration below.")
        self._uio.info("- Then enter 'Q' to continue.\n")
        host, port, username, password = self._get_mysql_attr()

        mysql_conn = None
        mysql_cursor = None
        start_time = time()
        try:
            mysql_conn = mysql.connector.connect(host=host, port=port, user=username, password=password)
            mysql_cursor = mysql_conn.cursor()
            self._uio.info("Connected to MySQL DB.")

            mysql_server_ct6_db_list = self._get_ct6_db_list(mysql_cursor)
            # Check that none of the sqlite database files exist before we start
            # The user must delete these manually if they wish to create them.
            # We check this first as it may take some time to convert files and we
            # want to let the user know now if a files already exists which will
            # stop the conversion process.
            for mysql_server_ct6_db in mysql_server_ct6_db_list:
                sqlite_db_file = self._get_sqlite_database_file(mysql_server_ct6_db, mysql_cursor)
                if sqlite_db_file and os.path.isfile(sqlite_db_file):
                    raise Exception(f"The {sqlite_db_file} sqlite database file already exists.")

            for mysql_server_ct6_db in mysql_server_ct6_db_list:
                self._convert_database(mysql_server_ct6_db, mysql_cursor)

        finally:
            if mysql_cursor:
                mysql_cursor.close()
            if mysql_conn:
                mysql_conn.close()
        elapsed_seconds = int(time() - start_time)
        hms_str = self.seconds_to_hms(elapsed_seconds)
        self._uio.info(f"Conversion took {hms_str} (HH:MM:SS)")

    def seconds_to_hms(self, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"

    def _convert_database(self, db_name, mysql_cursor):
        """@brief Convert the CT6 mysql database to an sqlite database.
           @param db_name The name of the mysql database.
           @param mysql_cursor The cursor connected to the mysql database."""
        sqlite_db_file = self._get_sqlite_database_file(db_name, mysql_cursor)
        if sqlite_db_file:
            if os.path.isfile(sqlite_db_file):
                raise Exception(f"{sqlite_db_file} file already exits.")
            self._copy_mysql_to_sqlite_db(mysql_cursor, sqlite_db_file)
            self.create_timestamp_index(sqlite_db_file, MYSQLImporter.VALID_CT6_DB_TABLE_NAMES[1])
            self.add_unit_name_column(sqlite_db_file, db_name)

    def _copy_mysql_to_sqlite_db(self, mysql_cursor, sqlite_db_file, batch_size=100000):
        """@brief Copy the contents of all the tables from the mysql db to the sqlite db.
           @param mysql_cursor The cursor for the mysql database.
           @param sqlite_db_file The sqlite DB to create.
           @param batch_size As the mysql tables may be quite large they are converted in chunks.
                  This is the chunk size in table records."""
        sqlite_conn = None
        sqlite_cursor = None
        try:
            sqlite_conn = sqlite3.connect(sqlite_db_file)
            sqlite_cursor = sqlite_conn.cursor()
            self._uio.info(f"Creating {sqlite_db_file} (sqlite) database file.")

            # Fetch MySQL table names
            mysql_cursor.execute("SHOW TABLES")
            tables = mysql_cursor.fetchall()

            mysql_cursor.execute("SELECT count(*) FROM CT6_SENSOR")
            columns = mysql_cursor.fetchall()

            for table_name in tables:
                table_name = table_name[0]
                self._uio.info(f"Processing table: {table_name}")

                # Get table structure from MySQL
                mysql_cursor.execute(f"DESCRIBE {table_name}")
                columns = mysql_cursor.fetchall()

                # Generate CREATE TABLE statement for SQLite
                column_definitions = []
                for col in columns:
                    col_name, col_type = col[0], col[1]
                    # Convert MySQL to SQLite types
                    if 'int' in col_type:
                        col_type = 'INTEGER'
                    elif 'varchar' in col_type or 'text' in col_type:
                        col_type = 'TEXT'
                    elif 'float' in col_type or 'double' in col_type:
                        col_type = 'REAL'
                    else:
                        col_type = 'TEXT'

                    column_definitions.append(f"{col_name} {col_type}")

                create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_definitions)});"
                sqlite_cursor.execute(create_table_sql)

                # Fetch data from MySQL and insert into SQLite using blocks
                mysql_cursor.execute(f"SELECT * FROM {table_name}")
                placeholders = ', '.join(['?'] * len(columns))

                total_rows = 0
                while True:
                    rows = mysql_cursor.fetchmany(batch_size)
                    if not rows:
                        break

                    sqlite_cursor.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)
                    total_rows += len(rows)
                    self._uio.info(f"Inserted {total_rows} rows into {table_name}...")

                self._uio.info(f"Finished inserting {total_rows} rows into {table_name}")

            # Commit and close
            sqlite_conn.commit()
            self._uio.info("Conversion completed successfully.")

        finally:
            if sqlite_cursor:
                sqlite_cursor.close()
                sqlite_cursor = None
            if sqlite_conn:
                sqlite_conn.close()
                sqlite_conn = None

    def add_unit_name_column(self, sqlite_db, unit_name):
        """@brief Add a unit name column to the CT6_META table. The mysql database does not have
                  this column. Create this field in the sqlite database.
           @param sqlite_db The sqlite database file.
           @param unit_name The name of the CT6 device."""
        sqlite_conn = None
        sqlite_cursor = None
        try:
            sqlite_conn = sqlite3.connect(sqlite_db)
            sqlite_cursor = sqlite_conn.cursor()
            print(f"Connected to SQLite: {sqlite_db}")

            # Step 1: Create a new table with the column at index 1
            sqlite_cursor.execute('''
            CREATE TABLE CT6_META_NEW (
                ID INTEGER PRIMARY KEY,
                HW_ASSY TEXT,
                UNIT_NAME TEXT,
                CT1_NAME TEXT,
                CT2_NAME TEXT,
                CT3_NAME TEXT,
                CT4_NAME TEXT,
                CT5_NAME TEXT,
                CT6_NAME TEXT
            )
            ''')

            # Step 2: Copy data, setting UNIT_NAME to NULL for now
            sqlite_cursor.execute('''
                INSERT INTO CT6_META_NEW (HW_ASSY, CT1_NAME, CT2_NAME, CT3_NAME, CT4_NAME, CT5_NAME, CT6_NAME)
                SELECT HW_ASSY, CT1_NAME, CT2_NAME, CT3_NAME, CT4_NAME, CT5_NAME, CT6_NAME FROM CT6_META
            ''')

            sqlite_cursor.execute(f"UPDATE CT6_META_NEW SET UNIT_NAME = '{unit_name}'")

            # Step 3: Optional - Drop the old table
            sqlite_cursor.execute('DROP TABLE CT6_META')

            # Step 4: Rename the new table to the original name
            sqlite_cursor.execute('ALTER TABLE CT6_META_NEW RENAME TO CT6_META')

            sqlite_conn.commit()

        except Exception:
            raise

        finally:
            if sqlite_cursor:
                sqlite_cursor.close()
            if sqlite_conn:
                sqlite_conn.close()

    def create_timestamp_index(self, sqlite_db_file, table_name):
        """@brief Create an index in the sqlite database on the TIMESTAMP column.
                  Most searches are based around timestamp so this should speed up these searches.
           @param sqlite_db The sqlite database file.
           @param table_name The name of the table to index.
           """
        sqlite_conn = None
        sqlite_cursor = None
        try:
            sqlite_conn = sqlite3.connect(sqlite_db_file)
            sqlite_cursor = sqlite_conn.cursor()
            self._uio.info(f"Indexing the {table_name} table in the {sqlite_db_file} database.")

            # Index on time stamp as most searches will be based around a date/time
            cmd = f"CREATE INDEX {table_name}_INDEX ON {table_name} ({SQLite3DBClient.TIMESTAMP})"
            sqlite_cursor.execute(cmd)

            sqlite_conn.commit()

        finally:
            if sqlite_cursor:
                sqlite_cursor.close()
            if sqlite_conn:
                sqlite_conn.close()

class AppServer(object):
    """@brief Responsible for
        - Starting the YViewCollector.
        - Storing data in the database.
        - Presenting the user with a web GUI to allow data to be displayed and manipulated."""

    DEFAULT_CONFIG_FILENAME = "ct6_app.cfg"
    LOCK_FILE_NAME = "ct6.lock"

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A ConfigBase instance."""
        self._uio = uio
        self._options = options
        self._config = config

    def _waitfor_sqlite_db(self):
        """@brief Block waiting for at least one sqlite database to be available."""
        db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
        while True:
            dbFileList = SQLite3DBClient.GetDBFileList(db_storage_folder)
            if len(dbFileList) > 0:
                break
            self._uio.info(f"Waiting for CT6 databases to appear in {db_storage_folder} before starting GUI.")
            sleep(10)

    def _startGUI(self, db_client):
        """@Start the App server running.
           @param db_client An instance of SQLite3DBClient."""
        try:
            # We block here waiting for CT6 db's to be created by the SQLite3DBClient thread.
            self._waitfor_sqlite_db()

            # If server login is enabled we pass the credentials file to the gui
            # This contains hashed credential details.
            loginEnabled = self._config.getAttr(ConfigBase.SERVER_LOGIN)
            if loginEnabled:
                credFile = CRED_JSON_FILE
            else:
                credFile = None
            gui = GUI(self._uio, self._options, self._config, credFile, db_client)
            openBrowser = not self._options.no_gui
            # Block waiting for at least one sqlite database to be available before starting the GUI.
            gui.runBlockingBokehServer(gui.get_app_method_dict(), openBrowser=openBrowser)

        finally:
            self.close()

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
            threading.Thread(target=self._localYViewCollector.start, args=(net_if,)).start()

            # Start a web UI to allow the user to view the data
            self._startGUI(db_client)

        finally:
            db_client.disconnect()

# PJA TODO, auto restart threads if they crash














class GUI(MultiAppServer):
    """@brief Responsible for providing the GUI dashboard for viewing data from CT6 devices.
              This is provided over a Web interface."""

    PAGE_TITLE                  = "CT6 Dashboard"
    BOKEH_ALLOW_WS_ORIGIN       = 'BOKEH_ALLOW_WS_ORIGIN'

    DB_META_TABLE_NAME          = BaseConstants.CT6_META_TABLE_NAME

    CT1_NAME                    = BaseConstants.CT1_NAME
    CT2_NAME                    = BaseConstants.CT2_NAME
    CT3_NAME                    = BaseConstants.CT3_NAME
    CT4_NAME                    = BaseConstants.CT4_NAME
    CT5_NAME                    = BaseConstants.CT5_NAME
    CT6_NAME                    = BaseConstants.CT6_NAME

    UPDATE_SECONDS              = "UPDATE_SECONDS"
    STATUS_MESSAGE              = "STATUS"
    STATUS_LINE_INDEX           = "STATUS_LINE_INDEX"
    CMD_COMPLETE                = "CMD_COMPLETE"
    ENABLE_ACTION_BUTTONS       = "ENABLE_ACTION_BUTTONS"
    SUMMARY_ROW                 = "SUMMARY_ROW"

    X_AXIS_NAME                 = "date"
    DEFAULT_YAXIS_NAME          = "kW"
    AC_VOLTS_YAXIS_NAME         = "Volts"
    AC_FREQ_YAXIS_NAME          = "Hertz"
    TEMP_YAXIS_NAME             = "°C"
    RSSI_YAXIS_NAME             = "dBm"

    MAX_RESOLUTION              = 0
    MINUTE_RESOLUTION           = 1
    HOUR_RESOLUTION             = 2
    DAY_RESOLUTION              = 3

    TOOLS                       = "crosshair,pan,wheel_zoom,zoom_in,zoom_out,box_zoom,undo,redo,reset,tap,save,box_select,poly_select,lasso_select"
    TOOLBAR_LOCATION            = "below"

    PLOT_TYPE_POWER_ACTIVE      = 1 # Show the active power plot.
    PLOT_TYPE_POWER_REACTIVE    = 2 # Show the reactive power plot.
    PLOT_TYPE_POWER_APPARENT    = 3 # Show the apparent power plot.
    PLOT_TYPE_POWER_FACTOR      = 4 # # Show the power factor plot.
    PLOT_TYPE_AC_VOLTS          = 5 # Show the AC voltage plot.
    PLOT_TYPE_AC_FREQ           = 6 # Show the AC frequency
    PLOT_TYPE_TEMP              = 7 # Show the unit temperature
    PLOT_TYPE_RSSI              = 8 # Show the WiFi signal strength

    BUTTON_TYPE                 = "success"

    SENSOR_COUNT                = 6

    LOCAL_PATH                  = os.path.dirname(os.path.abspath(__file__))

    META_DATA_ROW               = "META_DATA_ROW"

    META_TABLE_ID_INDEX = 0
    META_TABLE_ASSY_INDEX = 1
    META_TABLE_DEVNAME_INDEX = 2
    META_TABLE_CT1_NAME_INDEX = 3
    META_TABLE_CT2_NAME_INDEX = 4
    META_TABLE_CT3_NAME_INDEX = 5
    META_TABLE_CT4_NAME_INDEX = 6
    META_TABLE_CT5_NAME_INDEX = 7
    META_TABLE_CT6_NAME_INDEX = 8

    @staticmethod
    def GetLoginPage():
        """@brief Get the abs path to the login.html file.
           @return The full path to the login.html file."""
        loginHtmlFile = os.path.join(GUI.LOCAL_PATH, "assets/login.html")
        if not os.path.isfile(loginHtmlFile):
            loginHtmlFile = os.path.join(GUI.LOCAL_PATH, "../assets/login.html")
            if not os.path.isfile(loginHtmlFile):
                raise Exception(f'{loginHtmlFile} file not found.')
        return loginHtmlFile

    def __init__(self, uio, options, config, loginCredentialsFile, db_client):
        """@brief Constructor.
           @param uio A UIO instance responsible for stdout/stdin input output.
           @param options The command line argparse options instance.
           @param config The dash app config.
           @param loginCredentialsFile A file containing the login credentials or None if no server authentication is required.
           @param db_client An instance of SQLite3DBClient."""
        super().__init__(address=config.getAttr(AppConfig.LOCAL_GUI_SERVER_ADDRESS),
                         bokehPort=config.getAttr(AppConfig.LOCAL_GUI_SERVER_PORT),
                         credentialsJsonFile=loginCredentialsFile,
                         loginHTMLFile=GUI.GetLoginPage(),
                         accessLogFile=config.getAttr(AppConfig.SERVER_ACCESS_LOG_FILE) )
        self._uio = uio
        self._options = options
        self._config = config
        self._db_client = db_client

        self._doc = None
        self._server = None
        self._tabList = None
        self._dbHandler = None
        self._startUpdateTime = None
        self._programVersion = CT6Base.GetProgramVersion()

        # this queue is used to send commands from the GUI thread and read responses received from outside the GUI thread.
        self._commsQueue = Queue()

        self._startupShow = True

        self._plotPanel = None
        self._updatePlotType = GUI.PLOT_TYPE_POWER_ACTIVE
        self._cmdButtonList = []
        self._db_dicts = {}

    def get_app_method_dict(self):
        """@return The server app method dict."""
        appMethodDict = {}
        appMethodDict['/']=self._mainApp
        return appMethodDict

    def _executeSQL(self, conn, cmd):
        """@brief Execute an SQL cmd.
           @param cmd The SQL command.
           @return The response tuple."""
        cursor = conn.cursor()
        self._uio.debug(f"SQL CMD: {cmd}")
        cursor.execute(cmd)
        response_tuple = cursor.fetchall()
        conn.commit()
        cursor.close()
        return response_tuple

    def _update_db_dicts(self):
        """@brief Connect to all available databases."""
        db_storage_folder = self._config.getAttr(AppConfig.DB_STORAGE_PATH)
        db_file_list = SQLite3DBClient.GetDBFileList(db_storage_folder)
        for db_file in db_file_list:
            conn = None
            try:
                # Connect to the database
                conn = sqlite3.connect(db_file)
                # We'll store parameters in this dict
                db_dict = {}
                self._db_dicts[db_file]=db_dict
                # Get the meta data for the db and store in the db_dict
                cmd = "select * from {} limit 1;".format(GUI.DB_META_TABLE_NAME)
                response_tuple = self._executeSQL(conn, cmd)
                if response_tuple and len(response_tuple) > 0:
                    # The key in this dict will be the database name.
                    # The value is the contents of the first row in the table.
                    db_dict[GUI.META_DATA_ROW]=response_tuple[0]
            finally:
                if conn:
                    conn.close()
                    # Help garbage collector
                    conn = None

    def _updateEnabledState(self, newState, field, enabledText):
        """@brief Update the enabled/disabled state of the field
                  based upon its state.
           @param newState The new state as text.
           @param field The Widget to be updated.
           @param enabledText The value of newState when the field should be enabled."""
        if newState == enabledText:
            field.disabled = False
        else:
            field.disabled = True

    def _getDictValue(self, aDict, aKey, retInt=False):
        """@brief Get a value from a dict.
           @param aDict The idtc to read the value from.
           @param aKey The key to read from the dict.
           @param retInt If True then return an integer.
           @return The value read from the dict or None if not found."""
        retValue=None
        if aKey in aDict:
            retValue = aDict[aKey]
            if retInt:
                retValue=int(retValue)
        return retValue

    def _updateField(self, inputField, value):
        """@brief Update the input field if the value has changed.
           @param inputField The input field instance.
           @param value The value to be displayed in this input field."""
        if inputField.value != value:
            inputField.value = value

    def _refreshDevConfig(self):
        """@brief Refresh the displayed configuration."""
        assy = self._selectDeviceSelect.value
        if assy and len(assy) > 0:
            devDict = self._deviceDict[assy]
            self._updateSelectedDevice(devDict)

    def _todayButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        self._startDateTimePicker.value = today.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _yesterdayButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        yesterday = today - timedelta(days = 1)
        self._startDateTimePicker.value = yesterday.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
       # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisWeekButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfWeek = today.weekday()
        startOfWeek = today - timedelta(days = dayOfWeek)
        today = datetime.today()
        self._startDateTimePicker.value = startOfWeek.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastWeekButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfWeek = today.weekday()
        endOfLastWeek = today - timedelta(days = dayOfWeek+1)
        startOfLastWeek = endOfLastWeek - timedelta(days = 6)
        self._startDateTimePicker.value = startOfLastWeek.date()
        # Set resolution to mins to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 1
        endDateTime = endOfLastWeek.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisMonthButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfMonth = today.day
        firstDayOfMonth = today - timedelta(days = dayOfMonth-1)
        self._startDateTimePicker.value = firstDayOfMonth.date()
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        endDateTime = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastMonthButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        dayOfMonth = today.day
        lastDayOfLastMonth = today - timedelta(days = dayOfMonth)
        daysInLastMonth = calendar.monthrange(lastDayOfLastMonth.year, lastDayOfLastMonth.month)[1]
        firstDayOfLastMonth = lastDayOfLastMonth - timedelta(days = daysInLastMonth-1)
        self._startDateTimePicker.value = firstDayOfLastMonth.date()
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        endDateTime = lastDayOfLastMonth.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._stopDateTimePicker.value = endDateTime
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _thisYearButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = datetime.today()
        self._startDateTimePicker.value = datetime(today.year, 1, 1, 0, 0 , 0, 0)
        self._stopDateTimePicker.value  = datetime(today.year, 12, 31, 23,59, 39, 999999)
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _lastYearButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        today = date.today()
        self._startDateTimePicker.value = datetime(today.year-1, 1, 1, 0, 0 , 0, 0)
        self._stopDateTimePicker.value  = datetime(today.year-1, 12, 31, 23,59, 39, 999999)
        # Set resolution to hours to set a good trade off between plot time and resolution
        self._resRadioButtonGroup.active = 2
        # Kick of a plot attempt to save pressing the power button afterwards
        self._plotSensorData(True)

    def _powerButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._plotSensorData(True)

    def _powerFactorButtonHandler(self, event):
        """@brief Process button click.
           @param event The button event."""
        self._plotSensorData(False)

    def _plotSensorData(self, plotPower):
        if plotPower:
            if self._pwrTypeRadioButtonGroup.active == 0:
                self._updatePlotType = GUI.PLOT_TYPE_POWER_ACTIVE

            elif self._pwrTypeRadioButtonGroup.active == 1:
                self._updatePlotType = GUI.PLOT_TYPE_POWER_REACTIVE

            elif self._pwrTypeRadioButtonGroup.active == 2:
                self._updatePlotType = GUI.PLOT_TYPE_POWER_APPARENT

        else:
            self._updatePlotType = GUI.PLOT_TYPE_POWER_FACTOR

        self._startUpdateTime = time()
        self._enableReadDBButtons(False)
        self._clearSummaryTable()
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _enableReadDBButtons(self, enabled):
        """@brief Enable/Disable all buttons that allow the user to read from the database.
           @param enabled If True the buttons are enabled."""
        # Set the button state in a callback or a locking error will ensue
        if enabled:
            self._doc.add_next_tick_callback(self._setButtonsActive)
        else:
            self._doc.add_next_tick_callback(self._setButtonsDisabled)

    def _enableButtons(self, enabled):
        """@brief Enable/disable buttons.
           @param enabled True if buttons are to be enabled."""
        for button in self._cmdButtonList:
            button.disabled = not enabled

    def _setButtonsActive(self):
        self._enableButtons(True)

    def _setButtonsDisabled(self):
        self._enableButtons(False)

    def _getActionButtonPanel(self):
        self._powerButton = Button(label="Power", button_type=GUI.BUTTON_TYPE)
        self._powerButton.on_click(self._powerButtonHandler)

        self._powerFactorButton = Button(label="Power Factor", button_type=GUI.BUTTON_TYPE)
        self._powerFactorButton.on_click(self._powerFactorButtonHandler)

        self._voltageButton = Button(label="AC Voltage", button_type=GUI.BUTTON_TYPE)
        self._voltageButton.on_click(self._showACVolts)

        self._freqButton = Button(label="AC Frequency", button_type=GUI.BUTTON_TYPE)
        self._freqButton.on_click(self._showACFreq)

        row1 = row(children=[self._powerButton, self._powerFactorButton, self._voltageButton])

        self._tempButton = Button(label="Temperature", button_type=GUI.BUTTON_TYPE)
        self._tempButton.on_click(self._showTemp)

        self._rssiButton = Button(label="WiFi RSSI", button_type=GUI.BUTTON_TYPE)
        self._rssiButton.on_click(self._showRSSI)

        row2 = row(children=[self._freqButton, self._tempButton, self._rssiButton])

        return column(children=[row1, row2])

    def _showACVolts(self):
        """@brief Show the AC volts plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_VOLTS
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showACFreq(self):
        """@brief Show the AC freq plot."""
        self._updatePlotType = GUI.PLOT_TYPE_AC_FREQ
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showTemp(self):
        """@brief Show unit temperature plot."""
        self._updatePlotType = GUI.PLOT_TYPE_TEMP
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _showRSSI(self):
        """@brief Show the WiFi RSSI plot."""
        self._updatePlotType = GUI.PLOT_TYPE_RSSI
        self._startUpdateTime = time()
        self._clearSummaryTable()
        self._enableReadDBButtons(False)
        self._showStatus(0, "Reading Data...")
        # Run thread to recover the data from the database.
        threading.Thread( target=self._readDataBase, args=(self._getSelectedDataBase(),
                                                           self._startDateTimePicker.value,
                                                           self._stopDateTimePicker.value,
                                                           self._resRadioButtonGroup.active)).start()

    def _getControlPanel(self, sensorNames):
        """@brief Get an instance of the button panel.
           @param sensorNames A list of the names of the sensors.
           @return an instance of the button panel."""
        self._todayButton = Button(label="Today", button_type=GUI.BUTTON_TYPE)
        self._todayButton.on_click(self._todayButtonHandler)

        self._yesterdayButton = Button(label="Yesterday", button_type=GUI.BUTTON_TYPE)
        self._yesterdayButton.on_click(self._yesterdayButtonHandler)

        self._thisWeekButton = Button(label="This week", button_type=GUI.BUTTON_TYPE)
        self._thisWeekButton.on_click(self._thisWeekButtonHandler)

        self._lastWeekButton = Button(label="Last week", button_type=GUI.BUTTON_TYPE)
        self._lastWeekButton.on_click(self._lastWeekButtonHandler)

        self._thisMonthButton = Button(label="This Month", button_type=GUI.BUTTON_TYPE)
        self._thisMonthButton.on_click(self._thisMonthButtonHandler)

        self._lastMonthButton = Button(label="Last Month", button_type=GUI.BUTTON_TYPE)
        self._lastMonthButton.on_click(self._lastMonthButtonHandler)

        self._thisYearButton = Button(label="This Year", button_type=GUI.BUTTON_TYPE)
        self._thisYearButton.on_click(self._thisYearButtonHandler)

        self._lastYearButton = Button(label="Last Year", button_type=GUI.BUTTON_TYPE)
        self._lastYearButton.on_click(self._lastYearButtonHandler)

        addStartDaybutton = Button(label = ">")
        addStartDaybutton.on_click(self._addStartDayCallBack)

        subtractStartDaybutton = Button(label = "<")
        subtractStartDaybutton.on_click(self._subtractStartDayCallBack)

        addStopDaybutton = Button(label = ">")
        addStopDaybutton.on_click(self._addStopDayCallBack)

        subtractStopDaybutton = Button(label = "<")
        subtractStopDaybutton.on_click(self._subtractStopDayCallBack)

        self._startDateTimePicker = DatetimePicker(title='Start (year-month-day hour:min)')
        self._stopDateTimePicker = DatetimePicker(title='Stop (year-month-day hour:min)')

        # Div to move the table down to the top edge of the plot.
        div1 = Div(height=20)
        leftButtonPanel = column(children=[self._todayButton, self._thisWeekButton, self._thisMonthButton, self._thisYearButton])
        rightButtonPanel = column(children=[self._yesterdayButton, self._lastWeekButton, self._lastMonthButton, self._lastYearButton])
        buttonPanel0 = row(children=[leftButtonPanel, rightButtonPanel])
        buttonPanel1 = row(children=[subtractStartDaybutton, self._startDateTimePicker, addStartDaybutton])
        buttonPanel2 = row(children=[subtractStopDaybutton, self._stopDateTimePicker, addStopDaybutton])
        self._line0StatusDiv = Div()
        self._line1StatusDiv = Div()
        self._line2StatusDiv = Div()
        self._line3StatusDiv = Div()
        self._line4StatusDiv = Div()
        self._line5StatusDiv = Div()

        summaryTable = self._getSummaryTable()

        resLabels = ["Sec", "Min", "Hour", "Day"]
        self._resRadioButtonGroup = RadioButtonGroup(labels=resLabels, active=1)
        buttonPanel3 = row(children=[self._resRadioButtonGroup])

        pwrTypeLabels = ["Active", "Reactive", "Apparent"]
        self._pwrTypeRadioButtonGroup = RadioButtonGroup(labels=pwrTypeLabels, active=0)
        buttonPanel4 = row(children=[self._pwrTypeRadioButtonGroup])

        pwrPolarityLabels = ["Import is positive", "Import is negative"]
        if self._options.positive:
            defaultpwrPolarity = 0
        else:
            defaultpwrPolarity = 1
        self._pwrPolarityRadioButtonGroup = RadioButtonGroup(labels=pwrPolarityLabels, active=defaultpwrPolarity)
        buttonPanel5 = row(children=[self._pwrPolarityRadioButtonGroup])

        buttonPanel6 = column(children=[buttonPanel3,
                                        buttonPanel4,
                                        buttonPanel5])

        resLabelButton = HelpButton(label="", button_type="default", disabled=True, tooltip = Tooltip(content="Select the plot resolution.", position="left"))
        pwrTypeLabelButton = HelpButton(label="", button_type="default", disabled=True, tooltip = Tooltip(content="Select the power type. Active = Power normally charged by electricity supplier.", position="left"))
        pwrPolarityLabelButton = HelpButton(label="", button_type="default", disabled=True, tooltip = Tooltip(content="Select imported electrical power to be plotted as negative or positive values.", position="left"))

        labelPanel = column(children=[resLabelButton,
                                      pwrTypeLabelButton,
                                      pwrPolarityLabelButton])

        optionsButtonPanel = row(children=[labelPanel, buttonPanel6])

        actionButtonPanel = self._getActionButtonPanel()

        buttonPanel = column(children=[div1,
                                       summaryTable,
                                       buttonPanel0,
                                       buttonPanel1,
                                       buttonPanel2,
                                       optionsButtonPanel,
                                       actionButtonPanel,
                                       self._line0StatusDiv,
                                       self._line1StatusDiv,
                                       self._line2StatusDiv,
                                       self._line3StatusDiv,
                                       self._line4StatusDiv,
                                       self._line5StatusDiv])

        self._cmdButtonList = ( self._powerButton,
                                self._powerFactorButton,
                                self._voltageButton,
                                self._freqButton,
                                self._tempButton,
                                self._rssiButton,
                                self._todayButton,
                                self._yesterdayButton,
                                self._thisWeekButton,
                                self._lastWeekButton,
                                self._thisMonthButton,
                                self._lastMonthButton,
                                self._thisYearButton,
                                self._lastYearButton)

        return buttonPanel

    def _addStartDayCallBack(self, event):
        """@brief Called when the associated button is clicked to add a day to the start time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._startDateTimePicker.value/1000)
        self._startDateTimePicker.value = dateTimeObj + timedelta(days=1)

    def _subtractStartDayCallBack(self, event):
        """@brief Called when the associated button is clicked to subtract a day to the start time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._startDateTimePicker.value/1000)
        self._startDateTimePicker.value = dateTimeObj - timedelta(days=1)

    def _addStopDayCallBack(self, event):
        """@brief Called when the associated button is clicked to add a day to the stop time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._stopDateTimePicker.value/1000)
        self._stopDateTimePicker.value = dateTimeObj + timedelta(days=1)

    def _subtractStopDayCallBack(self, event):
        """@brief Called when the associated button is clicked to subtract a day to the stop time.
           @param event The event that triggered the method call."""
        dateTimeObj=datetime.fromtimestamp(self._stopDateTimePicker.value/1000)
        self._stopDateTimePicker.value = dateTimeObj - timedelta(days=1)

    def _getSelectedDevice(self):
        """@brief Get the name of the selected CT6 device.
           @return The name of the selected CT6 device or None if not selected."""
        if len(self._tabList) > 0 and \
           self._allTabsPanel.active >= 0 and \
           self._allTabsPanel.active < len(self._tabList):
            return self._tabList[self._allTabsPanel.active].title

        return None

    def _getSelectedDataBase(self):
        """@brief The name of the db file selected.
           @return The db file selected."""
        selected_dev = self._getSelectedDevice()
        selected_db_file = None
        for db_file in self._db_dicts.keys():
            db_dict = self._db_dicts[db_file]
            meta_row_data = db_dict[GUI.META_DATA_ROW]
            if selected_dev == meta_row_data[GUI.META_TABLE_DEVNAME_INDEX]:
                selected_db_file = db_file
                break
        return selected_db_file

    def _getSummaryTable(self):
        """@brief Get a DataTable instance of the summary table.
           @param sensorNames A list of  the names of the sensors.
           @return A DataTable instance."""
        summaryTable = None
        self._baseV = 0.0
        # We need separate row instances for each parameter to ensure first update works on first read.
        self._emptySensorColumn1 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._emptySensorColumn2 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._emptySensorColumn3 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._emptySensorColumn4 = ["" for i in range(0, GUI.SENSOR_COUNT)]
        self._data = dict(
                sensor      =   self._emptySensorColumn1, # At this point we don't know the sensor names as multiple databases from multiple CT6 devices may be found
                total       =   self._emptySensorColumn2,
                positive    =   self._emptySensorColumn3,
                negative    =   self._emptySensorColumn4,
            )
        self._summaryTableSource = ColumnDataSource(self._data)

        greenColTemplate="""<div style="background:green; color: black"><%= value %></div>"""
        greenFormatter =  HTMLTemplateFormatter(template=greenColTemplate)
        redColTemplate="""<div style="background:orange; color: white"><%= value %></div>"""
        redFormatter =  HTMLTemplateFormatter(template=redColTemplate)

        columns = [
                TableColumn(field="sensor", title="Sensor"),
                TableColumn(field="total", title="kWh"),
                TableColumn(field="positive", title="kWh",formatter=greenFormatter),
                TableColumn(field="negative", title="kWh",formatter=redFormatter),
            ]
        # Width 300 sets the width of the control panel on the left
        # 300 is wide enough to display the date picker when either
        # the start or stop dates are selected.
        # 180 is tall enough to display all 6 sensor names if configured.
        summaryTable = DataTable(source=self._summaryTableSource,
                                 columns=columns,
                                 index_position = None,
                                 height=180,
                                 width=340,
                                 )

        table_style = InlineStyleSheet(css="""
            .slick-header-columns {
                background-color: #17648D !important;
                font-weight: bold;
                font-size: 12pt;
                color: #FFFFFF;
                text-align: right;
            }
            .slick-row {
                font-size:12pt;
                text-align: left;
            }
        """)
        summaryTable.stylesheets = [table_style]


        return summaryTable


    def _clearSummaryTable(self):
        """@brief Clear the sensor summary table of all data except the names of the sensors."""
        rowCount = GUI.SENSOR_COUNT
        emptySensorColumn = ["" for i in range(0, rowCount)]
        data = dict(sensor=[(slice(rowCount),emptySensorColumn)],
                    total=[(slice(rowCount),emptySensorColumn)],
                    positive=[(slice(rowCount),emptySensorColumn)],
                    negative=[(slice(rowCount),emptySensorColumn)]
                    )
        self._summaryTableSource.patch(data)

    def _updateSummaryTable(self, rxDict):
        """@brief Clear the sensor summary table of all data except the names of the sensors.
           @brief rxDict The dict received from the _calcKWH() method"""
        invertKw = self._invertKW()
        if GUI.SUMMARY_ROW in rxDict:
            row = rxDict[GUI.SUMMARY_ROW]
            if len(row) == 5:
                rowIndex = row[0]-1 # Row index is one less than the CT number
                if invertKw:
                    data = dict(sensor=[(rowIndex,f"{row[1]}")],
                                total=[(rowIndex,f"{row[2]:.2f}")],
                                negative=[(rowIndex,f"{row[3]:.2f}")],
                                positive=[(rowIndex,f"{row[4]:.2f}")]
                                )
                else:
                    data = dict(sensor=[(rowIndex,f"{row[1]}")],
                                total=[(rowIndex,f"{row[2]:.2f}")],
                                positive=[(rowIndex,f"{row[3]:.2f}")],
                                negative=[(rowIndex,f"{row[4]:.2f}")]
                                )
                self._summaryTableSource.patch(data)

    def _showStatus(self, statusID, line):
        """@brief Show Status messages
           @param statusID The status line index.
           @param line The message text."""
        if statusID == 0:
            self._line0StatusDiv.text = line
        if statusID == 1:
            self._line1StatusDiv.text = line
        if statusID == 2:
            self._line2StatusDiv.text = line
        if statusID == 3:
            self._line3StatusDiv.text = line
        if statusID == 4:
            self._line4StatusDiv.text = line
        if statusID == 5:
            self._line5StatusDiv.text = line

    def _clearStatusLines(self):
        """@brief Clear all status line text."""
        self._line0StatusDiv.text = ""
        self._line1StatusDiv.text = ""
        self._line2StatusDiv.text = ""
        self._line3StatusDiv.text = ""
        self._line4StatusDiv.text = ""
        self._line5StatusDiv.text = ""

    def _mainApp(self, doc):
        """@brief create the GUI page.
           @param doc The document to add the plot to."""
        self._startupShow = True

        self._update_db_dicts()

        # Clear the queue once we have the lock to ensure it's
        # not being read inside the _update() method.
        while not self._commsQueue.empty():
            self._commsQueue.get(block=False)

        doc.clear()
        self._doc = doc
        # Set the Web page title
        self._doc.title = GUI.PAGE_TITLE
        self._tabList = []
        # 1 rem generally = 16px
        # Using rem rather than px can help ensure consistency of font size and spacing throughout your UI.
        fontSize='1rem'
        theme = "dark_minimal"
        self._plotPanels = []

        self._dbTableList = []
        self._cdsDict = {}
        for dbName in self._db_dicts.keys():
            db_dict = self._db_dicts[dbName]

            colors = itertools.cycle(Category20_20)

            # One panel multiple plot traces
            # By default select the zoom tool
            self._plotPanel = figure(title="",
                               sizing_mode="stretch_both",
                               tools=GUI.TOOLS,
                               toolbar_location="below",
                               x_axis_type='datetime',
                               active_drag="box_zoom",
                               y_axis_label="kW")
            self._plotPanels.append(self._plotPanel)

            hover = HoverTool()
            dateS =  '@{}'.format(GUI.X_AXIS_NAME)
            dateS += '{%F}'
            hover.tooltips = [("","$name"),("kW", "$y{1.1f}"), ('date', "$x{%Y-%m-%d}"), ('time', "$x{%H:%M:%S}"), ("sample", "$index")]
            hover.formatters = {'$x': 'datetime'}
            self._plotPanel.add_tools(hover)

            self._dbTableList.append( (dbName,0) )
            plotNames = self._get_db_plot_names(dbName)
            for i in range(0,6):
                if plotNames[i] and len(plotNames[i]) > 0:

                    cds = ColumnDataSource({GUI.X_AXIS_NAME: [],
                                            GUI.DEFAULT_YAXIS_NAME: []})
                    self._cdsDict[dbName + plotNames[i]] = cds
                    self._plotPanel.line(GUI.X_AXIS_NAME, GUI.DEFAULT_YAXIS_NAME, source=cds, name=plotNames[i], legend_label=plotNames[i], line_color=next(colors), line_width=3)
                    self._plotPanel.legend.click_policy="hide"
            self._plotPanel.legend.location = 'bottom_left'

            self._tabList.append( TabPanel(child=self._plotPanel,  title=db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_DEVNAME_INDEX]) )
            controlPanel = self._getControlPanel(plotNames)

        tabTextSizeSS = [{'.bk-tab': Styles(font_size='{}'.format(fontSize))}, {'.bk-tab': Styles(background='{}'.format('grey'))}]
        self._allTabsPanel = Tabs(tabs=self._tabList, sizing_mode="stretch_both", stylesheets=tabTextSizeSS)
        controlPanel = self._getControlPanel(plotNames)
        leftPanel = column(children=[self._allTabsPanel], sizing_mode="stretch_both")
        mainPanel = row(children=[leftPanel, controlPanel], sizing_mode="stretch_both")

        self._updateYAxis()

        self._doc.add_root( mainPanel )

        self._doc.theme = theme
        self._doc.add_periodic_callback(self._updateCallBack, 100)

        # On Startup set the start/stop dates to show today's data.
        self._todayButtonHandler(None)

        self._showStatus(5, f"Software Version: {self._programVersion}")

    def _get_db_plot_names(self, db_file):
        """@return A list (6 items) of the configured CT6 port names. If not found
                   a list of 6 empty names are returned."""
        plotNames = ['','','','','','']
        if db_file in self._db_dicts:
            db_dict = self._db_dicts[db_file]
            plotNames = (db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT1_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT2_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT3_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT4_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT5_NAME_INDEX],
                         db_dict[GUI.META_DATA_ROW][GUI.META_TABLE_CT6_NAME_INDEX])
        return plotNames

    def _updateYAxis(self):
        """@brief Add the callbacks to set the Y Axis label."""
        for pp in self._plotPanels:
            pwrCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "kW"
            """)
            self._powerButton.js_on_click(pwrCallback)
            self._todayButton.js_on_click(pwrCallback)
            self._yesterdayButton.js_on_click(pwrCallback)
            self._thisWeekButton.js_on_click(pwrCallback)
            self._lastWeekButton.js_on_click(pwrCallback)
            self._thisMonthButton.js_on_click(pwrCallback)
            self._lastMonthButton.js_on_click(pwrCallback)
            self._thisYearButton.js_on_click(pwrCallback)
            self._lastYearButton.js_on_click(pwrCallback)
            pwrFactorCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "Power Factor"
            """)
            self._powerFactorButton.js_on_click(pwrFactorCallback)
            voltageCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "Volts"
            """)
            self._voltageButton.js_on_click(voltageCallback)
            freqCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "Hz"
            """)
            self._freqButton.js_on_click(freqCallback)
            tempCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "°C"
            """)
            self._tempButton.js_on_click(tempCallback)
            rssiCallback = CustomJS(args=dict(axis=pp.yaxis[0]), code="""
                axis.axis_label = "dBm"
            """)
            self._rssiButton.js_on_click(rssiCallback)

    def _plotSingleField(self, plotName, units, appPlotIndex, rxDict):
        """@brief Show a single value list on the plot area
           @param plotName The name of the plot.
           @param units The unit (Y axis label).
           @param appPlotIndex The index of the field on the row data.
           @param rxDict The dict containing the value/s to plot."""
        try:
            self._showStatus(0, "Plotting Data...")

            self._plotPanel.legend.visible=False

            for dbName in self._db_dicts.keys():
                ct1Name, ct2Name, ct3Name, ct4Name, ct5Name, ct6Name = self._get_db_plot_names(dbName)
                ct1TraceKey=dbName+ct1Name
                ct2TraceKey=dbName+ct2Name
                ct3TraceKey=dbName+ct3Name
                ct4TraceKey=dbName+ct4Name
                ct5TraceKey=dbName+ct5Name
                ct6TraceKey=dbName+ct6Name
                if dbName in rxDict:
                    data = rxDict[dbName]
                    #Replace the data set with empty sets to remove traces from plot
                    ct1Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct2Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct3Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct4Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct5Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct6Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}

                    # Remove all data from other traces and use CT1 to display the single trace of interest
                    if ct2TraceKey in self._cdsDict:
                        self._cdsDict[ct2TraceKey].data = ct2Dict
                    if ct3TraceKey in self._cdsDict:
                        self._cdsDict[ct3TraceKey].data = ct3Dict
                    if ct4TraceKey in self._cdsDict:
                        self._cdsDict[ct4TraceKey].data = ct4Dict
                    if ct5TraceKey in self._cdsDict:
                        self._cdsDict[ct5TraceKey].data = ct5Dict
                    if ct6TraceKey in self._cdsDict:
                        self._cdsDict[ct6TraceKey].data = ct6Dict

                    for recordDict in data:
                        if appPlotIndex < len(recordDict):
                            ts = datetime.fromisoformat(recordDict[BaseConstants.TIMESTAMP_INDEX])
                            ct1Dict[GUI.X_AXIS_NAME].append(ts)
                            ct1Dict[GUI.DEFAULT_YAXIS_NAME].append(recordDict[appPlotIndex])
                    # Plot the value of interest using the ct1Dict trace
                    self._cdsDict[ct1TraceKey].data = ct1Dict

        finally:
            self._showStatus(0, "")
            self._enableReadDBButtons(True)
            exeTime = time()-self._startUpdateTime
            msg = f"Took {exeTime:.1f} seconds to read and plot the data."
            self._showStatus(0, msg)

    def _updateCallBack(self):
        # Call the update method so that to ensure it's safe to update the document.
        # This ensures an exception won't be thrown.
        self._doc.add_next_tick_callback(self._update)

    def _update(self, maxDwellMS=1000):
        """@brief Called periodically to update the Web GUI."""
        try:
            startTime = time()

            # Show todays data by default
            if self._startupShow:
                # We need a slight delay on startup of the web GUI is not
                # ready to receive the data from the database.
                sleep(.8)
                self._powerButtonHandler(None)
                self._startupShow = False

            else:

                while not self._commsQueue.empty():
                    rxMessage = self._commsQueue.get()
                    if isinstance(rxMessage, dict):
                        self._processRXDict(rxMessage)

                    # If we've spent long enough processing messages then exit.
                    # Unprocessed messages can be handled the next time _update() is called.
                    if time() > startTime+maxDwellMS:
                        break

        except Exception:
            self._uio.errorException()

    def _processRXDict(self, rxDict):
        """@brief Process the dicts received from the GUI message queue.
           @param rxDict The dict received from the GUI message queue."""
        startT = time()
        fName = inspect.currentframe().f_code.co_name
        self._uio.debug(f"{fName}:")
        if GUI.STATUS_MESSAGE in rxDict:
            index = rxDict[GUI.STATUS_LINE_INDEX]
            msg = rxDict[GUI.STATUS_MESSAGE]
            self._showStatus(index, msg)

        elif GUI.CMD_COMPLETE in rxDict:
            self._statusLabel.text = rxDict[GUI.CMD_COMPLETE]

        elif GUI.ENABLE_ACTION_BUTTONS in rxDict:
            enabled = rxDict[GUI.ENABLE_ACTION_BUTTONS]
            self._enableActionButtons(enabled)

        elif GUI.SUMMARY_ROW in rxDict:
            self._updateSummaryTable(rxDict)

        else:
            if self._updatePlotType == GUI.PLOT_TYPE_AC_VOLTS:
                appPlotIndex = BaseConstants.VOLTAGE_INDEX
                plotName = "AC Voltage"
                units = GUI.AC_VOLTS_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_AC_FREQ:
                appPlotIndex = BaseConstants.FREQUENCY_INDEX
                plotName = "AC Frequency"
                units = GUI.AC_FREQ_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_TEMP:
                appPlotIndex = BaseConstants.TEMPERATURE_INDEX
                plotName = "CT6 device Temperature"
                units = GUI.TEMP_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            elif self._updatePlotType == GUI.PLOT_TYPE_RSSI:
                appPlotIndex = BaseConstants.RSSI_DBM_INDEX
                plotName = "WiFi RSSI"
                units = GUI.RSSI_YAXIS_NAME
                self._plotSingleField(plotName, units, appPlotIndex, rxDict)

            else:
                self._plotKWH(rxDict, self._updatePlotType)

        exeTime = time()-startT
        self._uio.debug(f"{fName}: Execution time {exeTime:.1f} seconds.")


    def _plotKWH(self, rxDict, plotType):
        """@brief Plot the measured powers from the CT sensors.
           @param rxDict The dict of values read from the database.
           @param plotType The type of data to plot."""
        try:
            self._showStatus(0, "Plotting Data...")

            fieldIndexList = None
            if plotType == GUI.PLOT_TYPE_POWER_ACTIVE:
                fieldIndexList = (BaseConstants.CT1_ACT_WATTS_INDEX,
                                 BaseConstants.CT2_ACT_WATTS_INDEX,
                                 BaseConstants.CT3_ACT_WATTS_INDEX,
                                 BaseConstants.CT4_ACT_WATTS_INDEX,
                                 BaseConstants.CT5_ACT_WATTS_INDEX,
                                 BaseConstants.CT6_ACT_WATTS_INDEX)

            elif plotType == GUI.PLOT_TYPE_POWER_REACTIVE:
                fieldIndexList = (BaseConstants.CT1_REACT_WATTS_INDEX,
                                 BaseConstants.CT2_REACT_WATTS_INDEX,
                                 BaseConstants.CT3_REACT_WATTS_INDEX,
                                 BaseConstants.CT4_REACT_WATTS_INDEX,
                                 BaseConstants.CT5_REACT_WATTS_INDEX,
                                 BaseConstants.CT6_REACT_WATTS_INDEX)
                self._plotPanel.yaxis.axis_label = "kVA"
                self._line1StatusDiv.text = ""

            elif plotType == GUI.PLOT_TYPE_POWER_APPARENT:
                fieldIndexList = (BaseConstants.CT1_APP_WATTS_INDEX,
                                 BaseConstants.CT2_APP_WATTS_INDEX,
                                 BaseConstants.CT3_APP_WATTS_INDEX,
                                 BaseConstants.CT4_APP_WATTS_INDEX,
                                 BaseConstants.CT5_APP_WATTS_INDEX,
                                 BaseConstants.CT6_APP_WATTS_INDEX)
                self._plotPanel.yaxis.axis_label = "kVA"
                self._line1StatusDiv.text = ""

            elif plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                fieldIndexList = (BaseConstants.CT1_PF_INDEX,
                                 BaseConstants.CT2_PF_INDEX,
                                 BaseConstants.CT3_PF_INDEX,
                                 BaseConstants.CT4_PF_INDEX,
                                 BaseConstants.CT5_PF_INDEX,
                                 BaseConstants.CT6_PF_INDEX)
                self._plotPanel.yaxis.axis_label = "Power Factor"
                self._line1StatusDiv.text = ""

            self._plotPanel.legend.visible=True
            for dbName in self._db_dicts.keys():
                # This dict holds the values to be plotted
                # key = The name of the trace
                # value = A tuple containing
                #     0 = A list of the X values
                #     1 = A list of the Y values
                # If we have the results from this CT4 device in the database
                if dbName in rxDict:
                    ct1TraceKey = None
                    ct2TraceKey = None
                    ct3TraceKey = None
                    ct4TraceKey = None
                    ct5TraceKey = None
                    ct6TraceKey = None
                    rowList = rxDict[dbName]
                    ct1Name, ct2Name, ct3Name, ct4Name, ct5Name, ct6Name = self._get_db_plot_names(dbName)

                    #If CT1 is in use
                    if ct1Name and len(ct1Name) > 0:
                        ct1TraceKey=dbName+ct1Name

                    #If CT2 is in use
                    if ct2Name and len(ct2Name) > 0:
                        ct2TraceKey=dbName+ct2Name

                    #If CT3 is in use
                    if ct3Name and len(ct3Name) > 0:
                        ct3TraceKey=dbName+ct3Name

                    #If CT4 is in use
                    if ct4Name and len(ct4Name) > 0:
                        ct4TraceKey=dbName+ct4Name

                    #If CT5 is in use
                    if ct5Name and len(ct5Name) > 0:
                        ct5TraceKey=dbName+ct5Name

                    #If CT6 is in use
                    if ct6Name and len(ct6Name) > 0:
                        ct6TraceKey=dbName+ct6Name

                    #Replace the data set
                    ct1Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct2Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct3Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct4Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct5Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}
                    ct6Dict = {GUI.X_AXIS_NAME: [], GUI.DEFAULT_YAXIS_NAME: []}

                    for _row in rowList:

                        if ct1TraceKey:
                            self._addToPlot(ct1Dict, _row, fieldIndexList[0], plotType)

                        if ct2TraceKey:
                            self._addToPlot(ct2Dict, _row, fieldIndexList[1], plotType)

                        if ct3TraceKey:
                            self._addToPlot(ct3Dict, _row, fieldIndexList[2], plotType)

                        if ct4TraceKey:
                            self._addToPlot(ct4Dict, _row, fieldIndexList[3], plotType)

                        if ct5TraceKey:
                            self._addToPlot(ct5Dict, _row, fieldIndexList[4], plotType)

                        if ct6TraceKey:
                            self._addToPlot(ct6Dict, _row, fieldIndexList[5], plotType)

                    if ct1TraceKey:
                        self._cdsDict[ct1TraceKey].data = ct1Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(1, ct1Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct2TraceKey:
                        self._cdsDict[ct2TraceKey].data = ct2Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(2, ct2Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct3TraceKey:
                        self._cdsDict[ct3TraceKey].data = ct3Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(3, ct3Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct4TraceKey:
                        self._cdsDict[ct4TraceKey].data = ct4Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(4, ct4Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct5TraceKey:
                        self._cdsDict[ct5TraceKey].data = ct5Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(5, ct5Name, rowList, self._resRadioButtonGroup.active)).start()

                    if ct6TraceKey:
                        self._cdsDict[ct6TraceKey].data = ct6Dict
                        # Start a thread to calculate the kWh for this sensor
                        threading.Thread( target=self._calcKWH, args=(6, ct6Name, rowList, self._resRadioButtonGroup.active)).start()

        finally:
            self._showStatus(0, "")
            self._enableReadDBButtons(True)
            exeTime = time()-self._startUpdateTime
            msg = f"Took {exeTime:.1f} seconds to read and plot the data."
            self._showStatus(0, msg)

    def _invertKW(self):
        """@brief Determine if the user wishes to invert the kW plots.
                  By default imported electricity is shown as negative values.
           @return False if the user wishes to plot imported electicity as -ve values.
                   True if the user wishes to plot imported electicity as +ve values."""
        invertkW=False
        if self._pwrPolarityRadioButtonGroup.active == 0:
            invertkW=True
        return invertkW

    def _addToPlot(self, plotDict, rowData, index, plotType):
        """@brief Add to plot dict for a single trace.
           @param plotDict A dict containing x and Y values lists.
           @param rowData The source data.
           @param index The index to the field/column to be plotted.
           @param plotType The type of data being plotted."""
        invertKw = self._invertKW()

        ts = datetime.fromisoformat(rowData[BaseConstants.TIMESTAMP_INDEX])

        plotDict[GUI.X_AXIS_NAME].append(ts)
        if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
            plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[index]))
        else:
            if invertKw:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[index]/1000.0)
            else:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[index]/1000.0)

        # If plotting hourly we add a plot point at the end of the hour so
        # the user sees a stepped chart
        if self._resRadioButtonGroup.active == GUI.HOUR_RESOLUTION:
            ts=ts=ts.replace(minute=59, second=59, microsecond=999)
            plotDict[GUI.X_AXIS_NAME].append(ts)
            if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[index]))
            else:
                if invertKw:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[index]/1000.0)
                else:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[index]/1000.0)


        # If plotting daily we add a plot point at the end of the day so
        # the user sees a stepped chart
        if self._resRadioButtonGroup.active == GUI.DAY_RESOLUTION:
            ts=ts=ts.replace(hour=23, minute=59, second=59, microsecond=999)
            plotDict[GUI.X_AXIS_NAME].append(ts)
            if plotType == GUI.PLOT_TYPE_POWER_FACTOR:
                plotDict[GUI.DEFAULT_YAXIS_NAME].append(abs(rowData[index]))
            else:
                if invertKw:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(-rowData[index]/1000.0)
                else:
                    plotDict[GUI.DEFAULT_YAXIS_NAME].append(rowData[index]/1000.0)

    def _enableActionButtons(self, enabled):
        """@brief Enable/disable the action buttons.
           @param enabled If True enable the button."""
        if enabled:
            self._setButtonsActive()
        else:
            self._setButtonsDisabled()

    def updateGUI(self, msgDict):
        """@brief Send a message to the GUI so that it updates itself.
           @param msgDict A dict containing details of how to update the GUI."""
        # Record the seconds when we received the message
        msgDict[GUI.UPDATE_SECONDS]=time()
        self._commsQueue.put(msgDict)

    def _debug(self, msg):
        """@brief Show a debug message.
           @param msg The message text to show."""
        self._uio.debug(msg)

    def _stripInvalidCharacters(self, valueString):
        """@brief Strip invalid (non alphanumeric) characters.
           @param valueString The string entered by the user."""
        return re.sub(r'[^A-Za-z0-9]+-_', '', str(valueString) )

    # The following methods are called from the GUI but are executed in separate threads
    # outside the GUI thread.

    def _sendStatus(self, msg):
        """@brief Send a status message to be dislayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {GUI.STATUS_MESSAGE: msg}
        self.updateGUI(msgDict)

    def _sendCmdComplete(self, msg=""):
        """@brief Send a status message to be dislayed in the GUI.
           @param msg The message to be displayed."""
        msgDict = {GUI.CMD_COMPLETE: msg}
        self.updateGUI(msgDict)

    def _error(self, msg):
        """@brief Report an error to the user.
           @param The error message."""
        msgDict = {}
        # We use the first line for info/error messages.
        msgDict[GUI.STATUS_LINE_INDEX]=0
        msgDict[GUI.STATUS_MESSAGE]=msg
        self._commsQueue.put(msgDict)

    def _sendEnableActionButtonsMsg(self, enabled):
        """@brief Send an enable update button message through the Queue into the GUI thread.
           @param enabled If True the button is enabled."""
        msgDict = {}
        msgDict[GUI.ENABLE_ACTION_BUTTONS]=enabled
        self._commsQueue.put(msgDict)

    def _readDataBase(self, db_file, startDateTime, stopDateTime, resolution):
        """@brief Read data from the database.
           @param db_file The database file to read.
           @param startDateTime The first date/time of interest as epoch time
           @param stopDateTime The last date/time of interest as epoch time.
           @param The resolution of the data to read.
           @return A dict containing the results of the DB read."""
        results={}
        conn = None
        try:
            conn = sqlite3.connect(db_file)

            # Start and stop dates are in milliseconds since epoch time, convert to seconds since epoch time.
            startDT=datetime.fromtimestamp(startDateTime/1000)
            stopDT=datetime.fromtimestamp(stopDateTime/1000)
            if startDT >= stopDT:
                self._error("Stop must be after the start date.")
                self._sendEnableActionButtonsMsg(True)
                return results

            startDate = startDT.strftime("%Y-%m-%d")
            stopDate = stopDT.strftime("%Y-%m-%d")
            startHoursMins = startDT.strftime("%H:%M")
            stopHoursMins = stopDT.strftime("%H:%M")

            dBName = self._getSelectedDataBase()
            startT = time()
            fName = inspect.currentframe().f_code.co_name
            self._uio.debug(f"{fName}: DB={db_file}, startDate={startDate}, stopDate={stopDate}, resolution={resolution}")

            if resolution == GUI.MAX_RESOLUTION:
                tableName = BaseConstants.MAX_RES_DB_DATA_TABLE_NAME

            elif resolution == GUI.MINUTE_RESOLUTION:
                tableName = BaseConstants.MINUTE_RES_DB_DATA_TABLE_NAME

            elif resolution == GUI.HOUR_RESOLUTION:
                tableName = BaseConstants.HOUR_RES_DB_DATA_TABLE_NAME

            elif resolution == GUI.DAY_RESOLUTION:
                tableName = BaseConstants.DAY_RES_DB_DATA_TABLE_NAME

            maxRecordCount = self._options.maxpp
            # We find how many records match the search before read every nth (stride value) record.
            # This should allow resonable search times on large data sets.
            cmd = f"SELECT COUNT(*) FROM {tableName} where TIMESTAMP BETWEEN '{startDate} {startHoursMins}:00:000' AND '{stopDate} {stopHoursMins}:59:999';"
            responseTuple = self._executeSQL(conn, cmd)
            exeTime = time()-startT
            self._uio.debug(f"SQL command execution time {exeTime:.1f} seconds.")
            recordCount = responseTuple[0][0]
            self._uio.debug(f"recordCount = {recordCount}")

# PJA
            if recordCount > maxRecordCount:
                # PJA: Wired this out as it's probably better to abort very large plots due to the time and memory it takes.
                # The user can always use the '-m/--maxpp' command line argument to increase the default number of maximum
                # plot points if they have fast machines with lots of memory.
                pass
                # If we will have more than the max number of plot points then reduce the number of points
#                    stride = math.ceil( recordCount/maxRecordCount )
#                    cmd = f' WITH ordering AS ( SELECT ROW_NUMBER() OVER (ORDER BY TIMESTAMP) AS n, {tableName}.*'\
#                          f" FROM {tableName} where TIMESTAMP BETWEEN '{startDate} 00:00:00:000' AND '{stopDate} 23:59:59:999' ORDER BY TIMESTAMP"\
#                          " )"\
#                          f' SELECT * FROM ordering WHERE MOD(n, {stride}) = 0;'
            else:
                cmd = f"select * from {tableName} where TIMESTAMP BETWEEN '{startDate} {startHoursMins}:00:000' AND '{stopDate} {stopHoursMins}:59:999';"

                responseTuple = self._executeSQL(conn, cmd)
                recordCount = len(responseTuple)
            self._uio.debug("Found {} records.".format( recordCount ))
            if recordCount > self._options.maxpp:
                self._error(f"Reduce plot resolution ({recordCount} values read, max = {self._options.maxpp}).")
                self._sendEnableActionButtonsMsg(True)
            else:
                results[dBName]=responseTuple
                self._commsQueue.put(results)

            self._uio.debug(f"{fName}: Execution time {exeTime:.1f} seconds.")
            msgDict = {}
            msgDict[GUI.STATUS_LINE_INDEX]=0
            msgDict[GUI.STATUS_MESSAGE]=f"Took {exeTime:.1f} seconds to read data from DB."
        finally:
            if conn:
                conn.close()
        return results


    def _calcKWH(self, sensorID, sensorName, rowDictList, resolution):
        """@brief Calculate the kWh usage for the CT data.
           @param sensorID The ID of the sensor (0-3)
           @param sensorName The name of the sensor.
           @param rowDictList A list of dicts of each row in the database table."""
        invertKw = self._invertKW()
        startT = time()
        fName = inspect.currentframe().f_code.co_name
        self._uio.debug(f"{fName}: sensorID={sensorID}, sensorName={sensorName}")
        totalkWH = 0.0
        if sensorID == 1:
            key = BaseConstants.CT1_ACT_WATTS_INDEX
        elif sensorID == 2:
            key = BaseConstants.CT2_ACT_WATTS_INDEX
        elif sensorID == 3:
            key = BaseConstants.CT3_ACT_WATTS_INDEX
        elif sensorID == 4:
            key = BaseConstants.CT4_ACT_WATTS_INDEX
        elif sensorID == 5:
            key = BaseConstants.CT5_ACT_WATTS_INDEX
        elif sensorID == 6:
            key = BaseConstants.CT6_ACT_WATTS_INDEX

        wattHoursList = []
        pWattHoursList = []
        nWattHoursList = []
        lastTime = None
        pTotalkWh = 0.0
        nTotalkWh = 0.0
        for rowDict in rowDictList:
            thisTime = datetime.fromisoformat(rowDict[BaseConstants.TIMESTAMP_INDEX])
            if invertKw:
                watts = -rowDict[key]
            else:
                watts = rowDict[key]
            if lastTime is not None:
                elapsedHours = (thisTime-lastTime).total_seconds()/3600.0
                wh = elapsedHours*watts
                if wh >= 0.0:
                    pWattHoursList.append(wh)
                else:
                    nWattHoursList.append(wh)
                wattHoursList.append(wh)

            lastTime = thisTime

        totalkWH = sum(wattHoursList)/1000.0
        pTotalkWh = sum(pWattHoursList)/1000.0
        nTotalkWh = sum(nWattHoursList)/1000.0
        summaryDict = {}
        summaryDict[GUI.SUMMARY_ROW]=[sensorID, sensorName, totalkWH, pTotalkWh, nTotalkWh]
        self._commsQueue.put(summaryDict)

        msgDict = {}
        exeTime = time()-startT
        msgDict[GUI.STATUS_LINE_INDEX]=0
        msgDict[GUI.STATUS_MESSAGE]=f"Took {exeTime:.1f} seconds to read data from DB."

        self._uio.debug(f"{fName}: Execution time {exeTime:.1f} seconds.")


































def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="This application is responsible for the following.\n"\
                                                     "- Detecting CT6 units on the LAN/WiFi.\n"\
                                                     "- Regularly (every second) reasdin stats from CT6 these CT6 units.\n"\
                                                     "- Saving this data to databases.\n"\
                                                     "- Presenting a user friendly dashboard/web UI to view and manipulate the data.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",        action='store_true', help="Enable debugging.")
        parser.add_argument("-c", "--configure",    help="Configure this app.", action='store_true')
        parser.add_argument("--show_tables",        help="Show all the database tables.", action="store_true", default=False)

        parser.add_argument("-s", "--show",         help="Show CT6 JSON data received.", action="store_true", default=False)
        parser.add_argument("-i", "--include",      help="A comma separated list of IP addresses of CT6 units to include in the data collection. If omitted all CT6 units found are included.")
        parser.add_argument("-e", "--exclude",      help="A comma separated list of IP addresses of CT6 units to exclude from data collection.  If omitted no CT6 units are excluded.")

        parser.add_argument("-n", "--no_gui",       action='store_true', help="Do not display the GUI. By default a local web browser is opend displaying the GUI. If this option is used the user will need to connect to the server using a web browser before the GUI is displayed.")
        parser.add_argument("-m", "--maxpp",        help="The maximum number of plot points (default=86400).", type=int, default=86400)
        parser.add_argument("-p", "--positive",     action='store_true', help="Display imported electricity on plots as positive values. The default is that imported electricity appears as -ve values.")

        parser.add_argument("--conv_dbs",           action='store_true', help="Convert MYSQL CT6 DB's into SQLITE DB's.")

        parser.add_argument("--syslog",             action='store_true', help="Enable syslog debug data.")
        BootManager.AddCmdArgs(parser)

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.syslog, programName="ct6")
        if options.syslog:
            uio.info("Syslog enabled")

        handled = BootManager.HandleOptions(uio, options, options.syslog)
        if not handled:
            app_config = AppConfig(uio,
                                   SQLite3DBClient.GetConfigPathFile(AppServer.DEFAULT_CONFIG_FILENAME),
                                   AppConfig.DEFAULT_CONFIG)

            if options.conv_dbs:
                mysql_importer = MYSQLImporter(uio, options, app_config)
                mysql_importer.convert_mysql_to_sqlite()

            elif options.configure:
                app_config.configure(editConfigMethod=app_config.edit)

            else:
                db_client = SQLite3DBClient(uio, options, app_config)
                if options.show_tables:
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

        if options.debug:
            raise
        else:
            uio.error(str(ex))

if __name__== '__main__':
    main()
