import base64
import json
from argparse import Namespace

from inf_hub.config import (
    CONFIG_FILE,
    DEFAULT_TYPES,
    get_org_ids,
    get_orgs_or_exit,
    load_config,
    remove_local_value,
    save_config,
    save_local_inf,
    save_org,
    save_token_for_org,
    set_local_value,
)
from inf_hub.errors import ConfigError, ValidationError
from inf_hub.models import SecretUpdate
from inf_hub.runtime import build_api_for_org, get_api_for_org_silent, parse_id, resolve_org_id
from inf_hub import ui
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


def _interactive_org_id() -> str:
    orgs = get_orgs_or_exit()
    if len(orgs) == 1:
        return orgs[0]["id"]
    choices = [f"{o['id']} | {o['name']}" for o in orgs]
    return parse_id(ui.autocomplete_choice("Select organization", choices)) or ""


def _interactive_project_id(api) -> str | None:
    try:
        projects = api.list_projects().get("projects", [])
    except Exception:
        return None
    if not projects:
        return None
    choices = [f"{p['id']} | {p['name']}" for p in projects]
    return parse_id(ui.autocomplete_choice("Select project", choices))


def _interactive_environment(api, project_id: str) -> str | None:
    try:
        projects = api.list_projects().get("projects", [])
    except Exception:
        return None
    for p in projects:
        if p["id"] == project_id:
            envs = p.get("environments", [])
            if not envs:
                return None
            choices = [f"{e['slug']} | {e['name']}" for e in envs]
            return parse_id(ui.autocomplete_choice("Select environment", choices))
    return None


def _interactive_identity_id(api, org_id: str) -> str | None:
    try:
        identities = api.list_identities(org_id).get("identities", [])
    except Exception:
        return None
    if not identities:
        return None
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


def _require_org(args: Namespace, allow_prompt: bool) -> str:
    org_id = resolve_org_id(args, allow_prompt=allow_prompt, interactive_org_selector=_interactive_org_id)
    if not org_id:
        raise ValidationError("orgId is required")
    return org_id


def cmd_init_token(args: Namespace) -> None:
    ui.print_line("Configure ih")
    token = args.token
    org_id = parse_id(args.org_id) if args.org_id else None
    org_name = args.org_name

    if not args.yes and not token:
        token = ui.prompt("Infisical token", secret=True)

    token_org_id, token_org_name = _extract_org_info_from_token(token)
    if not args.yes and not org_id:
        org_id = parse_id(ui.prompt("Organization ID", default=token_org_id))
    if not args.yes and not org_name:
        org_name = ui.prompt("Organization name", default=token_org_name)

    if args.yes and not token:
        raise ValidationError("--token is required with --yes")
    if args.yes and not org_id:
        raise ValidationError("--org-id is required with --yes")
    if not token:
        raise ValidationError("token is required")
    if not org_id:
        org_id = token_org_id
    if not org_id:
        raise ValidationError("organization ID is required")

    if not args.skip_checks and token_org_id and token_org_id != org_id:
        raise ValidationError(f"org-id '{org_id}' does not match token org-id '{token_org_id}'. Use --skip-checks to bypass this check.")

    save_token_for_org(org_id, token)
    save_org(org_id, org_name)
    cfg = load_config() or {}
    cfg.pop("token", None)
    save_config(cfg)
    ui.print_line(f"Token saved to secure keyring for org {org_id} ({org_name or org_id}). Global config: {CONFIG_FILE}")


def cmd_init_folder(args: Namespace) -> None:
    org_id = parse_id(args.org_id) if args.org_id else None
    project_id = parse_id(args.project_id) if args.project_id else None
    environment = args.environment or "dev"

    if not args.yes:
        if not org_id:
            org_id = _interactive_org_id()
        api = get_api_for_org_silent(org_id)
        if not project_id:
            project_id = (_interactive_project_id(api) if api else None) or parse_id(ui.prompt("Project ID"))
        if not args.environment:
            environment = (_interactive_environment(api, project_id) if api else None) or ui.prompt("Environment", default="dev")
    else:
        if not org_id or not project_id:
            raise ValidationError("--org-id and --project-id are required with --yes")

    if not org_id or not project_id:
        raise ValidationError("orgId and projectId are required")

    if not args.yes and not ui.confirm("Proceed with local repository initialization?"):
        ui.print_line("Aborted.")
        return

    save_local_inf(org_id, project_id, environment)
    ui.print_line(f"Initialized local repository context in .inf (Env: {environment}).")


