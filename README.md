# ftp-usr-admin
Python script used for ProFTPD + MySQL/MariaDB (based on modified https://www.digitalocean.com/community/tutorials/how-to-set-up-proftpd-with-a-mysql-backend-on-ubuntu-12-10 install)  user/group administration.


## Usage
```
usage: ftp-user-adm.py [-h] {create,delete,info} ...

Add, search or modify ProFTPd virtual users.

optional arguments:
  -h, --help            show this help message and exit

command:
  {create,delete,info}
    create              Add new user or group
    delete              delete existing user
    info                info about users/groups
```
