REM The windows installer program is executed by the Windows installer once the 
REM file are copied to a Windows platform.
REM We only use poetry (not pipx) on a Windows platform as we need to modify the 
REM installation due to a bug in the pyreadline module (replaced with pyreadline3).

REM Check python is installed.
python --version
if  errorlevel 1 goto NO_PYTHON_ERROR

REM Install PIP
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
if  errorlevel 1 goto CMD_ERROR

python get-pip.py
if  errorlevel 1 goto CMD_ERROR

REM Ensure we have the latest pip version
python -m pip install --upgrade pip
if  errorlevel 1 goto CMD_ERROR

REM Install poetry
python -m pip install poetry
if  errorlevel 1 goto CMD_ERROR

REM Create the python poetry env
python -m poetry lock
if  errorlevel 1 goto CMD_ERROR
python -m poetry install
if  errorlevel 1 goto CMD_ERROR

REM Fixup error in the pyreadline module used by rshell
python -m poetry run python -m pip uninstall -y pyreadline
if  errorlevel 1 goto CMD_ERROR
REM pyreadline3 needs to be uninstalled and then re installed in order 
REM for it to take the place of the pyreadline module.
python -m poetry run python -m pip uninstall -y pyreadline3
if  errorlevel 1 goto CMD_ERROR
python -m poetry run python -m pip install pyreadline3
if  errorlevel 1 goto CMD_ERROR

REM Pause on completion of install.bat so that user can see all messages
pause
exit /b 0

:CMD_ERROR
REM The last command failed. Please try again.
pause
exit /b 1

:NO_PYTHON_ERROR
REM Python not installed. Install Python and try again.
REM The python command below should allow the user to start the Windows Python installer.
python
pause
exit /b 2

:EOF 