# Installing the CT6 applications.
Installers are available for windows (tested on Windows 11) and Linux (tested on Ubuntu 24.04).

# Installing on a Windows machine

- Before running the CT6 installer which can be found in ct6_meter_os/software/server/installers,
  ensure that python is installed on the Windows machine using the [python.org](https://www.python.org/downloads/windows/) installer for python 3.13.3.
- Once python is installed double click the installer file (E.G CT6_11.0.exe which can be found in
  the software/server/installers folder of the repo) and follow the regular installation wizard and wait for the installer to complete. This may take several minutes.


# Installing on a Linux machine
The server applications are installed onto a debian based Linux system as detailed below.

## Remove debian based installer
If you previously installed the ct6 software using the debian package it should be uninstalled before
proceeding as shown below.

```
sudo dpkg -r python-ct6-apps
```

## Python installation
You will need python installed on your computer. This should be version 3.13.3 or later. Click [here](https://www.python.org/downloads/) for details of how to install python on your computer.

## Python wheel installation.
The CT6 installer is provided as a python wheel file (.whl file extension). This can be used to install the
apps on a Linux machine. It should also be possible to use this file to install the apps onto other
operating systems, however only Linux has been tested. It should be noted that the python wheel file cannot be used to install the apps onto Windows systems. This is due to an issue with the pyreadline python module on windows systems. This is resolved if the CT6 Windows installer is used.

- Before installing the CT6 apps, pipx must be installed. Click [here](https://pipx.pypa.io/latest/installation/) for details of how to install pipx onto your computer.

- Once python and pipx are installed you must either install git onto your computer and clone the CT6 git repo.

    - For details of how to install git on your computer click [here](https://git-scm.com/downloads). The command below can then be used to create a local copy of the CT6 git repo on a Linux computer with git installed.

        ```
        git clone git@github.com:pjaos/ct6_meter_os.git
        ```

    - Alternatively you can download the ct6 zip file from github and unzip it locally. This zip file can be downloaded by clicking [here](https://github.com/pjaos/ct6_meter_os/archive/refs/heads/master.zip)

- The ct6 apps can be installed as shown below from a terminal window in the
root of the ct6 repo.

        pipx install software/server/installers/ct6-10.9-py3-none-any.whl
          installed package ct6 10.9, installed using Python 3.12.3
          These apps are now globally available
            - ct6_app
            - ct6_configurator
            - ct6_dash
            - ct6_dash_mgr
            - ct6_db_store
            - ct6_mfg_tool
            - ct6_stats
            - ct6_tool
        done! ✨ 🌟 ✨

  The above commands are now available on the command line.

  Command line help text can be viewed for each command if the -h argument is used.


