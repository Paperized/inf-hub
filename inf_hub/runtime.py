import os
from argparse import Namespace

from inf_hub.api import InfisicalAPI
from inf_hub.config import get_org_ids, get_token_for_org_or_exit, load_local_inf, load_token_for_org
from inf_hub.errors import ConfigError


def parse_id(value: str | None) -> str | None:
    if not value:
        return None
    return value.split("|")[0].strip()


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


def resolve_org_id(args: Namespace, allow_prompt: bool, interactive_org_selector) -> str | None:
    explicit = parse_id(getattr(args, "org_id", None)) if hasattr(args, "org_id") else None
    org_id = explicit or effective_local_value("orgId")
    if org_id:
        org_ids = get_org_ids()
        if org_ids and org_id not in org_ids:
            raise ConfigError(
                f"organization '{org_id}' not found in configured orgs. Run 'ih init token' to add it."
            )
    if not org_id and allow_prompt:
        org_id = interactive_org_selector()
    return org_id


def build_api_for_org(org_id: str) -> InfisicalAPI:
    base_url = os.environ.get("INFISICAL_API_URL")
    if not base_url:
        raise ConfigError("INFISICAL_API_URL is not set. Export INFISICAL_API_URL first.")
    org_ids = get_org_ids()
    if org_ids and org_id not in org_ids:
        raise ConfigError(f"organization '{org_id}' not found in configured orgs. Run 'ih init token' to add it.")
    token = get_token_for_org_or_exit(org_id)
    return InfisicalAPI(base_url, token)


def get_api_for_org_silent(org_id: str | None) -> InfisicalAPI | None:
    try:
        base_url = os.environ.get("INFISICAL_API_URL")
        if not base_url or not org_id:
            return None
        token = load_token_for_org(org_id)
        if not token:
            return None
        return InfisicalAPI(base_url, token)
    except Exception:
        return None