def cmd_create_project(args: Namespace) -> None:
    org_id = _require_org(args, allow_prompt=not args.yes)
    api = build_api_for_org(org_id)
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
                identity_id = _interactive_identity_id(api, org_id) or parse_id(ui.prompt("Machine identity ID"))
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

    if not args.yes and not ui.confirm("Proceed?"):
        ui.print_line("Aborted.")
        return

    project = api.create_project(name, org_id, slug)["project"]
    ui.print_line(f"Created project '{project['name']}' (ID: {project['id']}).")
    if identity_id:
        api.add_identity_to_project(project["id"], identity_id, role or "member")
        ui.print_line(f"Added identity {identity_id} with role {role or 'member'}.")


def cmd_list_orgs(_: Namespace) -> None:
    orgs = get_orgs_or_exit()
    for org in orgs:
        ui.print_line(f"{org['id']} | {org['name']}")


def cmd_list_projects(args: Namespace) -> None:
    org_id = _require_org(args, allow_prompt=not getattr(args, "yes", False))
    api = build_api_for_org(org_id)
    projects = api.list_projects().get("projects", [])
    if not projects:
        ui.print_line("No projects found.")
        return
    for p in projects:
        ui.print_line(f"{p['id']} | {p['name']} | {p['slug']}")


def cmd_list_identities(args: Namespace) -> None:
    org_id = _require_org(args, allow_prompt=not getattr(args, "yes", False))
    api = build_api_for_org(org_id)
    identities = api.list_identities(org_id).get("identities", [])
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
        org_id = _require_org(args, allow_prompt=True)
        api = build_api_for_org(org_id)
        if args.type == "orgId":
            value = _interactive_org_id()
        elif args.type == "projectId":
            value = _interactive_project_id(api)
        elif args.type == "environment":
            proj = _interactive_project_id(api)
            value = _interactive_environment(api, proj) if proj else None
        elif args.type == "identityId":
            value = _interactive_identity_id(api, org_id)

    if not value:
        raise ValidationError("value is required. Use --value or run in interactive mode.")
    if args.type in ("orgId", "projectId", "identityId"):
        value = parse_id(value)
    if args.type == "orgId":
        org_ids = get_org_ids()
        if org_ids and value not in org_ids:
            raise ValidationError(f"organization '{value}' not found in configured orgs. Run 'ih init token' to add it.")

    set_local_value(args.type, value)
    ui.print_line(f"Local {args.type} set to: {value}")


def cmd_unset(args: Namespace) -> None:
    if args.type not in DEFAULT_TYPES:
        raise ValidationError(f"invalid type '{args.type}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
    remove_local_value(args.type)
    ui.print_line(f"Local {args.type} removed.")


def cmd_pull(args: Namespace) -> None:
    org_id = _require_org(args, allow_prompt=not args.yes)
    api = build_api_for_org(org_id)
    project_id, environment = resolve_target(api, args, _interactive_project_id, _interactive_environment)
    secrets = api.list_secrets(project_id, environment).get("secrets", [])
    if args.p:
        for s in secrets:
            ui.print_line(f"{s['secretKey']}={s.get('secretValue', '')}")
        ui.print_line(f"Pulled secrets from Env: {environment} (printed to stdout).")
        return
    out_file = args.file or ".env"
    write_env_file(out_file, secrets)
    ui.print_line(f"Pulled secrets from Env: {environment} to file: {out_file}.")


def cmd_push(args: Namespace) -> None:
    org_id = _require_org(args, allow_prompt=not args.yes)
    api = build_api_for_org(org_id)
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
    if not args.yes:
        for update in updates:
            old = current.get(update.key)
            ui.print_line(f"{update.key}: {('<MISSING>' if old is None else old)} -> {update.value}")
        if not ui.confirm("Proceed?"):
            ui.print_line("Aborted.")
            return

    push_updates(api, project_id, environment, updates)
    out_file = args.file or ".env"
    synced = sync_local_if_exists(api, project_id, environment, out_file)
    ui.print_line(f"Pushed {len(updates)} secrets to Env: {environment} from {source_desc}.")
    if synced:
        ui.print_line(f"Updated local file: {synced}.")


def cmd_history(args: Namespace) -> None:
    org_id = _require_org(args, allow_prompt=not args.yes)
    api = build_api_for_org(org_id)
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
    org_id = _require_org(args, allow_prompt=not args.yes)
    api = build_api_for_org(org_id)
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
        version = ui.prompt("Version to rollback to")
    try:
        version_num = int(version)
    except ValueError as exc:
        raise ValidationError(f"invalid version '{version}'") from exc

    if not args.yes and not ui.confirm(f"Rollback '{secret_name}' to version {version_num}?"):
        ui.print_line("Aborted.")
        return

    result = rollback_secret(api, project_id, environment, secret_name, version_num)
    out_file = args.file or ".env"
    synced = sync_local_if_exists(api, project_id, environment, out_file)
    ui.print_line(result.message)
    if synced:
        ui.print_line(f"Updated local file: {synced}.")
