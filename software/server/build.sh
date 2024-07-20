#!/bin/bash
set -e
rm -rf picow 
cp -rf ../picow .
rm -rf dist
pyflakes3 ct6/*.py
poetry -vvv build
