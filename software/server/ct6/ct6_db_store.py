#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

#-------------------------------------------------------------------------------
# This application uses a MySQL DBMS
# How to get a MYSQL DBMS running
# install docker
# docker pull mysql
# docker run --name mysql-iot -v /home/pja/tmp/mysql-iot:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=changeme -d -p 3306:3306 mysql
# where
# mysql-iot               = The name of the docker container
# /home/pja/tmp/mysql-iot = The location of the mysql database outside the docker container
# changeme                = The root password for the database
# The database will present on TCP port 3306
# Once created the docker container can be stopped with
# docker stop mysql-iot
# The docker container can be removed with. If this is done then the docker container will need re creating
# using the first command above.
# docker rm mysql-iot
# On Ubuntu Antares SQL client can be used on Ubuntu to browse the database.
# This can be installed from the software manager.
#
# The following shows the docker DB container running.
#
# docker ps
# CONTAINER ID   IMAGE     COMMAND                  CREATED       STATUS       PORTS                                                  NAMES
# 55b31fffed72   mysql     "docker-entrypoint.s…"   12 days ago   Up 12 days   0.0.0.0:3306->3306/tcp, :::3306->3306/tcp, 33060/tcp   mysql-iot
#
# NOTE !
# To get the app to install correctly I had to run
# sudo apt-get install libmysqlclient-dev
#
# Also
# apt-get install libbz2-dev
# And then rebuild Python as the bz2 module was missing.
#
import warnings
warnings.filterwarnings('ignore')

import sys
import argparse
import threading
import traceback
import inspect
import os
import psutil
import pandas as pd
import MySQLdb
import objgraph
import json

import numpy as np

from time import time, sleep
from datetime import datetime, timedelta
from tempfile import gettempdir

from p3lib.helper import logTraceBack
from p3lib.uio import UIO
from p3lib.database_if import DBConfig, DatabaseIF
from p3lib.boot_manager import BootManager

from lib.config import ConfigBase
from lib.db_handler import DBHandler
from lib.yview import YViewCollector, LocalYViewCollector, YView
from lib.base_constants import BaseConstants

class CTDBClientConfig(ConfigBase):
    DEFAULT_CONFIG = {
        ConfigBase.MQTT_TOPIC:                 "#",
        ConfigBase.DB_HOST:                    "127.0.0.1",
        ConfigBase.DB_PORT:                    3306,
        ConfigBase.DB_USERNAME:                "",
        ConfigBase.DB_PASSWORD:                "",
        ConfigBase.CT6_DEVICE_DISCOVERY_INTERFACE: "",
    }

class LockFile(object):

    def __init__(self, lockFilename):
        """@brief Construct a ProcessLock instance.
           @param lockFilename The name (no path) of the lock file."""
        self._lockFile = self._getLockFile(lockFilename)

    def _getLockFile(self, lockFilename):
        """@return The full path name of the lock file.
           @param lockFilename The name of the lock file."""
        return os.path.join( gettempdir(), lockFilename)

    def getLockFile(self):
        """@return The full path of the lock file."""
        return self._lockFile

    def isLockFilePresent(self):
        """@return True if the process lock file is present."""
        fileFound = False
        if os.path.isfile(self._lockFile):
            fileFound = True
        return fileFound

    def createLockFile(self):
        """@brief Create the process lock file. The file is created and is overwritten if already present."""
        with open(self._lockFile , 'w'):
            pass

    def removeLockFile(self):
        """@brief Ensure no lock file is present. Remove it if it is present."""
        if os.path.isfile(self._lockFile):
            os.remove(self._lockFile)


