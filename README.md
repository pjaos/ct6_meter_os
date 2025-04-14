# CT6 Meter Project
For this project I developed the hardware to allow the measurement of household AC electrical energy usage on up to 6 circuits using current transformers (CT’s). It can be used to monitor solar system generation, storage battery charge/discharge, EV charging and household energy usage. Multiple CT6 devices can be used to monitor more circuits if required.

Each CT6 unit has 6 ports, each of which can be connected to a current transformer, clipped around a cable carrying AC mains power. Each port can measure the AC power flow bi directionally (I.E to and from the grid). The unit measures the active power (the power normally charged by a domestic electricity supplier), reactive and apparent power. The AC power factor, frequency and AC voltage is also measured along with the WiFi RSSI and CT6 device temperature.

The CT6 hardware.

![alt text](images/ct6.jpg "CT6 Unit")

![alt text](images/all_parts.jpg "CT6 Parts")

![alt text](images/pcb_with_display_on.jpg "CT6 PCB With Display Power On")

![alt text](images/pcb_with_display.jpg "CT6 PCB With Display Power Off")

![alt text](images/pcb.jpg "CT6 PCB")

I developed various software applications to allow the setup, recording and viewing of the data from CT6 devices. The ct6 configurator app allows the user to setup/configure a CT6 unit via a GUI interface. This includes connecting it to your WiFi, upgrading it to the latest firmware. Once CT6 device/s are connected to your WiFi network the ct6_app (running on a separate Windows or Linux computer) will read data from all CT6 units on your LAN, store the data in a database and present a Web UI to allow you to view your energy generation/usage without the need of a cloud based system. This web UI can be made available to all devices (PC’s, tablets and phones) on your LAN if required.

An example of the Web UI.
![alt text](software/server/images/ct6_dash.png "ct6_dash")

## Installing the software applications
Details of how to install the required CT6 software onto a Windows or Linux machine can be found [here](software/server/installers/README.md).

## Using the installed software applications
Details of how to setup your CT6 unit can be found [here](software/server/setting_up_ct6_units.md).

# Purchasing CT6 units
Complete CT6 units or assembled PCB's and associated parts can be purchased on Tindie at https://www.tindie.com/products/pausten/ct6-energy-monitor/

# Warning
This project is designed to use the YHDC SCT013 100A 0-1V split core current transformer. As mains voltage is dangerous it is the users responsibility to connect these current clamps safely using this hardware.
