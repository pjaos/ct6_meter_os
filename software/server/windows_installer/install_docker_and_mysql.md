# Install docker on windows

- Download installer from https://docs.docker.com/desktop/install/windows-install/
- Install using the default settings
- Reboot 
- Use recommended settings and step through all prompts until docker desktop is running
- docker pull mysql
- cd c:\Users\<USERNAME>\
- mkdir mysql-iot
- cd mysql-iot
- Create and start the mysql database docker image
  
  docker run --name mysql-iot -v .:/var/lib/mysql:rw -e MYSQL_ROOT_PASSWORD=changeme -d -p 3306:3306 mysql
  
  Subsequentally the docker image can be stopped and started using the following commands
  
  docker start mysql-iot
  docker stop mysql-iot
  
- Start process to read and save CT6 data. This will send out broadcast messages onto the local LAN/WiFi
  and store all messages received from CT6 units.
  
  python -m pipenv shell
  python .\ct6_db_store.py -c
  python .\ct6_db_store.py
INFO:  CPU Load AVG: 1.8, Used Mem (MB): 9118.3 Free Mem (MB): 7783.6
INFO:  Found 17573    object of type function
INFO:  Found 7990     object of type tuple
INFO:  Found 6979     object of type dict
INFO:  Found 3232     object of type ReferenceType
INFO:  Found 3208     object of type wrapper_descriptor
INFO:  Found 2856     object of type getset_descriptor
INFO:  Found 2678     object of type cell
INFO:  Found 2619     object of type builtin_function_or_method
INFO:  Found 2439     object of type method_descriptor
INFO:  Found 2305     object of type list

- Start the ct6 dash
  python -m pipenv shell
  python .\ct6_dash.py -c
  python .\ct6_dash.py
