# Micropython
The CT6 device runs a micropython app. The app1 folder contains
the all the CT6 device code including the libraries and hardware device drivers.

## Design

I decided to use the Raspberry Pi Pico W microcontroller. I also decided to use micropython as the operating system. On previous projects that used microcontrollers I have used [Mongose OS](https://mongoose-os.com/) which runs on top of [FreeRTOS](https://www.freertos.org/index.html) with the firmware written in C. I decided to use micropython as the speed/capability trade offs are changing with the continuing development of micropython and I wanted to see it's benefits/limitations on a real world project. Having completed the project I can say that micropython is more than capable for this type of project. I did compile the display SPI driver into the micropython firmware to speed up the display interface but other than that I was pleasantly surprised and plan to use it for other suitable projects in the future as the effort required to reach the development complete stage was considerably less using micropython than my previous approach.

The CT6 hardware was designed against the requirements detailed in the top level readme. This involved schematic design, PCB layout, [PCB manufacture](https://jlcpcb.com/). The PCB was fabricated, assembled, tested and a 3D printed case was produced. This took several iterations before I was happy with the design. The [hardware](hardware) folder contains details of the schematic and also the design for the 3D printed case.

## Tools
The tools folder contains several development tools. Some of the tools
also support ESP32 microcontrollers which would ease the process of changing the microcontroller if it should be needed in future.

### picow_erase_flash.sh
Allows the user to erase the contents of the Pico W flash. To do this the button on the Pico W module should be held
down while powering it up with the serial port connected to a Linux PC. The PC should then mount the pico W
flash (typically under the /media folder). Note this folder name.

To erase the flash. The 'username' shown below will typically be your Linux username.

```
./picow_erase_flash.sh /media/username/RPI-RP2/
```

Once complete the folder will be unmounted from the Linux machine.

### picow_micropython_flash.sh
This script can be used to program load micropython onto the Pico W. To do this the button on the Pico W module should be held down while powering it up with the serial port connected to a Linux PC as in the previous step. The PC should then mount the flash as previously.

To load micropython onto the Pico W flash the following command can be used with the username changed to your username.

```
./picow_micropython_flash.sh /media/username/RPI-RP2/
```

Once complete the folder will be unmounted.

To check that micropython is loaded onto the Pico W connect to the serial port. In this example I use the microcom program but any terminal emulation program will do the trick. To return the micropython version press CTRL B.

```
microcom -p /dev/ttyACM0 -s 115200
connected to /dev/ttyACM0
Escape character: Ctrl-\
Type the escape character to get to the prompt.

>>>
MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
Type "help()" for more information.
>>>
```

To exit microcom press 'CTRL \\' twice.


### deploy_and_run.py
The next stage is to load the micropython app onto the Pico W microcontroller. This may be done using this program. It will load the application (app1) onto the Pico W hardware using rshell over
a serial port connected to the Pico W hardware on the CT6 board. The *.py files are not loaded onto the microcontroller. They are converted to *.mpy files first and these are loaded onto the microcontroller. This saves a significant amount of flash space on the Pico W microcontroller.

This tool will also load code onto an ESP32 microcontroller that has
had micropython loaded onto it. However currently the CT6 hardware only
supports a Pico W microcontroller.

E.G

```
./deploy_and_run.py --picow
INFO:  Checking app1 using pyflakes3
INFO:  Checking for serial ports
INFO:  Detected /dev/ttyACM0
INFO:  Opened serial port: /dev/ttyACM0
INFO:  MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040

INFO:  Detected Python prompt.
INFO:  MicroPython prompt returned after CR
INFO:  Checking that the rshell python module is installed.
INFO:  Checking that the mpy_cross python module is installed.
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
INFO:  rshell --rts 1 --dtr 1 --timing -p /dev/ttyACM0 --buffer-size 512 -f get_cfg.cmd
Using buffer-size of 512
Connecting to /dev/ttyACM0 (buffer-size 512)...
Trying to connect to REPL  connected
Retrieving sysname ... rp2
Testing if ubinascii.unhexlify exists ... Y
Retrieving root directories ...
Setting time ... Aug 24, 2023 14:07:55
Evaluating board_name ... pyboard
Retrieving time epoch ... Jan 01, 1970
File '/pyboard/this.machine.cfg' doesn't exist
took 0.047 seconds
INFO:  rshell --rts 1 --dtr 1 --timing -p /dev/ttyACM0 --buffer-size 512 -f cmd_list.cmd
Using buffer-size of 512
Connecting to /dev/ttyACM0 (buffer-size 512)...
Trying to connect to REPL  connected
Retrieving sysname ... rp2
Testing if ubinascii.unhexlify exists ... Y
Retrieving root directories ...
Setting time ... Aug 24, 2023 14:07:55
Evaluating board_name ... pyboard
Retrieving time epoch ... Jan 01, 1970
cannot access '/pyboard/*.py': No such file or directory
took 0.091 seconds
Unable to remove '/pyboard/app1'
took 0.072 seconds
Unable to remove '/pyboard/app2'
took 0.076 seconds
took 0.075 seconds
took 0.082 seconds
took 0.092 seconds
took 0.092 seconds
File '/home/username/git_repos/ct_meter/software/picow/tools/this.machine.cfg' doesn't exist
took 0.038 seconds
Copying '/home/username/git_repos/ct_meter/software/picow/tools/main.py' to '/pyboard/main.py' ...
took 0.593 seconds
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/vga2_bold_16x16.mpy' to '/pyboard/app1/vga2_bold_16x16.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/__init__.mpy' to '/pyboard/app1/__init__.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/project.mpy' to '/pyboard/app1/project.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/cmd_handler.mpy' to '/pyboard/app1/cmd_handler.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/constants.mpy' to '/pyboard/app1/constants.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/app.mpy' to '/pyboard/app1/app.mpy' ...
took 3.250 seconds
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/base_cmd_handler.mpy' to '/pyboard/app1/lib/base_cmd_handler.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/__init__.mpy' to '/pyboard/app1/lib/__init__.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/base_constants.mpy' to '/pyboard/app1/lib/base_constants.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/uo.mpy' to '/pyboard/app1/lib/uo.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/wifi.mpy' to '/pyboard/app1/lib/wifi.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/config.mpy' to '/pyboard/app1/lib/config.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/bluetooth.mpy' to '/pyboard/app1/lib/bluetooth.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/ydev.mpy' to '/pyboard/app1/lib/ydev.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/fs.mpy' to '/pyboard/app1/lib/fs.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/io.mpy' to '/pyboard/app1/lib/io.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/base_machine.mpy' to '/pyboard/app1/lib/base_machine.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/rest_server.mpy' to '/pyboard/app1/lib/rest_server.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/hardware.mpy' to '/pyboard/app1/lib/hardware.mpy' ...
took 5.312 seconds
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/lcd.mpy' to '/pyboard/app1/lib/drivers/lcd.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/__init__.mpy' to '/pyboard/app1/lib/drivers/__init__.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/ads1115.mpy' to '/pyboard/app1/lib/drivers/ads1115.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/ssd1306.mpy' to '/pyboard/app1/lib/drivers/ssd1306.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/max6675.mpy' to '/pyboard/app1/lib/drivers/max6675.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/atm90e32.mpy' to '/pyboard/app1/lib/drivers/atm90e32.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/rotary_encoder.mpy' to '/pyboard/app1/lib/drivers/rotary_encoder.mpy' ...
Copying '/home/username/git_repos/ct_meter/software/picow/tools/app1/lib/drivers/st7789.mpy' to '/pyboard/app1/lib/drivers/st7789.mpy' ...
took 3.659 seconds
Entering REPL. Use Control-X to exit.
>
MicroPython v1.20.0-326-gcfcce4b53 on 2023-07-25; Raspberry Pi Pico W with RP2040
Type "help()" for more information.
>>>
>>> import main
DEBUG: activeApp=1
INFO:  Started app
INFO:  Running app1
DEBUG: Set CPU freq to 240.0 MHz (MAX)
INFO:  File system information.
INFO:  Total Space (MB): 0.87
INFO:  Used Space (MB):  0.18
INFO:  Used Space (%):   20.3
INFO:  Initialised ATM90E32 devices.
DEBUG: wifiConfigDict: {'MODE': 'AP', 'SSID': 'YDEV', 'PASSWD': '12345678', 'CHANNEL': 3, 'WIFI_CFG': 0}
INFO:  Activating WiFi.
DEBUG: Set AP mode (192.168.4.1/255.255.255.0).
INFO:  Bluetooth ON=1
```

Once the app is running on the hardware the Android app can be used to configure the WiFi interface on the Pico W microcontroller. See the README in the 'Android_App' folder.

The deploy_and_run.py file has command line help as shown below.

```
pja@E5570:/tmp/ct_meter/micropython$ ./deploy_and_run.py -h
usage: deploy_and_run.py [-h] [-d] [-l] [-r] [-f] [--esp32] [--picow] [-v]

Load python code onto an MCU (esp32 or pico W) device running micropython..

optional arguments:
  -h, --help           show this help message and exit
  -d, --debug          Enable debugging.
  -l, --load           Convert the app1 folder .py files to .mpy files and load onto the ESP32.
  -r, --remove         Remove all .mpy files.
  -f, --factory_reset  Reset the configuration to factory defaults.
  --esp32              Load ESP32 hardware.
  --picow              Load RPi pico W hardware.
  -v, --view           View received data on first /dev/ttyUSB* or /dev/ttyACM* serial port.
```


### ota_upgrade.sh
Once the WiFi interface on the Pico W is configured it is possible to upgrade the running app over the air using the ota_upgrade.sh script. This script performs an over the air upgrade of the software on the Pico W microcontroller. It uses the ct6_tool.py code which can be found in the ct6_app_server folder.

E.G

```
./ota_upgrade.sh 192.168.0.196
PING 192.168.0.196 (192.168.0.196) 56(84) bytes of data.
64 bytes from 192.168.0.196: icmp_seq=1 ttl=255 time=109 ms

--- 192.168.0.196 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 108.867/108.867/108.867/0.000 ms
INFO:  Inactive App Folder: /app2
INFO:  Converting project.py to project.mpy (bytecode).
INFO:  Sending app1/project.mpy to /app2/
INFO:  app1/project.mpy file XFER success.
INFO:  Converting cmd_handler.py to cmd_handler.mpy (bytecode).
INFO:  Sending app1/cmd_handler.mpy to /app2/
INFO:  app1/cmd_handler.mpy file XFER success.
INFO:  Converting vga2_bold_16x16.py to vga2_bold_16x16.mpy (bytecode).
INFO:  Sending app1/vga2_bold_16x16.mpy to /app2/
INFO:  app1/vga2_bold_16x16.mpy file XFER success.
INFO:  Converting uo.py to uo.mpy (bytecode).
INFO:  Sending app1/lib/uo.mpy to /app2/lib
INFO:  app1/lib/uo.mpy file XFER success.
INFO:  Converting bluetooth.py to bluetooth.mpy (bytecode).
INFO:  Sending app1/lib/bluetooth.mpy to /app2/lib
INFO:  app1/lib/bluetooth.mpy file XFER success.
INFO:  Converting max6675.py to max6675.mpy (bytecode).
INFO:  Sending app1/lib/drivers/max6675.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/max6675.mpy file XFER success.
INFO:  Converting ssd1306.py to ssd1306.mpy (bytecode).
INFO:  Sending app1/lib/drivers/ssd1306.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/ssd1306.mpy file XFER success.
INFO:  Converting __init__.py to __init__.mpy (bytecode).
INFO:  Sending app1/lib/drivers/__init__.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/__init__.mpy file XFER success.
INFO:  Converting atm90e32.py to atm90e32.mpy (bytecode).
INFO:  Sending app1/lib/drivers/atm90e32.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/atm90e32.mpy file XFER success.
INFO:  Converting lcd.py to lcd.mpy (bytecode).
INFO:  Sending app1/lib/drivers/lcd.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/lcd.mpy file XFER success.
INFO:  Converting st7789.py to st7789.mpy (bytecode).
INFO:  Sending app1/lib/drivers/st7789.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/st7789.mpy file XFER success.
INFO:  Converting rotary_encoder.py to rotary_encoder.mpy (bytecode).
INFO:  Sending app1/lib/drivers/rotary_encoder.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/rotary_encoder.mpy file XFER success.
INFO:  Converting ads1115.py to ads1115.mpy (bytecode).
INFO:  Sending app1/lib/drivers/ads1115.mpy to /app2/lib/drivers
INFO:  app1/lib/drivers/ads1115.mpy file XFER success.
INFO:  Converting ydev.py to ydev.mpy (bytecode).
INFO:  Sending app1/lib/ydev.mpy to /app2/lib
INFO:  app1/lib/ydev.mpy file XFER success.
INFO:  Converting base_cmd_handler.py to base_cmd_handler.mpy (bytecode).
INFO:  Sending app1/lib/base_cmd_handler.mpy to /app2/lib
INFO:  app1/lib/base_cmd_handler.mpy file XFER success.
INFO:  Converting hardware.py to hardware.mpy (bytecode).
INFO:  Sending app1/lib/hardware.mpy to /app2/lib
INFO:  app1/lib/hardware.mpy file XFER success.
INFO:  Converting __init__.py to __init__.mpy (bytecode).
INFO:  Sending app1/lib/__init__.mpy to /app2/lib
INFO:  app1/lib/__init__.mpy file XFER success.
INFO:  Converting config.py to config.mpy (bytecode).
INFO:  Sending app1/lib/config.mpy to /app2/lib
INFO:  app1/lib/config.mpy file XFER success.
INFO:  Converting rest_server.py to rest_server.mpy (bytecode).
INFO:  Sending app1/lib/rest_server.mpy to /app2/lib
INFO:  app1/lib/rest_server.mpy file XFER success.
INFO:  Converting base_machine.py to base_machine.mpy (bytecode).
INFO:  Sending app1/lib/base_machine.mpy to /app2/lib
INFO:  app1/lib/base_machine.mpy file XFER success.
INFO:  Converting base_constants.py to base_constants.mpy (bytecode).
INFO:  Sending app1/lib/base_constants.mpy to /app2/lib
INFO:  app1/lib/base_constants.mpy file XFER success.
INFO:  Converting fs.py to fs.mpy (bytecode).
INFO:  Sending app1/lib/fs.mpy to /app2/lib
INFO:  app1/lib/fs.mpy file XFER success.
INFO:  Converting wifi.py to wifi.mpy (bytecode).
INFO:  Sending app1/lib/wifi.mpy to /app2/lib
INFO:  app1/lib/wifi.mpy file XFER success.
INFO:  Converting io.py to io.mpy (bytecode).
INFO:  Sending app1/lib/io.mpy to /app2/lib
INFO:  app1/lib/io.mpy file XFER success.
INFO:  Converting __init__.py to __init__.mpy (bytecode).
INFO:  Sending app1/__init__.mpy to /app2/
INFO:  app1/__init__.mpy file XFER success.
INFO:  Converting constants.py to constants.mpy (bytecode).
INFO:  Sending app1/constants.mpy to /app2/
INFO:  app1/constants.mpy file XFER success.
INFO:  Converting app.py to app.mpy (bytecode).
INFO:  Sending app1/app.mpy to /app2/
INFO:  app1/app.mpy file XFER success.
INFO:  took 11.8 seconds to upgrade device.
INFO:  Cleaning up python bytecode files.
INFO:  Deleted app1/vga2_bold_16x16.mpy
INFO:  Deleted app1/__init__.mpy
INFO:  Deleted app1/project.mpy
INFO:  Deleted app1/lib/base_cmd_handler.mpy
INFO:  Deleted app1/lib/__init__.mpy
INFO:  Deleted app1/lib/drivers/lcd.mpy
INFO:  Deleted app1/lib/drivers/__init__.mpy
INFO:  Deleted app1/lib/drivers/ads1115.mpy
INFO:  Deleted app1/lib/drivers/ssd1306.mpy
INFO:  Deleted app1/lib/drivers/max6675.mpy
INFO:  Deleted app1/lib/drivers/atm90e32.mpy
INFO:  Deleted app1/lib/drivers/rotary_encoder.mpy
INFO:  Deleted app1/lib/drivers/st7789.mpy
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
INFO:  Deleted app1/cmd_handler.mpy
INFO:  Deleted app1/constants.mpy
INFO:  Deleted app1/app.mpy
INPUT: Upgrade complete. Do you wish to reboot the device y/n: : y
INFO:  The device is rebooting.
INFO:  Waiting for device (192.168.0.196) to reboot.
INFO:  The device has rebooted.
INFO:  Took 12.5 seconds for device to restart.
INFO:  Upgrade successful. Switched from /app1 to /app2
```

More information on the functionality of the ct6_tool can be found in the
ct6_app_server folder README.

### picow_start_rshell.sh
A helper script to access the microcontroller flash contents. The script
requires one argument that is the serial port to which the Pico W microcontroller is connected. The rshell python module is required to use this script.

To use the tool the following command can be used assuming the Pico W is
connected to /dev/ttyACM0.

```
./esp32_start_rshell.sh /dev/ttyACM0
```

### ESP32 support scripts
The esp32_erase_flash.sh and esp32_start_rshell.sh scripts are for future use should ESP32 microcontroller support be added to the CT6 project.
