#!/bin/sh
# Upgrade an esp32 or picow over the air
# The argument $1 smust be the Wifi IP address of the unit.
set -e
ping -c 1 $1
../../ct6_app_server/ct6_tool.py -a $1 --upgrade app1/
