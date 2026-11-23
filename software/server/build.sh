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
cp pyproject.toml ct6/assets/
pyflakes3 ct6/*.py
python3 -m pytest -q tests/test_ct6_dash2_auth.py
python3 -m pytest -q tests/test_ct6_data.py
python3 -m pytest -q tests/test_ct6_data_source_sqlite.py
python3 -m pytest -q tests/test_ct6_selfuse.py
python3 -m pytest -q tests/test_ct6_dash2_version.py
python3 -m pytest -q tests/test_ct6_data_source_cache.py
python3 -m pytest -q tests/test_ct6_heatpump.py
python3 -m pytest -q tests/test_ct6_tariff.py
python3 -m pytest -q tests/test_ct6_dash2_prefs.py
poetry -vvv build
cp dist/ct6-*-py3-none-any.whl installers/
