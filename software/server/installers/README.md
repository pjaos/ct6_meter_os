# Installing the CT6 applications.

Installers are available for windows (tested on Windows 11) and Linux (tested on Ubuntu 24.04).

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

- Python must be installed on the Linux machine before installing the ct6 debian package.
  The python applications were tested with python 3.12 installed on the Linux machine
  but may work with python versions down to 3.9.
- Once you have checked that python is installed run the following command to install
  the ct6 applications.

```
sudo dpkg -i python-ct6-apps-7.2-all.deb
```





  