class MySQLDBClient(BaseConstants):
    """@Responsible for
        - Providing an interface to view and change a database.."""

    LOCK_FILE_NAME = "MySQLDBClient.lock"

    @staticmethod
    def AddToTable(tableName, dictData, databaseIF):
        """@brief Add data to table. We assume this is in the currently selected database.
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
        sql += ', '.join(map(DatabaseIF.GetQuotedValue, valueList))
        sql += ');'
        databaseIF.executeSQL(sql)

    @staticmethod
    def AddListsToTable(tableName, colNameList, valueList, databaseIF):
        """@brief Add data to table. We assume this is in the currently selected database.
           @param tableName The name of the table to add to. If the table does not exist it will be created.
           @param colNameList A list of the column names to be added to the table.
           @param valueList A list of the column values to be added to the table (single row).
           @param databaseIF The database interface instance."""
        sql = "NOSQL"
        try:
            # Check for NaN ignoring the timestamp column
            containsNaN = np.isnan(np.array(valueList[1:])).any()
            #If not all the columns are valid
            if not containsNaN:
                sql = 'INSERT INTO `' + tableName
                sql += '` ('
                sql += ', '.join(colNameList)
                sql += ') VALUES ('
                sql += ', '.join(map(DatabaseIF.GetQuotedValue, valueList))
                sql += ');'

                databaseIF.executeSQL(sql)
        except:
            print(f"SQL CMD FAILED: {sql}")
            raise

    @staticmethod
    def AddBatchRowsToTable(tableName, colNameList, batchValueList, databaseIF):
        """@brief Add data to table in batches of rows to reduce execution time. We assume this is in the currently selected database.
           @param tableName The name of the table to add to. If the table does not exist it will be created.
           @param colNameList A list of the column names to be added to the table.
           @param batchValueList A list of rows to be added to the table. Each element contains a list of the column
                  values to be added to the table (single row).
           @param databaseIF The database interface instance."""
        sql = "NOSQL"
        try:
            validBatchList = []
            # Check for NaN ignoring the timestamp column on each set of row data
            for valueList in batchValueList:
                containsNaN = np.isnan(np.array(valueList[1:])).any()
                if not containsNaN:
                    validBatchList.append(valueList)

            #If not all the columns are valid
            if len(validBatchList) > 0:
                sql = 'INSERT INTO `' + tableName
                sql += '` ('
                sql += ', '.join(colNameList) + ') VALUES'
                for valueList in validBatchList:
                    sql += ' ('
                    sql += ', '.join(map(DatabaseIF.GetQuotedValue, valueList)) + '),'
                sql = sql.rstrip(',')
                sql += ';'
                databaseIF.executeSQL(sql)

        except:
            print(f"SQL CMD FAILED: {sql}")
            raise

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A AppServerConfig instance."""
        self._uio                   = uio
        self._options               = options
        self._config                = config
        self._ssh                   = None
        self._dataBaseIF            = None
        self._addedCount            = 0
        try:
            self._tableSchema       = self.getTableSchema()
        except:
            self._tableSchema       = ""
        self._startTime             = time()
        self._sqlCmdCount           = 0
        self._lockFile              = LockFile(MySQLDBClient.LOCK_FILE_NAME)

    def _setupDBConfig(self, dbName=None):
        """@brief Setup the internal DB config
           @param dbName Optional database name."""
        self._dbConfig                      = DBConfig()
        self._dbConfig.serverAddress        = self._config.getAttr(CTDBClientConfig.DB_HOST)
        self._dbConfig.serverPort           = self._config.getAttr(CTDBClientConfig.DB_PORT)
        self._dbConfig.username             = self._config.getAttr(CTDBClientConfig.DB_USERNAME)
        self._dbConfig.password             = self._config.getAttr(CTDBClientConfig.DB_PASSWORD)
        self._dbConfig.uio                  = self._uio
        self._dbConfig.dataBaseName         = dbName
        self._dataBaseIF                    = DatabaseIF(self._dbConfig)

    def getTableSchema(self):
        """@return the required MYSQL table schema"""
        return MySQLDBClient.GetTableSchema(self._options.table)

    def _shutdownDBSConnection(self):
        """@brief Shutdown the connection to the DBS"""
        if self._dataBaseIF:
            self._dataBaseIF.disconnect()
            self._dataBaseIF = None

    def _connectToDBS(self):
        """@brief connect to the database server."""
        self._shutdownDBSConnection()

        self._dataBaseIF.connect()
        self._uio.info("Connected to database")

    def createDB(self):
        """@brief Create the configured database on the MYSQL server"""
        try:
            if not self._options.db:
                raise Exception("--db required.")
            self._setupDBConfig()
            self._dataBaseIF.connectNoDB()

            self._dbConfig.dataBaseName = self._options.db
            self._dataBaseIF.createDatabase()

        finally:
            self._shutdownDBSConnection()

    def deleteDB(self):
        """@brief Delete the configured database on the MYSQL server"""
        try:
            if not self._options.db:
                raise Exception("--db required.")
            self._setupDBConfig()
            self._dbConfig.dataBaseName = self._options.db
            deleteDB = self._uio.getBoolInput("Are you sure you wish to delete the '{}' database [y/n]".format(self._dbConfig.dataBaseName))
            if deleteDB:

                self._dataBaseIF.connectNoDB()

                self._dataBaseIF.dropDatabase()

        finally:
            self._shutdownDBSConnection()

    def createTable(self):
        """@brief Create the database table configured"""
        try:
            if not self._options.db:
                raise Exception("--db required.")

            if not self._options.table:
                raise Exception("--table required.")

            if not self._options.schema:
                raise Exception("--schema required.")

            tableName = self._options.table
            self._setupDBConfig(dbName=self._options.db)

            self._dataBaseIF.connect()

            tableSchema = MySQLDBClient.GetTableSchema( self._options.schema )
            self._dataBaseIF.createTable(tableName, tableSchema)

        finally:
            self._shutdownDBSConnection()

    def deleteTable(self):
        """@brief Delete a database table configured"""
        try:
            if not self._options.db:
                raise Exception("--db required.")

            if not self._options.table:
                raise Exception("--table required.")

            tableName = self._options.table
            self._setupDBConfig(dbName=self._options.db)
            deleteDBTable = self._uio.getBoolInput("Are you sure you wish to delete the '{}' database table [y/n]".format(tableName))
            if deleteDBTable:

                self._dataBaseIF.connect()

                self._dataBaseIF.dropTable(tableName)

        finally:
            self._shutdownDBSConnection()

    def showDBS(self):
        """@brief List the databases."""
        try:

            self._setupDBConfig()

            self._dataBaseIF.connectNoDB()

            sql = 'SHOW DATABASES;'
            recordTuple = self._dataBaseIF.executeSQL(sql)
            for record in recordTuple:
                self._uio.info( str(record) )

        finally:
            self._shutdownDBSConnection()

    def showTables(self):
        """@brief List the databases."""
        try:
            if not self._options.db:
                raise Exception("--db required.")

            self._setupDBConfig(dbName=self._options.db)

            self._dataBaseIF.connect()

            sql = 'SHOW TABLES;'
            recordTuple = self._dataBaseIF.executeSQL(sql)
            for record in recordTuple:
                self._uio.info( str(record) )

        finally:
            self._shutdownDBSConnection()

    def readTable(self):
        """@brief Read a number of records from the end of the database table."""
        try:

            if not self._options.db:
                raise Exception("--db required.")

            if not self._options.table:
                raise Exception("--table required.")

            self._setupDBConfig(dbName=self._options.db)

            self._dataBaseIF.connect()

            tableName = self._options.table

            try:
                sql = 'SELECT * FROM `{}` ORDER BY {} DESC LIMIT {}'.format(self._options.db+'.'+tableName, MySQLDBClient.TIMESTAMP, self._options.read_count)
                recordTuple = self._dataBaseIF.executeSQL(sql)
            except:
                sql = 'SELECT * FROM `{}`'.format(tableName)
                recordTuple = self._dataBaseIF.executeSQL(sql)
            for record in recordTuple:
                self._uio.info( str(record) )

        finally:
            self._shutdownDBSConnection()

    def executeSQL(self):
        """@brief Execute SQL command provided on the command line."""
        try:
            if not self._options.sql:
                raise Exception("--sql required.")
            sql = self._options.sql

            if self._options.db:
                self._setupDBConfig(dbName=self._options.db)
                self._dataBaseIF.connect()
            else:
                self._setupDBConfig()
                self._dataBaseIF.connectNoDB()


            recordTuple = self._dataBaseIF.executeSQL(sql)
            for record in recordTuple:
                self._uio.info( str(record) )

        finally:
            self._shutdownDBSConnection()


    def showSchema(self):
        """@brief Execute SQL command provided on the command line."""
        try:
            if not self._options.db:
                raise Exception("--db required.")

            if not self._options.table:
                raise Exception("--table required.")

            tableName = self._options.table
            self._setupDBConfig(dbName=self._options.db)

            self._dataBaseIF.connect()

            sql = "DESCRIBE `{}`;".format(tableName)
            recordTuple = self._dataBaseIF.executeSQL(sql)
            for record in recordTuple:
                self._uio.info( str(record) )

        finally:
            self._shutdownDBSConnection()

    def showExSchema(self):
        """@brief Show an example schema so that the user can get a basic syntax for a table schema."""
        self._uio.info("PJA: TODO")
        #self._uio.info("LOCATION:VARCHAR(64) TIMESTAMP:TIMESTAMP VOLTS:FLOAT(5,2) AMPS:FLOAT(5,2) WATTS:FLOAT(10,2)")

    def getDBNameList(self):
        """@brief Get a list of all the CT6 databases on the database server.
                  Mus be connected to the database server before calling this. """
        ct6DatabaseList = []
        self._uio.info("Checking databases...")
        sql = 'SHOW DATABASES;'
        recordTuple = self._dataBaseIF.executeSQL(sql)
        self._sqlCmdCount += 1
        for record in recordTuple:
            if 'Database' in record:
                dBname = record['Database']
                sql = 'USE {};'.format(dBname)
                recordTuple = self._dataBaseIF.executeSQL(sql)
                self._sqlCmdCount += 1
                sql = 'SHOW TABLES;'
                recordTuple = self._dataBaseIF.executeSQL(sql)
                self._sqlCmdCount += 1
                key = 'Tables_in_{}'.format(dBname)
                for record in recordTuple:
                    tableName = record[key]
                    if tableName == MySQLDBClient.CT6_TABLE_NAME:
                        ct6DatabaseList.append(dBname)
                        break
        return ct6DatabaseList

    def createLowResTables(self):
        """@brief Create tables with lower resolution data. These tables are derived from the main CT6_SENSOR table data.
                  These are created because they are faster to access max resolution data
                  which are updated about once a second."""
        self._uio.warn("!!! Deleting and recreating the min, hour and day tables can take a long time.")
        self._uio.warn("!!! This is particularly true when you have a lot of data.")
        self._uio.warn("!!! Once started this process should be left to complete.")
        yes = self._uio.getBoolInput("Are you sure you want to do this ? y/n")
        if not yes:
            return
        try:
            self._sqlCmdCount = 0
            self._setupDBConfig()
            self._dataBaseIF.connectNoDB()
            dbNameList = self.getDBNameList()
            for dBname in dbNameList:
                sql = 'USE {};'.format(dBname)
                self._dataBaseIF.executeSQL(sql)

                self._uio.info(f"Creating Hour and Day tables in the {dBname} database.")
                # Delete all derived tables.
                for tableName in MySQLDBClient.LOW_RES_DATA_TABLE_LIST:
                    try:
                        self._dataBaseIF.dropTable(tableName)
                    except:
                        pass
                # Create empty derived tables.
                recordSets=[]
                for tableName in MySQLDBClient.LOW_RES_DATA_TABLE_LIST:
                    self._dataBaseIF.createTable(tableName, MySQLDBClient.GetTableSchema(CTDBClient.CT6_DB_TABLE_SCHEMA) )
                    self._uio.info(f"Created {tableName} table in {dBname}.")
                    # Create empty lists to be used later
                    recordSets.append([])

                self.updateLowResTables(dBname)

                startTime = time()

                # Create time stamp indexes for all derived tables to improve search speed.
                self._createIndex(dBname, MySQLDBClient.LOW_RES_DATA_TABLE_LIST)

                elapsedTime = time()-startTime
                self._uio.info(f"Took {elapsedTime:.1f} seconds to create derived tables in {dBname}")

            self._uio.info("Derived tables created.")

        finally:
            self._shutdownDBSConnection()

    def createLowResTablesLock(self):
        """@brief As per def createLowResTables() but ensure only one instance is running on a system."""
        try:
            # Provide some user info on how to remedy lock file issues.
            if self._lockFile.isLockFilePresent():
                self._uio.warn(f"The {self._lockFile.getLockFile()} file was found.")
                self._uio.warn(f"This indicates that another instance of {sys.argv[0]} is running with the '--create_dt' command line option.")
                self._uio.warn("Either wait for this this process to complete or kill the process and delete the above lock file.")
                self._uio.error("Unable to start this instance of this program.")

            else:
                self._lockFile.createLockFile()
                self.createLowResTables()
                self._lockFile.removeLockFile()

        except KeyboardInterrupt:
            self._lockFile.removeLockFile()

    def isCreatingLowResTables(self):
        """@return True if the low resolution database tables are currently being created."""
        return self._lockFile.isLockFilePresent()

    def _createIndex(self, dBname, tableNameList):
        """@brief Create an index on the timestamp field to improve search time.
           @param dBname The name of the database currently being used.
                         This database must have been selected before calling this method.
           @param tableNameList A list of the names of the tables to index"""
        # Create time stamp indexes for all derived tables to improve search speed.
        for tableName in tableNameList:
            # Index on time stamp as most search will be based around a date/time
            cmd = f"CREATE INDEX {tableName}_INDEX ON {tableName} ({CTDBClient.TIMESTAMP})"
            self._dataBaseIF.executeSQL(cmd)
            self._sqlCmdCount += 1
            self._uio.info(f"Created {tableName}_INDEX in {dBname}.")

    def updateLowResTables(self, dBname):
        """@brief Update all the low resolution tables.
           @param dBname The name of the database currently being used.
                         This database must have been selected before calling this method."""

        # Update derived tables
        firstTimeStamp = None
        colNames = None # The name of the columns.
        for reSampleSize, srcTableName, destTableName in [['min',     BaseConstants.CT6_TABLE_NAME, CTDBClient.MINUTE_RES_DB_DATA_TABLE_NAME],
                                                          ['60min',   CTDBClient.MINUTE_RES_DB_DATA_TABLE_NAME, CTDBClient.HOUR_RES_DB_DATA_TABLE_NAME],
                                                          ['1440min', CTDBClient.HOUR_RES_DB_DATA_TABLE_NAME, CTDBClient.DAY_RES_DB_DATA_TABLE_NAME] ]:
            startTime = time()
            self._uio.info(f"Creating {destTableName} table in the {dBname} database.")

            # Select the first record in the src table
            sql = f"SELECT * FROM {srcTableName} LIMIT 1"
            recordTuple = self._dataBaseIF.executeSQL(sql)
            self._sqlCmdCount += 1
            # If we have some data in the current source table.
            if len(recordTuple) > 0:
                # get it's time stamp
                startTS = recordTuple[0][CTDBClient.TIMESTAMP]
                # Store the TS as we may need it if other tables have no starting time. I.E no records in them.
                if srcTableName == BaseConstants.CT6_TABLE_NAME:
                    firstTimeStamp = startTS

            else:
                startTS = firstTimeStamp

            now = datetime.now()
            # Loop here until we've read all the records in the table.
            # We assume that no records exist in the database after the current date/time.
            while startTS < now:
                loopStartSecs = time()

                # 0 = Took 7.5 seconds. Record count = 42514. Took 0.175620 seconds per 1000 records.
                # 1 = Took 37.3 seconds. Record count = 117245. Took 0.318019 seconds per 1000 records.
                # 2 = Took 73.4 seconds. Record count = 199188. Took 0.368613 seconds per 1000 records.
                # Therefore chose 0 days
                stopTS = startTS + timedelta(days=0)
                # Stop at the end of a day.
                stopTS = stopTS.replace(hour=23, minute=59, second=59, microsecond=999999)
                self._uio.info(f"Reading from {startTS} to {stopTS}")

                # Search all records each day
                #stopTS = datetime(startTS.year, startTS.month, startTS.day, 23, 59, 59, 999999);
                sql = f"select * from {srcTableName} where TIMESTAMP BETWEEN '{startTS}' AND '{stopTS}';"

                # Process the SQL cmd and convert result to pandas DataFrame
                df = pd.read_sql(sql, con=self._dataBaseIF._dbCon)
                self._sqlCmdCount += 1
                recordCount = len(df.index)

                # This approach executes the SQL command and converts the result to a pandas DataFrame later
                # which was found to be generally slower.
                # recordTuple = self._dataBaseIF.executeSQL(sql)
                # self._sqlCmdCount += 1
                # recordCount = len(recordTuple)
                self._uio.info(f"Processing {recordCount} records.")
                # If we got some records to process
                if recordCount > 0:
                    # Convert to pandas dataframeif pd.read_sql is not used.
                    #df = pd.DataFrame(recordTuple)
                    # Create a table that contains the resampled data (E.G seconds -> mins, mins -> hours or hours -> days)
                    df1 = df.resample(reSampleSize, on='TIMESTAMP').mean()
                    # Each of the derived tables has the same columns so we only read these once. This saves a little time,
                    if colNames is None:
                        # Get a list of the column names
                        colNames = df1.columns.values.tolist()
                        # Add the timestamp to the start
                        colNames.insert(0, "TIMESTAMP")
                    rows = df1.itertuples()
                    #Add each row in the table to the database
                    batchOfRows = []
                    for row in rows:
                        # Add to the batch of rows to be written
                        batchOfRows.append(row)
                        # Write in batches of rows for speed. This speeds up writes by a factor of over 45 when
                        # compared with inserting one row at a time. After testing 150 appeared to be a good trade
                        # off between speed and buffer space needed to send large SQL messages containing the row data.
                        if len(batchOfRows) == 150:
                            self._uio.debug(f"Adding {len(batchOfRows)} rows of data to the {destTableName} table in the {dBname} database.")
                            MySQLDBClient.AddBatchRowsToTable(destTableName, colNames, batchOfRows, self._dataBaseIF)
                            batchOfRows = []
                            self._sqlCmdCount += 1
                    # If we have some unwritten rows add these now.
                    if len(batchOfRows) > 0:
                        self._uio.debug(f"Adding {len(batchOfRows)} rows of data to the {destTableName} table in the {dBname} database.")
                        MySQLDBClient.AddBatchRowsToTable(destTableName, colNames, batchOfRows, self._dataBaseIF)

                startTS += timedelta(days=1)
                if startTS.hour != 0 or startTS.min != 0 or startTS.second != 0 or startTS.microsecond != 0:
                    #Move to the start of the next unit of time
                    startTS = datetime(startTS.year, startTS.month, startTS.day, 0, 0, 0, 0);

                elapsedSecs = time()-loopStartSecs
                perRecordET = 0
                if elapsedSecs > 0 and recordCount > 0:
                    perRecordET = elapsedSecs/(recordCount/1000)
                self._uio.info(f"Took {elapsedSecs:.1f} seconds. Record count = {recordCount}. Took {perRecordET:.6f} seconds per 1000 records ({self._sqlCmdCount} SQL commands).")

            elapsedSecs=time()-startTime
            self._uio.info(f"Took {elapsedSecs:.1f} seconds to write {destTableName} table in {dBname}")


