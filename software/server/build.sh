#!/bin/bash
set -e
rm -rf dist/ct6-*-py3-none-any.whl
rm -rf installers/ct6-*-py3-none-any.whl
rm -rf dist
pyflakes3 ct6/*.py
poetry -vvv build
cp dist/ct6-*-py3-none-any.whl installers/
