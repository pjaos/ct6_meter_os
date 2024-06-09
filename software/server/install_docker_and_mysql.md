# MYSQL on Linux
The steps below detail how to run a MYSQL database using docker on a Linux (Ubuntu) platform.

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

PATH TO STORE MYSQL DATABASE = The path on the Ubuntu machine to store the CT6 database.

MYSQL PASSWORD = The root password for the mysql database.

- Check the mysql database is running. The output should be similar to that shown below to indicate the docker container is running.

```
# docker ps
# CONTAINER ID   IMAGE     COMMAND                  CREATED       STATUS       PORTS                                                  NAMES
# 55b31fffed72   mysql     "docker-entrypoint.s…"   12 days ago   Up 12 days   0.0.0.0:3306->3306/tcp, :::3306->3306/tcp, 33060/tcp   mysql-iot
```

# MYSQL on windows

- Download the docker installer from https://docs.docker.com/desktop/install/windows-install/
- Install using the default settings
- Reboot 
- Use recommended settings and step through all prompts until docker desktop is running
- Open a powershell window
- Enter the following command to get the mysql docker image

```
docker pull mysql
```

- cd to your home folder

```
cd c:\Users\<USERNAME>\
```

where USERNAME is your Windows username.


- Create a folder to hold the MYSQL database.

```
mkdir mysql-iot
```

- cd to the folder just created.

```
cd mysql-iot
```

- Create and start the mysql database docker image
  
```
docker run --name mysql-iot -v .:/var/lib/mysql:rw -e MYSQL_ROOT_PASSWORD=YOUR_PASSWORD -d -p 3306:3306 mysql
```

Where YOUR_PASSWORD is the root password you wish to create for the MYSQL database.

Subsequently the docker image can be stopped and started using the following commands

```
docker stop mysql-iot
```

```
docker start mysql-iot
```
 
You can also use the Docker Desktop application to start/stop docker images.
Enter 'Docker Desktop' at the windows start button to start this application.