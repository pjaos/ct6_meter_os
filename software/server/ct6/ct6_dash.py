#!/usr/bin/env python3

import argparse

from p3lib.helper import logTraceBack
from p3lib.uio import UIO
from p3lib.boot_manager import BootManager

from lib.config import ConfigBase
from ct6.ct6_dash_mgr import CRED_JSON_FILE
from ct6.ct6_dash_gui import GUI

from ct6.ct6_dash_gui import CT6DashConfig

class CTAppServer(object):
    """@brief Responsible for
        - Starting the YViewCollector.
        - Storing data in the database.
        - Presenting the user with a web GUI to allow data to be displayed and manipulated."""

    def __init__(self, uio, options, config):
        """@brief Constructor
           @param uio A UIO instance
           @param options The command line options instance
           @param config A GUIConfigBase instance."""
        self._uio                   = uio
        self._options               = options
        self._config                = config
        self._dbHandler             = None

    def close(self):
        """@brief Close down the app server."""

        if self._dbHandler:
            self._dbHandler.disconnect()
            self._dbHandler = None

    def start(self):
        """@Start the App server running."""
        try:
            loginEnabled = self._config.getAttr(ConfigBase.SERVER_LOGIN)
            if loginEnabled:
                credFile = CRED_JSON_FILE
            else:
                credFile = None
            gui = GUI(self._uio, self._options, self._config, credFile)
            openBrowser = not self._options.no_gui
            gui.runBlockingBokehServer(gui.getAppMethodDict(), openBrowser=openBrowser)

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
        parser.add_argument("-d", "--debug",  action='store_true', help="Enable debugging.")
        parser.add_argument("-c", "--configure",    help="Enter/Modify the app configuration.", action='store_true')
        parser.add_argument("-f", "--config_file",  help="The configuration file for the CT6 Dash Server"\
                            " (default={}).".format(CT6DashConfig.GetConfigFile(CT6DashConfig.DEFAULT_CONFIG_FILENAME)),
                            default=CT6DashConfig.GetConfigFile(CT6DashConfig.DEFAULT_CONFIG_FILENAME))
        parser.add_argument("--negative",           action='store_true', help="Display imported electricity (kW) on plots as negative values.")
        parser.add_argument("-n", "--no_gui",       action='store_true', help="Do not display the GUI. By default a local web browser is opend displaying the GUI.")
        parser.add_argument("-s", "--enable_syslog",action='store_true', help="Enable syslog debug data.")
        # Default plot points allows 1 week of minute resolution (60*24*7 = 10080)
        parser.add_argument("-m", "--maxpp",        help="The maximum number of plot points (default=86400).", type=int, default=86400)
        BootManager.AddCmdArgs(parser)

        options = parser.parse_args()
        uio.enableDebug(options.debug)
        uio.logAll(True)
        uio.enableSyslog(options.enable_syslog, programName="ct6_dash")
        if options.enable_syslog:
            uio.info("Syslog enabled")

        dashConfig = CT6DashConfig(uio, options.config_file, CT6DashConfig.DEFAULT_CONFIG)
        ctAppServer = CTAppServer(uio, options, dashConfig)

        handled = BootManager.HandleOptions(uio, options, options.enable_syslog)
        if not handled:
            if options.configure:
                dashConfig.configure(editConfigMethod=dashConfig.edit)

            else:
                ctAppServer.start()

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
