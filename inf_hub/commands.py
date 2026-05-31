import base64
import json
from argparse import Namespace

from inf_hub import ui
from inf_hub.config import (
    CONFIG_FILE,
    DEFAULT_TYPES,
    delete_token_for_token_id,
    get_token_entry,
    get_token_ids,
    get_tokens_or_exit,
    load_config,
    remove_local_value,
    remove_token_entry,
    save_config,
    save_local_inf,
    save_token_entry,
    save_token_for_token_id,
    set_local_value,
)
from inf_hub.errors import ValidationError
from inf_hub.models import SecretUpdate
from inf_hub.runtime import build_api_for_token, parse_id, resolve_token_id
from inf_hub.services import (
    pair_updates,
    parse_env_file,
    push_updates,
    resolve_target,
    rollback_secret,
    sync_local_if_exists,
    write_env_file,
)

VALID_ROLES = ("admin", "member", "viewer", "no-access")


def _extract_org_info_from_token(token: str | None) -> tuple[str | None, str | None]:
    if not token:
        return None, None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None, None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return data.get("organizationId"), data.get("organizationName")
    except Exception:
        return None, None


def _interactive_token_id() -> str:
    tokens = get_tokens_or_exit()
    choices = [f"{t['tokenId']} | {t.get('orgId', '')}" for t in tokens]
    return parse_id(ui.autocomplete_choice("Select token", choices)) or ""


def _interactive_project_id(api) -> str | None:
    try:
        projects = api.list_projects().get("projects", [])
    except Exception as exc:
        raise ValidationError(f"cannot load projects for selected token: {exc}") from exc
    if not projects:
        raise ValidationError("no projects found for selected token")
    choices = [f"{p['id']} | {p['name']}" for p in projects]
    return parse_id(ui.autocomplete_choice("Select project", choices))


def _interactive_environment(api, project_id: str) -> str | None:
    try:
        projects = api.list_projects().get("projects", [])
    except Exception as exc:
        raise ValidationError(f"cannot load environments for selected project: {exc}") from exc
    for p in projects:
        if p["id"] == project_id:
            envs = p.get("environments", [])
            if not envs:
                raise ValidationError("no environments found for selected project")
            choices = [f"{e['slug']} | {e['name']}" for e in envs]
            return parse_id(ui.autocomplete_choice("Select environment", choices))
    raise ValidationError("selected project not found while resolving environments")


def _interactive_identity_id(api, org_id: str) -> str | None:
    try:
        identities = api.list_identities(org_id).get("identities", [])
    except Exception as exc:
        raise ValidationError(f"cannot load identities for selected token: {exc}") from exc
    if not identities:
        raise ValidationError("no identities found for selected token")
    choices = [f"{i.get('identityId', i.get('id'))} | {i.get('identity', {}).get('name', 'unknown')}" for i in identities]
    return parse_id(ui.autocomplete_choice("Select machine identity", choices))


def _interactive_secret_name(api, project_id: str, environment: str, allow_new: bool = False) -> tuple[str, bool]:
    secrets = api.list_secrets(project_id, environment).get("secrets", [])
    keys = sorted([s.get("secretKey") for s in secrets if s.get("secretKey")])
    if not keys and not allow_new:
        raise ValidationError("no secrets found in selected environment")

    if allow_new:
        choices = keys + ["+ Create new secret"]
        selected = ui.autocomplete_choice("Select secret name", choices)
        if selected == "+ Create new secret":
            new_name = ui.prompt("New secret name")
            if not new_name:
                raise ValidationError("secret name is required")
            return new_name, True
        return selected, False

    return ui.autocomplete_choice("Select secret name", keys), False


def _display_rollback_versions(api, project_id: str, environment: str, secret_name: str) -> tuple[int, list[tuple[int, str]]]:
    result = api.get_secret(project_id, environment, secret_name)
    current = result.get("secret", {})
    current_version = int(current.get("version", 1))
    current_value = str(current.get("secretValue", ""))
    ui.print_line(f"Current version v{current_version} value {current_value}")

    versions: list[tuple[int, str]] = []
    for version in range(current_version - 1, 0, -1):
        try:
            secret = api.get_secret(project_id, environment, secret_name, version=version).get("secret", {})
            versions.append((version, str(secret.get("secretValue", ""))))
        except Exception:
            continue

    return current_version, versions


