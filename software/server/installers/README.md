# Installing the CT6 applications.
Installers are available for windows (tested on Windows 11) and Linux (tested on Ubuntu 24.04).

# Installing on a Windows machine

- Before running the CT6 installer which can be found in ct6_meter_os/software/server/installers,
  ensure that python is installed on the Windows machine as detailed below.
    - Open a PowerShell window on your windows machine
      - Enter 'python'. If a window is presented with an install button the click it
        and install python. When prompted select the 'Pin To Start' button.
      - If the python prompt is displayed but the python version is not at least 3.12
        then uninstall python using the 'Add or remove programs' option and perform the above 
        step to install python.
- Once python is installed double click the installer file (E.G CT6_7.9.exe which can be found in
  the software/server/installers folder of the repo) and follow the regular 
  installation wizard and wait for the installer to complete. This may take several minutes.


# Installing on a Linux machine
The server applications are installed onto a debian based Linux system as detailed below.

## Python installation
The python version installed onto you Linux machine should be at least 3.12. Testing was
performed using Python3.12.

## Python wheel installation.
The installer is now provided as a python wheel file (*.whl file extension). This can be used to install the
apps on a Linux machine. It should also be possible to use this file to install the apps onto other 
operating systems, however only Linux has been tested. It should be noted that the python wheel file cannot be used to
install the apps onto Windows systems. This is due to an issue with the pyreadline python module on windows 
systems. This is resolved if the above Windows installer is used as shown above.

- In a local folder on your Linux machine issue the command below to checkout the ct6_meter_os
  repo.

```
git clone git@github.com:pjaos/ct6_meter_os.git
```

- Before installing the python wheel pipx must be installed. pipx can be installed onto an ubuntu 24.04
machine using the following commands in a terminal.

```
sudo apt update
sudo apt install pipx
pipx ensurepath
```

- Once pipx is installed the ct6 apps can be installed as shown below from a terminal window in the 
software/server/installers folder of the repo.

```
pipx install ct6-7.9-py3-none-any.whl
  installed package ct6 7.9, installed using Python 3.12.3
  These apps are now globally available
    - ct6_configurator
    - ct6_dash
    - ct6_dash_mgr
    - ct6_db_store
    - ct6_mfg_tool
    - ct6_tool
done! ✨ 🌟 ✨
```

  The above commands are now available to you on the command line. 
  Command line help text can be viewed for each command if the -h argument is used.
  The software/server/README.md file details how to use the installed software.

