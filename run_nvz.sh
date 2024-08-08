#!/bin/bash

# cd to /nagios directory 
cd /Users/mdeeds/zabbix_api_python/nagios

# pull the latest changes from the git repository
git pull origin main

cd /Users/mdeeds/zabbix_api_python

# run the python script
python nvz.py 2374