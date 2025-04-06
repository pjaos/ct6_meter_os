REM This is for use when developing CT6 on a Windows platform.
REM it should be executed after the setup_dev_python_env.bat file.

REM We need this line because the default path may be to long. 
REM This will stop the python bleak module loading. 
REM set POETRY_VIRTUALENVS_PATH=C:\venvs
REM Create the python poetry env
python -m python -m pip install --upgrade pip
python -m pip install poetry
python -m poetry self update
REM python3.12 -m poetry env remove python
REM python3.12 -m poetry env remove python3.12
python -m poetry config virtualenvs.path C:\Python_Program_Files\CT6\venvs
python -m poetry lock
python -m poetry install
REM This installs the shell cmd with poetry >= 2.0
python -m poetry self add poetry-plugin-shell



