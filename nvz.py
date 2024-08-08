import csv
import os
import sys
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# get number of hosts in zabbix
def get_zabbix_hosts():
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": "extend",
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    data = api_request(payload)
    return len(data['result'])

def main():
    # read arguments
    if len(sys.argv) < 2:
        print("Usage: python nvz.py <nagios_count>")
        sys.exit(1)

    nag_count = sys.argv[1]

    print("Nagios count: " + nag_count)

    # get number of hosts in zabbix
    zabbix_hosts = get_zabbix_hosts()
    print("Zabbix hosts: " + str(zabbix_hosts))
    

if __name__ == "__main__":
    main()