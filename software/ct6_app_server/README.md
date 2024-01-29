# CT6 Applications
The CT6 hardware is responsible for measuring the bi directional power from
up to 6 CT sensors. The hardware allows CT6 units to be stacked to provide up
to 24 bi directional CT ports. However the software does not currently support
more than 6 ports per unit. The applications are all written in python and have the
following functionality.

## ct6_db_store
This application is responsible for sending are you there (AYT) broadcast messages to
CT6 modules. The modules then respond with the data from each port. This
includes

- The RMS power (watts) from each port.
- The Apparent power (watts) from each port.
- The reactive power (watts) from each port.
- The RMS current (amps) from each port.
- The Peak current (amps) from each port.
- The power factor for the power on each port.
- The direction of the power from each port.
- The RMS AC voltage.
- The AC Frequency (Hz).
- The module temperature (°C).
- The WiFi RSSI (dBm).

When this information is received the ct6_db_store app is responsible for storing it in a mysql database.

## ct6_dash
This app is responsible for presenting a web server interface that displays a dashboard which reports the
bi directional power. An example of this dashboard is shown below.

![alt text](images/ct6_dash.png "ct6_dash")

This dashboard allows the user to examine the data from CT6 hardware units. Each CT6 unit is displayed in a separate tab.

 - The Today/Yesterday, This Week/Last Week, This Month/Last Month and This Year/Last Year green buttons populate the start and stop date fields and trigger a new power plot of the data. The '>' and '<' buttons either side of the start and stop fields can be used to increment or decrement the fields by one day for each press. The Start and Stop fields can also be updated directly. The buttons at the bottom of the dash can then be selected to plot the data.

 - The grey Sec, Min, Hour and Day buttons set the resolution of the data to plot (default = Min). It may be necessary for the user to reduce the resolution when plotting over long time periods.

 - The grey Active, Reactive and Apparent buttons select the type of AC power to be displayed (default = Active). The active power is the power that electricity suppliers normally charge for.

 - The grey 'Import is positive' and 'Import is negative' buttons set the imported power to be plotted as either negative or positive values (default = Import is negative).

Below this the green buttons allow the user to plot the data of interest.

 - Power: 			Plot the AC power measured on each sensor.
 - Power Factor:	Plot the AC power factor measured on each sensor.
 - AC Voltage:		Plot the AC voltage measured by the CT6 unit.
 - AC Frequency:	Plot the AC frequency measured by the CT6 unit.
 - Temperature:		Plot the temperature of the CT6 unit.
 - WiFi RSSI:		Plot the WiFi signal strenght measured by the CT6 unit.

For graphs that show data for each sensor, each name is that which the user gives to each CT port on the CT6 hardware unit.

If the user hovers their mouse over data points on the graph the values at these data points are displayed in popup menus.

The user can select the legend for each trace to toggle it on/off.

## ct6_tool
This is responsible for providing the features needed to manage CT6 hardware.
This includes upgrading the micropython firmware on CT6 units over the air.

Each of the above tools can be executed on the command line. These three apps
provide all the functionality required to use, commission and calibrate the CT6 hardware.



# System Setup
The following provides the detail necessary to setup the system.


#### CT6 configuration
The CT6 unit name and names of each of its ports can be configured as shown below.