def _require_token_id(args: Namespace, allow_prompt: bool) -> str:
    token_id = resolve_token_id(args, allow_prompt=allow_prompt, interactive_token_selector=_interactive_token_id)
    if not token_id:
        raise ValidationError("tokenId is required")
    return token_id


def cmd_register_token(args: Namespace) -> None:
    ui.print_line("Configure ih")
    token = args.token
    token_id = parse_id(args.token_id) if args.token_id else None

    if not args.yes and not token:
        token = ui.prompt("Infisical token", secret=True)

    org_id, _token_org_name = _extract_org_info_from_token(token)
    if not org_id:
        raise ValidationError("cannot extract organization ID from token")

    if not args.yes and not token_id:
        token_id = parse_id(ui.prompt("Token unique name"))
    if args.yes and not token_id:
        raise ValidationError("--token-id is required with --yes")
    if not token_id:
        raise ValidationError("tokenId is required")

    if token_id in get_token_ids():
        raise ValidationError(f"tokenId '{token_id}' already exists")

    save_token_for_token_id(token_id, token)
    save_token_entry(token_id, org_id)
    cfg = load_config() or {}
    cfg.pop("token", None)
    save_config(cfg)
    ui.print_line(f"Token saved to secure keyring for tokenId {token_id} (orgId: {org_id}). Config: {CONFIG_FILE}")


def cmd_unregister_token(args: Namespace) -> None:
    token_id = parse_id(args.token_id) if args.token_id else None
    if not token_id:
        token_id = _interactive_token_id()
    entry = get_token_entry(token_id)
    if not entry:
        raise ValidationError(f"tokenId '{token_id}' not found")

    if not args.yes:
        ui.print_table(
            "Pending token removal",
            ["orgId", "tokenId"],
            [[entry.get("orgId", ""), token_id]],
        )
    if not args.yes and not ui.confirm(f"Remove token '{token_id}' from config and keyring?"):
        ui.print_line("Aborted.")
        return

    delete_token_for_token_id(token_id)
    remove_token_entry(token_id)
    ui.print_line(f"Unregistered token '{token_id}' (orgId: {entry.get('orgId', '')}).")


def cmd_init_folder(args: Namespace) -> None:
    token_id = parse_id(args.token_id) if args.token_id else None
    project_id = parse_id(args.project_id) if args.project_id else None
    environment = args.environment or "dev"

    if not args.yes:
        if not token_id:
            token_id = _interactive_token_id()
        api, _entry = build_api_for_token(token_id)
        if not project_id:
            project_id = _interactive_project_id(api)
        if not args.environment:
            environment = _interactive_environment(api, project_id)
    else:
        if not token_id or not project_id:
            raise ValidationError("--token-id and --project-id are required with --yes")

    if not token_id or not project_id:
        raise ValidationError("tokenId and projectId are required")

    if not args.yes:
        ui.print_table(
            "Pending local context initialization",
            ["tokenId", "projectId", "environment"],
            [[token_id, project_id, environment]],
        )
    if not args.yes and not ui.confirm("Proceed with local repository initialization?"):
        ui.print_line("Aborted.")
        return

    save_local_inf(token_id, project_id, environment)
    ui.print_line(f"Initialized local repository context in .inf (Env: {environment}).")


def cmd_create_project(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not args.yes)
    api, entry = build_api_for_token(token_id)
    org_id = entry["orgId"]
    name = args.name
    slug = args.slug
    identity_id = parse_id(args.identity_id)
    role = args.role

    if not args.yes:
        if not name:
            name = ui.prompt("Project name")
        if not slug:
            slug = ui.prompt("Slug", default=name)
        if ui.confirm("Add machine identity?"):
            if not identity_id:
                identity_id = _interactive_identity_id(api, org_id)
            if not role:
                role = ui.autocomplete_choice("Select role", list(VALID_ROLES))
        else:
            identity_id = None

    if not name:
        raise ValidationError("project name is required")
    if not slug:
        slug = name
    if role and role not in VALID_ROLES:
        raise ValidationError(f"invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}")

    if not args.yes:
        ui.print_table(
            "Pending project creation",
            ["tokenId", "orgId", "projectName", "slug", "identityId", "role"],
            [[token_id, org_id, name, slug, identity_id or "", role or ""]],
        )
    if not args.yes and not ui.confirm("Proceed?"):
        ui.print_line("Aborted.")
        return

    project = api.create_project(name, org_id, slug)["project"]
    ui.print_line(f"Created project '{project['name']}' (ID: {project['id']}).")
    if identity_id:
        api.add_identity_to_project(project["id"], identity_id, role or "member")
        ui.print_line(f"Added identity {identity_id} with role {role or 'member'}.")


