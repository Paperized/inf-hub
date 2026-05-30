import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "infisical-utils"
CONFIG_FILE = CONFIG_DIR / "config.json"

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
    config = load_config()
    if not config:
        print("Error: not configured. Run 'infisical-utils init' first.")
        raise SystemExit(1)
    return config


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