```
ct6_tool -a 192.168.0.34 --config
INFO:  Configure 192.168.0.34
INFO:  Reading configuration from 192.168.0.34
INFO:  ID Description    Value
INFO:  1  Device name     
INFO:  2  Port 1 name     
INFO:  3  Port 2 name     
INFO:  4  Port 3 name     
INFO:  5  Port 4 name     
INFO:  6  Port 5 name     
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: 1
INPUT: Enter the Device name value: Meter Cupboard
INFO:  ID Description    Value
INFO:  1  Device name     Meter_Cupboard
INFO:  2  Port 1 name     
INFO:  3  Port 2 name     
INFO:  4  Port 3 name     
INFO:  5  Port 4 name     
INFO:  6  Port 5 name     
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: 2
INPUT: Enter the Port 1 name value: Grid
INFO:  ID Description    Value
INFO:  1  Device name     Meter_Cupboard
INFO:  2  Port 1 name     Grid
INFO:  3  Port 2 name     
INFO:  4  Port 3 name     
INFO:  5  Port 4 name     
INFO:  6  Port 5 name     
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: 3
INPUT: Enter the Port 2 name value: Solar
INFO:  ID Description    Value
INFO:  1  Device name     Meter_Cupboard
INFO:  2  Port 1 name     Grid
INFO:  3  Port 2 name     Solar
INFO:  4  Port 3 name     
INFO:  5  Port 4 name     
INFO:  6  Port 5 name     
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: 4
INPUT: Enter the Port 3 name value: Battery
INFO:  ID Description    Value
INFO:  1  Device name     Meter_Cupboard
INFO:  2  Port 1 name     Grid
INFO:  3  Port 2 name     Solar
INFO:  4  Port 3 name     Battery
INFO:  5  Port 4 name     
INFO:  6  Port 5 name     
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: 5
INPUT: Enter the Port 4 name value: Aircon
INFO:  ID Description    Value
INFO:  1  Device name     Meter_Cupboard
INFO:  2  Port 1 name     Grid
INFO:  3  Port 2 name     Solar
INFO:  4  Port 3 name     Battery
INFO:  5  Port 4 name     Aircon
INFO:  6  Port 5 name     
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: 6
INPUT: Enter the Port 5 name value: House
INFO:  ID Description    Value
INFO:  1  Device name     Meter_Cupboard
INFO:  2  Port 1 name     Grid
INFO:  3  Port 2 name     Solar
INFO:  4  Port 3 name     Battery
INFO:  5  Port 4 name     Aircon
INFO:  6  Port 5 name     House
INFO:  7  Port 6 name     
INFO:  8  Device Active   0
INPUT: Enter the ID to change, S to store or Q to quit: s
INFO:  Saved parameters to CT6 device.
```


## Storing CT6 data
Once the CT6 unit has been configured as detailed above the ct6_db_store tool saves data from the CT6 unit to a database.

