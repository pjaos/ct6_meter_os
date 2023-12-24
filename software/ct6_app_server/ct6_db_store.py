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
import argparse
import threading
import traceback

import pandas as pd

from time import time
from datetime import datetime

from p3lib.helper import logTraceBack
from p3lib.uio import UIO
from p3lib.database_if import DBConfig, DatabaseIF
from p3lib.ssh import SSH

from lib.config import ConfigBase
from lib.db_handler import DBHandler
from lib.yview import YViewCollector, LocalYViewCollector
from lib.base_constants import BaseConstants

class CTDBClientConfig(ConfigBase):
    DEFAULT_CONFIG = {
        ConfigBase.ICONS_ADDRESS:              "127.0.0.1",
        ConfigBase.ICONS_PORT:                 22,
        ConfigBase.ICONS_USERNAME:             "",
        ConfigBase.ICONS_SSH_KEY_FILE:         SSH.GetPrivateKeyFile(),
        ConfigBase.MQTT_TOPIC:                 "#",
        ConfigBase.DB_HOST:                    "127.0.0.1",
        ConfigBase.DB_PORT:                    3306,
        ConfigBase.DB_USERNAME:                "",
        ConfigBase.DB_PASSWORD:                ""
    }
    
class MySQLDBClient(BaseConstants):
    """@Responsible for
        - Providing an interface to view and change a database.."""
    
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
    
    def createLowResTables(self):
        """@brief Create tables with lower resolution data derived from the main sensor table.
                  These are created because they are faster to than the full resolution data."""            
        try:
            self._uio.info("Creating Hour and Day tables...")
            self._setupDBConfig()
            self._dataBaseIF.connectNoDB()
            sql = 'SHOW DATABASES;'
            recordTuple = self._dataBaseIF.executeSQL(sql)
            for record in recordTuple:
                startTime = time()
                if 'Database' in record:
                    dBname = record['Database']
                    sql = 'USE {};'.format(dBname)
                    recordTuple = self._dataBaseIF.executeSQL(sql)
                    sql = 'SHOW TABLES;'
                    recordTuple = self._dataBaseIF.executeSQL(sql)
                    key = 'Tables_in_{}'.format(dBname)
                    ct6Database = False
                    for record in recordTuple:
                        tableName = record[key]
                        if tableName == MySQLDBClient.CT6_TABLE_NAME:
                            ct6Database = True
                            break
                        
                    if ct6Database:
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

                        self._uio.info(f"Creating derived tables in {dBname}.")
                        # This can take a while with a large database. However once written these tables allow faster access.
                        for chunkLen, srcTableName, destTableName in [[60, BaseConstants.CT6_TABLE_NAME, CTDBClient.MINUTE_RES_DB_DATA_TABLE_NAME],
                                                                      [60, CTDBClient.MINUTE_RES_DB_DATA_TABLE_NAME, CTDBClient.HOUR_RES_DB_DATA_TABLE_NAME],
                                                                      [24, CTDBClient.HOUR_RES_DB_DATA_TABLE_NAME, CTDBClient.DAY_RES_DB_DATA_TABLE_NAME] ]:
                        
                            sql = f"select * from {srcTableName};"
                            recordTuple = self._dataBaseIF.executeSQL(sql)
                            df = pd.DataFrame(recordTuple)
                            # This appears no faster and raises compatibility message, s use above
                            # df = pd.read_sql(f"select * from {BaseConstants.CT6_TABLE_NAME};", con=self._dataBaseIF._dbCon)
                            startT=time()
                            # Chop up into 60 second blocks
                            n = chunkLen
                            chunks = [df[i:i+n] for i in range(0,df.shape[0],n)]
                            elapsedSecs=time()-startT
                            startT=time()
                            # Write a single record with the average of all records.
                            for chunk in chunks:
                                MySQLDBClient.AddToTable(destTableName, chunk.mean(), self._dataBaseIF)
                            elapsedSecs=time()-startT
                            self._uio.info(f"Took {elapsedSecs:.1f} seconds to write {destTableName} table in {dBname}")

                        # Create time stamp indexes for all derived tables to improve search speed.
                        for tableName in MySQLDBClient.LOW_RES_DATA_TABLE_LIST:  
                            # Index on time stamp as most search will be based around a date/time
                            cmd = f"CREATE INDEX {tableName}_INDEX ON {tableName} ({CTDBClient.TIMESTAMP})"
                            self._dataBaseIF.executeSQL(cmd)
                            self._uio.info(f"Created {tableName}_INDEX in {dBname}.")
                        
                        elapsedTime = time()-startTime
                        self._uio.info(f"Took {elapsedTime:.1f} seconds to create derived tables in {dBname}")
                        
            self._uio.info("Derived tables created.")

        finally:
            self._shutdownDBSConnection()
 

