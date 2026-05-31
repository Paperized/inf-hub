import json
from pathlib import Path

import keyring
import yaml

CONFIG_DIR = Path.home() / ".config" / "inf-hub"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYRING_SERVICE = "inf-hub"
KEYRING_USERNAME = "default-token"
LOCAL_INF_FILE = Path(".inf")

DEFAULT_TYPES = ("orgId", "identityId", "projectId", "environment")


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    CONFIG_FILE.chmod(0o600)


def load_token_secure():
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)


def save_token_secure(token):
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)


def _org_token_username(org_id):
    return f"orgId:{org_id}"


def load_token_for_org(org_id):
    if not org_id:
        return None
    return keyring.get_password(KEYRING_SERVICE, _org_token_username(org_id))


def save_token_for_org(org_id, token):
    keyring.set_password(KEYRING_SERVICE, _org_token_username(org_id), token)


def get_token_for_org_or_exit(org_id):
    token = load_token_for_org(org_id)
    if token:
        return token
    print(f"Error: missing token for org '{org_id}'. Run 'ih init token --org-id {org_id}'.")
    raise SystemExit(1)


def load_orgs():
    config = load_config()
    raw = (config or {}).get("orgs", [])
    orgs = []
    for entry in raw:
        if isinstance(entry, str):
            orgs.append({"id": entry, "name": entry})
        elif isinstance(entry, dict):
            orgs.append({"id": entry.get("id", ""), "name": entry.get("name", entry.get("id", ""))})
    return orgs


def get_org_ids():
    return [o["id"] for o in load_orgs()]


def save_org(org_id, org_name=None):
    config = load_config() or {}
    orgs = config.get("orgs", [])
    normalized = []
    found = False
    for entry in orgs:
        if isinstance(entry, str):
            if entry == org_id:
                normalized.append({"id": org_id, "name": org_name or org_id})
                found = True
            else:
                normalized.append({"id": entry, "name": entry})
        elif isinstance(entry, dict):
            if entry.get("id") == org_id:
                normalized.append({"id": org_id, "name": org_name or entry.get("name", org_id)})
                found = True
            else:
                normalized.append(entry)
    if not found:
        normalized.append({"id": org_id, "name": org_name or org_id})
    config["orgs"] = normalized
    save_config(config)


def get_orgs_or_exit():
    orgs = load_orgs()
    if not orgs:
        print("Error: no organizations configured. Run 'ih init token' first.")
        raise SystemExit(1)
    return orgs


def load_local_inf():
    if not LOCAL_INF_FILE.exists():
        return None
    with open(LOCAL_INF_FILE) as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Invalid .inf format: expected a YAML object with keys orgId/projectId/environment.")
    return data


def save_local_inf(org_id, project_id, environment):
    payload = {
        "orgId": org_id,
        "projectId": project_id,
        "environment": environment,
    }
    with open(LOCAL_INF_FILE, "w") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def ensure_local_repo_or_exit():
    if not LOCAL_INF_FILE.exists():
        print("Error: repository not initialized in current directory. Run 'ih init folder' first.")
        raise SystemExit(1)


def set_local_value(key, value):
    ensure_local_repo_or_exit()
    data = load_local_inf() or {}
    data[key] = value
    with open(LOCAL_INF_FILE, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def remove_local_value(key):
    ensure_local_repo_or_exit()
    data = load_local_inf() or {}
    data.pop(key, None)
    with open(LOCAL_INF_FILE, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
