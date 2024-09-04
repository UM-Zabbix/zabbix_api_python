import csv
import os
import sys
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Creates host objects in Zabbix and adds them to a proxy group.

# Provide a list of hosts as a python list and add them to a proxygroup in Zabbix.
hosts = ["HOST-A", "HOST-B", "HOST-C"]
proxygroupname = "On-prem Proxies"
hostgroupname = "Ann Arbor/ITS/TestTeam/Prod"

def get_hostgroup_id_by_name(hostgroupname):
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": "extend",
            "filter": {
                "name": [
                    hostgroupname
                ]
            }
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    data = api_request(payload)
    return data['result'][0]['groupid']

def get_proxygroups():
    payload = {
            "jsonrpc": "2.0",
            "method": "proxygroup.get",
            "params": {
                "output": "extend",
                "selectProxies": ["proxyid", "name"]
            },
            "auth": ZABBIX_API_token,
            "id": 1
        }
    data = api_request(payload)
    return data

def create_host(name, proxy_groupid, groupid):
    payload = {
    "jsonrpc": "2.0",
    "method": "host.create",
    "params": {
        "host": name,
        "groups": [
            {
                "groupid": groupid
            }
        ],
        "monitored_by": 2,
        "proxy_groupid": proxy_groupid,
    },
    "auth": ZABBIX_API_token,
    "id": 1
}

def main():
    proxygroups = get_proxygroups()
    print(proxygroups)
    for groups in proxygroups['result']:
        if groups['name'] == proxygroupname:
            proxy_groupid = groups['proxy_groupid']
            break

    hostgroup_id = get_hostgroup_id_by_name(hostgroupname)
    print("Host Group ID: " + str(hostgroup_id))
    
    for host in hosts:
        create_host(host, proxy_groupid, hostgroup_id)
        print("Creating host: " + host)
        print("Proxy Group ID: " + str(proxy_groupid))
        print("Host Group ID: " + str(hostgroup_id))
        print("")

if __name__ == "__main__":
    main()