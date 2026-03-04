import csv
import os
import sys
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Creates web scenarios in Zabbix to monitor that web pages are reachable.
#
# Usage:
#   python create-web-scenarios.py <csv_file> <hostgroup_name> [--dry-run]
#
# CSV format (no header):
#   url,hostname
#
# Example CSV:
#   https://example.com,webserver-01
#   https://app.example.com/health,appserver-01
#
# The script will:
#   1. Look up each host by name in Zabbix
#   2. Verify the host belongs to the specified hostgroup
#   3. Create a web scenario on the host that checks the URL returns HTTP 200

def get_hostgroup_id_by_name(hostgroupname):
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": "extend",
            "filter": {
                "name": [hostgroupname]
            }
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }
    data = api_request(payload)
    if not data.get('result'):
        print(f"Error: hostgroup '{hostgroupname}' not found.")
        sys.exit(1)
    return data['result'][0]['groupid']

def get_host_id_by_name(hostname):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host"],
            "filter": {
                "host": [hostname]
            }
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }
    data = api_request(payload)
    if not data.get('result'):
        return None
    return data['result'][0]['hostid']

def create_web_scenario(hostid, url, hostname):
    # Use the URL as the scenario name for clarity
    scenario_name = f"Check {url}"

    payload = {
        "jsonrpc": "2.0",
        "method": "httptest.create",
        "params": {
            "name": scenario_name,
            "hostid": hostid,
            "steps": [
                {
                    "name": f"GET {url}",
                    "url": url,
                    "status_codes": "200",
                    "no": 1
                }
            ]
        },
        "auth": ZABBIX_API_token,
        "id": 1
    }

    data = api_request(payload)
    return data

def main():
    if len(sys.argv) < 3:
        print("Usage: python create-web-scenarios.py <csv_file> <hostgroup_name> [--dry-run]")
        print("")
        print("CSV format (no header):")
        print("  url,hostname")
        sys.exit(1)

    csv_file = sys.argv[1]
    hostgroupname = sys.argv[2]
    dry_run = "--dry-run" in sys.argv

    if not os.path.isfile(csv_file):
        print(f"Error: file '{csv_file}' not found.")
        sys.exit(1)

    # Verify the hostgroup exists
    groupid = get_hostgroup_id_by_name(hostgroupname)
    print(f"Host Group: {hostgroupname} (ID: {groupid})")

    # Read URL/host pairs from CSV
    entries = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            url = row[0].strip()
            hostname = row[1].strip()
            if url and hostname:
                entries.append((url, hostname))

    if not entries:
        print("No entries found in CSV file.")
        sys.exit(1)

    print(f"Found {len(entries)} web scenario(s) to create.")
    print("")

    if dry_run:
        print("=== DRY RUN (no changes will be made) ===")
        print("")

    errors = []
    for url, hostname in entries:
        hostid = get_host_id_by_name(hostname)
        if not hostid:
            msg = f"Host '{hostname}' not found in Zabbix, skipping {url}"
            print(msg)
            errors.append(msg)
            continue

        if dry_run:
            print(f"Would create web scenario on '{hostname}' (ID: {hostid}) for URL: {url}")
            continue

        result = create_web_scenario(hostid, url, hostname)

        if 'error' in result:
            msg = f"Error creating scenario for {url} on {hostname}: {result['error']['data']}"
            print(msg)
            errors.append(msg)
        else:
            httptestid = result['result']['httptestids'][0]
            print(f"Created web scenario for {url} on '{hostname}' (httptestid: {httptestid})")

    print("")
    if errors:
        print(f"Completed with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("All web scenarios created successfully." if not dry_run else "Dry run complete.")

if __name__ == "__main__":
    main()
