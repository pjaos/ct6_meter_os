#!/bin/sh
# Requires rshell is installed (pip install rshell)
# Requires a single argument. This is the USB port device (E.G /dev/ttyUSB0).
# This command gives access to the rshell that allows you to manually inspect
# the contents of the picow flash in the cd /pyboard/ folder.
# Once running you can copy files to the /pyboard folder and
# these will then be present in the picow flash folder.
# For pico W
# rshell --rts 1 --dtr 0 -p $1 --buffer-size 512
rshell --rts 1 --dtr 1 -p $1 --buffer-size 512