#!/bin/sh
set -e

#Check the python files and exit on error.
pyflakes3 ct6_db_store.py ct6_dash.py ct6_dash_mgr.py ct6_tool.py ct6_mfg_tool.py

sudo python3 -m pipenv2deb pipenv2deb

