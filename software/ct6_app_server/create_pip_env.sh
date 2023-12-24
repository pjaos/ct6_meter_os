#!/bin/sh
export PIPENV_VENV_IN_PROJECT=enabled
pipenv --rm
# Create the .venv dir so that pipenv notices it's presence
mkdir .venv
python3 -m pipenv install --three
