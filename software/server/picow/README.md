# Micropython
The CT6 device runs a micropython app. The app1 folder contains
the all the CT6 device code including the libraries and hardware device drivers.

## Design

I decided to use the Raspberry Pi Pico W microcontroller. I also decided to use micropython as the operating system. On previous projects that used microcontrollers I have used [Mongose OS](https://mongoose-os.com/) which runs on top of [FreeRTOS](https://www.freertos.org/index.html) with the firmware written in C. I decided to use micropython as the speed/capability trade offs are changing with the continuing development of micropython and I wanted to see it's benefits/limitations on a real world project. Having completed the project I can say that micropython is more than capable for this type of project. I did compile the display SPI driver into the micropython firmware to speed up the display interface but other than that I was pleasantly surprised and plan to use it for other suitable projects in the future as the effort required to reach the development complete stage was considerably less using micropython than my previous approach.

The CT6 hardware was designed against the requirements detailed in the top level readme. This involved schematic design, PCB layout and PCB manufacture. The PCB was fabricated, assembled, tested and a 3D printed case was produced. This took several iterations before I was happy with the design. The [hardware](hardware) folder contains details of the schematic and also the design for the 3D printed case.

## Tools
The tools folder contains several development tools. Some of the tools also support ESP32 microcontrollers which would ease the process of changing the microcontroller if it should be needed in future. The ct6_tool.py and ct6_mfg_tool.py (in the software/server) contain functionality that is useful when developing the software and hardware. This includes over the air upgrade functionality. See the command line help on these tools for more information.

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
