import csv
import os
import sys
import json
import requests
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_host_by_name(hostname):
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

def get_usergroups():
    payload = {
        "jsonrpc": "2.0",
        "method": "usergroup.get",
        "params": {
            "output": "extend",
            "selectHostGroupRights": "extend"
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    data = api_request(payload)
    return data['result']

def get_usergroup_by_name(name):
    usergroups = get_usergroups()
    for group in usergroups:
        if group['name'] == name:
            return group
    return None

def get_hostgroups_by_id(id):
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": "extend",
            "groupids": id
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    data = api_request(payload)
    return data['result']

def main():
    # constants
    HOST_HEADER = "HOST"
    ENVIRONMENT_HEADER = "STATUS"
    PROD_DESCRIPTOR = "PRODUCTION"
    NON_PROD_DESCRIPTOR = "NON-PRODUCTION"

    # read arguments to get the csv file
    if len(sys.argv) < 2:
        print("Usage: python add-hostgroup.py <csv_file> <usergroup> (--dry-run) (--force)")
        sys.exit(1)

    csv_file = sys.argv[1]
    usergroup = sys.argv[2]
    try:
        dry_run = sys.argv[3]
        if dry_run != "--dry-run":
            print("Usage: python add-hostgroup.py <csv_file> <usergroup> (--dry-run) (--force)")
            sys.exit(1)
    except:
        dry_run = None

    try:
        force = sys.argv[4]
        if force != "--force":
            print("Usage: python add-hostgroup.py <csv_file> <usergroup> (--dry-run) (--force)")
            sys.exit(1)
    except:
        force = None

    # check to see if the csv file exists
    try:
        with open(csv_file, 'r') as file:
            print(f"> File {csv_file} exists")
            pass
    except:
        print(f"File {csv_file} does not exist!")
        sys.exit(1)

    # check to see if the usergroup exists
    usergroup_data = get_usergroup_by_name(usergroup)
    if usergroup_data is None:
        print(f"Usergroup {usergroup} does not exist!")
        sys.exit(1)
    else:
        print(f"> Usergroup {usergroup} exists")
    
    # get ids with permission of 3
    hostgroup_rights = []
    for right in usergroup_data['hostgroup_rights']:
        if right['permission'] == '3':
            hostgroup_rights.append(right['id'])

    # get hostgroups
    hostgroups = []
    for id in hostgroup_rights:
        hostgroups.append(get_hostgroups_by_id(id))

    # determine which hostgroup is Prod and which is Non-Prod
    prod = 0
    prod_name = ""
    non_prod = 0
    non_prod_name = ""
    for group in hostgroups:
        # if name contains Prod, set prod to id
        if "/Prod" in group[0]['name']:
            prod = group[0]['groupid']
            prod_name = group[0]['name']
        elif "/NonProd" in group[0]['name']:
            non_prod = group[0]['groupid']
            non_prod_name = group[0]['name']
        else:
            print(f"Hostgroup {group[0]['name']} does not match Prod or NonProd!")
            sys.exit(1)

    if prod == 0 or non_prod == 0:
        print("Prod or Non-Prod hostgroup not found!")
        sys.exit(1)

    print(f"Prod Hostgroup: {prod}")
    print(f"Non-Prod Hostgroup: {non_prod}")

    # open the csv file and read the column titled 'host'
    hosts = []
    environment = []
    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            hosts.append(row[HOST_HEADER])
            environment.append(row[ENVIRONMENT_HEADER])

    # check for log file and remove it
    try:
        with open("hosts_not_in_zabbix.log", 'r') as file:
            print("> Log file exists")
            pass
    except:
        print("> Log file does not exist")
        pass
    else:
        print("> Removing log file")
        os.remove("hosts_not_in_zabbix.log")

    # check to see if each host exists
    in_zabbix = []
    missing = []
    for host in hosts:
        # make host lower case
        host = host.lower()
        hostid = get_host_by_name(host + ".adsroot.itcs.umich.edu")
        if hostid is None:
            print(f"Host {host} does not exist")
            in_zabbix.append(None)
            # open a file to log hosts that do not exist
            with open("hosts_not_in_zabbix.log", "a") as file:
                file.write(host + "\n")
            missing.append(host)
        else:
            print(f"Host {host} exists")
            in_zabbix.append(hostid)
    
    index = 0
    prod_hosts = []
    non_prod_hosts = []
    for host in in_zabbix:
        if host is not None:
            if environment[index] == PROD_DESCRIPTOR:
                # host_info = {
                #     "hostid": host,
                #     "groupid": prod
                # }
                prod_hosts.append(host)
            elif environment[index] == NON_PROD_DESCRIPTOR:
                # host_info = {
                #     "hostid": host,
                #     "groupid": non_prod
                # }
                non_prod_hosts.append(host)
            else:
                print(f"Host {hosts[index]} does not match Prod or Non-Prod")
                sys.exit(1)
        index += 1

    # print("Prod Hosts")
    # print(prod_hosts)
    # print("Non-Prod Hosts")
    # print(non_prod_hosts)

    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    # print len of hosts from file
    print(f"Number of hosts read from CSV:          {len(hosts)}")
    # print len of missing hosts
    print(f"Number of host missing from Zabbix:     {len(missing)}")
    print(f"Number of avaible hosts to add:         {len(hosts) - len(missing)}")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    # print number of hosts in prod and non-prod
    print(f"Number of hosts in Prod list:           {len(prod_hosts)}")
    print(f"Number of hosts in Non-Prod list:       {len(non_prod_hosts)}")
    # print total number of hosts
    print(f"Total number of hosts to add:           {len(prod_hosts) + len(non_prod_hosts)}")

    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");
    # print prod hostgroup name
    print(f"Prod Hostgroup: {prod_name}")
    # print non-prod hostgroup name
    print(f"Non-Prod Hostgroup: {non_prod_name}")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~");

    # if dry-run is set, exit
    if dry_run is not None:
        print("Dry run, Exiting...")
        sys.exit(1)

    if force is None:
        # ask user if they want to continue
        answer = input("Do you want to continue adding hosts to hostgroup? (y/n): ")
        if answer.lower() == 'n':
            print("Exiting...")
            sys.exit(1)

    prod_array = []
    for host in prod_hosts:
        prod_array.append({
            "hostid": host
        })
    
    non_prod_array = []
    for host in non_prod_hosts:
        non_prod_array.append({
            "hostid": host
        })

    print("Adding hosts to hostgroups...")
    
    # add all hosts to prod hostgroup
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.massadd",
        "params": {
            "groups": [
                {
                    "groupid": prod
                },
            ],
            "hosts": prod_array,
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }
    try:
        prod_output = api_request(payload)
        print(prod_output)
    except:
        print("Error adding hosts to Prod hostgroup")
        print(prod_output)
        sys.exit(1)

    # add all hosts to non-prod hostgroup
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.massadd",
        "params": {
            "groups": [
                {
                    "groupid": non_prod
                },
            ],
            "hosts": non_prod_array,
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    try:
        non_prod_output = api_request(payload)
        print(non_prod_output)
    except:
        print("Error adding hosts to Non-Prod hostgroup")
        print(non_prod_output)
        sys.exit(1)    
    

    print("Hosts added to hostgroups!")
    sys.exit(0)

if __name__ == "__main__":
    main()