# Installing the CT6 applications.
Installers are available for windows (tested on Windows 11) and Linux (tested on Ubuntu 24.04).

# Installing on a Windows machine

- Before running the CT6 installer which can be found in ct6_meter_os/software/server/installers,
  ensure that python is installed on the Window machine as detailed below.
    - Open a PowerShell window on your windows machine
      - Enter 'python'. If a window is presented with an install button the click it
        and install python. When prompted select the 'Pin To Start' button.
      - If the python prompt is displayed but the python version is not at least 3.12
        then uninstall python using the 'Add or remove programs' option and perform the above 
        step to install python.
- Once python is installed double click the installer file (E.G CT6_7.2.exe) and follow the regular 
  installation wizard and wait for the installer to complete. This may take several minutes.


# Installing on a Linux machine
The server applications are installed onto a debian based Linux system as detailed below.
Testing was performed using Ubuntu 24.04.

## Python installation
The python version installed onto you Linux machine should be at least 3.9. Testing was
performed using Python3.12.

## Debian package installation.

- In a local folder on your Linux machine issue the command below to checkout the ct6_meter_os
  repo.

```
git clone git@github.com:pjaos/ct6_meter_os.git
```

- Install the deb file contained in the installers folder.

```
sudo dpkg -i ct6_meter_os/software/server/installers/python-ct6-apps-7.2-all.deb
(Reading database ... 229248 files and directories currently installed.)
Preparing to unpack .../python-ct6-apps-7.2-all.deb ...
Unpacking python-ct6-apps (7.2) over (7.2) ...
Setting up python-ct6-apps (7.2) ...
Removing virtualenv (/usr/local/bin/python-ct6-apps.pipenvpkg/.venv)...
Creating a virtualenv for this project...
Pipfile: /usr/local/bin/python-ct6-apps.pipenvpkg/Pipfile
Using default python from /usr/bin/python3 (3.12.3) to create virtualenv...
⠙ Creating virtual environment...created virtual environment CPython3.12.3.final.0-64 in 83ms
  creator CPython3Posix(dest=/usr/local/bin/python-ct6-apps.pipenvpkg/.venv, clear=False, no_vcs_ignore=False, global=False)
  seeder FromAppData(download=False, pip=bundle, via=copy, app_data_dir=/root/.local/share/virtualenv)
    added seed packages: pip==24.0
  activators BashActivator,CShellActivator,FishActivator,NushellActivator,PowerShellActivator,PythonActivator

✔ Successfully created virtual environment!
Virtualenv location: /usr/local/bin/python-ct6-apps.pipenvpkg/.venv
Installing dependencies from Pipfile.lock (29e225)...
To activate this project's virtualenv, run pipenv shell.
Alternatively, run a command inside the virtualenv with pipenv run.
***************************************************************************
* The following commands are available.                                   *
* - ct6_db_store                                                          *
* Allow data from CT6 devices to be stored in a MYSQL databse.            *
* - ct6_dash                                                              *
* Display a dashboard to read and display the data in the database.       *
* - ct6_dash_mgr                                                          *
* Add/Remove users to the access list for the server if enabled in config *
* - ct6_mfg_tool                                                          *
* Perform manufacturing test and calibration of a CT6 unit.               *
* - ct6_tool                                                              *
* Provides functionality that is useful when developing CT6 software.     *
* - ct6_configurator                                                      *
* Provides the ability to configure a CT6 unit from a web GUI.            *
***************************************************************************
```

- These commands now available to you on the command line. 
  Command line help text can be viewed for each command if the -h argument is used.
  The software/server/README.md file details how to use the installed software.