def cmd_list_orgs(_: Namespace) -> None:
    tokens = get_tokens_or_exit()
    for t in tokens:
        ui.print_line(f"{t.get('orgId', '')} | {t['tokenId']}")


def cmd_list_projects(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not getattr(args, "yes", False))
    api, _entry = build_api_for_token(token_id)
    projects = api.list_projects().get("projects", [])
    if not projects:
        ui.print_line("No projects found.")
        return
    for p in projects:
        ui.print_line(f"{p['id']} | {p['name']} | {p['slug']}")


def cmd_list_identities(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not getattr(args, "yes", False))
    api, entry = build_api_for_token(token_id)
    identities = api.list_identities(entry["orgId"]).get("identities", [])
    if not identities:
        ui.print_line("No identities found.")
        return
    for i in identities:
        ui.print_line(f"{i.get('identityId', i.get('id'))} | {i.get('identity', {}).get('name', 'unknown')} | {i.get('role', '')}")


def cmd_set(args: Namespace) -> None:
    if args.type not in DEFAULT_TYPES:
        raise ValidationError(f"invalid type '{args.type}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
    value = args.value
    if not value:
        if args.type == "tokenId":
            value = _interactive_token_id()
        else:
            token_id = _require_token_id(args, allow_prompt=True)
            api, entry = build_api_for_token(token_id)
            if args.type == "projectId":
                value = _interactive_project_id(api)
            elif args.type == "environment":
                proj = _interactive_project_id(api)
                value = _interactive_environment(api, proj) if proj else None
            elif args.type == "identityId":
                value = _interactive_identity_id(api, entry["orgId"])
    if not value:
        raise ValidationError("value is required. Use --value or run in interactive mode.")
    if args.type in ("tokenId", "projectId", "identityId"):
        value = parse_id(value)
    if args.type == "tokenId":
        token_ids = get_token_ids()
        if token_ids and value not in token_ids:
            raise ValidationError(f"tokenId '{value}' not found in configured tokens. Run 'ih register token' to add it.")

    set_local_value(args.type, value)
    ui.print_line(f"Local {args.type} set to: {value}")


def cmd_unset(args: Namespace) -> None:
    if args.type not in DEFAULT_TYPES:
        raise ValidationError(f"invalid type '{args.type}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
    remove_local_value(args.type)
    ui.print_line(f"Local {args.type} removed.")


def cmd_pull(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not args.yes)
    api, _entry = build_api_for_token(token_id)
    project_id, environment = resolve_target(api, args, _interactive_project_id, _interactive_environment)
    secrets = api.list_secrets(project_id, environment).get("secrets", [])
    if args.p:
        rows = [[s["secretKey"], s.get("secretValue", "")] for s in secrets]
        ui.print_table("Pulled secrets", ["Secret", "Value"], rows)
        ui.print_line(f"Pulled secrets from Env: {environment} (printed to stdout).")
        return
    out_file = args.file or ".env"
    write_env_file(out_file, secrets)
    ui.print_line(f"Pulled secrets from Env: {environment} to file: {out_file}.")


def cmd_push(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not args.yes)
    api, _entry = build_api_for_token(token_id)
    project_id, environment = resolve_target(api, args, _interactive_project_id, _interactive_environment)

    has_file = bool(args.file)
    has_inline = bool(args.k or args.v)
    if has_file and has_inline:
        raise ValidationError("use either -f or -k/-v, not both")

    if has_inline:
        updates = pair_updates(args.k or [], args.v or [])
        source_desc = "inline key/value input"
    elif not has_file and not args.yes:
        secret_name, is_new = _interactive_secret_name(api, project_id, environment, allow_new=True)
        secret_value = ui.prompt("Secret value", secret=True)
        updates = [SecretUpdate(key=secret_name, value=secret_value)]
        source_desc = "interactive input"
        if is_new:
            ui.print_line(f"New secret selected: {secret_name}")
    else:
        path = args.file or ".env"
        updates = parse_env_file(path)
        source_desc = f"file: {path}"

    if not updates:
        raise ValidationError("no values to push")

    current = {s.get("secretKey"): s.get("secretValue", "") for s in api.list_secrets(project_id, environment).get("secrets", [])}
    to_apply: list[SecretUpdate] = []
    ignored: list[SecretUpdate] = []
    preview_rows: list[list[str]] = []
    for update in updates:
        old = current.get(update.key)
        if old == update.value:
            ignored.append(update)
            preview_rows.append([update.key, "<MISSING>" if old is None else old, update.value, "IGNORE"])
        else:
            to_apply.append(update)
            preview_rows.append([update.key, "<MISSING>" if old is None else old, update.value, "APPLY"])

    if not args.yes:
        ui.print_table("Pending secret updates", ["Secret", "Current", "New", "Action"], preview_rows)
        if not to_apply:
            ui.print_line("No changes detected: all values are unchanged.")
            return
        if not ui.confirm("Proceed?"):
            ui.print_line("Aborted.")
            return

    if to_apply:
        push_updates(api, project_id, environment, to_apply)
    out_file = args.file or ".env"
    synced = sync_local_if_exists(api, project_id, environment, out_file)
    msg = f"Pushed {len(to_apply)} secrets to {environment}"
    if ignored:
        msg += f" and ignored {len(ignored)}"
    msg += "."
    ui.print_line(msg)
    if synced:
        ui.print_line(f"Updated local file: {synced}.")


def cmd_history(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not args.yes)
    api, _entry = build_api_for_token(token_id)
    project_id, environment = resolve_target(api, args, _interactive_project_id, _interactive_environment)

    secret_name = args.name
    if not secret_name:
        if args.yes:
            raise ValidationError("--name is required with --yes")
        secret_name, _ = _interactive_secret_name(api, project_id, environment, allow_new=False)

    result = api.get_secret(project_id, environment, secret_name)
    current_version = result.get("secret", {}).get("version", 1)
    ui.print_line(f"Env: {environment}")
    ui.print_line(f"History for '{secret_name}' (current version: {current_version})")
    for version in range(current_version, 0, -1):
        try:
            secret = api.get_secret(project_id, environment, secret_name, version=version).get("secret", {})
            ui.print_line(f"v{version} | updatedAt={secret.get('updatedAt', '')} | value={secret.get('secretValue', '')}")
        except Exception:
            ui.print_line(f"v{version} | not available")


def cmd_rollback(args: Namespace) -> None:
    token_id = _require_token_id(args, allow_prompt=not args.yes)
    api, _entry = build_api_for_token(token_id)
    project_id, environment = resolve_target(api, args, _interactive_project_id, _interactive_environment)

    secret_name = args.name
    if not secret_name:
        if args.yes:
            raise ValidationError("--name is required with --yes")
        secret_name, _ = _interactive_secret_name(api, project_id, environment, allow_new=False)

    version = args.version
    if not version:
        if args.yes:
            raise ValidationError("--version is required with --yes")
        current_version, versions = _display_rollback_versions(api, project_id, environment, secret_name)
        if current_version <= 1 or not versions:
            raise ValidationError("no previous versions available for rollback")
        choices = [f"{value} | v{version_num}" for version_num, value in versions]
        selected = ui.autocomplete_choice("Select version to rollback to", choices)
        version = selected.rsplit("| v", 1)[-1].strip()
    try:
        version_num = int(version)
    except ValueError as exc:
        raise ValidationError(f"invalid version '{version}'") from exc

    current = api.get_secret(project_id, environment, secret_name).get("secret", {})
    current_value = str(current.get("secretValue", ""))
    selected = api.get_secret(project_id, environment, secret_name, version=version_num).get("secret", {})
    selected_value = str(selected.get("secretValue", ""))

    if not args.yes:
        ui.print_table(
            "Pending rollback",
            ["tokenId", "projectId", "environment", "secret", "current", "selected", "action"],
            [[
                token_id,
                project_id,
                environment,
                secret_name,
                current_value,
                selected_value,
                "IGNORE" if current_value == selected_value else "APPLY",
            ]],
        )
    if current_value == selected_value:
        ui.print_line(
            f"Rollback ignored for '{secret_name}' in {environment}: selected version v{version_num} is unchanged."
        )
        return

    if not args.yes and not ui.confirm(f"Rollback '{secret_name}' to version {version_num}?"):
        ui.print_line("Aborted.")
        return

    result = rollback_secret(api, project_id, environment, secret_name, version_num)
    out_file = args.file or ".env"
    synced = sync_local_if_exists(api, project_id, environment, out_file)
    ui.print_line(result.message)
    if synced:
        ui.print_line(f"Updated local file: {synced}.")
