# CT6 Meter Project
For this project I developed the hardware to allow the measurement of household AC electrical energy usage on up to 6 circuits using current transformers (CT’s). It can be used to monitor solar system generation, storage battery charge/discharge, EV charging, household energy usage, etc...

Multiple CT6 devices can be used to monitor more circuits if required.

Each CT6 unit has 6 ports, each of which can be connected to a current transformer, clipped around a cable carrying AC mains power. Each port can measure the AC power flow bi directionally (I.E to and from the grid). The unit measures the active power (the power normally charged by a domestic electricity supplier), reactive and apparent power. The AC power factor, frequency and AC voltage is also measured along with the WiFi RSSI and CT6 device temperature.

## The CT6 hardware.

![alt text](images/ct6.jpg "CT6 Unit")

![alt text](images/all_parts.jpg "CT6 Parts")

![alt text](images/pcb_with_display_on.jpg "CT6 PCB With Display Power On")

![alt text](images/pcb_with_display.jpg "CT6 PCB With Display Power Off")

![alt text](images/pcb.jpg "CT6 PCB")

### CT6 Hardware details
More details of the CT6 hardware can be found [here](hardware/README.md).

## Installing CT6 Software Applications
Details of how to install the CT6 software package onto a Windows or Linux machine can be found [here](software/server/installers/README.md).

## The CT6 Software Applications
An overview of the CT6 software applications are shown below. These can all be started from a terminal window on the command line by entering the name of each command.

- ct6_configurator

The ct6 configurator app allows the user to setup/configure a CT6 unit via a GUI interface. This includes connecting it to your WiFi, upgrading it to the latest firmware. Click [here](software/server/setting_up_ct6_units.md).

- ct6_app

When at least one CT6 device is connected to your WiFi network you can start this app (enter ct6_app in a terminal window). This app will find all CT6 units. These CT6 units will send data to the ct6_app which then stores it in an sqlite database. A server is then started and a browser window will open, connected to the server, to display the data from the database as shown.

![alt text](software/server/images/ct6_dash.png "ct6_dash")

- ct6_db_store

Similar to part of the ct6_app in that it detects all CT6 units on the LAN/WiFi and stores the data in a database. However the database is a mysql database. This allows for a more scalable system than the ct6_app. Details of how to use this app can be found [here](software/server/mode_1_mysql_db_and_dashboard.md).

- ct6_dash

This presents the data stored in the above mysql database and presents a GUI in a web browser as displayed above.  Details of how to use this app can be found [here](software/server/mode_1_mysql_db_and_dashboard.md).

- ct6_dash_mgr

Both the ct6_app and the ct6_dash app present a GUI in a browser interface via a local web server. This app allows you to configure credentials (username/password) to allow access to the web server. The ct6_app and ct6_dash apps must be configured to require a login in order to use these credentials. The example below shows auser being added for web server access.

```
ct6_dash_mgr
INFO:
INFO:  ------------
INFO:  | USERNAME |
INFO:  ------------
INFO:  0 credentials stored in /home/pja/.ct6_dash_credentials.json
INFO:
INFO:  A - Add a username/password.
INFO:  D - Delete a username/password.
INFO:  C - Check a username/password is stored.
INFO:  Q - Quit.
INPUT: Enter one of the above options: : a
INFO:  Add a username/password
INPUT: Enter the username: : auser
INPUT: Enter the password: : apassword
INFO:
INFO:  ------------
INFO:  | USERNAME |
INFO:  ------------
INFO:  |    auser |
INFO:  ------------
INFO:  1 credentials stored in /home/pja/.ct6_dash_credentials.json
INFO:
INFO:  A - Add a username/password.
INFO:  D - Delete a username/password.
INFO:  C - Check a username/password is stored.
INFO:  Q - Quit.
INPUT: Enter one of the above options: : q
```

- ct6_mfg_tool

This tool is used to load SW and perform manufacturing tests on CT6 hardware in order to commission them.

- ct6_stats

This finds CT6 devices on the LAN/WiFi and displays the JSON data received from CT6 devices.

- ct6_tool

This provides functionality that is useful when checking the operation of CT6 units in a development environment.

More details of how to use the installed software applications can be found [here](software/server/README.md).

# Home Assistant integration
Click [here](software/server/homeassistant_README.md) for details of how to use CT6 devices with homeassistant.

# Purchasing CT6 units
Complete CT6 units or assembled PCB's and associated parts can be purchased [here](https://www.tindie.com/products/pausten/ct6-energy-monitor/) on Tindie.

If you wish to purchase the PCB and assemble it the PCB is available [here](https://www.ebay.co.uk/itm/197238433051?_skw=ct6+energy+monitor&itmmeta=01JSDZHK5C73DRCH2B6C3826B8&hash=item2dec53a51b:g:JuUAAOSwgS1oBlyi&itmprp=enc%3AAQAKAAAA8FkggFvd1GGDu0w3yXCmi1cBRlOOjv8sOKb%2FTHOQEqPMlhxXlGHQDXkllzre4%2BcAD9Xe%2BMO3c0eWxNT1whArwip%2BVjcEObn3zDHjn7rUXmn8Eg7MvTBtyVcclCey1ORpy%2FhiubO1FkwFZiuEHAs4gDc7YZebYCdjbKHG5OuyfSEBxeywqPoqp1HD85w0z3N8VLhNet%2Bpgp%2BQRGP00zPNf2Xa50bkNm3EAlkhm49pyxJM4nAW9pQ1wKwWL--ZpUE0TlTCsp9zG0qZx4K2688cyUG2xWnXUhBAK9Xy%2FJXSpeQd6Zgui8Vw8m%2FYUpzmoOYeIg%3D%3D%7Ctkp%3ABk9SR-yyxr_LZQ) on ebay and the Bill of materials (BOM) is available [here](hardware/ct_meter_2.1_bom.csv).

# Warning
This project is designed to use the YHDC SCT013 100A 0-1V split core current transformer. As mains voltage is dangerous it is the users responsibility to connect these current clamps safely using this hardware.
