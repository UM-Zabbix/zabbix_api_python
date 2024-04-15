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