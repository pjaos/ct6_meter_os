#!/usr/bin/env python3

import argparse
from p3lib.uio import UIO
from p3lib.helper import logTraceBack
from lib.yview import YViewCollector, LocalYViewCollector
from time import sleep
import rich
import json

class CT6Stats(object):
    """@brief Responsible for discovering all CT6 units on the local network and displaying the stats as
              JSON text on the command line."""

    IP_ADDRESS_KEY = "IP_ADDRESS"

    def __init__(self, uio, options):
        """@brief Constructor
           @param uio A UIO instance handling user input and output (E.G stdin/stdout or a GUI)
           @param options An instance of the OptionParser command line options."""
        self._uio = uio
        self._options = options

    def process(self):
        """@brief Search for all CT6 units on the LAN and display stats received from all units."""
        # Start running the local collector in a separate thread
        self._localYViewCollector = LocalYViewCollector(self._uio, self._options)
        self._localYViewCollector.setValidProuctIDList(YViewCollector.VALID_PRODUCT_ID_LIST)
        self._localYViewCollector.addDevListener(self)
        self._localYViewCollector.start()
        # Wait here while until CTRL C
        while True:
            sleep(1)

    def hear(self, devDict):
        """@brief Called when data is received from the device.
           @param devDict The device dict."""
        # If the user wants to view data from a single unit.
        if self._options.address:
            if CT6Stats.IP_ADDRESS_KEY in devDict and devDict[CT6Stats.IP_ADDRESS_KEY] == self._options.address:
                rich.print_json(json.dumps(devDict))
        # If the user wants to view data from all units.
        else:
            rich.print_json(json.dumps(devDict))

def main():
    """@brief Program entry point"""
    uio = UIO()

    try:
        parser = argparse.ArgumentParser(description="A tool to discover all CT6 units on the local network and displaying the stats as JSON text on the command line.",
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-d", "--debug",   action='store_true', help="Enable debugging.")
        parser.add_argument("-a", "--address", help="The IP address of a single CT6 unit if you wish to get the stats from a single device.", default=None)


        options = parser.parse_args()

        uio.enableDebug(options.debug)
        ct6Stats = CT6Stats(uio, options)
        ct6Stats.process()

    # If the program throws a system exit exception
    except SystemExit:
        pass
    # Don't print error information if CTRL C pressed
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logTraceBack(uio)

        if options.debug:
            raise
        else:
            uio.error(str(ex))


if __name__ == '__main__':
    main()
