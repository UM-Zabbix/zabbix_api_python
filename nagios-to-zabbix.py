import csv
import re
import socket
import sys
import urllib3
from api import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Migrates Nagios hosts to Zabbix from the shared_NagiosConfig CSV exports.
#
# Usage:
#   python nagios-to-zabbix.py [--dry-run] [--group <nagios_group>] [--skip-web] [--skip-hosts]
#
# Options:
#   --dry-run        Show what would be done without making changes
#   --group <name>   Only process hosts from a specific Nagios host group
#   --skip-web       Skip creating web scenarios
#   --skip-hosts     Skip creating real hosts (only do web scenarios)
#   --host <name>    Only process a single host by Nagios name
#   --report-only    Just print the categorized host report, no API calls

HOSTS_CSV = "csv/shared_NagiosConfig-updated-02032026 - Hosts.csv"
GROUPS_CSV = "csv/shared_NagiosConfig-updated-02032026 - Host Groups.csv"
SERVICES_CSV = "csv/shared_NagiosConfig-updated-02032026 - Services.csv"

PROXY_GROUP_NAME = "On-prem Proxies"
BASE_HOSTGROUP = "Ann Arbor/DENT/Informatics"
PROD_HOSTGROUP = "Ann Arbor/DENT/Informatics/Prod"

ICMP_PING_TEMPLATE = "ICMP Ping"
ICMP_PING_IP_TEMPLATE = "ICMP Ping - IP"

# Nagios host groups that are web-scenario-only (no real device, just URL checks)
WEB_ONLY_GROUPS = {"miserver_HTTPS", "miserver_Calendars"}


# ── Zabbix API helpers ──────────────────────────────────────────────────────

