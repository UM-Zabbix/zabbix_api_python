import requests
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