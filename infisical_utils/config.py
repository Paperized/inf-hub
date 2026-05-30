import json
from pathlib import Path

import keyring
import yaml

CONFIG_DIR = Path.home() / ".config" / "infisical-utils"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYRING_SERVICE = "infisical-utils"
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


def get_config_or_exit():
    token = load_token_secure()
    config = load_config()
    legacy_token = (config or {}).get("token")
    if not token and not legacy_token:
        print("Error: not configured. Run 'infisical-utils init' first.")
        raise SystemExit(1)
    if not config:
        config = {}
    config["token"] = token or legacy_token
    return config


def load_token_secure():
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)


def save_token_secure(token):
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)


def delete_token_secure():
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass


def get_token_or_exit():
    token = load_token_secure()
    if token:
        return token

    config = load_config() or {}
    legacy_token = config.get("token")
    if legacy_token:
        return legacy_token

    print("Error: not configured. Run 'infisical-utils init' first.")
    raise SystemExit(1)


def get_default(key):
    config = load_config()
    if not config:
        return None
    entry = config.get("defaults", {}).get(key)
    if entry is None:
        return None
    if isinstance(entry, dict):
        return entry.get("value")
    return entry


def set_default(key, value):
    config = load_config() or {}
    if "defaults" not in config:
        config["defaults"] = {}
    config["defaults"][key] = {"value": value}
    save_config(config)


def remove_default(key):
    config = load_config()
    if not config or "defaults" not in config:
        return
    config["defaults"].pop(key, None)
    save_config(config)


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