def get_all_zabbix_hosts():
    """Return a (set, dict) of host identifiers currently in Zabbix.

    The set includes both the technical name (host) and visible name (name)
    for each host, plus their lowercased variants, so that lookups work even
    when Nagios uses short names and Zabbix stores FQDNs (or vice-versa).

    The dict maps every name variant (lowercased) to its hostid, so callers
    can resolve a hostid without extra API calls.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"output": ["host", "name"]},
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    hosts = set()
    host_ids = {}
    for h in data.get("result", []):
        hid = h["hostid"]
        hosts.add(h["host"])
        hosts.add(h["name"])
        hosts.add(h["host"].lower())
        hosts.add(h["name"].lower())
        host_ids[h["host"].lower()] = hid
        host_ids[h["name"].lower()] = hid
    return hosts, host_ids


def host_exists_in_zabbix(name, address, zabbix_hosts):
    """Check whether a Nagios host already exists in Zabbix.

    Matches on the host name, its address/FQDN, or the short-name
    prefix of the address (everything before the first dot), all
    case-insensitively.
    """
    candidates = {name, name.lower()}
    if address:
        candidates.add(address)
        candidates.add(address.lower())
        # Also try the short-name portion of the address
        short = address.split(".")[0]
        candidates.add(short)
        candidates.add(short.lower())
    return bool(candidates & zabbix_hosts)


def find_host_id(name, address, zabbix_host_ids):
    """Look up the Zabbix hostid for a Nagios host from the pre-built dict.

    Tries the same candidate set as host_exists_in_zabbix (name, address,
    short name, all lowercased). Returns the hostid or None.
    """
    candidates = [name.lower()]
    if address:
        candidates.append(address.lower())
        short = address.split(".")[0].lower()
        candidates.append(short)
    for c in candidates:
        if c in zabbix_host_ids:
            return zabbix_host_ids[c]
    return None


def is_short_name(address):
    """Return True if address is a short hostname (no dots, not an IP)."""
    return bool(address) and "." not in address


def resolve_hostname(name):
    """Resolve a short hostname to its FQDN via DNS.
    Returns the FQDN if resolution adds domain info, or None if
    resolution fails or returns the same short name back.
    """
    try:
        info = socket.getaddrinfo(name, None, flags=socket.AI_CANONNAME)
        fqdn = info[0][3]
        if fqdn and fqdn != name:
            return fqdn
    except socket.gaierror:
        pass
    return None


def add_hosts_to_group(host_ids, groupid, dry_run=False):
    """Add hosts to a host group using hostgroup.massadd (preserves existing memberships)."""
    if not host_ids:
        return True
    if dry_run:
        print(f"  [DRY RUN] Would add {len(host_ids)} host(s) to group {groupid}")
        return True
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.massadd",
        "params": {
            "groups": [{"groupid": groupid}],
            "hosts": [{"hostid": hid} for hid in host_ids],
        },
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if "error" in data:
        print(f"  ERROR adding hosts to group: {data['error']['data']}")
        return False
    return True


def get_or_create_hostgroup(name, dry_run=False):
    """Return groupid for the named host group, creating it if needed."""
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {"output": ["groupid"], "filter": {"name": [name]}},
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if data.get("result"):
        return data["result"][0]["groupid"]

    if dry_run:
        print(f"  [DRY RUN] Would create host group: {name}")
        return None

    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.create",
        "params": {"name": name},
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if "error" in data:
        print(f"  ERROR creating host group '{name}': {data['error']['data']}")
        return None
    gid = data["result"]["groupids"][0]
    print(f"  Created host group: {name} (groupid: {gid})")
    return gid


def get_proxy_group_id(name):
    payload = {
        "jsonrpc": "2.0",
        "method": "proxygroup.get",
        "params": {"output": "extend", "selectProxies": ["proxyid", "name"]},
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    for pg in data.get("result", []):
        if pg["name"] == name:
            return pg["proxy_groupid"]
    return None


def get_template_id(name):
    """Return the templateid for the named template, or None."""
    payload = {
        "jsonrpc": "2.0",
        "method": "template.get",
        "params": {"output": ["templateid"], "filter": {"host": [name]}},
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if data.get("result"):
        return data["result"][0]["templateid"]
    return None


def create_zabbix_host(hostname, address, groupid, proxy_groupid, dry_run=False,
                       templateid=None):
    """Create a host with an ICMP ping agent interface."""
    if dry_run:
        tmpl_note = f", template id {templateid}" if templateid else ""
        print(f"  [DRY RUN] Would create host: {hostname} ({address}{tmpl_note})")
        return True

    params = {
        "host": hostname,
        "groups": [{"groupid": groupid}],
        "interfaces": [
            {
                "type": 1,      # agent
                "main": 1,
                "useip": 1 if re.match(r"^\d+\.\d+\.\d+\.\d+$", address) else 0,
                "ip": address if re.match(r"^\d+\.\d+\.\d+\.\d+$", address) else "",
                "dns": address if not re.match(r"^\d+\.\d+\.\d+\.\d+$", address) else "",
                "port": "10050",
            }
        ],
    }
    if templateid:
        params["templates"] = [{"templateid": templateid}]
    if proxy_groupid:
        params["monitored_by"] = 2
        params["proxy_groupid"] = proxy_groupid

    payload = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": params,
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if "error" in data:
        print(f"  ERROR creating host '{hostname}': {data['error']['data']}")
        return False
    hid = data["result"]["hostids"][0]
    print(f"  Created host: {hostname} (hostid: {hid})")
    return True


def link_templates_to_existing_hosts(host_ids, fqdn_templateid, ip_templateid,
                                     dry_run=False):
    """Link the appropriate ICMP Ping template to existing hosts.

    Queries each host's interfaces and existing templates, then links
    'ICMP Ping' (for DNS hosts) or 'ICMP Ping - IP' (for IP hosts)
    if not already present.
    """
    if not host_ids or (not fqdn_templateid and not ip_templateid):
        return
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host"],
            "hostids": host_ids,
            "selectInterfaces": ["useip"],
            "selectParentTemplates": ["templateid"],
        },
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    for host in data.get("result", []):
        uses_ip = host["interfaces"][0]["useip"] == "1" if host.get("interfaces") else False
        needed_id = ip_templateid if uses_ip else fqdn_templateid
        if not needed_id:
            continue
        existing_ids = {t["templateid"] for t in host.get("parentTemplates", [])}
        if needed_id in existing_ids:
            continue
        new_templates = [{"templateid": tid} for tid in existing_ids]
        new_templates.append({"templateid": needed_id})
        if dry_run:
            tmpl_name = ICMP_PING_IP_TEMPLATE if uses_ip else ICMP_PING_TEMPLATE
            print(f"  [DRY RUN] Would link template '{tmpl_name}' to host {host['host']}")
            continue
        update_payload = {
            "jsonrpc": "2.0",
            "method": "host.update",
            "params": {
                "hostid": host["hostid"],
                "templates": new_templates,
            },
            "auth": ZABBIX_API_token,
            "id": 1,
        }
        result = api_request(update_payload)
        if "error" in result:
            print(f"  ERROR linking template to {host['host']}: {result['error']['data']}")
        else:
            tmpl_name = ICMP_PING_IP_TEMPLATE if uses_ip else ICMP_PING_TEMPLATE
            print(f"  Linked template '{tmpl_name}' to host {host['host']}")


def get_host_id(hostname):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"output": ["hostid"], "filter": {"host": [hostname]}},
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if data.get("result"):
        return data["result"][0]["hostid"]
    return None


def create_web_scenario(hostid, url, scenario_name, dry_run=False, host_name=None):
    if dry_run:
        on_host = f" on host {host_name}" if host_name else ""
        print(f"  [DRY RUN] Would create web scenario: {scenario_name} -> {url}{on_host}")
        return True

    payload = {
        "jsonrpc": "2.0",
        "method": "httptest.create",
        "params": {
            "name": scenario_name,
            "hostid": hostid,
            "steps": [
                {
                    "name": f"GET {url}"[:64],
                    "url": url,
                    "status_codes": "200",
                    "no": 1,
                }
            ],
        },
        "auth": ZABBIX_API_token,
        "id": 1,
    }
    data = api_request(payload)
    if "error" in data:
        print(f"  ERROR creating web scenario '{scenario_name}': {data['error']['data']}")
        return False
    tid = data["result"]["httptestids"][0]
    print(f"  Created web scenario: {scenario_name} (httptestid: {tid})")
    return True


# ── CSV parsing ─────────────────────────────────────────────────────────────

def parse_hosts_csv():
    """Return dict: hostname -> {alias, address, ...}"""
    hosts = {}
    with open(HOSTS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Host Name"].strip()
            hosts[name] = {
                "alias": row["Alias/Description"].strip(),
                "address": row["Address"].strip(),
            }
    return hosts


def parse_hostgroups_csv():
    """Return dict: group_name -> list of host names."""
    groups = {}
    with open(GROUPS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gname = row["Group Name"].strip()
            members_raw = row.get("Host Members", "").strip()
            members = [m.strip() for m in members_raw.split(",") if m.strip()]
            groups[gname] = members
    return groups


def parse_services_csv():
    """Return dict: hostname -> list of {description, check_command}."""
    services = {}
    with open(SERVICES_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            host = row["Host"].strip()
            desc = row["Description"].strip()
            cmd = row["Check Command"].strip()
            if host not in services:
                services[host] = []
            services[host].append({"description": desc, "check_command": cmd})
    return services


def extract_url_from_alias(alias):
    """Extract URL from Nagios alias like 'ExtRef Biopsy Form ( https://referrals.dent.umich.edu/biopsy/form )'"""
    m = re.search(r"(https?://\S+?)(?:\s|\))", alias)
    if m:
        return m.group(1)
    return None


def extract_url_from_check_command(cmd):
    """Extract URL from check_http command like 'check_http!-u https://... !-S'"""
    m = re.search(r"(https?://\S+)", cmd)
    if m:
        url = m.group(1).rstrip("!")
        return url
    return None


def get_backend_server(url):
    """Extract the hostname from a URL to use as the Zabbix parent host."""
    m = re.match(r"https?://([^/]+)", url)
    if m:
        return m.group(1)
    return None


# ── Main logic ──────────────────────────────────────────────────────────────

def build_host_to_groups(hostgroups):
    """Invert hostgroups dict: return hostname -> set of group names."""
    h2g = {}
    for gname, members in hostgroups.items():
        for m in members:
            h2g.setdefault(m, set()).add(gname)
    return h2g


def categorize(hosts, hostgroups, services):
    """
    Return three dicts:
      web_scenarios: backend_server -> [{nagios_name, url, scenario_name}]
      real_hosts:    nagios_group -> [{name, address}]
      skipped:       list of (name, reason)
    """
    h2g = build_host_to_groups(hostgroups)

    web_scenarios = {}  # backend_server -> list of scenario dicts
    real_hosts = {}     # nagios_group -> list of host dicts
    skipped = []

    for name, info in hosts.items():
        groups = h2g.get(name, set())

        # Determine if this is a web-only host
        is_web = bool(groups & WEB_ONLY_GROUPS)

        if is_web:
            # Try to get the URL from the service check_command first
            url = None
            if name in services:
                for svc in services[name]:
                    url = extract_url_from_check_command(svc["check_command"])
                    if url:
                        break
            # Fall back to alias
            if not url:
                url = extract_url_from_alias(info["alias"])

            if not url:
                skipped.append((name, "web-only host but could not extract URL"))
                continue

            backend = get_backend_server(url)
            if not backend:
                skipped.append((name, f"could not parse backend from URL: {url}"))
                continue

            web_scenarios.setdefault(backend, []).append({
                "nagios_name": name,
                "url": url,
                "scenario_name": f"{name}",
            })
        else:
            # Skip localhost
            if name == "localhost":
                skipped.append((name, "localhost - skip"))
                continue

            # Determine which Nagios group to use as the Zabbix sub-group
            # Pick the most specific non-test group, or fall back
            group = "ungrouped"
            for g in groups:
                if g not in WEB_ONLY_GROUPS:
                    group = g
                    break

            real_hosts.setdefault(group, []).append({
                "name": name,
                "address": info["address"],
            })

    return web_scenarios, real_hosts, skipped


def print_report(web_scenarios, real_hosts, skipped, zabbix_hosts, zabbix_host_ids):
    print("=" * 70)
    print("NAGIOS TO ZABBIX MIGRATION REPORT")
    print("=" * 70)

    print(f"\nTotal hosts already in Zabbix: {len(zabbix_hosts)}")

    # Real hosts
    print(f"\n{'─' * 70}")
    print("REAL HOSTS (need Zabbix host objects)")
    print(f"{'─' * 70}")
    total_real = 0
    total_real_new = 0
    for group in sorted(real_hosts.keys()):
        hosts_list = real_hosts[group]
        new = [h for h in hosts_list if not host_exists_in_zabbix(h["name"], h.get("address", ""), zabbix_hosts)]
        existing = [h for h in hosts_list if host_exists_in_zabbix(h["name"], h.get("address", ""), zabbix_hosts)]
        total_real += len(hosts_list)
        total_real_new += len(new)
        zabbix_group = f"{BASE_HOSTGROUP}/{group}"
        print(f"\n  {zabbix_group}:")
        print(f"    Total: {len(hosts_list)}  |  New: {len(new)}  |  Already in Zabbix: {len(existing)}")
        if existing:
            print(f"    Existing: {', '.join(h['name'] for h in existing)}")
        if new:
            for h in new:
                addr = h['address']
                note = ""
                if is_short_name(addr):
                    fqdn = resolve_hostname(addr)
                    note = f" -> {fqdn}" if fqdn else " (unresolvable)"
                print(f"    + {h['name']:40s}  {addr}{note}")

    total_existing = total_real - total_real_new
    print(f"\n  TOTAL REAL HOSTS: {total_real}  |  NEW: {total_real_new}  |  EXISTING: {total_existing}")
    if total_existing > 0:
        print(f"\n  NOTE: {total_existing} existing host(s) will be added to {PROD_HOSTGROUP}")

    # Web scenarios
    print(f"\n{'─' * 70}")
    print("WEB SCENARIOS (URL monitors attached to backend server hosts)")
    print(f"{'─' * 70}")
    total_web = 0
    for backend in sorted(web_scenarios.keys()):
        scenarios = web_scenarios[backend]
        total_web += len(scenarios)
        backend_in_zabbix = host_exists_in_zabbix(backend, backend, zabbix_hosts)
        print(f"\n  Backend host: {backend}  {'(exists in Zabbix)' if backend_in_zabbix else '(NEEDS CREATION)'}")
        for s in scenarios:
            print(f"    + {s['scenario_name']:40s}  {s['url']}")

    print(f"\n  TOTAL WEB SCENARIOS: {total_web}")

    # Skipped
    if skipped:
        print(f"\n{'─' * 70}")
        print("SKIPPED")
        print(f"{'─' * 70}")
        for name, reason in skipped:
            print(f"  {name}: {reason}")

    print(f"\n{'=' * 70}")
    print(f"SUMMARY:  {total_real_new} new hosts to create  |  {total_web} web scenarios to create  |  {total_existing} existing to add to Prod")
    print(f"{'=' * 70}")


def execute_migration(web_scenarios, real_hosts, skipped, zabbix_hosts,
                      zabbix_host_ids, dry_run=False, skip_web=False,
                      skip_hosts=False, only_group=None, only_host=None):

    proxy_groupid = None
    if not dry_run:
        proxy_groupid = get_proxy_group_id(PROXY_GROUP_NAME)
        if not proxy_groupid:
            print(f"ERROR: Proxy group '{PROXY_GROUP_NAME}' not found.")
            sys.exit(1)
        print(f"Using proxy group: {PROXY_GROUP_NAME} (id: {proxy_groupid})")
    else:
        print("=== DRY RUN MODE ===\n")

    if only_host:
        print(f"Single host mode: {only_host}")

    fqdn_templateid = get_template_id(ICMP_PING_TEMPLATE)
    ip_templateid = get_template_id(ICMP_PING_IP_TEMPLATE)
    if not dry_run and not fqdn_templateid:
        print(f"WARNING: Template '{ICMP_PING_TEMPLATE}' not found in Zabbix")
    if not dry_run and not ip_templateid:
        print(f"WARNING: Template '{ICMP_PING_IP_TEMPLATE}' not found in Zabbix")
    if fqdn_templateid:
        print(f"Using template: {ICMP_PING_TEMPLATE} (id: {fqdn_templateid})")
    if ip_templateid:
        print(f"Using template: {ICMP_PING_IP_TEMPLATE} (id: {ip_templateid})")

    errors = []
    created_hosts = 0
    created_scenarios = 0
    skipped_existing = 0

    # ── Create real hosts ───────────────────────────────────────────────
    existing_host_ids = []
    if not skip_hosts:
        print("\n── Creating Real Hosts ──\n")
        for group in sorted(real_hosts.keys()):
            if only_group and group != only_group:
                continue

            zabbix_group = f"{BASE_HOSTGROUP}/{group}"
            print(f"\nGroup: {zabbix_group}")

            groupid = get_or_create_hostgroup(zabbix_group, dry_run)

            for h in real_hosts[group]:
                if only_host and h["name"] != only_host:
                    continue
                if host_exists_in_zabbix(h["name"], h.get("address", ""), zabbix_hosts):
                    skipped_existing += 1
                    hid = find_host_id(h["name"], h.get("address", ""), zabbix_host_ids)
                    if hid:
                        existing_host_ids.append(hid)
                    continue

                address = h["address"]
                if is_short_name(address):
                    fqdn = resolve_hostname(address)
                    if fqdn:
                        print(f"  Resolved {address} -> {fqdn}")
                        address = fqdn
                    else:
                        print(f"  WARNING: Could not resolve {address}, using as-is")

                is_ip = bool(re.match(r"^\d+\.\d+\.\d+\.\d+$", address))
                tmpl_id = ip_templateid if is_ip else fqdn_templateid
                ok = create_zabbix_host(h["name"], address, groupid,
                                        proxy_groupid, dry_run,
                                        templateid=tmpl_id)
                if ok:
                    created_hosts += 1
                else:
                    errors.append(f"Failed to create host: {h['name']}")

        # ── Add existing hosts to Prod hostgroup ─────────────────────────
        if existing_host_ids:
            prod_groupid = get_or_create_hostgroup(PROD_HOSTGROUP, dry_run)
            if prod_groupid or dry_run:
                add_hosts_to_group(existing_host_ids, prod_groupid, dry_run)
            action = "Would add" if dry_run else "Added"
            print(f"\n{action} {len(existing_host_ids)} existing host(s) to {PROD_HOSTGROUP}")
            link_templates_to_existing_hosts(existing_host_ids, fqdn_templateid,
                                             ip_templateid, dry_run)

    # ── Create web scenario hosts + scenarios ───────────────────────────
    if not skip_web and not only_host:
        print("\n── Creating Web Scenario Hosts & Scenarios ──\n")
        web_group = f"{BASE_HOSTGROUP}/miserver_HTTPS"
        web_groupid = get_or_create_hostgroup(web_group, dry_run)

        for backend in sorted(web_scenarios.keys()):
            if only_group and only_group not in ("miserver_HTTPS", "miserver_Calendars"):
                continue

            print(f"\nBackend: {backend}")
            hostid = get_host_id(backend)
            # Try short name if FQDN lookup failed
            if not hostid and "." in backend:
                short_name = backend.split(".")[0]
                hostid = get_host_id(short_name)
                if hostid:
                    print(f"  Found backend under short name: {short_name}")

            if not hostid:
                # Create the backend server as a Zabbix host
                ok = create_zabbix_host(backend, backend, web_groupid,
                                        proxy_groupid, dry_run)
                if ok and not dry_run:
                    hostid = get_host_id(backend)
                    created_hosts += 1
                elif not ok:
                    errors.append(f"Failed to create backend host: {backend}")
                    continue

            for scenario in web_scenarios[backend]:
                ok = create_web_scenario(
                    hostid,
                    scenario["url"],
                    scenario["scenario_name"],
                    dry_run,
                    host_name=backend,
                )
                if ok:
                    created_scenarios += 1
                else:
                    errors.append(f"Failed to create web scenario: {scenario['scenario_name']}")

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    action = "Would create" if dry_run else "Created"
    print(f"{action} {created_hosts} host(s), {created_scenarios} web scenario(s)")
    print(f"Skipped {skipped_existing} host(s) already in Zabbix")
    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
    print(f"{'=' * 70}")


def main():
    dry_run = "--dry-run" in sys.argv
    skip_web = "--skip-web" in sys.argv
    skip_hosts = "--skip-hosts" in sys.argv
    report_only = "--report-only" in sys.argv

    only_group = None
    if "--group" in sys.argv:
        idx = sys.argv.index("--group")
        if idx + 1 < len(sys.argv):
            only_group = sys.argv[idx + 1]

    only_host = None
    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            only_host = sys.argv[idx + 1]

    print("Parsing Nagios CSV files...")
    hosts = parse_hosts_csv()
    hostgroups = parse_hostgroups_csv()
    services = parse_services_csv()

    print(f"  Hosts: {len(hosts)}  |  Host Groups: {len(hostgroups)}  |  Service entries: {sum(len(v) for v in services.values())}")

    web_scenarios, real_hosts, skipped = categorize(hosts, hostgroups, services)

    if report_only:
        print("\nQuerying Zabbix for existing hosts...")
        zabbix_hosts, zabbix_host_ids = get_all_zabbix_hosts()
        print_report(web_scenarios, real_hosts, skipped, zabbix_hosts, zabbix_host_ids)
        return

    print("\nQuerying Zabbix for existing hosts...")
    zabbix_hosts, zabbix_host_ids = get_all_zabbix_hosts()
    print(f"  Found {len(zabbix_hosts)} existing hosts in Zabbix")

    # Always print report first
    print_report(web_scenarios, real_hosts, skipped, zabbix_hosts, zabbix_host_ids)

    if not dry_run:
        print("\n*** LIVE MODE - Changes will be made to Zabbix ***")
        resp = input("Proceed? (yes/no): ").strip().lower()
        if resp != "yes":
            print("Aborted.")
            return

    execute_migration(web_scenarios, real_hosts, skipped, zabbix_hosts,
                      zabbix_host_ids, dry_run=dry_run, skip_web=skip_web,
                      skip_hosts=skip_hosts, only_group=only_group,
                      only_host=only_host)


if __name__ == "__main__":
    main()
