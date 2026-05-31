import os
from argparse import Namespace

from inf_hub.api import InfisicalAPI
from inf_hub.config import get_token_entry, get_token_for_token_id_or_exit, get_token_ids, load_local_inf
from inf_hub.errors import ConfigError


def parse_id(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split("|")
    return parts[-1].strip()


def load_local_inf_safe() -> dict | None:
    try:
        return load_local_inf()
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def effective_local_value(key: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    local_inf = load_local_inf_safe()
    if local_inf is not None and local_inf.get(key):
        return local_inf.get(key)
    return None


def resolve_token_id(args: Namespace, allow_prompt: bool, interactive_token_selector) -> str | None:
    explicit = parse_id(getattr(args, "token_id", None)) if hasattr(args, "token_id") else None
    token_id = explicit or effective_local_value("tokenId")
    if token_id:
        token_ids = get_token_ids()
        if token_ids and token_id not in token_ids:
            raise ConfigError(f"tokenId '{token_id}' not found in configured tokens. Run 'ih register token' to add it.")
    if not token_id and allow_prompt:
        token_id = interactive_token_selector()
    return token_id


def build_api_for_token(token_id: str) -> tuple[InfisicalAPI, dict]:
    base_url = os.environ.get("INFISICAL_API_URL")
    if not base_url:
        raise ConfigError("INFISICAL_API_URL is not set. Export INFISICAL_API_URL first.")
    entry = get_token_entry(token_id)
    if not entry:
        raise ConfigError(f"tokenId '{token_id}' not found in configured tokens. Run 'ih register token' to add it.")
    token = get_token_for_token_id_or_exit(token_id)
    return InfisicalAPI(base_url, token), entry