class CTDBClient(DBHandler):
    """@responsible for CT6 sensor database access."""

    LOCK_FILE_NAME = "CTDBClient.lock"

    def __init__(self, uio, options, config, mySQLDBClient):
        """@brief Constructor
           @param uio A UIO instance.
           @param options The command line options instance.
           @param config A ConfigBase instance.
           @param mySQLDBClient An instance of MySQLDBClient."""
        super().__init__(uio, config)
        self._options = options
        self._mySQLDBClient = mySQLDBClient
        self._metaTableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_META_TABLE_SCHEMA )
        self._tableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_TABLE_SCHEMA )
        self._dbLock = threading.Lock()
        self._historyDicts={}
        self._hourRecordSets=[]
        self._devDictList = []
        self._metaTableUpdateTime = time()

        #Create a list of CT6 unit addresses that the user does not wish to collect data from
        self._excludeAddressList = []
        if self._options.exclude:
            self._excludeAddressList = self._options.exclude.split(",")

        if len(self._excludeAddressList) > 0:
            for address in self._excludeAddressList:
                self._uio.info(f"Excluding CT6 device: {address}")

    def _getDeviceIPAddress(self, rxDict):
        """@brief Get the IP address of the device.
           @return the IP address of the device or None if the dict does not contain the device IP address."""
        ipAddress = None
        if CTDBClient.IP_ADDRESS in rxDict:
            ipAddress = rxDict[CTDBClient.IP_ADDRESS]
        return ipAddress

    def _getDatabaseName(self, devDict):
        """@brief Get the database name.
           @param devDict The device dictionary as received in response to the AYT message.
           @return The name of the database or None if not found"""
        dbName = None
        if CTDBClient.UNIT_NAME in devDict:
            dbName = devDict[CTDBClient.UNIT_NAME]
        return dbName

    def _ensureDBTables(self, devDict):
        """@brief Ensure the database and tables exist in the connected database assuming that
                  devDict contains the assy label of the device.
           @param devDict The device dictionary as received in response to the AYT message.
           @return The name of the database."""

        startT = devDict[YView.RX_TIME_SECS]
        self._recordDeviceTimestamp(startT, 1)
        dBName = None
        dbFound = False
        if CTDBClient.UNIT_NAME in devDict and CTDBClient.PRODUCT_ID in devDict :
            unitName = devDict[CTDBClient.UNIT_NAME]
            if len(unitName) == 0:
                ipAddress = self._getDeviceIPAddress(devDict)
                if ipAddress:
                    self._uio.warn(f"{ipAddress}: Device name not set.")

                else:
                    self._uio.warn("Found a CT6 device that does not have the device name field set.")
                # Don't record data unless the device name has been set.
                # The device name is used as the database name.
                return

            productID = devDict[CTDBClient.PRODUCT_ID]
            # Check that this app can handle data from this type of device.
            if productID in CTDBClient.VALID_PRODUCT_ID_LIST:
                dBName = unitName
                self._dbConfig.dataBaseName = dBName
                self._recordDeviceTimestamp(startT, 2)
                recordTuple = self._dataBaseIF.executeSQL(DBHandler.SHOW_DATABASES_SQL_CMD)
                self._recordDeviceTimestamp(startT, 3)
                for record in recordTuple:
                    if DBHandler.DATABASE_KEY in record:
                        dbName = record[DBHandler.DATABASE_KEY]
                        if dbName == unitName:
                            dbFound = True
                            break

                if not dbFound:
                    # Create the database
                    self._dataBaseIF.createDatabase()
                self._dataBaseIF.executeSQL("USE {};".format(unitName))
                # Create the database tables
                self._dataBaseIF.createTable(CTDBClient.CT6_META_TABLE_NAME, self._metaTableSchema)
                self._dataBaseIF.createTable(CTDBClient.CT6_TABLE_NAME, self._tableSchema)
                self._dataBaseIF.createTable(CTDBClient.MINUTE_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                self._dataBaseIF.createTable(CTDBClient.HOUR_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                self._dataBaseIF.createTable(CTDBClient.DAY_RES_DB_DATA_TABLE_NAME, self._tableSchema)
                try:
                    # Index on time stamp as most search will be based around a date/time
                    cmd = f"CREATE INDEX {CTDBClient.CT6_TABLE_NAME}_INDEX ON {CTDBClient.CT6_TABLE_NAME} ({CTDBClient.TIMESTAMP})"
                    self._dataBaseIF.executeSQL(cmd)
                except:
                    pass

        self._recordDeviceTimestamp(startT, 4)
        return dBName

    def _updateMetaTable(self, dbName, devDict):
        """@brief Update the table containing meta data. This keeps the meta table up to date.
           @param dbName The name of the database to update.
           @param devDict The device dict."""
        self._devDictList.append(devDict)
        if time() >= self._metaTableUpdateTime:
            self._dataBaseIF.executeSQL("USE {};".format(dbName))
            rowCount = self._dataBaseIF.getTableRowCount(CTDBClient.CT6_META_TABLE_NAME)
            self._dataBaseIF.createTable(CTDBClient.CT6_META_TABLE_NAME, self._metaTableSchema)
            cmd = 'INSERT INTO {}({},{},{},{},{},{},{}) VALUES("{}","{}","{}","{}","{}","{}","{}");'.format(dbName+"."+CTDBClient.CT6_META_TABLE_NAME,
                                                                             CTDBClient.HW_ASSY,
                                                                             CTDBClient.CT1_NAME,
                                                                             CTDBClient.CT2_NAME,
                                                                             CTDBClient.CT3_NAME,
                                                                             CTDBClient.CT4_NAME,
                                                                             CTDBClient.CT5_NAME,
                                                                             CTDBClient.CT6_NAME,
                                                                             devDict[CTDBClient.ASSY],
                                                                             devDict[CTDBClient.CT1][CTDBClient.NAME],
                                                                             devDict[CTDBClient.CT2][CTDBClient.NAME],
                                                                             devDict[CTDBClient.CT3][CTDBClient.NAME],
                                                                             devDict[CTDBClient.CT4][CTDBClient.NAME],
                                                                             devDict[CTDBClient.CT5][CTDBClient.NAME],
                                                                             devDict[CTDBClient.CT6][CTDBClient.NAME] )
            self._dataBaseIF.executeSQL(cmd)
            # We keep only one row in this table
            if rowCount > 0:
                self._dataBaseIF.deleteRows(CTDBClient.CT6_META_TABLE_NAME, rowCount)
            # Init the list and set the time for the next update.
            self._devDictList = []
            self._metaTableUpdateTime = time()+60

    def _updateDerivedTables(self, dbName, thisRecord, historyDicts, dataBaseIF, lowResTableList):
        """@brief Update the min, hour and day tables in the database with new data just read from a sensor.
           @param dbName The name of the database to update. We assume this has been selected previously (sql use DB command issued).
           @param thisRecord The dict containing the data to be added to the database.
           @param historyDicts The dicts containing the reading history.
           @param dataBaseIF The interface to the database.
           @param lowResTableList The list of the NAMES OF THE databaSE TABLES (MIN, HOUR AND DAY).
           @PARAM UIO A UIO instance (if defined) to record debug information as records are added to the database tables."""
        if not dbName in historyDicts:
            # We need lists to hold the min, hour and day records
            historyDicts[dbName]=[[],[],[]]
        # Get the record sets for this database
        recordSets = historyDicts[dbName]

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
                MySQLDBClient.AddToTable(tableName, df.mean(), dataBaseIF)
                recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                recordSet.append(thisRecord) # Add the new data to the next record set.
                self._uio.debug(f"{dbName}: Record added to {tableName} table: {datetime.now()}")

                # Second derived table (hour)
                tableName = lowResTableList[1]
                recordSet = recordSets[1]
                # If we've moved into the next hour
                if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].hour != recordSet[0][BaseConstants.TIMESTAMP].hour):
                    # Use a pandas data frame to calculate the mean values for each column
                    df = pd.DataFrame(recordSet)
                    MySQLDBClient.AddToTable(tableName, df.mean(), dataBaseIF)
                    recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                    recordSet.append(thisRecord) # Add the new data to the next record set.
                    self._uio.debug(f"{dbName}: Record added to {tableName} table: {datetime.now()}")

                    # Third derived table (day)
                    tableName = lowResTableList[2]
                    recordSet = recordSets[2]
                    # If we've moved into the next day
                    if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].day != recordSet[0][BaseConstants.TIMESTAMP].day):
                        # Use a pandas data frame to calculate the mean values for each column
                        df = pd.DataFrame(recordSet)
                        MySQLDBClient.AddToTable(tableName, df.mean(), dataBaseIF)
                        recordSet.clear() # Clear rather than creating a new list so we don't change it's reference
                        recordSet.append(thisRecord) # Add the new data to the next record set.

                        self._uio.debug(f"{dbName}: Record added to {tableName} table: {datetime.now()}")

                    else:
                        # Add to the set of record to be averaged later
                        recordSet.append(thisRecord)

                else:
                    # Add to the set of record to be averaged later
                    recordSet.append(thisRecord)

        else:
            # Add to the set of record to be averaged later
            recordSet.append(thisRecord)

    def _recordDeviceTimestamp(self, startT, id):
        """@brief Record the time since device data was received from the CT6 device.
           @param startT The time in seconds when the message was received from the CT6 unit.
           @param id A string identifying the call location."""
        callerRef = inspect.stack()[2][4][0]
        callerRef = callerRef.strip()
        elapsedT = time() - startT
        self._uio.debug(f"DEVTS: {callerRef: >40} id={id} elapsed time = {elapsedT:.6f} seconds.")

    def _addDevice(self, dbName, devDict):
        """@brief Add device data to the database.
           @param dbName The name of the database to update.
           @param devDict The device dict."""
        startT = devDict[YView.RX_TIME_SECS] # This field is not added to the database. It holds the time
                                             # the dict was received on this machine.
        self._dataBaseIF.executeSQL("USE {};".format(dbName))
        self._recordDeviceTimestamp(startT, 1)

        sensorDataDict = {}
        # Record the time the message was received on the TCP socket rather than the time now
        # as CPU delays may cause dither in the time we get to this point.
        sensorDataDict[MySQLDBClient.TIMESTAMP] = datetime.fromtimestamp(startT)

        # active power
        sensorDataDict[CTDBClient.CT1_ACT_WATTS]=devDict[CTDBClient.CT1][CTDBClient.PRMS]
        sensorDataDict[CTDBClient.CT2_ACT_WATTS]=devDict[CTDBClient.CT2][CTDBClient.PRMS]
        sensorDataDict[CTDBClient.CT3_ACT_WATTS]=devDict[CTDBClient.CT3][CTDBClient.PRMS]
        sensorDataDict[CTDBClient.CT4_ACT_WATTS]=devDict[CTDBClient.CT4][CTDBClient.PRMS]
        sensorDataDict[CTDBClient.CT5_ACT_WATTS]=devDict[CTDBClient.CT5][CTDBClient.PRMS]
        sensorDataDict[CTDBClient.CT6_ACT_WATTS]=devDict[CTDBClient.CT6][CTDBClient.PRMS]
        # Reactive power
        sensorDataDict[CTDBClient.CT1_REACT_WATTS]=devDict[CTDBClient.CT1][CTDBClient.PREACT]
        sensorDataDict[CTDBClient.CT2_REACT_WATTS]=devDict[CTDBClient.CT2][CTDBClient.PREACT]
        sensorDataDict[CTDBClient.CT3_REACT_WATTS]=devDict[CTDBClient.CT3][CTDBClient.PREACT]
        sensorDataDict[CTDBClient.CT4_REACT_WATTS]=devDict[CTDBClient.CT4][CTDBClient.PREACT]
        sensorDataDict[CTDBClient.CT5_REACT_WATTS]=devDict[CTDBClient.CT5][CTDBClient.PREACT]
        sensorDataDict[CTDBClient.CT6_REACT_WATTS]=devDict[CTDBClient.CT6][CTDBClient.PREACT]
        # Aparent power
        sensorDataDict[CTDBClient.CT1_APP_WATTS]=devDict[CTDBClient.CT1][CTDBClient.PAPPARENT]
        sensorDataDict[CTDBClient.CT2_APP_WATTS]=devDict[CTDBClient.CT2][CTDBClient.PAPPARENT]
        sensorDataDict[CTDBClient.CT3_APP_WATTS]=devDict[CTDBClient.CT3][CTDBClient.PAPPARENT]
        sensorDataDict[CTDBClient.CT4_APP_WATTS]=devDict[CTDBClient.CT4][CTDBClient.PAPPARENT]
        sensorDataDict[CTDBClient.CT5_APP_WATTS]=devDict[CTDBClient.CT5][CTDBClient.PAPPARENT]
        sensorDataDict[CTDBClient.CT6_APP_WATTS]=devDict[CTDBClient.CT6][CTDBClient.PAPPARENT]

        # Power factor
        sensorDataDict[CTDBClient.CT1_PF]=devDict[CTDBClient.CT1][CTDBClient.PF]
        sensorDataDict[CTDBClient.CT2_PF]=devDict[CTDBClient.CT2][CTDBClient.PF]
        sensorDataDict[CTDBClient.CT3_PF]=devDict[CTDBClient.CT3][CTDBClient.PF]
        sensorDataDict[CTDBClient.CT4_PF]=devDict[CTDBClient.CT4][CTDBClient.PF]
        sensorDataDict[CTDBClient.CT5_PF]=devDict[CTDBClient.CT5][CTDBClient.PF]
        sensorDataDict[CTDBClient.CT6_PF]=devDict[CTDBClient.CT6][CTDBClient.PF]

        sensorDataDict[CTDBClient.VOLTAGE]=devDict[CTDBClient.CT1][CTDBClient.VRMS]
        sensorDataDict[CTDBClient.FREQUENCY]=devDict[CTDBClient.CT1][CTDBClient.FREQ]
        sensorDataDict[CTDBClient.TEMPERATURE]=devDict[CTDBClient.TEMPERATURE]
        sensorDataDict[CTDBClient.RSSI_DBM]=devDict[CTDBClient.RSSI]

        self._updateMetaTable(dbName, devDict)
        self._recordDeviceTimestamp(startT, 2)

        # Add sensor data to the table containing all sensor data
        MySQLDBClient.AddToTable( CTDBClient.CT6_TABLE_NAME, sensorDataDict, self._dataBaseIF)

        self._recordDeviceTimestamp(startT, 3)

        # If the user does not have another instance running deleting and creating the low resolution data tables.
        if not self._mySQLDBClient.isCreatingLowResTables():
            # Update these tables with new data we have just received.
            self._updateDerivedTables(dbName, sensorDataDict, self._historyDicts, self._dataBaseIF, CTDBClient.LOW_RES_DATA_TABLE_LIST)
        else:
            self._uio.info("Not updating low resolution data tables as they are currently being re created.")

        self._recordDeviceTimestamp(startT, 4)

    def _reportMemoryUsage(self):
        """@brief Report the memory usage while running."""
        _, _, load15 = psutil.getloadavg()
        loadAvg = (load15/os.cpu_count()) * 100
        usedMB = psutil.virtual_memory()[3]/1000000
        freeMB = psutil.virtual_memory()[4]/1000000
        self._uio.debug(f"CPU Load AVG: {loadAvg:.1f}, Used Mem (MB): {usedMB:.1f} Free Mem (MB): {freeMB:.1f}")

        objList = objgraph.most_common_types()
        for elemList in objList:
            _type = elemList[0]
            _count = elemList[1]
            self._uio.debug(f"Found {_count: <8.0f} object of type {_type}")

    def hear(self, devDict):
        """@brief Called when data is received from the device.
           @param devDict The device dict."""
        if self._options.show:
            pretty = json.dumps(devDict, indent=4)
            self._uio.info(f"JSON DATA START <\n{pretty}\n>JSON DATA STOP")

        self._reportMemoryUsage()
        startT = devDict[YView.RX_TIME_SECS]
        try:
            ipAddress = self._getDeviceIPAddress(devDict)
            # If the address of this CT6 unit is in the exclude list
            if ipAddress in self._excludeAddressList:
                # Abort
                return
            # Later CT6 device SW contains an ACTIVE flag that can be set to 0/False
            # This stops the population of databases from the device if device is not active.
            # This config option can be set using ct6_tool.py
            devActive = True
            if CTDBClient.ACTIVE in devDict:
                if not devDict[CTDBClient.ACTIVE]:

                    self._uio.info(f"{ipAddress}: Is not active.")
                    devActive = False

            self._recordDeviceTimestamp(startT, 1)
            if devActive:
                with self._dbLock:
                    self._recordDeviceTimestamp(startT, 2)
                    dbName = self._getDatabaseName(devDict)
                    if dbName:
                        try:
                            self._addDevice(dbName, devDict)
                        except MySQLdb.OperationalError:
                            # If database not found, attempt to create them.
                            self._ensureDBTables(devDict)
                            self._addDevice(dbName, devDict)
                    self._recordDeviceTimestamp(startT, 3)

        except Exception as ex:
            self._uio.error( str(ex) )
            lines = traceback.format_exc().split("\n")
            for line in lines:
                self._uio.debug(line)
            self.disconnect()
            # Enter an loop trying to reconnect with the database server
            # We keep trying to connect until we are successful.
            while True:
                try:
                    self.connect()
                    break
                except Exception as ex:
                    self._uio.error( str(ex) )
                    self._uio.error("Failed to reconnect to the database server")
                    self._uio.error("Trying again in 5 seconds.")
                    sleep(5)



