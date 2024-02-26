import sys
import requests
import datetime
import pprint
import warnings

from os import environ as env
from dotenv import find_dotenv, load_dotenv

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
    ZABBIX_API_URL = env.get("ZABBIX_API_URL")
    ZABBIX_API_token = env.get("ZABBIX_API_token")
else:
    # ask user for url and token
    ZABBIX_API_URL = input("Enter Zabbix API URL: ")
    ZABBIX_API_token = input("Enter Zabbix API Token: ")

headers = {
    'Authorization': 'Bearer ' + ZABBIX_API_token,
}

def api_request(payload) -> dict:
    response = requests.post(ZABBIX_API_URL, json=payload, headers=headers, verify=False)
    return response.json()

def host_maintenance(hostname):
    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.get",
        "params": {
            "output": "extend",
            "selectGroups": "extend",
            "selectTimeperiods": "extend",
            "selectHosts": "extend",
            "selectTimeperiods": "extend",
        },
        "id": 1,
    }
    
    maintenance_list = []
    data = api_request(payload)
    for maintenance in data['result']:
        if maintenance['hosts'] != []:
            if maintenance['hosts'][0]['name'] == hostname:
                maintenance_list.append(maintenance)
                
    if maintenance_list == []:
        print("No Maintenance window for host: ", hostname)
        return
                
    for maintenance in maintenance_list:
        # convert unix timestamp to datetime
        start_time = datetime.datetime.fromtimestamp(int(maintenance['active_since'])).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.datetime.fromtimestamp(int(maintenance['active_till'])).strftime('%Y-%m-%d %H:%M:%S')
        for host in maintenance['hosts']:
            print("Host:        ", host['name'])
        print("Start Time:  ", start_time)
        print("End Time:    ", end_time)
        # is the current time within the maintenance window?
        current_time = datetime.datetime.now().timestamp()
        # print past maintenance if current time is greater than end time
        if current_time > int(maintenance['active_till']):
            print("Past Maintenance window")
        else:
            print("Currently in Maintenance")
            
        print()
        
def current_maintenance() -> list:
    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.get",
        "params": {
            "output": "extend",
            "selectGroups": "extend",
            "selectTimeperiods": "extend",
            "selectHosts": "extend",
            "selectTimeperiods": "extend",
        },
        "id": 1,
    }
    
    data = api_request(payload)
    # return maintenance windows that are currently active
    current_maintenance = []
    for maintenance in data['result']:
        if later_date(int(maintenance['active_till'])):
            print(maintenance['name'])
            current_maintenance.append(maintenance)
            
    print()
    return current_maintenance
            
def later_date(timestamp):
    # compare current time with the timestamp
    current_time = datetime.datetime.now().timestamp()
    if current_time > timestamp:
        return False
    else:
        return True
    
def all_hosts_in_maintenance():
    payload = {
        "jsonrpc": "2.0",
        "method": "maintenance.get",
        "params": {
            "output": "extend",
            "selectGroups": "extend",
            "selectTimeperiods": "extend",
            "selectHosts": "extend",
            "selectTimeperiods": "extend",
        },
        "id": 1,
    }
    
    data = api_request(payload)
    hosts_in_maintenance = []
    for maintenance in data['result']:
        for host in maintenance['hosts']:
            hosts_in_maintenance.append(host['name'])
            
    return hosts_in_maintenance
        
def main():
    warnings.filterwarnings('ignore')
    
    if len(sys.argv) < 2:
        print("Usage: python maintenance.get.py <option>")
        sys.exit(1)
    
    selected = sys.argv[1]
    
    # does the input host have a maintenance window? 
    # if yes, print the maintenance window
    if selected == "--all" or selected == "1":    
        hostname = input("Enter hostname: ")
        print()
        host_maintenance(hostname)
        
    # print all current maintenance windows
    if selected == "--all" or selected == "2":
        print("Current Maintenance Windows")
        print()
        result = current_maintenance()
        if result == []:
            print("No current maintenance windows")
        # else:
            # pprint.pprint(result)
            
    # print all hosts in maintenance
    if selected == "--all" or selected == "3":
        print("Hosts in Maintenance")
        print()
        result = all_hosts_in_maintenance()
        if result == []:
            print("No hosts in maintenance")
        else:
            for host in result:
                print(host)
            print()
        
if __name__ == "__main__":
    main()