REM Add commands here that need to be executed on installation

REM We need PIP installed
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py

REM Ensure we have the latest pip version
python -m pip install --upgrade pip

# REM we need pipenv to run the tools in their own pyhton env
pip install pipenv

create_pip_env.bat

REM uninstall the modules
REM pip uninstall -y cryptography
REM pip uninstall -y paramiko
REM pip uninstall -y mysqlclient
REM pip uninstall -y paho-mqtt
REM pip uninstall -y p3lib
REM pip uninstall -y bokeh
REM pip uninstall -y requests
REM pip uninstall -y ifaddr
REM pip uninstall -y pandas
REM pip uninstall -y ping3
REM pip uninstall -y pyserial
REM pip uninstall -y retry
REM pip uninstall -y argon2-cffi
REM pip uninstall -y rshell
REM pip uninstall -y mpy_cross
REM pip uninstall -y pyflakes
REM pip uninstall -y pyflakes3
REM pip uninstall -y psutil
REM pip uninstall -y objgraph
REM pip uninstall -y ip2geotools

REM install the modules we need using pip rather than pipenv
REM pip install cryptography>=42.0.4
REM pip install paramiko>=2.10.1
REM pip install mysqlclient
REM pip install paho-mqtt
REM pip install p3lib>=1.1.71
REM pip install bokeh==3.1.0
REM pip install requests
REM pip install ifaddr
REM pip install pandas
REM pip install ping3
REM pip install pyserial==3.5
REM pip install retry
REM pip install argon2-cffi
REM pip install rshell
REM pip install mpy_cross
REM pip install pyflakes
REM pip install pyflakes3
REM pip install psutil
REM pip install objgraph
REM install the # comment at the start of this line if you wish the server
REM access log file to contain country, region and city information. 
REM The down side to this is that about 70 extra python modules are pulled
REM in making installation longer.
REM pip install ip2geotools 