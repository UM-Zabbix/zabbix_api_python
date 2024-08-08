import csv
import os
import sys
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Provide a list of hosts as a python list and add them to a hostgroup in Zabbix.

# THINGS TO CHANGE
# Add list of hosts here
hostlist = ["HOST-A", "HOST-B", "HOST-C"]

# Add postfix here
postfix = ".dsc.umich.edu"

# Add hostgroup name here
hostgroupname = "Ann Arbor/ITS/Team/Prod"


def get_hostid_by_name(hostname):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": "extend",
            "filter": {
                "host": [
                    hostname
                ]
            }
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    try:
        data = api_request(payload)
        hostid = data['result'][0]['hostid']
    except:
        hostid = None

    return hostid

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

    try:
        data = api_request(payload)
        hostgroupid = data['result'][0]['groupid']
    except:
        hostgroupid = None

    return hostgroupid

def update_hostgroup(host_ids, hostgroup_id):
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.massupdate",
        "params": {
            "groups": [
                {
                    "groupid": hostgroup_id
                }
            ],
            "hosts": host_ids
        },
         "auth": ZABBIX_API_token,
        "id": 1
    }
    data = api_request(payload)
    return data

def main():
    hostgroupid = get_hostgroup_id_by_name(hostgroupname)

    print("Adding hosts to hostgroup: " + hostgroupname + " (" + str(hostgroupid) + ")")
    
    hlist_len = len(hostlist)
    num_found = 0
    hostidlist = []
    for host in hostlist:
        # host to lower case
        host = host.lower()
        hostid = get_hostid_by_name(host + postfix)
        if hostid:
            print(host + ": " + str(hostid))
            hostidlist.append(hostid)
            num_found += 1
        else:
            print("Host not found: " + host)

    if hlist_len != num_found:
        print("Only " + str(num_found) + " of " + str(hlist_len) + " hosts found.")
        sys.exit(1)
    
    if hlist_len == num_found:
        print("All hosts found! (" + str(num_found) + " of " + str(hlist_len) + ")")

    # ask user to confirm
    print("Add " + str(len(hostidlist)) + " hosts to hostgroup " + hostgroupname + "? (y/n)")
    confirm = input()
    if confirm != "y":
        print("Aborted")
        sys.exit(1)

    # create hostid list
    id_list = []
    for hostid in hostidlist:
        id_list.append({"hostid": hostid})

    print(id_list)

    # update hostgroup
    data = update_hostgroup(id_list, hostgroupid)

    print(data)


if __name__ == "__main__":
    main()