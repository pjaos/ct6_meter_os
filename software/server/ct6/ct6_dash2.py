#!/usr/bin/env python3
"""@brief ct6_dash2: a NiceGUI dashboard for CT6 data stored by ct6_db_store.
          It can run alongside ct6_dash as it uses its own config file and TCP port."""

import argparse

from p3lib.helper import logTraceBack, get_program_version
from p3lib.uio import UIO
from p3lib.boot_manager import BootManager

from lib.config import ConfigBase

from ct6.ct6_data_source import create_data_source_factory
from ct6.ct6_dash2_gui import CT6Dash2GUI


class CT6Dash2Config(ConfigBase):
    """@brief The ct6_dash2 configuration. Separate from ct6_dash's so both can run at once."""
    DEFAULT_CONFIG_FILENAME = "ct6Dash2.cfg"
    DEFAULT_CONFIG = {
        ConfigBase.DB_HOST:                     "127.0.0.1",
        ConfigBase.DB_PORT:                     3306,
        ConfigBase.DB_USERNAME:                 "",
        ConfigBase.DB_PASSWORD:                 "",
        ConfigBase.LOCAL_GUI_SERVER_ADDRESS:    "",
        ConfigBase.LOCAL_GUI_SERVER_PORT:       10001,
        ConfigBase.SERVER_ACCESS_LOG_FILE:      ""
    }


def main():
    """@brief Program entry point"""
    uio = UIO()
    options = None
    try:
        parser = argparse.ArgumentParser(description="A web dashboard (NiceGUI) to view the data stored in the\n"
                                                     "MySQL database by ct6_db_store.",
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
                gui = CT6Dash2GUI(uio,
                                  options,
                                  create_data_source_factory(config),
                                  config.getAttr(ConfigBase.LOCAL_GUI_SERVER_ADDRESS),
                                  config.getAttr(ConfigBase.LOCAL_GUI_SERVER_PORT),
                                  access_log_file=config.getAttr(ConfigBase.SERVER_ACCESS_LOG_FILE),
                                  version=get_program_version())
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
