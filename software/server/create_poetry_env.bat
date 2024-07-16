REM This is for use when developing CT6 on a Windows platform.
REM it should be executed after the setup_dev_python_env.bat file.

REM Create the python poetry env
python -m poetry lock
python -m poetry install

REM Fixup error in the pyreadline module used by rshell
python -m poetry run python -m pip uninstall -y pyreadline
REM pyreadline3 needs to be uninstalled and then re installed in order 
REM for it to take the place of the pyreadline module.
python -m poetry run python -m pip uninstall -y pyreadline3
python -m poetry run python -m pip install pyreadline3

