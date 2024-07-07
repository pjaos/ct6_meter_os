# CT6 Test and Calibration.
This document details how to install the software onto the RPi Pico W on the CT6 unit, test it and calibrate it.

## Installation of SW
To use the tools to test and calibrate a CT6 unit the Linux package must be installed.
This installer has to be built first. To build the installer perform the following

```
python3 -m pip install pipenv2deb
./build.sh
INFO:  Using existing create_pip_env.sh file.
INFO:  Created build/DEBIAN
INFO:  Created build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/assets to build/usr/local/bin/python-ct6-apps.pipenvpkg/assets
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/app1 to build/usr/local/bin/python-ct6-apps.pipenvpkg/app1
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/images to build/usr/local/bin/python-ct6-apps.pipenvpkg/images
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/lib to build/usr/local/bin/python-ct6-apps.pipenvpkg/lib
INFO:  Copied Pipfile to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied Pipfile.lock to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied create_pip_env.sh to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/ct6_dash.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/ct6_mfg_tool.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/ct6_db_store.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/ct6_dash_mgr.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/ct6_tool.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/main.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Copied /scratch/git_repos/ct6_meter/software/server/t.py to build/usr/local/bin/python-ct6-apps.pipenvpkg
INFO:  Creating build/DEBIAN/postinst
INFO:  Set executable attribute: build/DEBIAN/postinst
INFO:  Set executable attribute: build/DEBIAN/control
INFO:  Set executable attribute: build/DEBIAN/postinst
INFO:  Set executable attribute: build/DEBIAN/preinst
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/ct6_dash.py
INFO:  Created: build/usr/local/bin/ct6_dash
INFO:  Set executable attribute: build/usr/local/bin/ct6_dash
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/ct6_mfg_tool.py
INFO:  Created: build/usr/local/bin/ct6_mfg_tool
INFO:  Set executable attribute: build/usr/local/bin/ct6_mfg_tool
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/ct6_db_store.py
INFO:  Created: build/usr/local/bin/ct6_db_store
INFO:  Set executable attribute: build/usr/local/bin/ct6_db_store
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/ct6_dash_mgr.py
INFO:  Created: build/usr/local/bin/ct6_dash_mgr
INFO:  Set executable attribute: build/usr/local/bin/ct6_dash_mgr
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/ct6_tool.py
INFO:  Created: build/usr/local/bin/ct6_tool
INFO:  Set executable attribute: build/usr/local/bin/ct6_tool
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/main.py
INFO:  Created: build/usr/local/bin/main
INFO:  Set executable attribute: build/usr/local/bin/main
INFO:  Set executable attribute: build/usr/local/bin/python-ct6-apps.pipenvpkg/t.py
INFO:  Created: build/usr/local/bin/t
INFO:  Set executable attribute: build/usr/local/bin/t
INFO:  Executing: dpkg-deb -Zgzip -b build packages/python-ct6-apps-5.4-all.deb
dpkg-deb: building package 'python-ct6-apps' in 'packages/python-ct6-apps-5.4-all.deb'.
INFO:  Removed build path
```

To install the deb file perform the following command. Note that the version of the package may change.

```
sudo dpkg -i packages/python-ct6-apps-5.4-all.deb
(Reading database ... 588237 files and directories currently installed.)
Preparing to unpack .../python-ct6-apps-5.4-all.deb ...
Unpacking python-ct6-apps (5.4) over (5.4) ...
Setting up python-ct6-apps (5.4) ...
Removing virtualenv (/usr/local/bin/python-ct6-apps.pipenvpkg/.venv)...
Creating a virtualenv for this project...
Pipfile: /usr/local/bin/python-ct6-apps.pipenvpkg/Pipfile
Using /usr/local/bin/python3.9 (3.9.8) to create virtualenv...
⠸ Creating virtual environment...created virtual environment CPython3.9.8.final.0-64 in 182ms
  creator CPython3Posix(dest=/usr/local/bin/python-ct6-apps.pipenvpkg/.venv, clear=False, no_vcs_ignore=False, global=False)
  seeder FromAppData(download=False, pip=bundle, setuptools=bundle, wheel=bundle, via=copy, app_data_dir=/root/.local/share/virtualenv)
    added seed packages: pip==23.3.2, setuptools==68.2.2, wheel==0.42.0
  activators BashActivator,CShellActivator,FishActivator,PowerShellActivator,PythonActivator,XonshActivator

✔ Successfully created virtual environment!
Virtualenv location: /usr/local/bin/python-ct6-apps.pipenvpkg/.venv
Installing dependencies from Pipfile.lock (7b1881)...
  🐍   ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉ 41/41 — 00:00:19
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
* - ct6_mfg_tool.py                                                       *
* Perform manufacturing test and calibration of a CT6 unit.               *
* - ct6_tool.py                                                           *
* Provides functionality that is useful when developing CT6 software.     *
***************************************************************************
```

## Full test and calibration of a CT6 unit.

