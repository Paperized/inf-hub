import json
from pathlib import Path

import keyring
import yaml

CONFIG_DIR = Path.home() / ".config" / "inf-hub"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYRING_SERVICE = "inf-hub"
LOCAL_INF_FILE = Path(".inf")

DEFAULT_TYPES = ("tokenId", "identityId", "projectId", "environment")


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


def _token_key_username(token_id: str) -> str:
    return f"tokenId:{token_id}"


def load_token_for_token_id(token_id: str | None):
    if not token_id:
        return None
    return keyring.get_password(KEYRING_SERVICE, _token_key_username(token_id))


def save_token_for_token_id(token_id: str, token: str):
    keyring.set_password(KEYRING_SERVICE, _token_key_username(token_id), token)


def delete_token_for_token_id(token_id: str):
    try:
        keyring.delete_password(KEYRING_SERVICE, _token_key_username(token_id))
    except keyring.errors.PasswordDeleteError:
        pass


def get_token_for_token_id_or_exit(token_id: str):
    token = load_token_for_token_id(token_id)
    if token:
        return token
    print(f"Error: missing token for tokenId '{token_id}'. Run 'ih register token --token-id {token_id}'.")
    raise SystemExit(1)


def load_tokens():
    config = load_config()
    raw = (config or {}).get("tokens", [])
    tokens = []
    for entry in raw:
        if isinstance(entry, dict):
            tid = entry.get("tokenId", "")
            if not tid:
                continue
            tokens.append(
                {
                    "tokenId": tid,
                    "orgId": entry.get("orgId", ""),
                }
            )
    return tokens


def get_token_ids():
    return [t["tokenId"] for t in load_tokens()]


def get_token_entry(token_id: str):
    for entry in load_tokens():
        if entry["tokenId"] == token_id:
            return entry
    return None


def save_token_entry(token_id: str, org_id: str):
    config = load_config() or {}
    tokens = config.get("tokens", [])
    normalized = []
    found = False
    for entry in tokens:
        if not isinstance(entry, dict):
            continue
        if entry.get("tokenId") == token_id:
            normalized.append({"tokenId": token_id, "orgId": org_id})
            found = True
        else:
            normalized.append(entry)
    if not found:
        normalized.append({"tokenId": token_id, "orgId": org_id})
    config["tokens"] = normalized
    save_config(config)


def remove_token_entry(token_id: str):
    config = load_config() or {}
    tokens = config.get("tokens", [])
    filtered = [t for t in tokens if isinstance(t, dict) and t.get("tokenId") != token_id]
    config["tokens"] = filtered
    save_config(config)


def get_tokens_or_exit():
    tokens = load_tokens()
    if not tokens:
        print("Error: no tokens configured. Run 'ih register token' first.")
        raise SystemExit(1)
    return tokens


def load_local_inf():
    if not LOCAL_INF_FILE.exists():
        return None
    with open(LOCAL_INF_FILE) as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Invalid .inf format: expected a YAML object with keys tokenId/projectId/environment.")
    return data


def save_local_inf(token_id, project_id, environment):
    payload = {
        "tokenId": token_id,
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