class CTDBClient(DBHandler):
    """@responsible for CT6 sensor database access."""

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance.
           @param options The command line options instance.
           @param config A ConfigBase instance."""
        super().__init__(uio, config)
        self._options = options
        self._metaTableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_META_TABLE_SCHEMA )
        self._tableSchema = DBHandler.GetTableSchema( CTDBClient.CT6_DB_TABLE_SCHEMA )
        self._dbLock = threading.Lock()
        self._historyDicts={}
        self._hourRecordSets=[]
        
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
            
    def _ensureDBTables(self, devDict):
        """@brief Ensure the database and tables exist in the connected database assuming that
                  devDict contains the assy label of the device.
           @param The device dictionary as received from the YView server.
           @return The name of the database."""
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
                # Don't record data unless the device name has been set as this is used as the database name.
                return
            
            productID = devDict[CTDBClient.PRODUCT_ID]
            # Check that this app can handle data from this type of device.
            if productID in CTDBClient.VALID_PRODUCT_ID_LIST:
                dBName = unitName
                self._dbConfig.dataBaseName = dBName
                recordTuple = self._dataBaseIF.executeSQL(DBHandler.SHOW_DATABASES_SQL_CMD)
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
                            
        return dBName
 
    def _updateMetaTable(self, dbName, devDict):
        """@brief Update the table containing meta data.
           @param dbName The name of the database to update.
           @param devDict The device dict."""
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
            
    def _updateDerivedTables(self, dbName, thisRecord, historyDicts, dataBaseIF, lowResTableList):
        """@brief Update the min, hour and day tables in the database.
           @param dbName The name of the database to update. We assume this has been selected previously (sql use DB command issued).
           @param thisRecord The dict containing the data to be added to the database.
           @param historyDicts The dicts containing the reading history.
           @param dataBaseIF The interface to the database.
           @param lowResTableList The list of the NAMES OF THE databaSE TABLES (MIN, HOUR AND DAY).
           @PARAM UIO A UIO instance (if defined) to record debug information as records are added to the database tables."""
        if not dbName in historyDicts:
            # We need lists to hold the min, hour and day records
            historyDicts[dbName]=[[],[],[]]
        # The record sets for this database
        recordSets = historyDicts[dbName]

        # First derived table (minute)
        tableName = lowResTableList[0]
        recordSet = recordSets[0]
        # If we've moved into the next minute
        if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].second  - recordSet[0][BaseConstants.TIMESTAMP].second) <= 0:
            # Ensure we have several records as we may get two readings in the same second (microseconds apart) but we don't want to add
            # data to the database unless it's valid. We should have 60 second values in the list but this may vary slightly as 
            # poll/response and  network delays to-from the CT6 device may move the sampling times.
            if len(recordSet) > 5:
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
                if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].minute - recordSet[0][BaseConstants.TIMESTAMP].minute) <= 0:
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
                    if len(recordSet) > 0 and (thisRecord[BaseConstants.TIMESTAMP].hour - recordSet[0][BaseConstants.TIMESTAMP].hour) <= 0:
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

    def _addDevice(self, dbName, devDict):
        """@brief Add device data to the database.
           @param dbName The name of the database to update.
           @param devDict The device dict."""

        self._dataBaseIF.executeSQL("USE {};".format(dbName))
        sensorDataDict = {}
        sensorDataDict[MySQLDBClient.TIMESTAMP] = datetime.now()
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
                    
        # Add sensor data to the table containing all sensor data
        MySQLDBClient.AddToTable( CTDBClient.CT6_TABLE_NAME, sensorDataDict, self._dataBaseIF)            

        self._updateDerivedTables(dbName, sensorDataDict, self._historyDicts, self._dataBaseIF, CTDBClient.LOW_RES_DATA_TABLE_LIST)       
    
    def hear(self, devDict):
        """@brief Called when data is received from the device.
           @param devDict The device dict."""
        try:
            ipAddress = self._getDeviceIPAddress(devDict)
            # If the address of this CT6 unit is in the exclude list
            if ipAddress in self._excludeAddressList:
                # Abort
                return
            # Later CT6 device SW contains an ACTIVE flag that can be set to 0/False
            # This stops the population of databases from the device.
            devActive = True
            if CTDBClient.ACTIVE in devDict:
                if not devDict[CTDBClient.ACTIVE]:
                    
                    self._uio.warn(f"{ipAddress}: Is not active.")
                    devActive = False
                    
            if devActive:
                with self._dbLock:
                    dbName = self._ensureDBTables(devDict)
                    if dbName:
                        self._addDevice(dbName, devDict)

        except Exception as ex:
            self._uio.error( str(ex) )
            lines = traceback.format_exc().split("\n")
            for line in lines:
                self._uio.debug(line)
            self.disconnect()
            self.connect()           
            
class CTAppServer(object):
    """@brief Responsible for
        - Starting the YViewCollector.
        - Storing data in the database.
        - Presenting the user with a web GUI to allow data to be displayed and manipulated."""

    DEFAULT_CONFIG_FILENAME = "ct6DBStore.cfg"
    
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

    def close(self):
        """@brief Close down the app server."""
        if self._yViewCollector:
            self._yViewCollector.close(halt=True)
            self._yViewCollector = None

        if self._dbHandler:
            self._dbHandler.disconnect()
            self._dbHandler = None

    def startIcons(self):
        """@Start the App server running."""
        raise Exception("PJA will not work now we have put the device on a different YDEV AT UDP port.")
        try:
            # Connect to the database
            self._dbHandler = CTDBClient(self._uio, self._options, self._config)
            self._dbHandler.connect()
            
            # Start running the collector in a separate thread
            self._yViewCollector = YViewCollector(self._uio, self._options, self._config)
            self._yViewCollector.setValidProuctIDList(YViewCollector.VALID_PRODUCT_ID_LIST)
            # Register the dBHandler as a listener for device data so that it can be
            # stored in the database.
            self._yViewCollector.addDevListener(self._dbHandler)
            self._yViewCollector.start()

        finally:
            self.close()
            
    def startLocal(self):
        """@Start the App server running."""
        try:
            # Connect to the database
            self._dbHandler = CTDBClient(self._uio, self._options, self._config)
            self._dbHandler.connect()
            
            # Start running the local collector in a separate thread
            self._localYViewCollector = LocalYViewCollector(self._uio, self._options)
            self._localYViewCollector.setValidProuctIDList(YViewCollector.VALID_PRODUCT_ID_LIST)
            
            # Register the dBHandler as a listener for device data so that it can be
            # stored in the database.
            self._localYViewCollector.addDevListener(self._dbHandler)
            self._localYViewCollector.start()

        finally:
            self.close()


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
        parser.add_argument("-i", "--icons",        action='store_true', help="Collect data from an ICON server. If this command line argument is not used then data is collected from local (to this LAN) devices.")
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
        parser.add_argument("--create_dt",          help=f"This option creates the tables derived from the main sensor table ({BaseConstants.CT6_TABLE_NAME}). These contain lower resolution data that is faster to search.", action="store_true", default=False)
        parser.add_argument("-s", "--enable_syslog",action='store_true', help="Enable syslog debug data.")
        parser.add_argument("-n", "--nodtc",        action='store_true', help="Do not create the derived tables on startup.")
        parser.add_argument("-e", "--exclude",      help="A comma separated list of addresses of CT6 units to exclude from data collection.")
        
        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_db_store")
        if options.enable_syslog:
            uio.info("Syslog enabled")
            
        ctDBClientConfig = CTDBClientConfig(uio, options.config_file, CTDBClientConfig.DEFAULT_CONFIG)
        mySQLDBClient = MySQLDBClient(uio, options, ctDBClientConfig)
        
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
            if options.nodtc:
                raise Exception("Invalid command line argument combination: --create_dt and --nodtc")
            mySQLDBClient.createLowResTables()

        else:
            # By default we recreate the min, hour and day tables when starting the process of reaping data
            if not options.nodtc:
                mySQLDBClient.createLowResTables()
            else:
                uio.info("Skipping derived tables creation.")
            ctAppServer = CTAppServer(uio, options, ctDBClientConfig)
            
            if options.icons:
                ctAppServer.startIcons()
            else:
                ctAppServer.startLocal()

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
