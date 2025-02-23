REM Remove the files created during installation

rd /S /Q ct6
rd /S /Q lib

python -m poetry env remove --all
if  errorlevel 1 goto CMD_ERROR

del get-pip.py
if  errorlevel 1 goto CMD_ERROR

del poetry.lock
if  errorlevel 1 goto CMD_ERROR

exit /b 0

:CMD_ERROR
REM The last command failed. Uninstall did not complete successfully.
pause
exit /b 1



