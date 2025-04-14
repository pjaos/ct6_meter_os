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

## Remove debian based installer
If you previously installed the software using the debian package it should be uninstalled before
proceeding as shown below.

```
sudo dpkg -r python-ct6-apps
```

## Python installation
The python version installed onto your Linux machine should be at least 3.12.4. Testing was
performed using Python3.12.4. If the target machines default python3 version is lower than
this then you should install python3.12.4 as shown below.

### Install python3.12.4
Install python3.12.4 as an alternative version of python so that it does not change the
default python3 version installed onto your machine as shown below.

```
cd /tmp
curl -O https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tar.xz
tar -xf - tar -xf Python-3.12.4.tar.xz
cd /tmp/Python-3.12.4/
./configure --enable-optimizations
sudo make altinstall
```

Note, the last command can take some time.

Check the python installation as shown below.

```
python3.12
Python 3.12.4 (main, Jul 19 2024, 06:02:43) [GCC 11.4.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import ctypes
>>> import ssl
```

If either of the above import statements fail, the following command sequences should fix the issue.

```
sudo apt-get install libssl-dev
sudo apt-get install libffi-dev
cd /tmp/Python-3.12.4/
sudo make clean
./configure --enable-optimizations
sudo make altinstall
```

Repeat the steps shown above to check the python installation.

## Python wheel installation.
The CT6 installer is provided as a python wheel file (.whl file extension). This can be used to install the
apps on a Linux machine. It should also be possible to use this file to install the apps onto other
operating systems, however only Linux has been tested. It should be noted that the python wheel file cannot be used to
install the apps onto Windows systems. This is due to an issue with the pyreadline python module on windows
systems. This is resolved if the CT6 Windows installer is used.

- Before installing the CT6 apps, pipx must be installed. pipx can be installed onto an ubuntu 24.04
machine using the following commands in a terminal.

```
sudo apt update
sudo apt install pipx
pipx ensurepath
```

- The python path is required for the next step. This can be found using the following command.

```
which python3.12
/usr/local/bin/python3.12
```

- In a local folder on your Linux machine, issue the command below to checkout the ct6_meter_os repo.

```
git clone git@github.com:pjaos/ct6_meter_os.git
```

- Once pipx is installed, the ct6 apps can be installed as shown below from a terminal window in the
software/server/installers folder of the repo checked out above. Note that the python path is
used in the pipx command line.

```
pipx install ct6-7.9-py3-none-any.whl --python /usr/local/bin/python3.12
  installed package ct6 7.9, installed using Python 3.12.3
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
```

  The above commands are now available to you on the command line.
  Command line help text can be viewed for each command if the -h argument is used.
  The software/server/README.md file details how to use the installed software.

