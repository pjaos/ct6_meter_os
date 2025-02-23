#!/bin/bash
set -e

# Run some tests on the codebase. If this fails then
# the installer file is not built.
python3 tests/tests.py

# Create the git hash to be included in the installer file
# for version tracking purposes.
git rev-parse --short HEAD > assets/git_hash.txt

rm -rf dist/ct6-*-py3-none-any.whl
rm -rf installers/ct6-*-py3-none-any.whl
rm -rf dist
pyflakes3 ct6/*.py
poetry -vvv build
cp dist/ct6-*-py3-none-any.whl installers/
