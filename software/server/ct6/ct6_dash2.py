#!/usr/bin/env python3
"""@brief ct6_dash2: a NiceGUI dashboard for CT6 data stored by ct6_db_store.
          It can run alongside ct6_dash as it uses its own config file and TCP port."""

import argparse
import os

from importlib import metadata

from p3lib.helper import logTraceBack, get_program_version
from p3lib.uio import UIO
from p3lib.boot_manager import BootManager

from lib.config import ConfigBase

from ct6.ct6_data_source import (create_data_source_factory, default_sqlite_path,
                                  BACKEND_MYSQL, BACKEND_SQLITE, DB_BACKEND, SQLITE_DB_PATH)
from ct6.ct6_dash2_gui import CT6Dash2GUI
from ct6.ct6_dash2_auth import LoginManager, load_or_create_secret
from ct6.ct6_dash_mgr import CRED_JSON_FILE


def program_version():
    """@brief Get the ct6 package version for display. Never raises: the version is
              only shown in the GUI, so a lookup problem must not stop the app."""
    try:
        # Name the package explicitly. Without it p3lib guesses the package from the
        # entry point script's folder, which is 'bin' when installed with pip/pipx.
        return get_program_version("ct6")
    except Exception:
        try:
            return metadata.version("ct6")
        except Exception:
            return "unknown"


class CT6Dash2Config(ConfigBase):
    """@brief The ct6_dash2 configuration. Separate from ct6_dash's so both can run at once."""
    DEFAULT_CONFIG_FILENAME = "ct6Dash2.cfg"
    DEFAULT_CONFIG = {
        DB_BACKEND:                             BACKEND_MYSQL,
        SQLITE_DB_PATH:                         default_sqlite_path(),
        ConfigBase.DB_HOST:                     "127.0.0.1",
        ConfigBase.DB_PORT:                     3306,
        ConfigBase.DB_USERNAME:                 "",
        ConfigBase.DB_PASSWORD:                 "",
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS:    "",
        ConfigBase.LOCAL_GUI_SERVER_PORT:       10001,
        ConfigBase.SERVER_ACCESS_LOG_FILE:      "",
        ConfigBase.SERVER_LOGIN:                False
    }
    SECRET_FILENAME = "ct6Dash2.secret"         # Signs session cookies (created on first run, mode 0600)
    STORAGE_FOLDER = "ct6_dash2_sessions"       # NiceGUI per-browser session data

    def edit(self, key):
        """@brief Edit a config parameter (adds the database backend settings to ConfigBase.edit())."""
        if key == DB_BACKEND:
            previous = self.getAttr(DB_BACKEND)
            while True:
                self.inputStr(DB_BACKEND, f"Enter the database type: '{BACKEND_MYSQL}' (ct6_db_store) "
                                          f"or '{BACKEND_SQLITE}' (ct6_app)", False)
                value = str(self.getAttr(DB_BACKEND)).strip().lower()
                if value in (BACKEND_MYSQL, BACKEND_SQLITE):
                    self.addAttr(DB_BACKEND, value)
                    break
                self._uio.error(f"Enter {BACKEND_MYSQL} or {BACKEND_SQLITE}.")
                self.addAttr(DB_BACKEND, previous)

        elif key == SQLITE_DB_PATH:
            previous = self.getAttr(SQLITE_DB_PATH)
            while True:
                self.inputStr(SQLITE_DB_PATH, "Enter the folder holding the ct6_app SQLite (.db) files "
                                              "(enter d for the default value)", False)
                path = str(self.getAttr(SQLITE_DB_PATH)).strip()
                if path.lower() == "d":
                    path = default_sqlite_path()
                path = os.path.abspath(os.path.expanduser(path))
                self.addAttr(SQLITE_DB_PATH, path)
                if os.path.isdir(path):
                    break
                self._uio.error(f"{path} folder not found.")
                self.addAttr(SQLITE_DB_PATH, previous)

        else:
            super().edit(key)


def main():
    """@brief Program entry point"""
    uio = UIO()
    options = None
    try:
        parser = argparse.ArgumentParser(description="A web dashboard (NiceGUI) to view CT6 data stored in the\n"
                                                     "MySQL database by ct6_db_store or the SQLite databases by ct6_app.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",         action='store_true', help="Enable debugging.")
        parser.add_argument("-c", "--configure",     action='store_true', help="Enter/Modify the app configuration.")
        parser.add_argument("-f", "--config_file",   help="The configuration file for ct6_dash2"
                            " (default={}).".format(CT6Dash2Config.GetConfigFile(CT6Dash2Config.DEFAULT_CONFIG_FILENAME)),
                            default=CT6Dash2Config.GetConfigFile(CT6Dash2Config.DEFAULT_CONFIG_FILENAME))
        parser.add_argument("--negative",            action='store_true', help="Display imported electricity (kW) on plots as negative values.")
        parser.add_argument("-n", "--no_gui",        action='store_true', help="Do not display the GUI. By default a local web browser is opened displaying the GUI.")
        parser.add_argument("-s", "--enable_syslog", action='store_true', help="Enable syslog debug data.")
        parser.add_argument("-m", "--maxpp",         help="The maximum number of values that may be read from the database for one plot (default=86400).", type=int, default=86400)
        parser.add_argument("--sqlite",              help="Read the SQLite database files written by ct6_app from this folder, "
                                                          "instead of using the database type set in the configuration.", default=None)
        parser.add_argument("--maxdp",               help="The maximum number of points per trace sent to the browser. Larger plots are reduced, keeping the min/max values (default=20000).", type=int, default=20000)
        BootManager.AddCmdArgs(parser)

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_dash2")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        config = CT6Dash2Config(uio, options.config_file, CT6Dash2Config.DEFAULT_CONFIG)

        handled = BootManager.HandleOptions(uio, options, options.enable_syslog)
        if not handled:
            if options.configure:
                config.configure(editConfigMethod=config.edit)

            else:
                config_dir = os.path.dirname(os.path.abspath(options.config_file))
                login_manager = None
                if config.getAttr(ConfigBase.SERVER_LOGIN):
                    login_manager = LoginManager(CRED_JSON_FILE)
                    if login_manager.user_count() == 0:
                        raise Exception(f"Login is enabled but no users are set up in {CRED_JSON_FILE}. "
                                        "Run ct6_dash_mgr to add a user, or disable login with ct6_dash2 -c.")
                    uio.info(f"Login enabled ({login_manager.user_count()} user(s) in {CRED_JSON_FILE}).")
                gui = CT6Dash2GUI(uio,
                                  options,
                                  create_data_source_factory(config, sqlite_path=options.sqlite),
                                  config.getAttr(ConfigBase.LOCAL_GUI_SERVER_ADDRESS),
                                  config.getAttr(ConfigBase.LOCAL_GUI_SERVER_PORT),
                                  access_log_file=config.getAttr(ConfigBase.SERVER_ACCESS_LOG_FILE),
                                  version=program_version(),
                                  login_manager=login_manager,
                                  storage_path=os.path.join(config_dir, CT6Dash2Config.STORAGE_FOLDER),
                                  storage_secret=load_or_create_secret(os.path.join(config_dir, CT6Dash2Config.SECRET_FILENAME)))
                gui.run()

    # If the program throws a system exit exception
    except SystemExit:
        pass
    # Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if options and options.debug:
            raise
        else:
            uio.error(str(ex))


if __name__ == '__main__':
    main()
