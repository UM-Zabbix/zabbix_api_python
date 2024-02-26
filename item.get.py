import sys
import datetime
import pprint
import warnings
from api import *

def hostid(hostname):
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
    
    data = api_request(payload)
    hostid = data['result'][0]['hostid']
    
    return hostid

def get_lastclock(hostname, key):
    host_id = hostid(hostname)
    payload={
        "jsonrpc": "2.0",
        "method": "item.get",
        "params": {
            "hostids": [host_id],
            "search": {
                "key_": "agent.ping"
            },
            'output': ["lastclock"],
        },
        
        "id": 1
    }
    
    data = api_request(payload)
    
    return data

def main():
    warnings.filterwarnings('ignore')
    
    if len(sys.argv) < 2:
        print("Usage: python item.get.py <option>")
        sys.exit(1)
    
    selected = sys.argv[1]
    
    # get last clock for an item on a host
    if selected == "--all" or selected == "1":    
        # last time for agent.ping on host
        ouptut = get_lastclock("aquamon.dsc.umich.edu", "agent.ping")
        print(ouptut)
        print()
        print("Last time for agent.ping on host: ", ouptut['result'][0]['lastclock'])
        
if __name__ == "__main__":
    main()