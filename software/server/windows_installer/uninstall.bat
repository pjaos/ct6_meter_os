REM This removes the artefacts created by the pipx install in the install.bat file.
python -m pipx uninstall ct6
REM Remove the installation folder.
rmdir /S /Q "C:\Python_Program_Files\CT6"


