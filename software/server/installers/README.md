# Installing the CT6 applications.

Installers are available for windows (tested on Windows 11 but should work on Windows 10) and 
Linux (Tested on Ubuntu 24.04).

# Instaling on a Windows machine

- Before running the installer ensure that python is installed on the Window machine as detailed
  below.
    - Open a PowerShell window on your windows machine
      - Enter 'python'. If a window is presented with an install button the click it
        and install python. When prompted select the 'Pin To Start' button.
      - If the python prompt is displayed but the python version is not at least 3.12
        then uninstall python using the 'Add or remove programs' option and perform the above step to install python.
- Once python is installed double click the installer file (E.G CT6_7.2.exe) and wait for the   
  installer to complete. This may take several minutes.

# Installing on a Linux machine




 Ensure python is installed as detailed in the 'Checking python is installed' section of this
  document.

To build the windows installer run the build.bat file on a Windows 11
machine that has the following installed

- Ensure python is installed as detailed in the 'Checking python is installed' section of this
  document.
- Ensure the NullSoft Install System is installed. The installers for this can be found 
  at 'https://sourceforge.net/projects/nsis/files/NSIS%202/'.
- Run the setup_dev_python_env.bat file to install the requires python modules.

# Checking python is installed
- Open a PowerShell window on your windows machine
  - Enter 'python'. If a window is presented with an install button the click it
    and install python. When prompted select the 'Pin To Start' button.
  - If the python prompt is displayed but the python version is not at least 3.12
    then uninstall python using the 'Add or remove programs' option and perform the above step to install python



  
