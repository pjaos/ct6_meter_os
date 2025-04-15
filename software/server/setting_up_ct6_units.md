# Setting Up CT6 devices
The ct6_configurator program allows you to setup your CT6 unit. Once the software has
been installed the ct6_configurator software can be started as detailed below.

- Linux system
Enter 'ct6_configurator' in a terminal window.

- Windows System
The 'CT6 Configurator' App can be started from the windows Start button.

This command starts a local web server and then starts you systems web browser
connected to this web server. The following browser window is displayed initially.

![alt text](images/ct6_configurator_1.png "CT6 Configurator Initial Window")

## WiFi Configuration

The first thing you need to do with a CT6 device is connect it to
your WiFi network. The WiFi tab is the first tab an is selected by default when the
web browser starts.


You may configure the WiFi ssid and password either over a Bluetooth or a USB connection as detailed below.

### Bluetooth WiFi Configuration
To configure the CT6 WiFi over a bluetooth connection the computer running the
ct6_configurator software must have it's bluetooth interface enabled.

If the Bluetooth radio button is selected when you select the 'Setup WiFi' button you will
be prompted as shown below.

![alt text](images/ct6_configurator_2D.png "CT6 Configurator WiFi Setup Via Bluetooth 1")
![alt text](images/ct6_configurator_2E.png "CT6 Configurator WiFi Setup Via Bluetooth 2")
![alt text](images/ct6_configurator_2F.png "CT6 Configurator WiFi Setup Via Bluetooth 3")

The CT6 device should then show it's IP address at the bottom of the display as shown
below.

 ![alt text](../../images/ct6.jpg "CT6 device connected to WiFi")


### USB WiFi Configuration
If the USB radio button is selected when you select the 'Setup WiFi' button you will
be prompted to connect a USB cable to the CT6 device.

The USB interface of the RPi Pico W device inside the CT6 can be accessed by removing
the small panel on the lower edge of the unit that covers the USB port.

![alt text](../../images/all_parts.jpg "CT6 Parts")

The following shows configuration of the WiFi over a USB interface.

![alt text](images/ct6_configurator_2A.png "CT6 Configurator WiFi Setup Via USB 1")
![alt text](images/ct6_configurator_2B.png "CT6 Configurator WiFi Setup Via USB 2")
![alt text](images/ct6_configurator_2C.png "CT6 Configurator WiFi Setup Via USB 2")

 ![alt text](../../images/ct6.jpg "CT6 device connected to WiFi")


## Upgrade the CT6 firmware.

 After the WiFi has been setup you should upgrade the CT6 devices firmware to the latest version using
 the Upgrade tab. The CT6 firmware will be upgraded over your WiFi network. To do this select the
 Upgrade tab, ensure the IP address is the same IP address that is displayed on the display of the
 CT6 device and then select the 'Upgrade CT6 Device' button. The upgrade will take a minute or two
 to complete and when complete the window will look similar to that shown below.

 ![alt text](images/ct6_configurator_3.png "CT6 Configurator Upgrade Complete")


## Set CT6 Device Name
 Once you have upgraded the CT6 unit you must set the name of the CT6 unit. This is used as it's name in the the databases and in the GUI when viewing energy usage data. Therefore give some thought to the name
 you wish to set. You may have multiple CT6 devices and therefore you should give your CT6 device a name to
 identify it. The 'Device Name' tab allows you to do this. Select the 'Device Name' tab, check the
 IP address is correct and then enter a name for the device. The name should not have and space or
 tab characters and if they are entered they will be changed to underscore characters.

 Select the 'Set' button to save the device name to the CT6 device. Select the 'Get' button to
 read the device name from the CT6 device.

 ![alt text](images/ct6_configurator_4.png "CT6 Configurator Device Name")

## Set CT6 Port Names
 Your should then set the port names. Typically these should be set to the device which that port is used to monitor. E.G Solar, EV, Air Source Heat Pump, Hot water Heater, etc. The name should not have and space or tab characters.

 Each port on the CT6 device can be given a name using the 'Port Names' tab. To set the port names
 check that the IP address is correct, enter the name for each port and select the 'Set' button.
 If the 'Get' button is selected the names of each port are read from the CT6 device.

 ![alt text](images/ct6_configurator_5.png "CT6 Configurator Port Names")

