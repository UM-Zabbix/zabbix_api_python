# export a list of all hosts from Zabbix to a CSV file.

import csv
import os
import sys
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# get number of hosts in zabbix
def get_zabbix_hosts_list():
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
    return data['result']

def main():
    print("Hello")
    # read arguments
    if len(sys.argv) < 2:
        print("Usage: python allhosts.py <output_file>")
        sys.exit(1)

    output_file = sys.argv[1]

    # get number of hosts in zabbix
    zabbix_hosts = get_zabbix_hosts_list()
    print("Zabbix hosts: " + str(len(zabbix_hosts)))

    with open(output_file, mode='w') as file:
        writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Host', 'Host ID'])
        for host in zabbix_hosts:
            writer.writerow([host['host'], host['hostid']])


if __name__ == "__main__":
    main()