class CTAppServer(object):
    """@brief Responsible for
        - Starting the YViewCollector.
        - Storing data in the database.
        - Presenting the user with a web GUI to allow data to be displayed and manipulated."""

    DEFAULT_CONFIG_FILENAME = "ct6DBStore.cfg"
    LOCK_FILE_NAME          = "CTAppServer.lock"

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A ConfigBase instance."""
        self._uio                   = uio
        self._options               = options
        self._config                = config
        self._yViewCollector        = None
        self._dbHandler             = None
        self._lockFile              = LockFile(CTAppServer.LOCK_FILE_NAME)

    def close(self):
        """@brief Close down the app server."""
        if self._yViewCollector:
            self._yViewCollector.close(halt=True)
            self._yViewCollector = None

        if self._dbHandler:
            self._dbHandler.disconnect()
            self._dbHandler = None

    def _start(self, mySQLDBClient):
        """@Start the App server running.
           @param mySQLDBClient An instance of MySQLDBClient."""
        try:

            # Connect to the database
            self._dbHandler = CTDBClient(self._uio, self._options, self._config, mySQLDBClient)
            self._dbHandler.connect()

            # Start running the local collector in a separate thread
            self._localYViewCollector = LocalYViewCollector(self._uio, self._options)
            self._localYViewCollector.setValidProuctIDList(YViewCollector.VALID_PRODUCT_ID_LIST)

            # Register the dBHandler as a listener for device data so that it can be
            # stored in the database.
            self._localYViewCollector.addDevListener(self._dbHandler)
            net_if = self._config.getAttr(CTDBClientConfig.CT6_DEVICE_DISCOVERY_INTERFACE)
            self._localYViewCollector.start(net_if=net_if)

        finally:
            self.close()

    def startLock(self, mySQLDBClient):
        """@brief As per def startLock() but ensure only one instance is running on a system.
           @param mySQLDBClient An instance of MySQLDBClient."""
        try:
            # Provide some user info on how to remedy lock file issues.
            if self._lockFile.isLockFilePresent():
                self._uio.warn(f"The {self._lockFile.getLockFile()} file was found.")
                self._uio.warn(f"This indicates that another instance of {sys.argv[0]} is running to collect data from CT6 units.")
                self._uio.warn("Either wait for this this process to complete or kill the process and delete the above lock file.")
                self._uio.error("Unable to start this instance of this program.")

            else:

                self._lockFile.createLockFile()
                self._start(mySQLDBClient)
                self._lockFile.removeLockFile()

        # Ensure the lock file is removed when we shutdown
        finally:
            self._lockFile.removeLockFile()

def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="This application is responsible for the following.\n"\
                                                     "- Connecting to a YView icon server to receive device data.\n"\
                                                     "- Storing the Data in a mysql database.\n"\
                                                     "- Presenting a web interface to view and manipulate the data.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",        action='store_true', help="Enable debugging.")
        parser.add_argument("-c", "--configure",    help="Configure the CT App Server.", action='store_true')
        parser.add_argument("-f", "--config_file",  help="The configuration file for the CT App Server"\
                            " (default={}).".format(CTDBClientConfig.GetConfigFile(CTAppServer.DEFAULT_CONFIG_FILENAME)),
                                                    default=CTDBClientConfig.GetConfigFile(CTAppServer.DEFAULT_CONFIG_FILENAME))
        parser.add_argument("-a", "--all",          action='store_true', help="Select all messages rather than just those for the location.")
        parser.add_argument("--show",               action='store_true', help="Show the message data.")

        parser.add_argument("--show_dbs",           help="Show all the databases on the MySQL server.", action="store_true", default=False)
        parser.add_argument("--show_tables",        help="Show all the database tables for the configured database on the MySQL server.", action="store_true", default=False)
        parser.add_argument("--show_table_schema",  help="Show the schema of an SQL table.", action="store_true", default=False)
        parser.add_argument("--db",                 help="The name of the database to use.", default=None)
        parser.add_argument("--create_db",          help="Create the configured database.", action="store_true", default=None)
        parser.add_argument("--delete_db",          help="Delete the configured database.", action="store_true", default=None)
        parser.add_argument("--table",              help="The name of the database table to use.", default=None)
        parser.add_argument("--schema",             help="The database schema to use when creating a database table.", default=None)
        parser.add_argument("--ex_schema",          help="Example database schema.", action="store_true", default=False)
        parser.add_argument("--create_table",       help="Create a table in the configured database.", action="store_true", default=None)
        parser.add_argument("--delete_table",       help="Delete a table from the configured database.", action="store_true", default=None)
        parser.add_argument("--read",               help="Read a number of records from the end of the database table.", action="store_true", default=False)
        parser.add_argument("--read_count",         help="The number of lines to read from the end of the database table (default=1).", type=int, default=1)
        parser.add_argument("--sql",                help="Execute an SQL command.")
        parser.add_argument("--create_dt",          help=f"This option creates the tables derived from the main sensor table ({BaseConstants.CT6_TABLE_NAME}). These tables contain lower resolution data (min, hour and day) for faster data access.", action="store_true", default=False)
        parser.add_argument("-s", "--enable_syslog",action='store_true', help="Enable syslog debug data.")
        parser.add_argument("-e", "--exclude",      help="A comma separated list of addresses of CT6 units to exclude from data collection.")
        BootManager.AddCmdArgs(parser)

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_db_store")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        ctDBClientConfig = CTDBClientConfig(uio, options.config_file, CTDBClientConfig.DEFAULT_CONFIG)
        mySQLDBClient = MySQLDBClient(uio, options, ctDBClientConfig)

        handled = BootManager.HandleOptions(uio, options, options.enable_syslog)
        if not handled:

            if options.configure:
                ctDBClientConfig.configure(editConfigMethod=ctDBClientConfig.edit)

            elif options.create_db:
                mySQLDBClient.createDB()

            elif options.delete_db:
                mySQLDBClient.deleteDB()

            elif options.create_table:
                mySQLDBClient.createTable()

            elif options.delete_table:
                mySQLDBClient.deleteTable()

            elif options.show_dbs:
                mySQLDBClient.showDBS()

            elif options.show_tables:
                mySQLDBClient.showTables()

            elif options.read:
                mySQLDBClient.readTable()

            elif options.sql:
                mySQLDBClient.executeSQL()

            elif options.show_table_schema:
                mySQLDBClient.showSchema()

            elif options.ex_schema:
                mySQLDBClient.showExSchema()

            elif options.create_dt:
                mySQLDBClient.createLowResTablesLock()

            else:
                ctAppServer = CTAppServer(uio, options, ctDBClientConfig)
                ctAppServer.startLock(mySQLDBClient)

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
