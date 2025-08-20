import warnings
import requests
from os import environ as env
from dotenv import find_dotenv, load_dotenv

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
else:
    ENV_FILE = "PATH_TO_ENV_FILE"
    load_dotenv(ENV_FILE)
    
ZABBIX_API_URL = env.get("ZABBIX_API_URL")
ZABBIX_API_token = env.get("ZABBIX_API_token")

headers = {
    'Authorization': 'Bearer ' + ZABBIX_API_token,
}

# post request to zabbix api
def api_request(payload) -> dict:
    response = requests.post(ZABBIX_API_URL, json=payload, headers=headers, verify=False)
    return response.json()

# update templates for a host
def update_templates(template_ids, host_id) -> dict | None:
    templates_list = []
    for template_id in template_ids:
        templates_list.append({"templateid": template_id})

    payload = {
        "jsonrpc": "2.0",
        "method": "host.update",
        "params": {
            "hostid": host_id,
            "templates": templates_list
        },
        "id": 1
    }

    data = api_request(payload)
    return data

# return template id for a given name
def get_template_id(name) -> str | None:
    payload = {
        "jsonrpc": "2.0",
        "method": "template.get",
        "params": {
            "output": "extend",
            "filter": {
                "name": [
                    name
                ]
            }
        },
        "id": 1,
    }
    
    data = api_request(payload)
    
    try:
        return data['result'][0]['templateid']
    except:
        return None

def main():
    warnings.filterwarnings('ignore')

    # Specify the host ID
    host_id = 10629
    # Specify the template names to link
    template_names = ["null", "wangbicj - testing 2"]

    # Get template IDs
    template_ids = []
    for name in template_names:
        template_id = get_template_id(name)
        if template_id:
            template_ids.append(template_id)
        else:
            print(f"Template '{name}' not found.")

    # Update templates for the host and print the output
    output = update_templates(template_ids, host_id)
    print(output)

if __name__ == "__main__":
    main()
