#!/usr/bin/env python3

from p3lib.database_if import DBConfig, DatabaseIF

from .config import ConfigBase
from .base_constants import BaseConstants

class DBHandler(BaseConstants):
    """@brief Responsible for interacting with a mysql database."""
    def __init__(self, uio, config):
        """@brief Constructor
           @param uio A UIO instance.
           @param config A ConfigBase instance."""
        self._uio = uio
        self._config = config
        self._dataBaseIF = None

    def connect(self):
        """@brief connect to the database server."""
        self.disconnect()

        self._setupDBConfig()

        self._dataBaseIF.connectNoDB()
        self._uio.info("Connected to MySQL server.")

    def disconnect(self):
        """@brief Shutdown the connection to the DBS"""
        if self._dataBaseIF:
            self._dataBaseIF.disconnect()
            self._dataBaseIF = None

    def _setupDBConfig(self):
        """@brief Setup the internal DB config"""
        self._dataBaseIF                    = None
        self._dbConfig                      = DBConfig()
        self._dbConfig.serverAddress        = self._config.getAttr(ConfigBase.DB_HOST)
        self._dbConfig.username             = self._config.getAttr(ConfigBase.DB_USERNAME)
        self._dbConfig.password             = self._config.getAttr(ConfigBase.DB_PASSWORD)
        self._dbConfig.autoCreateTable      = True
        # Pass uio if debugging is enabled to get more info.
        if self._uio.isDebugEnabled():
            self._dbConfig.uio              = self._uio
        self._dataBaseIF                    = DatabaseIF(self._dbConfig)

    def getDatabaseIF(self):
        return self._dataBaseIF
        

        
        
