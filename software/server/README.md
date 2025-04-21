# CT6 Applications
The CT6 hardware is responsible for measuring the bi directional power from
up to 6 CT sensors.

Before using the CT6 apps detailed below you must setup your CT6 device as detailed [here](setting_up_ct6_units.md).

- Mode 1
This is the normal operating mode.

  - The ct6_app will detect CT6 devices on the LAN, save the data to a database (sqlite) and present
    a GUI (via a web server) to allow you to view current and historical CT6 data. This is
    the easiest way to get up an running with a CT6 device.
    Once the CT6 device is connected to your WiFi network simply start the ct6_app and energy usage
    data is stored and can be viewed using a web browser on the same or another PC (tablet or phone) in your house.
    It is possible (using the -c command line option and ct6_dash_mgr tool) to configure the ct6_app tool so that
    credentials (username and password pairs) are required to log into the web interface if you wish to control access to this data.

   - Click [here](mode_1_mysql_db_and_dashboard.md) if you wish to have a more scalable system the ct6_db_store app will detect CT6 devices on the LAN, save the data to a mysql database and the ct6_dash app will display a similar interface to the ct6_app.

- Mode 2
   - Send data to an MQTT server to integrate with other systems. In this case the CT6 device must be configured to
     send data to an MQTT server. Details of how to configure a CT6 device can be
     found [here](setting_up_ct6_units.md). The ability to send data to an MQTT server
     allows integration with other systems (E.G [ioBroker](https://www.iobroker.net/)).



