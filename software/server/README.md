# CT6 Applications
The CT6 hardware is responsible for measuring the bi directional power from
up to 6 CT sensors.

Before using the CT6 apps detailed below you must setup your CT6 device as detailed [here](setting_up_ct6_units.md).

- Mode 1
This is the normal operating mode.

  - The ct6_app will detect CT6 devices on the LAN, save the data to a database (sqlite) and present
    a GUI (via a web server) to allow you to view current and historical CT6 data. This is
    the easiest way to get up an running with a CT6 device. Once the CT6 device is connected to your WiFi network you just need to run the ct6_app command (from the command line) one the command line to get this running.

   - Click [here](mode_1_mysql_db_and_dashboard.md) if you wish to have a more scalable system the ct6_db_store app will detect CT6 devices on the LAN, save the data to a mysql database.

- Mode 2
   - Send data to an MQTT server. In this case the CT6 device must be configured to
     send data to an MQTT server. Details of how to configure a CT6 device can be
     found [here](setting_up_ct6_units.md). The ability to send data to an MQTT server
     allows integration with other systems (E.G [ioBroker](https://www.iobroker.net/)).



