REM This is for use when developing CT6 on a Windows platform.

REM We need PIP installed
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py

REM Ensure we have the latest pip version
python -m pip install --upgrade pip

REM Install poetry
python -m pip install poetry