### Equipment required
- CT6 unit hardware (CT6 board with display connected).
- CT6 AC power supply.
- Modified micro USB cable. This cable must have the +5v power lead disconnected. This is normally the red wire in the 4 wire USB cable.
- AC power meter ([E.G ENERGENIE ENE007](https://energenie4u.co.uk/catalogue/product/ENER007)). However it should be noted that the accuracy of this device will govern the CT6 calibration accuracy.
- Linux PC running Ubuntu 20.04 or later.
- [SCT013_100A current transformer](https://www.mouser.com/datasheet/2/744/101990029_SCT_013_000_Datasheet-2487743.pdf)
- [Mains Test Block](https://uk.rs-online.com/web/p/mains-test-blocks/0458926?gb=b)
- AC load that draws at least 5 amps, preferably about 10 amps. A 2kW fan heater can be used for this.

The equipment should be connected as per the diagram shown below.

![alt text](images/cal_system.png "Test/Calibration System")

### CT6 initialisation and calibration

- The ct6_mfg_tool program will load all code onto the CT6 unit, test it and calibrate each port as shown below.
  You must run the ct6_mfg_tool in the software/server folder. Note that '<YOUR WIFI SSID>' and '<YOUR WIFI PASSWORD>' should be replaced with your WiFi SSID and password. You must run this process if you have a new RPi Pico W board as it erases the Pico W flash and loads Micro Python onto it.

Note that if your AC supply is 60 Hz (default = 50 Hz) you'll also need to add the '--ac60hz' command line option to the command below.

```
ct6_mfg_tool
INPUT: The local WiFi SSID: : <YOUR WIFI SSID>
INPUT: The local WiFi password: : <YOUR WIFI PASSWORD>
INFO:  -----------------------------------
INFO:  | Test Case |         Description |
INFO:  -----------------------------------
INFO:  |      1000 | Enter ASSY and S.N. |
INFO:  -----------------------------------
INPUT: Enter the board assembly number or 'r' to repeat last test: ASY0398V01.6
INPUT: Enter the board serial number: SN00001823
INFO:  ----------------------------------
INFO:  |         UNIT UNDER TEST |      |
INFO:  ----------------------------------
INFO:  |         Assembly Number |  398 |
INFO:  ----------------------------------
INFO:  |    CT6 hardware version |  1.6 |
INFO:  ----------------------------------
INFO:  | CT6 board serial Number | 1823 |
INFO:  ----------------------------------
INFO:  ------------------------------------------
INFO:  | Test Case |                Description |
INFO:  ------------------------------------------
INFO:  |      3000 | Erase Pico W flash memory. |
INFO:  ------------------------------------------
INFO:  Ensure the USB Pico W is connected to this PC.
INFO:  Hold the button down on the Pico W and power up the CT6 device.
INFO:  Waiting for RPi Pico W to restart.
INFO:  
INFO:  Release the button on the Pico W.
INFO:  
INFO:  Copying ../picow/tools/picow_flash_images/flash_nuke.uf2 to /media/auser/RPI-RP2
INFO:  Waiting for RPi Pico W to restart.
INFO:  Checking /media/auser/RPI-RP2
INFO:  ----------------------------------------------------------
INFO:  | Test Case |                                Description |
INFO:  ----------------------------------------------------------
INFO:  |      4000 | Load MicroPython onto Pico W flash memory. |
INFO:  ----------------------------------------------------------
INFO:  Ensure the USB Pico W is connected to this PC.
INFO:  Hold the button down on the Pico W and power up the CT6 device.
INFO:  Waiting for RPi Pico W to restart.
INFO:  Loading micropython image onto the RPi Pico W
INFO:  Copying ../picow/tools/picow_flash_images/firmware.uf2 to /media/auser/RPI-RP2
INFO:  Waiting for RPi Pico W to restart.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  --------------------------------------
INFO:  | Test Case |            Description |
INFO:  --------------------------------------
INFO:  |      5000 | Load the CT6 firmware. |
INFO:  --------------------------------------
INFO:  Checking python code in the app1 folder using pyflakes
INFO:  pyflakes found no issues with the app1 folder code.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
cannot access '/pyboard/*': No such file or directory
INFO:  Rebooting the MCU
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Rebooted the MCU
INFO:  Checking serial connections for CT6 device.
INFO:  Generated app1/project.mpy from app1/project.py
INFO:  Generated app1/cmd_handler.mpy from app1/cmd_handler.py
INFO:  Generated app1/vga2_bold_16x16.mpy from app1/vga2_bold_16x16.py
INFO:  Generated app1/__init__.mpy from app1/__init__.py
INFO:  Generated app1/constants.mpy from app1/constants.py
INFO:  Generated app1/app.mpy from app1/app.py
INFO:  Generated app1/lib/uo.mpy from app1/lib/uo.py
INFO:  Generated app1/lib/bluetooth.mpy from app1/lib/bluetooth.py
INFO:  Generated app1/lib/ydev.mpy from app1/lib/ydev.py
INFO:  Generated app1/lib/base_cmd_handler.mpy from app1/lib/base_cmd_handler.py
INFO:  Generated app1/lib/hardware.mpy from app1/lib/hardware.py
INFO:  Generated app1/lib/__init__.mpy from app1/lib/__init__.py
INFO:  Generated app1/lib/config.mpy from app1/lib/config.py
INFO:  Generated app1/lib/rest_server.mpy from app1/lib/rest_server.py
INFO:  Generated app1/lib/base_machine.mpy from app1/lib/base_machine.py
INFO:  Generated app1/lib/base_constants.mpy from app1/lib/base_constants.py
INFO:  Generated app1/lib/fs.mpy from app1/lib/fs.py
INFO:  Generated app1/lib/wifi.mpy from app1/lib/wifi.py
INFO:  Generated app1/lib/io.mpy from app1/lib/io.py
INFO:  Generated app1/lib/drivers/max6675.mpy from app1/lib/drivers/max6675.py
INFO:  Generated app1/lib/drivers/ssd1306.mpy from app1/lib/drivers/ssd1306.py
INFO:  Generated app1/lib/drivers/__init__.mpy from app1/lib/drivers/__init__.py
INFO:  Generated app1/lib/drivers/atm90e32.mpy from app1/lib/drivers/atm90e32.py
INFO:  Generated app1/lib/drivers/lcd.mpy from app1/lib/drivers/lcd.py
INFO:  Generated app1/lib/drivers/st7789.mpy from app1/lib/drivers/st7789.py
INFO:  Generated app1/lib/drivers/rotary_encoder.mpy from app1/lib/drivers/rotary_encoder.py
INFO:  Generated app1/lib/drivers/ads1115.mpy from app1/lib/drivers/ads1115.py
INFO:  Loading CT6 firmware. Please wait...
INFO:  Loaded all 28 python files.
INFO:  Deleted app1/vga2_bold_16x16.mpy
INFO:  Deleted app1/__init__.mpy
INFO:  Deleted app1/project.mpy
INFO:  Deleted app1/cmd_handler.mpy
INFO:  Deleted app1/constants.mpy
INFO:  Deleted app1/app.mpy
INFO:  Deleted app1/lib/base_cmd_handler.mpy
INFO:  Deleted app1/lib/__init__.mpy
INFO:  Deleted app1/lib/base_constants.mpy
INFO:  Deleted app1/lib/uo.mpy
INFO:  Deleted app1/lib/wifi.mpy
INFO:  Deleted app1/lib/config.mpy
INFO:  Deleted app1/lib/bluetooth.mpy
INFO:  Deleted app1/lib/ydev.mpy
INFO:  Deleted app1/lib/fs.mpy
INFO:  Deleted app1/lib/io.mpy
INFO:  Deleted app1/lib/base_machine.mpy
INFO:  Deleted app1/lib/rest_server.mpy
INFO:  Deleted app1/lib/hardware.mpy
INFO:  Deleted app1/lib/drivers/lcd.mpy
INFO:  Deleted app1/lib/drivers/__init__.mpy
INFO:  Deleted app1/lib/drivers/ads1115.mpy
INFO:  Deleted app1/lib/drivers/ssd1306.mpy
INFO:  Deleted app1/lib/drivers/max6675.mpy
INFO:  Deleted app1/lib/drivers/atm90e32.mpy
INFO:  Deleted app1/lib/drivers/rotary_encoder.mpy
INFO:  Deleted app1/lib/drivers/st7789.mpy
INFO:  Running the CT6 firmware
INFO:  Running APP1 on the CT6 unit. Waiting for WiFi connection...
INFO:  Checking serial connections for CT6 device.
INFO:  Updating the MCU WiFi configuration.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Rebooting the MCU
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Rebooted the MCU
INFO:  Starting MCU to register on the WiFi network.
INFO:  Running APP1 on the CT6 unit. Waiting for WiFi connection...
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 IP address = 192.168.0.19
INFO:  Waiting for firmware to startup on CT6 device.
INFO:  Firmware is now running on the CT6 device.
INFO:  The CT6 unit (192.168.0.19) has rebooted. Waiting for it to re register on the WiFi network.
INFO:  CT6 unit is now connected to the WiFi network.
INFO:  ---------------------------------
INFO:  | Test Case |       Description |
INFO:  ---------------------------------
INFO:  |      6000 | Temperature test. |
INFO:  ---------------------------------
INFO:  Checking the CT6 board temperature.
INFO:  CT6 board temperature = 20.7 °C
INFO:  ---------------------------
INFO:  | Test Case | Description |
INFO:  ---------------------------
INFO:  |      7000 |   LED test. |
INFO:  ---------------------------
INFO:  Is the green LED next to the WiFi switch flashing ? y/n
y
INFO:  Is the blue LED next to the reset switch flashing ? y/n
y
INFO:  ----------------------------
INFO:  | Test Case |  Description |
INFO:  ----------------------------
INFO:  |      8000 | Switch test. |
INFO:  ----------------------------
INFO:  Hold down the WiFi switch on the CT6 board.
INFO:  Checking serial connections for CT6 device.
INFO:  The WiFi switch is working. Release the WiFi switch.
INFO:  Press and release the reset switch on the CT6 board.
INFO:  The CT6 unit (192.168.0.19) has rebooted. Waiting for it to re register on the WiFi network.
INFO:  CT6 unit is now connected to the WiFi network.
INFO:  -----------------------------------------
INFO:  | Test Case |               Description |
INFO:  -----------------------------------------
INFO:  |      9000 | Power cycle circuit test. |
INFO:  -----------------------------------------
INFO:  Checking the power cycle feature on the CT6 board.
INFO:  Waiting for the CT6 unit  (192.168.0.19) to reboot.
INFO:  The CT6 unit (192.168.0.19) has rebooted. Waiting for it to re register on the WiFi network.
INFO:  CT6 unit is now connected to the WiFi network.
INFO:  -----------------------------
INFO:  | Test Case |   Description |
INFO:  -----------------------------
INFO:  |     10000 | Display test. |
INFO:  -----------------------------
INFO:  Is the display showing AC voltage ?
INPUT: Is the display showing the CT6 IP address y/n: y
INFO:  ------------------------------------------------------
INFO:  | Test Case |                            Description |
INFO:  ------------------------------------------------------
INFO:  |     11000 | Set assembly number and serial number. |
INFO:  ------------------------------------------------------
INFO:  Factory setup and calibration of CT6 unit (192.168.0.19).
INFO:  Reading configuration from 192.168.0.19
INFO:  
INFO:  Setting assembly label to ASY0398_V001.600_SN00001823.
INFO:  Successfully set the unit serial number.
INFO:  --------------------------------------------
INFO:  | Test Case |                  Description |
INFO:  --------------------------------------------
INFO:  |     12000 | Perform calibration process. |
INFO:  --------------------------------------------
INFO:  Factory setup and calibration of 192.168.0.19
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 1 and press RETURN:
INFO:  Calibrating U5 VOLTAGE gain.
INFO:  
INPUT: Enter the AC RMS voltage as measured by an external meter: 245.1
INFO:  AC Freq = 50 Hz
INFO:  Voltage gain = 50000
INFO:  Checking that CT1 detects at least 100 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 219.62 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Read 219.60 Volts (error = 25.50 Volts)
INFO:  Voltage gain = 55806
INFO:  Reading stats from 192.168.0.19
INFO:  Read 245.00 Volts (error = 0.10 Volts)
INFO:  CT1 voltage calibration complete.
INFO:  Calibrating CT1 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN:
INFO:  Current gain = 8000
INFO:  Checking that CT1 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 8.641 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.46
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 8.59 Amps (error = 2.87 Amps)
INFO:  Current gain = 10675
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 11.45 Amps (error = 0.01 Amps)
INFO:  
INFO:  CT1 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN:
INFO:  Calibrating CT1 CURRENT offset.
INFO:  Checking that CT1 load has been turned off.
INFO:  Reading stats from 192.168.0.19
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.0 amps.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 2 and press RETURN:
INFO:  Calibrating CT2 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN:
INFO:  Current gain = 8000
INFO:  Checking that CT2 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 8.667 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.43
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 8.56 Amps (error = 2.87 Amps)
INFO:  Current gain = 10679
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 11.43 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT2 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN:
INFO:  Calibrating CT2 CURRENT offset.
INFO:  Checking that CT2 load has been turned off.
INFO:  Reading stats from 192.168.0.19
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.0 amps.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 3 and press RETURN:
INFO:  Calibrating CT3 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN:
INFO:  Current gain = 8000
INFO:  Checking that CT3 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 8.63 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.41
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 8.54 Amps (error = 2.87 Amps)
INFO:  Current gain = 10687
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 11.41 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT3 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN:
INFO:  Calibrating CT3 CURRENT offset.
INFO:  Checking that CT3 load has been turned off.
INFO:  Reading stats from 192.168.0.19
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.0 amps.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 4 and press RETURN:
INFO:  Calibrating U4 VOLTAGE gain.
INFO:  
INPUT: Enter the AC RMS voltage as measured by an external meter: 243.58
INFO:  AC Freq = 50 Hz
INFO:  Voltage gain = 50000
INFO:  Checking that CT4 detects at least 100 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 219.45 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Read 219.55 Volts (error = 24.03 Volts)
INFO:  Voltage gain = 55472
INFO:  Reading stats from 192.168.0.19
INFO:  Read 243.42 Volts (error = 0.16 Volts)
INFO:  CT4 voltage calibration complete.
INFO:  Calibrating CT4 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN:
INFO:  Current gain = 8000
INFO:  Checking that CT4 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 8.716 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.44
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 8.57 Amps (error = 2.87 Amps)
INFO:  Current gain = 10684
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 11.44 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT4 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN:
INFO:  Calibrating CT4 CURRENT offset.
INFO:  Checking that CT4 load has been turned off.
INFO:  Reading stats from 192.168.0.19
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.0 amps.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 5 and press RETURN:
INFO:  Calibrating CT5 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN:
INFO:  Current gain = 8000
INFO:  Checking that CT5 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 8.652 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.44
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 8.57 Amps (error = 2.87 Amps)
INFO:  Current gain = 10684
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 11.43 Amps (error = 0.01 Amps)
INFO:  
INFO:  CT5 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN:
INFO:  Calibrating CT5 CURRENT offset.
INFO:  Checking that CT5 load has been turned off.
INFO:  Reading stats from 192.168.0.19
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.0 amps.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 6 and press RETURN:
INFO:  Calibrating CT6 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN:
INFO:  Current gain = 8000
INFO:  Checking that CT6 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 8.661 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.46
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 8.58 Amps (error = 2.88 Amps)
INFO:  Current gain = 10682
INFO:  Reading configuration from 192.168.0.19
INFO:  Reading stats from 192.168.0.19
INFO:  Read 11.46 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT6 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN:
INFO:  Calibrating CT6 CURRENT offset.
INFO:  Checking that CT6 load has been turned off.
INFO:  Reading stats from 192.168.0.19
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.19
INFO:  Detected a residual current of 0.0 amps.
INFO:  Saving the factory configuration file to the CT6 unit.
INFO:  Get factory.cfg from 192.168.0.19.
INFO:  Save to factory.cfg from 192.168.0.19.
INFO:  Saved to /home/auser/test_logs/ASY0398_V01.6000_SN00001823_20240111063130_factory.cfg
INFO:  CT6 unit calibration successful.
INFO:  ----------------------------------------------
INFO:  | Test Case |                    Description |
INFO:  ----------------------------------------------
INFO:  |     13000 | Store CT6 configuration files. |
INFO:  ----------------------------------------------
INFO:  Get this.machine.cfg from 192.168.0.19.
INFO:  Save to this.machine.cfg from 192.168.0.19.
INFO:  Saved to /home/auser/test_logs/ASY0398_V01.6000_SN00001823_20240111063130_this.machine.cfg
INFO:  ---------------------------------------------------
INFO:  | Test Case |                         Description |
INFO:  ---------------------------------------------------
INFO:  |     14000 | Load factory default configuration. |
INFO:  ---------------------------------------------------
INFO:  Set factory CT6 WiFi.
INFO:  Took 422.2 seconds to test.
```

The CT6 unit is now ready for use. See the README.md file for more information on this.


### CT6 Upgrade and recalibration

To upgrade and recalibrate a CT6 unit the following process can be used using the same test system as detailed above. This process only requires a WiFi connection to the CT6 unit, no serial port connection is required. 

First cd to the ct6_meter_os/software/server git repo folder and then run the following command. Note that if your AC supply is 60 Hz (default = 50 Hz) you'll also need to use the '--ac60hz' command line option.

```
ct6_mfg_tool -a 192.168.0.76 --upcal

INFO:  Get this.machine.cfg from 192.168.0.76.
INFO:  ----------------------------------
INFO:  |         UNIT UNDER TEST |      |
INFO:  ----------------------------------
INFO:  |         Assembly Number |  398 |
INFO:  ----------------------------------
INFO:  |    CT6 hardware version |  3.2 |
INFO:  ----------------------------------
INFO:  | CT6 board serial Number | 1831 |
INFO:  ----------------------------------
INPUT: Enter the board assembly number or 'r' to repeat last test: ASY0398V3.2
INPUT: Enter the board serial number: SN00001831
INFO:  Test SW git hash: 0a6c856
INFO:  ----------------------------------
INFO:  |         UNIT UNDER TEST |      |
INFO:  ----------------------------------
INFO:  |         Assembly Number |  398 |
INFO:  ----------------------------------
INFO:  |    CT6 hardware version |  3.2 |
INFO:  ----------------------------------
INFO:  | CT6 board serial Number | 1831 |
INFO:  ----------------------------------
INFO:  
INFO:  Receiving factory.cfg from 192.168.0.76
INFO:  Created local /tmp/factory.cfg
INFO:  Sending /tmp/factory.cfg to /
INFO:  /tmp/factory.cfg file XFER success.
INFO:  Peforming an OTA upgrade of 192.168.0.76
INFO:  Inactive App Folder: /app1
INFO:  Converting project.py to project.mpy (bytecode).
INFO:  Sending app1/project.mpy to /app1/
INFO:  app1/project.mpy file XFER success.
INFO:  Converting cmd_handler.py to cmd_handler.mpy (bytecode).
INFO:  Sending app1/cmd_handler.mpy to /app1/
INFO:  app1/cmd_handler.mpy file XFER success.
INFO:  Converting vga2_bold_16x16.py to vga2_bold_16x16.mpy (bytecode).
INFO:  Sending app1/vga2_bold_16x16.mpy to /app1/
INFO:  app1/vga2_bold_16x16.mpy file XFER success.
INFO:  Converting uo.py to uo.mpy (bytecode).
INFO:  Sending app1/lib/uo.mpy to /app1/lib
INFO:  app1/lib/uo.mpy file XFER success.
INFO:  Converting bluetooth.py to bluetooth.mpy (bytecode).
INFO:  Sending app1/lib/bluetooth.mpy to /app1/lib
INFO:  app1/lib/bluetooth.mpy file XFER success.
INFO:  Converting __init__.py to __init__.mpy (bytecode).
INFO:  Sending app1/lib/drivers/__init__.mpy to /app1/lib/drivers
INFO:  app1/lib/drivers/__init__.mpy file XFER success.
INFO:  Converting atm90e32.py to atm90e32.mpy (bytecode).
INFO:  Sending app1/lib/drivers/atm90e32.mpy to /app1/lib/drivers
INFO:  app1/lib/drivers/atm90e32.mpy file XFER success.
INFO:  Converting lcd.py to lcd.mpy (bytecode).
INFO:  Sending app1/lib/drivers/lcd.mpy to /app1/lib/drivers
INFO:  app1/lib/drivers/lcd.mpy file XFER success.
INFO:  Converting st7789.py to st7789.mpy (bytecode).
INFO:  Sending app1/lib/drivers/st7789.mpy to /app1/lib/drivers
INFO:  app1/lib/drivers/st7789.mpy file XFER success.
INFO:  Converting ydev.py to ydev.mpy (bytecode).
INFO:  Sending app1/lib/ydev.mpy to /app1/lib
INFO:  app1/lib/ydev.mpy file XFER success.
INFO:  Converting base_cmd_handler.py to base_cmd_handler.mpy (bytecode).
INFO:  Sending app1/lib/base_cmd_handler.mpy to /app1/lib
INFO:  app1/lib/base_cmd_handler.mpy file XFER success.
INFO:  Converting hardware.py to hardware.mpy (bytecode).
INFO:  Sending app1/lib/hardware.mpy to /app1/lib
INFO:  app1/lib/hardware.mpy file XFER success.
INFO:  Converting __init__.py to __init__.mpy (bytecode).
INFO:  Sending app1/lib/__init__.mpy to /app1/lib
INFO:  app1/lib/__init__.mpy file XFER success.
INFO:  Converting config.py to config.mpy (bytecode).
INFO:  Sending app1/lib/config.mpy to /app1/lib
INFO:  app1/lib/config.mpy file XFER success.
INFO:  Converting rest_server.py to rest_server.mpy (bytecode).
INFO:  Sending app1/lib/rest_server.mpy to /app1/lib
INFO:  app1/lib/rest_server.mpy file XFER success.
INFO:  Converting base_machine.py to base_machine.mpy (bytecode).
INFO:  Sending app1/lib/base_machine.mpy to /app1/lib
INFO:  app1/lib/base_machine.mpy file XFER success.
INFO:  Converting base_constants.py to base_constants.mpy (bytecode).
INFO:  Sending app1/lib/base_constants.mpy to /app1/lib
INFO:  app1/lib/base_constants.mpy file XFER success.
INFO:  Converting fs.py to fs.mpy (bytecode).
INFO:  Sending app1/lib/fs.mpy to /app1/lib
INFO:  app1/lib/fs.mpy file XFER success.
INFO:  Converting wifi.py to wifi.mpy (bytecode).
INFO:  Sending app1/lib/wifi.mpy to /app1/lib
INFO:  app1/lib/wifi.mpy file XFER success.
INFO:  Converting io.py to io.mpy (bytecode).
INFO:  Sending app1/lib/io.mpy to /app1/lib
INFO:  app1/lib/io.mpy file XFER success.
INFO:  Converting __init__.py to __init__.mpy (bytecode).
INFO:  Sending app1/__init__.mpy to /app1/
INFO:  app1/__init__.mpy file XFER success.
INFO:  Converting constants.py to constants.mpy (bytecode).
INFO:  Sending app1/constants.mpy to /app1/
INFO:  app1/constants.mpy file XFER success.
INFO:  Converting app.py to app.mpy (bytecode).
INFO:  Sending app1/app.mpy to /app1/
INFO:  app1/app.mpy file XFER success.
INFO:  took 16.8 seconds to upgrade device.
INFO:  Cleaning up python bytecode files.
INFO:  Deleted local app1/vga2_bold_16x16.mpy
INFO:  Deleted local app1/__init__.mpy
INFO:  Deleted local app1/project.mpy
INFO:  Deleted local app1/lib/base_cmd_handler.mpy
INFO:  Deleted local app1/lib/__init__.mpy
INFO:  Deleted local app1/lib/drivers/lcd.mpy
INFO:  Deleted local app1/lib/drivers/__init__.mpy
INFO:  Deleted local app1/lib/drivers/atm90e32.mpy
INFO:  Deleted local app1/lib/drivers/st7789.mpy
INFO:  Deleted local app1/lib/base_constants.mpy
INFO:  Deleted local app1/lib/uo.mpy
INFO:  Deleted local app1/lib/wifi.mpy
INFO:  Deleted local app1/lib/config.mpy
INFO:  Deleted local app1/lib/bluetooth.mpy
INFO:  Deleted local app1/lib/ydev.mpy
INFO:  Deleted local app1/lib/fs.mpy
INFO:  Deleted local app1/lib/io.mpy
INFO:  Deleted local app1/lib/base_machine.mpy
INFO:  Deleted local app1/lib/rest_server.mpy
INFO:  Deleted local app1/lib/hardware.mpy
INFO:  Deleted local app1/cmd_handler.mpy
INFO:  Deleted local app1/constants.mpy
INFO:  Deleted local app1/app.mpy
INFO:  CT6 unit is now power cycling.
INFO:  192.168.0.76 ping success.
INFO:  Factory setup and calibration of 192.168.0.76
INFO:  192.168.0.76 ping success.
INFO:  Calibrating U5 VOLTAGE gain.
INFO:  
INPUT: Enter the AC RMS voltage as measured by an external meter: 242.4
INFO:  AC Freq = 50 Hz
INFO:  Voltage gain = 50000
INFO:  Checking that CT1 detects at least 100 volts.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 213.28 volts.
INFO:  Reading stats from 192.168.0.76
INFO:  Read 213.72 Volts (error = 28.68 Volts)
INFO:  Voltage gain = 56709
INFO:  Reading stats from 192.168.0.76
INFO:  Read 242.40 Volts (error = 0.00 Volts)
INFO:  CT1 voltage calibration complete.
INFO:  Calibrating U4 VOLTAGE gain.
INFO:  
INFO:  AC Freq = 50 Hz
INFO:  Voltage gain = 50000
INFO:  Checking that CT4 detects at least 100 volts.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 213.97 volts.
INFO:  Reading stats from 192.168.0.76
INFO:  Read 213.91 Volts (error = 28.49 Volts)
INFO:  Voltage gain = 56659
INFO:  Reading stats from 192.168.0.76
INFO:  Read 242.45 Volts (error = 0.05 Volts)
INFO:  CT4 voltage calibration complete.
INFO:  192.168.0.76 ping success.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 1 and press RETURN: 
INFO:  Calibrating CT1 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN: 
INFO:  Current gain = 8000
INFO:  Checking that CT1 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 8.567 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.36
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 8.49 Amps (error = 2.87 Amps)
INFO:  Current gain = 10703
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 11.35 Amps (error = 0.01 Amps)
INFO:  
INFO:  CT1 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN: 
INFO:  Calibrating CT1 CURRENT offset.
INFO:  Checking that CT1 load has been turned off.
INFO:  Reading stats from 192.168.0.76
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.0 amps.
INFO:  192.168.0.76 ping success.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 2 and press RETURN: 
INFO:  Calibrating CT2 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN: 
INFO:  Current gain = 8000
INFO:  Checking that CT2 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 8.566 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.35
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 8.49 Amps (error = 2.86 Amps)
INFO:  Current gain = 10688
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 11.35 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT2 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN: 
INFO:  Calibrating CT2 CURRENT offset.
INFO:  Checking that CT2 load has been turned off.
INFO:  Reading stats from 192.168.0.76
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.0 amps.
INFO:  192.168.0.76 ping success.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 3 and press RETURN: 
INFO:  Calibrating CT3 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN: 
INFO:  Current gain = 8000
INFO:  Checking that CT3 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 8.557 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.37
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 8.51 Amps (error = 2.86 Amps)
INFO:  Current gain = 10693
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 11.36 Amps (error = 0.01 Amps)
INFO:  
INFO:  CT3 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN: 
INFO:  Calibrating CT3 CURRENT offset.
INFO:  Checking that CT3 load has been turned off.
INFO:  Reading stats from 192.168.0.76
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.0 amps.
INFO:  192.168.0.76 ping success.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 4 and press RETURN: 
INFO:  Calibrating CT4 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN: 
INFO:  Current gain = 8000
INFO:  Checking that CT4 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 8.487 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.39
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 8.41 Amps (error = 2.98 Amps)
INFO:  Current gain = 10834
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 11.39 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT4 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN: 
INFO:  Calibrating CT4 CURRENT offset.
INFO:  Checking that CT4 load has been turned off.
INFO:  Reading stats from 192.168.0.76
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.0 amps.
INFO:  192.168.0.76 ping success.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 5 and press RETURN: 
INFO:  Calibrating CT5 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN: 
INFO:  Current gain = 8000
INFO:  Checking that CT5 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 0.0 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 8.564 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.33
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 8.42 Amps (error = 2.91 Amps)
INFO:  Current gain = 10759
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 11.33 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT5 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN: 
INFO:  Calibrating CT5 CURRENT offset.
INFO:  Checking that CT5 load has been turned off.
INFO:  Reading stats from 192.168.0.76
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.0 amps.
INFO:  192.168.0.76 ping success.
INFO:  
INFO:  Ensure no AC load is connected.
INPUT: Connect an SCT013_100A current transformer (CT) to port 6 and press RETURN: 
INFO:  Calibrating CT6 CURRENT gain.
INFO:  
INPUT: Ensure an AC load drawing at least 5 amps is connected and press RETURN: 
INFO:  Current gain = 8000
INFO:  Checking that CT6 detects at least 5 amps.
INFO:  Reading stats from 192.168.0.76
INFO:  Detected 8.518 amps.
INPUT: Enter the AC RMS current in amps as measured with an external meter: 11.38
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 8.48 Amps (error = 2.90 Amps)
INFO:  Current gain = 10729
INFO:  Reading configuration from 192.168.0.76
INFO:  Reading stats from 192.168.0.76
INFO:  Read 11.38 Amps (error = 0.00 Amps)
INFO:  
INFO:  CT6 current calibration complete.
INPUT: DISCONNECT the AC load and press RETURN: 
INFO:  Calibrating CT6 CURRENT offset.
INFO:  Checking that CT6 load has been turned off.
INFO:  Reading stats from 192.168.0.76
INFO:  Current offset register = 0
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.001 amps.
INFO:  Current offset register = 64536
INFO:  Reading stats from 192.168.0.76
INFO:  Detected a residual current of 0.0 amps.
INFO:  Saving the factory configuration file to the CT6 unit.
INFO:  Setting assembly label to ASY0398_V003.200_SN00001831.
INFO:  Get factory.cfg from 192.168.0.76.
INFO:  Save to factory.cfg from 192.168.0.76.
INFO:  Saved to /home/username/test_logs/ASY0398_V03.2000_SN00001831_20240218202334_factory.cfg
INFO:  CT6 unit calibration successful.
INFO:  Completed calibration.
INFO:  The CT6 unit is now power cycling.
```



## CT6 unit bring up and calibration load.

### Equipment required
- CT6 unit hardware (CT6 board with display connected).
- CT6 AC power supply.
- Modified micro USB cable. This cable must have the +5v power lead disconnected. This is normally the red wire in the 4 wire USB cable.

The equipment should be connected as per the diagram shown below.

![alt text](images/erase_and_bringup.png "Test System")

### CT6 initialisation and loading calibration data

- It is important to understand that the calibration file created in the previous section (/home/auser/test_logs/ASY0398_V01.6000_SN00001823_20240111063130_factory.cfg) is only valid if the same AC PSU is used. It should be possible to use the same type (make/model) of PSU. However at the time of writing I have calibrated each unit with the PSU it will be used with to ensure that the measurement accuracy is as good as possible. The same PSU must be used because the AC line frequency is measured on the CT6 hardware using the voltage across R22 which is derived from the AC supply voltage through the AC -AC transformer and the potential divider of R21 and R22.

This section details how to fully wipe and reload the code on the Pico W and then reload the factory configuration file.

- The steps below show will load all code onto the CT6 unit and test it. You must run the ct6_mfg_tool in the software/server folder. Note that '<YOUR WIFI SSID>' and '<YOUR WIFI PASSWORD>' should be replaced with your WiFi SSID and password.

```
ct6_mfg_tool --no_cal
INPUT: The local WiFi SSID: : <YOUR WIFI SSID>
INPUT: The local WiFi password: : <YOUR WIFI PASSWORD>
INFO:  Created house_wifi.cfg
INFO:  -----------------------------------
INFO:  | Test Case |         Description |
INFO:  -----------------------------------
INFO:  |      1000 | Enter ASSY and S.N. |
INFO:  -----------------------------------
INPUT: Enter the board assembly number or 'r' to repeat last test: ^TASY0398V01.6
INPUT: Enter the board serial number: ^TSN00001823
INFO:  ----------------------------------
INFO:  |         UNIT UNDER TEST |      |
INFO:  ----------------------------------
INFO:  |         Assembly Number |  398 |
INFO:  ----------------------------------
INFO:  |    CT6 hardware version |  1.6 |
INFO:  ----------------------------------
INFO:  | CT6 board serial Number | 1823 |
INFO:  ----------------------------------
INFO:  ------------------------------------------
INFO:  | Test Case |                Description |
INFO:  ------------------------------------------
INFO:  |      3000 | Erase Pico W flash memory. |
INFO:  ------------------------------------------
INFO:  Ensure the USB Pico W is connected to this PC.
INFO:  Hold the button down on the Pico W and power up the CT6 device.
INFO:  Waiting for RPi Pico W to restart.
INFO:  
INFO:  Release the button on the Pico W.
INFO:  
INFO:  Copying ../picow/tools/picow_flash_images/flash_nuke.uf2 to /media/pja/RPI-RP2
INFO:  Waiting for RPi Pico W to restart.
INFO:  Checking /media/pja/RPI-RP2
INFO:  ----------------------------------------------------------
INFO:  | Test Case |                                Description |
INFO:  ----------------------------------------------------------
INFO:  |      4000 | Load MicroPython onto Pico W flash memory. |
INFO:  ----------------------------------------------------------
INFO:  Ensure the USB Pico W is connected to this PC.
INFO:  Hold the button down on the Pico W and power up the CT6 device.
INFO:  Waiting for RPi Pico W to restart.
INFO:  Loading micropython image onto the RPi Pico W
INFO:  Copying ../picow/tools/picow_flash_images/firmware.uf2 to /media/pja/RPI-RP2
INFO:  Waiting for RPi Pico W to restart.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  --------------------------------------
INFO:  | Test Case |            Description |
INFO:  --------------------------------------
INFO:  |      5000 | Load the CT6 firmware. |
INFO:  --------------------------------------
INFO:  Checking python code in the app1 folder using pyflakes
INFO:  pyflakes found no issues with the app1 folder code.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
cannot access '/pyboard/*': No such file or directory
INFO:  Rebooting the MCU
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Rebooted the MCU
INFO:  Checking serial connections for CT6 device.
INFO:  Generated app1/project.mpy from app1/project.py
INFO:  Generated app1/cmd_handler.mpy from app1/cmd_handler.py
INFO:  Generated app1/vga2_bold_16x16.mpy from app1/vga2_bold_16x16.py
INFO:  Generated app1/__init__.mpy from app1/__init__.py
INFO:  Generated app1/constants.mpy from app1/constants.py
INFO:  Generated app1/app.mpy from app1/app.py
INFO:  Generated app1/lib/uo.mpy from app1/lib/uo.py
INFO:  Generated app1/lib/bluetooth.mpy from app1/lib/bluetooth.py
INFO:  Generated app1/lib/ydev.mpy from app1/lib/ydev.py
INFO:  Generated app1/lib/base_cmd_handler.mpy from app1/lib/base_cmd_handler.py
INFO:  Generated app1/lib/hardware.mpy from app1/lib/hardware.py
INFO:  Generated app1/lib/__init__.mpy from app1/lib/__init__.py
INFO:  Generated app1/lib/config.mpy from app1/lib/config.py
INFO:  Generated app1/lib/rest_server.mpy from app1/lib/rest_server.py
INFO:  Generated app1/lib/base_machine.mpy from app1/lib/base_machine.py
INFO:  Generated app1/lib/base_constants.mpy from app1/lib/base_constants.py
INFO:  Generated app1/lib/fs.mpy from app1/lib/fs.py
INFO:  Generated app1/lib/wifi.mpy from app1/lib/wifi.py
INFO:  Generated app1/lib/io.mpy from app1/lib/io.py
INFO:  Generated app1/lib/drivers/max6675.mpy from app1/lib/drivers/max6675.py
INFO:  Generated app1/lib/drivers/ssd1306.mpy from app1/lib/drivers/ssd1306.py
INFO:  Generated app1/lib/drivers/__init__.mpy from app1/lib/drivers/__init__.py
INFO:  Generated app1/lib/drivers/atm90e32.mpy from app1/lib/drivers/atm90e32.py
INFO:  Generated app1/lib/drivers/lcd.mpy from app1/lib/drivers/lcd.py
INFO:  Generated app1/lib/drivers/st7789.mpy from app1/lib/drivers/st7789.py
INFO:  Generated app1/lib/drivers/rotary_encoder.mpy from app1/lib/drivers/rotary_encoder.py
INFO:  Generated app1/lib/drivers/ads1115.mpy from app1/lib/drivers/ads1115.py
INFO:  Loading CT6 firmware. Please wait...
INFO:  Loaded all 28 python files.
INFO:  Deleted app1/vga2_bold_16x16.mpy
INFO:  Deleted app1/__init__.mpy
INFO:  Deleted app1/project.mpy
INFO:  Deleted app1/cmd_handler.mpy
INFO:  Deleted app1/constants.mpy
INFO:  Deleted app1/app.mpy
INFO:  Deleted app1/lib/base_cmd_handler.mpy
INFO:  Deleted app1/lib/__init__.mpy
INFO:  Deleted app1/lib/base_constants.mpy
INFO:  Deleted app1/lib/uo.mpy
INFO:  Deleted app1/lib/wifi.mpy
INFO:  Deleted app1/lib/config.mpy
INFO:  Deleted app1/lib/bluetooth.mpy
INFO:  Deleted app1/lib/ydev.mpy
INFO:  Deleted app1/lib/fs.mpy
INFO:  Deleted app1/lib/io.mpy
INFO:  Deleted app1/lib/base_machine.mpy
INFO:  Deleted app1/lib/rest_server.mpy
INFO:  Deleted app1/lib/hardware.mpy
INFO:  Deleted app1/lib/drivers/lcd.mpy
INFO:  Deleted app1/lib/drivers/__init__.mpy
INFO:  Deleted app1/lib/drivers/ads1115.mpy
INFO:  Deleted app1/lib/drivers/ssd1306.mpy
INFO:  Deleted app1/lib/drivers/max6675.mpy
INFO:  Deleted app1/lib/drivers/atm90e32.mpy
INFO:  Deleted app1/lib/drivers/rotary_encoder.mpy
INFO:  Deleted app1/lib/drivers/st7789.mpy
INFO:  Running the CT6 firmware
INFO:  Running APP1 on the CT6 unit. Waiting for WiFi connection...
INFO:  Checking serial connections for CT6 device.
INFO:  Updating the MCU WiFi configuration.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Rebooting the MCU
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Rebooted the MCU
INFO:  Starting MCU to register on the WiFi network.
INFO:  Running APP1 on the CT6 unit. Waiting for WiFi connection...
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 IP address = 192.168.0.19
INFO:  Waiting for firmware to startup on CT6 device.
INFO:  Firmware is now running on the CT6 device.
INFO:  The CT6 unit (192.168.0.19) has rebooted. Waiting for it to re register on the WiFi network.
INFO:  CT6 unit is now connected to the WiFi network.
INFO:  ---------------------------------
INFO:  | Test Case |       Description |
INFO:  ---------------------------------
INFO:  |      6000 | Temperature test. |
INFO:  ---------------------------------
INFO:  Checking the CT6 board temperature.
INFO:  CT6 board temperature = 20.2 °C
INFO:  ---------------------------
INFO:  | Test Case | Description |
INFO:  ---------------------------
INFO:  |      7000 |   LED test. |
INFO:  ---------------------------
INFO:  Is the green LED next to the WiFi switch flashing ? y/n
y
INFO:  Is the blue LED next to the reset switch flashing ? y/n
y
INFO:  ----------------------------
INFO:  | Test Case |  Description |
INFO:  ----------------------------
INFO:  |      8000 | Switch test. |
INFO:  ----------------------------
INFO:  Hold down the WiFi switch on the CT6 board.
INFO:  Checking serial connections for CT6 device.
INFO:  The WiFi switch is working. Release the WiFi switch.
INFO:  Press and release the reset switch on the CT6 board.
INFO:  The CT6 unit (192.168.0.19) has rebooted. Waiting for it to re register on the WiFi network.
INFO:  CT6 unit is now connected to the WiFi network.
INFO:  -----------------------------------------
INFO:  | Test Case |               Description |
INFO:  -----------------------------------------
INFO:  |      9000 | Power cycle circuit test. |
INFO:  -----------------------------------------
INFO:  Checking the power cycle feature on the CT6 board.
INFO:  Waiting for the CT6 unit  (192.168.0.19) to reboot.
INFO:  The CT6 unit (192.168.0.19) has rebooted. Waiting for it to re register on the WiFi network.
INFO:  CT6 unit is now connected to the WiFi network.
INFO:  -----------------------------
INFO:  | Test Case |   Description |
INFO:  -----------------------------
INFO:  |     10000 | Display test. |
INFO:  -----------------------------
INFO:  Is the display showing AC voltage ?
INPUT: Is the display showing the CT6 IP address y/n: y
INFO:  ------------------------------------------------------
INFO:  | Test Case |                            Description |
INFO:  ------------------------------------------------------
INFO:  |     11000 | Set assembly number and serial number. |
INFO:  ------------------------------------------------------
INFO:  Factory setup and calibration of CT6 unit (192.168.0.19).
INFO:  Reading configuration from 192.168.0.19
INFO:  
INFO:  Setting assembly label to ASY0398_V001.600_SN00001823.
INFO:  Successfully set the unit serial number.
INFO:  ----------------------------------------------
INFO:  | Test Case |                    Description |
INFO:  ----------------------------------------------
INFO:  |     13000 | Store CT6 configuration files. |
INFO:  ----------------------------------------------
INFO:  Get this.machine.cfg from 192.168.0.19.
INFO:  Save to this.machine.cfg from 192.168.0.19.
INFO:  Saved to /home/pja/test_logs/ASY0398_V01.6000_SN00001823_20240116140956_this.machine.cfg
WARN:  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
WARN:  !!! The CT6 unit is NOT CALIBRATED.             !!!
WARN:  !!! To resolve this issue                       !!!
WARN:  !!! 1: Run this tool with '--setup_wifi' to     !!!
WARN:  !!!    connect the WiFi to your network.        !!!
WARN:  !!! 2: Run this tool with either '--cal_only'   !!!
WARN:  !!!    or '--restore'                           !!!
WARN:  !!!    --cal_only takes you through the CT6     !!!
WARN:  !!!      calibration process.                   !!!
WARN:  !!!    --restore allows you to load an old      !!!
WARN:  !!!      calibration (factory config) file      !!!
WARN:  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
INFO:  ---------------------------------------------------
INFO:  | Test Case |                         Description |
INFO:  ---------------------------------------------------
INFO:  |     14000 | Load factory default configuration. |
INFO:  ---------------------------------------------------
INFO:  Set factory CT6 WiFi.
INFO:  Took 137.4 seconds to test.
```

- Now reload your WiFi configuration to the CT6 unit run the following command.

```
ct6_mfg_tool --setup_wifi
INFO:  Setting up CT6 WiFi interface.
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  WiFi SSID: <YOUR WIFI SSID>
INFO:  The CT6 WiFi interface is now configured.
```

- The CT6 unit is now up and running but has no calibration data loaded. This step allows you to load the calibration data.
  In this example the calibration file is held in the /home/auser folder and is named ASY0398_V02.0000_SN00001900_20240111063130_factory.cfg
  and the CT6 unit IP address (as show on it's display) is 192.168.0.10.

```
ct6_mfg_tool --restore /home/auser/ASY0398_V02.0000_SN00001900_20240111063130_factory.cfg -a 192.168.0.10
INFO:  Get this.machine.cfg from 192.168.0.10.
INFO:  ----------------------------------
INFO:  |         UNIT UNDER TEST |      |
INFO:  ----------------------------------
INFO:  |         Assembly Number |  398 |
INFO:  ----------------------------------
INFO:  |    CT6 hardware version |  2.0 |
INFO:  ----------------------------------
INFO:  | CT6 board serial Number | 1900 |
INFO:  ----------------------------------
INFO:  Checking serial connections for CT6 device.
INFO:  CT6 Unit:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
INFO:  Loaded the factory.cfg data to the CT6 board.
```

The CT6 unit is now ready for use. See the README.md file for more information on this.

## Calibrating the AC voltage

### Equipment required
- CT6 unit hardware (CT6 board with display connected).
- CT6 AC power supply.
- Modified micro USB cable. This cable must have the +5v power lead disconnected. This is normally the red wire in the 4 wire USB cable.
- A digital multimeter (DMM) capable of reading the AC mains voltage.

### Performing the AC mains voltage calibration

If you have a AC-AC power supply that is not the one detailed in the hardware/README.md file then this section can be used to update the voltage calibration after the calibration file has been loaded as detailed in the previous section.

The test system can be setup as per the previous section with the addition of meter to measure the mains AC voltage.

Note !!!
As mains voltage is dangerous ensure that the wiring is safe to allow the AC voltage to be measured.

The equipment should be connected as per the diagram shown below.

![alt text](images/calibrate_ac_voltage.png "Test/Voltage Calibration System")

Run the following command to calibrate the AC voltage. Note that if your AC supply is 60 Hz (default = 50 Hz) you'll also need to add the '--ac60hz' command line option to the command below.

```
ct6_mfg_tool --voltage_cal_only -a 192.168.0.19
INFO:  Get this.machine.cfg from 192.168.0.19.
INFO:  ----------------------------------
INFO:  |         UNIT UNDER TEST |      |
INFO:  ----------------------------------
INFO:  |         Assembly Number |  398 |
INFO:  ----------------------------------
INFO:  |    CT6 hardware version |  1.6 |
INFO:  ----------------------------------
INFO:  | CT6 board serial Number | 1823 |
INFO:  ----------------------------------
INFO:  192.168.0.19: CT6 voltage calibration.
INFO:  Calibrating U5 VOLTAGE gain.
INFO:  
INPUT: Enter the AC RMS voltage as measured by an external meter: 248.03
INFO:  AC Freq = 50 Hz
INFO:  Voltage gain = 50000
INFO:  Checking that CT1 detects at least 100 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 221.74 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Read 221.64 Volts (error = 26.39 Volts)
INFO:  Voltage gain = 55953
INFO:  Reading stats from 192.168.0.19
INFO:  Read 248.12 Volts (error = 0.09 Volts)
INFO:  CT1 voltage calibration complete.
INFO:  Calibrating U4 VOLTAGE gain.
INFO:  
INFO:  Voltage gain = 50000
INFO:  Checking that CT4 detects at least 100 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Detected 222.13 volts.
INFO:  Reading stats from 192.168.0.19
INFO:  Read 221.96 Volts (error = 26.07 Volts)
INFO:  Voltage gain = 55872
INFO:  Reading stats from 192.168.0.19
INFO:  Read 247.95 Volts (error = 0.08 Volts)
INFO:  CT4 voltage calibration complete.
INFO:  Saving the factory configuration file to the CT6 unit.
```

The CT6 unit is now ready for use. See the README.md file for more information on this.