### Setup a MYSQL database using docker
- [Install docker on the Ubuntu machine.](https://docs.docker.com/engine/install/ubuntu/)
- Install the mysql docker container

```
docker pull mysql
```

- Run the mysql docker container.

```
docker run --name mysql-iot -v PATH TO STORE MYSQL DATABASE:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=<MYSQL PASSWORD> -d -p 3306:3306 mysql
```

Where

PATH TO STORE MYSQL DATABASE = The path on the Ubuntu machine to store the CT6 data.

MYSQL PASSWORD = The root password for the mysql database.

- Check the mysql database is running. The output should be similar to that shown below to indicate the docker container is running.

```
# docker ps
# CONTAINER ID   IMAGE     COMMAND                  CREATED       STATUS       PORTS                                                  NAMES
# 55b31fffed72   mysql     "docker-entrypoint.s…"   12 days ago   Up 12 days   0.0.0.0:3306->3306/tcp, :::3306->3306/tcp, 33060/tcp   mysql-iot
```


### Save CT6 data to the above database.
The ct6_db_store tool should be executed on the Ubuntu machine that has access to the WiFi network on which the CT6 unit is registered.

```
ct6_db_store -c
INFO:  Loaded config from /home/username/.ct6DBStore.cfg
INFO:  Saved config to /home/username/.ct6DBStore.cfg
INFO:  ID  PARAMETER           VALUE
INFO:  1   ICONS_ADDRESS       127.0.0.1
INFO:  2   ICONS_PORT          22
INFO:  3   ICONS_USERNAME      
INFO:  4   ICONS_SSH_KEY_FILE  /home/username/.ssh/id_rsa
INFO:  5   MQTT_TOPIC          HOME/#
INFO:  6   DB_HOST             192.168.0.22
INFO:  7   DB_PORT             3306
INFO:  8   DB_USERNAME         root
INFO:  9   DB_PASSWORD         changeme
INPUT: Enter 'E' to edit a parameter, or 'Q' to quit:
```

ID's  1,2,3 and 4 can be left at the default values or unset. They are not currently used.

ID 5  Should be set to 'HOME/#'.

ID 6  Should be set to the IP address of the Ubuntu machine on the LAN.

ID 7  This can be left at 3306 unless the docker container is setup for a different port.

ID 8  The database username can be left as root

ID 9  Ensure the password is set to the password used when the mysql docker container was started.

Once this has been completed 'Q' should be entered to quit the ct6_db_tool.

Repeat 'CT6 configuration' (from above system setup section) and use option (ID) 8 to set the device as active. This causes the ct6_db_store tool to start saving it's data to the database.

Start the ct6_db_tool without arguments. This causes messages to be sent to CT6 units which return data to be stored in the database as shown below.

```
ct6_db_store
INFO:  Loaded config from /home/username/.ct6DBStore.cfg
INFO:  Saved config to /home/username/.ct6DBStore.cfg
INFO:  Creating Hour and Day tables...
INFO:  Connecting to 192.168.0.22:3306
INFO:  Connected
INFO:  Deleted CT6_SENSOR_MINUTE database table.
INFO:  Deleted CT6_SENSOR_HOUR database table.
INFO:  Deleted CT6_SENSOR_DAY database table.
INFO:  Created CT6_SENSOR_MINUTE table in Meter_Cupboard.
INFO:  Created CT6_SENSOR_HOUR table in Meter_Cupboard.
INFO:  Created CT6_SENSOR_DAY table in Meter_Cupboard.
INFO:  Creating derived tables in Meter_Cupboard.
INFO:  Took 7.0 seconds to write CT6_SENSOR_MINUTE table in Meter_Cupboard
INFO:  Took 0.1 seconds to write CT6_SENSOR_HOUR table in Meter_Cupboard
INFO:  Took 0.0 seconds to write CT6_SENSOR_DAY table in Meter_Cupboard
INFO:  Created CT6_SENSOR_MINUTE_INDEX in Meter_Cupboard.
INFO:  Created CT6_SENSOR_HOUR_INDEX in Meter_Cupboard.
INFO:  Created CT6_SENSOR_DAY_INDEX in Meter_Cupboard.
INFO:  Took 9.0 seconds to create derived tables in Meter_Cupboard
INFO:  Derived tables created.
INFO:  Disconnected from 192.168.0.22:3306
INFO:  Connected to MySQL server.
INFO:  Sending AYT messages.
INFO:  Listening on UDP port 29340
INFO:  Found device on 192.168.0.34
```

The ct6_db_store is now storing data it receives from CT6 units. If multiple units are found they will be stored in different databases.

## Displaying CT6 data
The CT6 data can be displayed using the ct6_dash app. This app starts a web server which uses the python bokeh module to present a user interface shown near the top of this document.

The command line shown below allows the user to configure the parameters needed by the app.

```
ct6_dash -c
INFO:  Loaded config from /home/username/.ct6Dash.cfg
INFO:  Saved config to /home/username/.ct6Dash.cfg
INFO:  ID  PARAMETER                 VALUE
INFO:  1   DB_HOST                   192.168.0.22
INFO:  2   DB_PORT                   3306
INFO:  3   DB_USERNAME               root
INFO:  4   DB_PASSWORD               changeme
INFO:  5   LOCAL_GUI_SERVER_ADDRESS  192.168.0.23
INFO:  6   LOCAL_GUI_SERVER_PORT     10000
INPUT: Enter 'E' to edit a parameter, or 'Q' to quit:
```

1 = The host address of the machine running the ct6_db_store program.

2 = The TCP port number to connect to the database.

3 = The username of the database.

4 = The password for access to the database.

5 = The address of the local machine on the LAN.

6 = The port number to present the web server on.

To start the web server enter the following command.

```
ct6_dash
INFO:  Loaded config from /home/username/.ct6Dash.cfg
INFO:  Saved config to /home/username/.ct6Dash.cfg
INFO:  Connected to MySQL server.
```

If executed from an Ubuntu desktop machine the above command will also launch a browser session. If a browser session is started for the above configuration then the URL http://192.168.0.23:10000 will connect to the server.


## Bringing Up A CT6 unit.

More information can be found on this [here](README_MFG.md)