#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import argparse
import sqlite3
import threading
import shutil

from time import time, sleep

import mysql.connector

from p3lib.uio import UIO
from p3lib.boot_manager import BootManager
from p3lib.helper import logTraceBack

from lib.config import ConfigBase
from lib.yview import YViewCollector, LocalYViewCollector

from ct6.ct6_dash_mgr import CRED_JSON_FILE

from ct6.ct6_app_gui import AppConfig, SQLite3DBClient, GUI


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
           @param config An AppConfig instance.
           @param db_client An SQLite3DBClient instance."""
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

    def _get_sqlite_database_file(self, mysql_db_name, mysql_cursor, imported=False):
        """@brief Get a list of the sqlite database files.
           @param mysql_database_files A list of the mysql database files.
           @param mysql_cursor A cursor connected to the mysql database.
           @param imported If True add '.imported' to the filename.
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
            if imported:
                sqlite_db_name = sqlite_db_name + ".imported"
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
                db_file = self._get_sqlite_database_file(mysql_server_ct6_db, mysql_cursor, imported=False)
                if db_file and os.path.isfile(db_file):
                    raise Exception(f"The {db_file} sqlite database file already exists.")

                db_file = self._get_sqlite_database_file(mysql_server_ct6_db, mysql_cursor, imported=True)
                if db_file and os.path.isfile(db_file):
                    raise Exception(f"The {db_file} sqlite database file already exists.")

            for mysql_server_ct6_db in mysql_server_ct6_db_list:
                # This takes the mysql database and creates the *.db.imported file
                self._convert_database(mysql_server_ct6_db, mysql_cursor)

        finally:
            if mysql_cursor:
                mysql_cursor.close()
            if mysql_conn:
                mysql_conn.close()
        elapsed_seconds = int(time() - start_time)
        hms_str = self.seconds_to_hms(elapsed_seconds)
        self._uio.info(f"Took {hms_str} (HH:MM:SS) to import the CT6 MYSQL databases.")

    def seconds_to_hms(self, seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"

    def _convert_database(self, db_name, mysql_cursor):
        """@brief Convert the CT6 mysql database to an sqlite database.
           @param db_name The name of the mysql database.
           @param mysql_cursor The cursor connected to the mysql database."""
        imported_sqlite_db_file = self._get_sqlite_database_file(db_name, mysql_cursor, imported=True)
        self._copy_mysql_to_sqlite_db(mysql_cursor, imported_sqlite_db_file)
        self.create_timestamp_index(imported_sqlite_db_file, MYSQLImporter.VALID_CT6_DB_TABLE_NAMES[1])
        self.add_unit_name_column(imported_sqlite_db_file, db_name)
        sqlite_db_file = self._get_sqlite_database_file(db_name, mysql_cursor, imported=False)
        shutil.move(imported_sqlite_db_file, sqlite_db_file)
        self._uio.info(f"Renamed {imported_sqlite_db_file} to {sqlite_db_file}")

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
            self._uio.info(f"Connected to SQLite: {sqlite_db}")

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
            gui.runBlockingBokehServer(gui.getAppMethodDict(), openBrowser=openBrowser)

        finally:
# PJA no close() method exists !!!
            pass
#            self.close()

    def startPopulatingDatabase(self, db_client):
        """@brief Starts the threads that collect data from CT6 units and populate the sqlite database.
           @param db_client An instance of SQLite3DBClient."""
        # Start running the local collector in a separate thread
        self._localYViewCollector = LocalYViewCollector(self._uio, self._options)
        self._localYViewCollector.setValidProductIDList(YViewCollector.VALID_PRODUCT_ID_LIST)

        # Register the dBHandler as a listener for device data so that it can be
        # stored in the database.
        self._localYViewCollector.addDevListener(db_client)
        net_if = self._config.getAttr(AppConfig.CT6_DEVICE_DISCOVERY_INTERFACE)
        collector_thread = threading.Thread(target=self._localYViewCollector.start, args=(net_if,))
        collector_thread.daemon = True
        collector_thread.start()

    def start(self, db_client):
        """@Start the App server running.
            @param db_client An instance of SQLite3DBClient."""
        try:
            self.startPopulatingDatabase(db_client)

            # Start a web UI to allow the user to view the data
            self._startGUI(db_client)

        finally:
            db_client.disconnect()

# PJA TODO, auto restart threads if they crash

















































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
        parser.add_argument("--negative",           action='store_true', help="Display imported electricity (kW) on plots as negative values.")

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

            if options.configure:
                app_config.configure(editConfigMethod=app_config.edit)

            else:
                start_db_update = True
                if options.conv_dbs or options.show_tables:
                    start_db_update = False

                db_client = SQLite3DBClient(uio,
                                            options,
                                            app_config,
                                            start_db_update=start_db_update)

                app_server = AppServer(uio, options, app_config)

                if options.conv_dbs:
                    app_server.startPopulatingDatabase(db_client)
                    # Wait for detected CT6 dev messages to appear on std out before
                    # prompting the user to enter the import config.
                    sleep(5)
                    mysql_importer = MYSQLImporter(uio, options, app_config)
                    # This may take a while with large databases.
                    mysql_importer.convert_mysql_to_sqlite()
                    # Update the database/s with all the CT6 dev_dict's received
                    # while the database was being imported from the mysql database.
                    count = db_client.update_db_from_dev_dict_queue()
                    uio.info(f"Updated databases with {count} CT6 messages received while importing mysql data.")
                    # Start the app server so we don't miss data
                    app_server.start(db_client)

                elif options.show_tables:
                    db_client.show_tables()

                else:
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
