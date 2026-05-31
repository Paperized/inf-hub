from argparse import Namespace
from pathlib import Path

from inf_hub.api import InfisicalAPI
from inf_hub.errors import ValidationError
from inf_hub.models import CommandResult, SecretUpdate
from inf_hub.runtime import effective_local_value, parse_id


def parse_env_file(path: str) -> list[SecretUpdate]:
    updates: list[SecretUpdate] = []
    with open(path) as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                raise ValidationError(f"Invalid .env format at line {i}: expected KEY=VALUE")
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                raise ValidationError(f"Invalid .env format at line {i}: empty key")
            updates.append(SecretUpdate(key=key, value=value))
    return updates


def write_env_file(path: str, secrets: list[dict]) -> None:
    with open(path, "w") as f:
        for item in secrets:
            f.write(f"{item['secretKey']}={item.get('secretValue', '')}\n")


def pair_updates(keys: list[str], values: list[str]) -> list[SecretUpdate]:
    if len(keys) != len(values):
        raise ValidationError("-k and -v must be provided in pairs.")
    return [SecretUpdate(key=k, value=v) for k, v in zip(keys, values)]


def resolve_target(api: InfisicalAPI, args: Namespace, select_project, select_environment) -> tuple[str, str]:
    project_id = parse_id(getattr(args, "project_id", None)) or effective_local_value("projectId")
    environment = getattr(args, "environment", None) or effective_local_value("environment") or "dev"

    if not project_id:
        if not getattr(args, "yes", False):
            project_id = select_project(api)
        else:
            raise ValidationError("--project-id is required with --yes")
    if not project_id:
        raise ValidationError("projectId is required.")

    if not getattr(args, "environment", None) and not effective_local_value("environment") and not getattr(args, "yes", False):
        selected_env = select_environment(api, project_id)
        if selected_env:
            environment = selected_env

    return project_id, environment


def sync_local_if_exists(api: InfisicalAPI, project_id: str, environment: str, out_file: str) -> str | None:
    if not Path(out_file).exists():
        return None
    secrets = api.list_secrets(project_id, environment).get("secrets", [])
    write_env_file(out_file, secrets)
    return out_file


def push_updates(api: InfisicalAPI, project_id: str, environment: str, updates: list[SecretUpdate]) -> None:
    for upd in updates:
        try:
            api.update_secret(project_id, environment, upd.key, upd.value)
        except RuntimeError as exc:
            if "404" in str(exc):
                api.create_secret(project_id, environment, upd.key, upd.value)
            else:
                raise


def rollback_secret(api: InfisicalAPI, project_id: str, environment: str, secret_name: str, version: int) -> CommandResult:
    old = api.get_secret(project_id, environment, secret_name, version=version).get("secret", {})
    old_value = old.get("secretValue", "")
    api.update_secret(project_id, environment, secret_name, old_value)
    return CommandResult(message=f"Rolled back secret '{secret_name}' to version {version} in Env: {environment}.")
