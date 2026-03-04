# Zabbix API Python Examples

Create .env file in repo root directory with the following variables:

``` shell
ZABBIX_API_URL=https://zabbix.it.umich.edu/api_jsonrpc.php
ZABBIX_API_token=12345faketoken67890
```

## maintenance.get

Examples:
  
1. Does the input host have a maintenance window?
2. Print all current maintenance windows
3. Print all hosts in maintenance

Run:

``` shell
python maintenance.get.py EXAMPLE_NUMBER

python maintenance.get.py 3
```

or

``` shell
python maintenance.get.py --all
```

## item.get

Examples:
  
1. Get last time for zabbix agent ping


## add-hostgroup.py
- Script adds hosts to hostgroups based on csv input
- Give a csv containing hostnames and whether prod or non-prod

## create-hosts.py
- Script creates new hosts in Zabbix that are monitored by a proxy group
- Hosts to add and hostgroup to add them to are defined in the python file

## create-web-scenarios.py
- Creates web scenarios in Zabbix to monitor that web pages are reachable
- Each scenario does a GET request and expects HTTP 200

Create a CSV file (no header) with `url,hostname` pairs:

```
https://example.com,webserver-01
https://app.example.com/health,appserver-01
https://status.example.com,webserver-02
```

Run:

``` shell
# Preview what will be created
python create-web-scenarios.py urls.csv "Ann Arbor/ITS/TestTeam/Prod" --dry-run

# Actually create the scenarios
python create-web-scenarios.py urls.csv "Ann Arbor/ITS/TestTeam/Prod"
```

## nagios-to-zabbix.py

Migrates hosts from a Nagios CSV export into Zabbix. Parses the three
`shared_NagiosConfig` CSV files (Hosts, Host Groups, Services) and:

- Categorizes each Nagios host as either a **real host** (gets an ICMP
  interface) or a **web scenario** (URL monitor attached to the backend
  server host)
- Creates Zabbix host groups under `Ann Arbor/DENT/Informatics/<nagios_group>`
- Skips hosts that already exist in Zabbix
- Assigns all hosts to the **On-prem Proxies** proxy group

### CSV files expected in `csv/`

```
shared_NagiosConfig-updated-02032026 - Hosts.csv
shared_NagiosConfig-updated-02032026 - Host Groups.csv
shared_NagiosConfig-updated-02032026 - Services.csv
```

### Usage

``` shell
# See a report of what would be migrated (no changes made)
python nagios-to-zabbix.py --report-only

# Simulate the full migration (calls Zabbix API to check existing hosts, but creates nothing)
python nagios-to-zabbix.py --dry-run

# Run the migration (prompts for confirmation before making changes)
python nagios-to-zabbix.py

# Only process a single Nagios host group
python nagios-to-zabbix.py --dry-run --group simlab

# Only create real hosts, skip web scenarios
python nagios-to-zabbix.py --dry-run --skip-web

# Only create web scenarios, skip real hosts
python nagios-to-zabbix.py --dry-run --skip-hosts
```