## Set MQTT server configuration.
 If you are using your CT6 unit to send data to an MQTT server to integrate with other
 systems (E.G [ioBroker](https://www.iobroker.net/)) you may optionally set the MQTT server details here.

 If you wish to send power usage data to an MQTT server then the MQTT Server Address, MQTT Server Port (default 1883) and MQTT Topic must be entered. The MQTT Username and MQTT Password are optional. The TX Period (Milliseconds) defines how often the CT6 device will send data to an MQTT server. It is not recommended to set this value less than 1000 millseconds.

 The 'Set' button sets the MQTT Server parameters and the 'Get' button reads the parameters from
 the CT6 device.

 ![alt text](images/ct6_configurator_6.png "CT6 Configurator MQTT Server")

 The data sent to the MQTT server is in JSON format. Below is an example of the data that MQTT
 subscribers will receive. In this case the configured MQTT topic is 'CT6'.

```
{
  "CT2": {
    "NAME": 2.0,
    "PRMS": 0.0,
    "IPEAK": 0.0,
    "IRMS": 0.0,
    "TEMP": 0.0,
    "PAPPARENT": 0.0,
    "PF": 0.0,
    "PREACT": 0.0,
    "TYPE": "SCT013_100A",
    "FREQ": 0.0,
    "VRMS": 0.0
  },
  "PF_WATTS_THRESHOLD": 5,
  "CT3": {
    "NAME": 3.0,
    "PRMS": 0.0,
    "IPEAK": 0.0,
    "IRMS": 0.0,
    "TEMP": 0.0,
    "PAPPARENT": 0.0,
    "PF": 0.0,
    "PREACT": 0.0,
    "TYPE": "SCT013_100A",
    "FREQ": 0.0,
    "VRMS": 0.0
  },
  "CT1": {
    "NAME": 1.0,
    "PRMS": 0.0,
    "IPEAK": 0.0,
    "IRMS": 0.0,
    "TEMP": 0.0,
    "PAPPARENT": 0.0,
    "PF": 0.0,
    "PREACT": 0.0,
    "TYPE": "SCT013_100A",
    "FREQ": 0.0,
    "VRMS": 0.0
  },
  "DEVICE_TYPE": "6_CHNL_CT_SENSOR",
  "OS": "micropython",
  "CT6": {
    "NAME": 6.0,
    "PRMS": 0.0,
    "IPEAK": 0.0,
    "IRMS": 0.0,
    "TEMP": 0.0,
    "PAPPARENT": 0.0,
    "PF": 0.0,
    "PREACT": 0.0,
    "TYPE": "SCT013_100A",
    "FREQ": 0.0,
    "VRMS": 0.0
  },
  "CT5": {
    "NAME": 5.0,
    "PRMS": 0.0,
    "IPEAK": 0.0,
    "IRMS": 0.0,
    "TEMP": 0.0,
    "PAPPARENT": 0.0,
    "PF": 0.0,
    "PREACT": 0.0,
    "TYPE": "SCT013_100A",
    "FREQ": 0.0,
    "VRMS": 0.0
  },
  "PRODUCT_ID": "CT6",
  "BOARD_TEMPERATURE": 15.94435,
  "RSSI": -39.18182,
  "FIRMWARE_VERSION": "3.0",
  "SERVICE_LIST": "WEB:80",
  "UNIT_NAME": "offlineCT6",
  "CT4": {
    "NAME": 4.0,
    "PRMS": 0.0,
    "IPEAK": 0.0,
    "IRMS": 0.0,
    "TEMP": 0.0,
    "PAPPARENT": 0.0,
    "PF": 0.0,
    "PREACT": 0.0,
    "TYPE": "SCT013_100A",
    "FREQ": 0.0,
    "VRMS": 0.0
  },
  "TIMESENT": [
    2025,
    4,
    15,
    16,
    7,
    51,
    1,
    105,
    1744733271
  ],
  "ACTIVE": 1.0,
  "YDEV_UNIT_NAME": "offlineCT6",
  "GROUP_NAME": "",
  "IP_ADDRESS": "172.16.13.17",
  "ASSY": "ASY0398_V003.300_SN00001846",
  "READ_TIME_NS": 29564.67,
  "RX_TIME_SECS": 1744733271.3176482
}
```

 If you do not wish to send data to an MQTT server then the MQTT Server Address field should be empty.

## Activating a CT6 device
 A CT6 device will not send stats data until it is activated.

 A CT6 device may send data to the ct6_app or ct6_db_store apps. Both of these apps send out broadcast messages so that all CT6 devices on the LAN/WiFi send data back to them.

 If an MQTT server is configured then messages are sent from the CT6 device/s at the configured periodicity.

 The 'Activate Device' tab allows you to set a CT6 device as active/inactive.

 ![alt text](images/ct6_configurator_7.png "CT6 Configurator Activate Device")

## Install SW onto a CT6 device
 This option allows you to wipe the CT6 device flash and reload it.

 First the factory configuration is read from the CT6 device flash. The flash will then be erased, MicroPython will be reloaded followed by the CT6 firmware. This option allows the user to recover a CT6 unit that is not working correctly if required.

 A USB cable must be connected to the CT6 device to use this option. Select the 'Install CT6 SW' button
 and the CT6 factory configuration will be read from the device as shown below.

  ![alt text](images/ct6_configurator_8_a.png "CT6 Configurator Install")

As instructed in the window remove power from the CT6 device and hold the button on the Pico W device down.
The hole next to the C on the CT6 on the front of the CT6 case allows you hold this button down without
removing the Pico W from the CT6 case. The Pico W device will then be erased and reloaded and should
complete as shown below.

  ![alt text](images/ct6_configurator_8_b.png "CT6 Configurator Install")

## Scan for CT6 devices
 The Scan tab allows you to check your LAN for any CT6 devices that may be present. Select the Scan button
 to start the scanning process. The dropdown list of CT6 Devices is then populated with those that are found.

  ![alt text](images/ct6_configurator_9_a.png "CT6 Configurator Scan")

You can then power cycle a CT6 device remotely if required by selecting the device from the drop down list and then selecting the 'Power Cycle CT6 Device' button. The CT6 device will power off and after 4 or 5 seconds power back on again to reconnect to the WiFi network as shown below.

  ![alt text](images/ct6_configurator_9_b.png "CT6 Configurator Scan")

## Calibrate the CT6 measurements
The CT6 device measures the AC mains voltage and the current on port connected to a current transformer (CT).

### Voltage Calibration

The CT6 device is powered from an AC supply. The CT6 device measures the mains AC voltage by measuring its AC supply voltage.
This supply voltage is dropped down to 9-16 volts from the AC mains voltage by the power adapter used.
When the CT6 device is manufactured it's voltage measurements are calibrated. This is done using the recommended
power adaptor. If you wish to use another power adaptor it must provide between 9 and 16V AC to the CT6 device and
be calibrated. Using the 'CALIBRATE VOLTAGE' tab you can perform CT6 voltage calibration to ensure the voltage
measured by the CT6 device is accurate.

To do this you have to manually measure the AC voltage using a digital multimeter (DMM) or some other device. Care must be taken when doing this as the AC mains voltage is dangerous. Use a connector block to measure the AC mains voltage with a DMM. Some inline energy monitoring devices will report the AC mains voltage which could be used instead of a DMM. Note that the accuracy of the voltage measurement will dictate the accuracy of the CT6 device power readings.

To perform the voltage calibration enter the measures AC voltage into the field on the CALIBRATE VOLTAGE tab. The '60 Hz AC supply switch should be left off unless your AC mains supply frequency is 60 Hz. In this case the AC mains frequency is assumed to be 50 Hz. Then select the 'PERFORM VOLTAGE CALIBRATION' button as shown below.

  ![alt text](images/ct6_configurator_10_a.png "CT6 Voltage Calibration")


### Current Calibration

When the CT6 device is manufactured it is calibrated using a 'YHDC SCT013 100A 0-1V' current transformer. If you wish to use a different transformer then you will need to calibrate the CT port with the new CT connected. A current of at least 1 amps must be passing through the cable that the CT is connected to in order to calibrate it. It is recommended that this current is around 10 amps. The 'CALIBRATE CURRENT' tab can used to calibrate the current measurement on the device port. You will need an external method to measure the current so that you can enter the value into the 'AC Current (Amps)' field. The equipment to perform this calibration is detailed in [README_MFG]README_MFG.md).

With a load on the connected CT enter the 'AC Current (Amps)' measured value. The '60 Hz AC supply switch should be left off unless your AC mains supply frequency is 60 Hz. Then select the 'CALIBRATE CURRENT' button as shown below.

  ![alt text](images/ct6_configurator_10_b.png "CT6 Current Calibration")





