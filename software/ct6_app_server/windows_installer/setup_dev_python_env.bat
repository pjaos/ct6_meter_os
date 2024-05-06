REM Add commands here that need to be executed on installation

REM We need PIP installed
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py

REM Ensure we have the latest pip version
python -m pip install --upgrade pip

REM install the nsist module the dev needs to build the installer
pip install pynsist

