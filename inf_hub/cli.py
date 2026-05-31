# PYTHON_ARGCOMPLETE_OK
import argparse
import base64
import getpass
import json
import os
import sys
from pathlib import Path

import argcomplete
try:
    import questionary
    HAS_QUESTIONARY = True
except Exception:
    HAS_QUESTIONARY = False

from inf_hub.api import InfisicalAPI
from inf_hub.config import (
    CONFIG_FILE,
    DEFAULT_TYPES,
    get_org_ids,
    get_orgs_or_exit,
    get_token_for_org_or_exit,
    load_config,
    load_local_inf,
    load_orgs,
    load_token_for_org,
    remove_local_value,
    save_config,
    save_local_inf,
    save_org,
    save_token_secure,
    save_token_for_org,
    set_local_value,
)

VALID_ROLES = ("admin", "member", "viewer", "no-access")


def _print(msg):
    print(msg)


def _print_org_line(org_id, org_name, projects_count):
    if HAS_QUESTIONARY:
        # questionary does not control plain command output styling.
        pass
    try:
        from rich.console import Console
        console = Console()
        if org_name == "Token Org":
            console.print(
                f"[bold cyan]{org_id}[/bold cyan] | [bold magenta]{org_name}[/bold magenta] | projects={projects_count}"
            )
            return
        console.print(f"{org_id} | {org_name} | projects={projects_count}")
        return
    except Exception:
        pass
    _print(f"{org_id} | {org_name} | projects={projects_count}")


def _parse_id(value):
    if not value:
        return None
    return value.split("|")[0].strip()


def _get_api_for_org_silent(org_id):
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


def _extract_org_info_from_token(token):
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


def _extract_org_id_from_token(token):
    org_id, _ = _extract_org_info_from_token(token)
    return org_id


def _resolve_org_id(args, allow_prompt=False):
    explicit = _parse_id(getattr(args, "org_id", None)) if hasattr(args, "org_id") else None
    org_id = explicit or _effective_value("orgId")
    if org_id:
        org_ids = get_org_ids()
        if org_ids and org_id not in org_ids:
            _print(f"Error: organization '{org_id}' not found in configured orgs. Run 'ih init token' to add it.")
            raise SystemExit(1)
    if not org_id and allow_prompt:
        org_id = _interactive_org_id()
    return org_id


def _api_for_org_or_exit(org_id):
    base_url = os.environ.get("INFISICAL_API_URL")
    if not base_url:
        _print("Error: INFISICAL_API_URL is not set.")
        _print("Set it with:")
        _print("  export INFISICAL_API_URL=https://app.infisical.com")
        raise SystemExit(1)
    org_ids = get_org_ids()
    if org_ids and org_id not in org_ids:
        _print(f"Error: organization '{org_id}' not found in configured orgs. Run 'ih init token' to add it.")
        raise SystemExit(1)
    token = get_token_for_org_or_exit(org_id)
    return InfisicalAPI(base_url, token)


def _load_local_inf_or_exit():
    try:
        return load_local_inf()
    except ValueError as e:
        _print(f"Error: {e}")
        raise SystemExit(1)


def _effective_value(key, explicit=None):
    if explicit:
        return explicit
    local_inf = _load_local_inf_or_exit()
    if local_inf is not None and local_inf.get(key):
        return local_inf.get(key)
    return None


def _warn_local_override(local_key, explicit):
    local_inf = _load_local_inf_or_exit()
    if explicit and local_inf is not None:
        _print(f"Warning: overriding local .inf value for {local_key}.")


def _select(message, choices):
    if HAS_QUESTIONARY:
        result = questionary.select(message, choices=choices).ask()
        if result is None:
            raise KeyboardInterrupt
        return result
    return None


def _prompt(label, secret=False, default=None):
    if HAS_QUESTIONARY:
        if secret:
            v = questionary.password(label).ask()
            if v is None:
                raise KeyboardInterrupt
            return (v or "").strip()
        v = questionary.text(label, default=default or "").ask()
        if v is None:
            raise KeyboardInterrupt
        return (v or "").strip() or default
    suffix = f" [{default}]" if default else ""
    if secret:
        v = getpass.getpass(f"{label}{suffix}: ")
    else:
        v = input(f"{label}{suffix}: ")
    return v.strip() if v.strip() else default


def _confirm(message):
    if HAS_QUESTIONARY:
        result = questionary.confirm(message, default=False).ask()
        if result is None:
            raise KeyboardInterrupt
        return bool(result)
    return input(f"{message} [y/N]: ").lower() in ("y", "yes")


def _secret_keys(api, project_id, environment):
    secrets = api.list_secrets(project_id, environment).get("secrets", [])
    return sorted([s.get("secretKey") for s in secrets if s.get("secretKey")])


def _interactive_secret_name(api, project_id, environment, allow_new=False):
    keys = _secret_keys(api, project_id, environment)
    if not keys and not allow_new:
        _print("Error: no secrets found in selected environment.")
        raise SystemExit(1)

    if HAS_QUESTIONARY:
        if allow_new:
            choices = keys + ["+ Create new secret"]
            selected = questionary.autocomplete(
                "Select secret name",
                choices=choices,
                validate=lambda text: text in choices or "Choose a value from autocomplete list",
            ).ask()
            if selected is None:
                raise KeyboardInterrupt
            if selected == "+ Create new secret":
                new_name = _prompt("New secret name")
                if not new_name:
                    _print("Error: secret name is required.")
                    raise SystemExit(1)
                return new_name, True
            return selected, False

        selected = questionary.autocomplete(
            "Select secret name",
            choices=keys,
            validate=lambda text: text in keys or "Choose a value from autocomplete list",
        ).ask()
        if selected is None:
            raise KeyboardInterrupt
        return selected, False

    if allow_new:
        choices = keys + ["+ Create new secret"]
        selected = _select("Select secret name", choices)
        if selected == "+ Create new secret":
            new_name = _prompt("New secret name")
            if not new_name:
                _print("Error: secret name is required.")
                raise SystemExit(1)
            return new_name, True
        return selected, False

    selected = _select("Select secret name", keys)
    return selected, False


def _interactive_org_id():
    orgs = get_orgs_or_exit()
    if len(orgs) == 1:
        return orgs[0]["id"]
    choices = [f"{o['id']} | {o['name']}" for o in orgs]
    selected = _select("Select organization", choices)
    return _parse_id(selected)


def _interactive_project_id(api):
    try:
        projects = api.list_projects().get("projects", [])
    except Exception:
        return None
    if not projects:
        return None
    return _parse_id(_select("Select project", [f"{p['id']} | {p['name']}" for p in projects]))


def _interactive_environment(api, project_id):
    if not project_id:
        return None
    try:
        projects = api.list_projects().get("projects", [])
    except Exception:
        return None
    for p in projects:
        if p["id"] == project_id:
            envs = p.get("environments", [])
            if not envs:
                return None
            return _parse_id(_select("Select environment", [f"{e['slug']} | {e['name']}" for e in envs]))
    return None


def _interactive_identity_id(api, org_id):
    if not org_id:
        return None
    try:
        identities = api.list_identities(org_id).get("identities", [])
    except Exception:
        return None
    if not identities:
        return None
    choices = [f"{i.get('identityId', i.get('id'))} | {i.get('identity', {}).get('name', 'unknown')}" for i in identities]
    return _parse_id(_select("Select machine identity", choices))





def _parse_env_file(path):
    updates = []
    with open(path) as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                raise ValueError(f"Invalid .env format at line {i}: expected KEY=VALUE")
            k, v = line.split("=", 1)
            k = k.strip()
            if not k:
                raise ValueError(f"Invalid .env format at line {i}: empty key")
            updates.append((k, v))
    return updates


def _write_env_file(path, secrets):
    with open(path, "w") as f:
        for s in secrets:
            f.write(f"{s['secretKey']}={s.get('secretValue','')}\n")


def cmd_init_token(args):
    _print("Configure ih")
    if not os.environ.get("INFISICAL_API_URL"):
        _print("Warning: INFISICAL_API_URL is not set.")
        _print("Set it with:")
        _print("  export INFISICAL_API_URL=https://app.infisical.com")

    org_id = _parse_id(args.org_id) if args.org_id else None
    org_name = args.org_name
    token = args.token
    skip_checks = args.skip_checks
    if not args.yes and not token:
        token = _prompt("Infisical token", secret=True)
    
    token_org_id, token_org_name = _extract_org_info_from_token(token)
    
    if not args.yes and not org_id:
        org_id = _parse_id(_prompt("Organization ID", default=token_org_id))
    if not args.yes and not org_name:
        org_name = _prompt("Organization name", default=token_org_name)
    if args.yes and not token:
        _print("Error: --token is required with --yes")
        raise SystemExit(1)
    if args.yes and not org_id:
        _print("Error: --org-id is required with --yes")
        raise SystemExit(1)
    if not token:
        _print("Error: token is required.")
        raise SystemExit(1)
    if not org_id:
        org_id = token_org_id
    if not org_id:
        _print("Error: organization ID is required.")
        raise SystemExit(1)

    if not skip_checks:
        if token_org_id and token_org_id != org_id:
            _print(f"Error: org-id '{org_id}' does not match token org-id '{token_org_id}'.")
            _print("Use --skip-checks to bypass this check.")
            raise SystemExit(1)

        base_url = os.environ.get("INFISICAL_API_URL")
        if base_url:
            try:
                test_api = InfisicalAPI(base_url, token)
                test_api.list_projects()
            except Exception as e:
                _print(f"Error: token validation failed: {e}")
                _print("Use --skip-checks to bypass this check.")
                raise SystemExit(1)
        else:
            _print("Warning: cannot validate token without INFISICAL_API_URL. Use --skip-checks to suppress this warning.")

    save_token_for_org(org_id, token)
    save_org(org_id, org_name)
    cfg = load_config() or {}
    cfg.pop("token", None)
    save_config(cfg)
    _print(f"Token saved to secure keyring for org {org_id} ({org_name or org_id}). Global config: {CONFIG_FILE}")


def cmd_init_folder(args):
    org_id = _resolve_org_id(args, allow_prompt=False)
    api = _get_api_for_org_silent(org_id)
    org_id = _parse_id(args.org_id) if args.org_id else None
    project_id = _parse_id(args.project_id) if args.project_id else None
    environment = args.environment or "dev"

    if not args.yes:
        if not org_id:
            org_id = _interactive_org_id()
        if not project_id:
            project_id = (_interactive_project_id(api) if api else None) or _parse_id(_prompt("Project ID"))
        if not args.environment:
            environment = (_interactive_environment(api, project_id) if api else None) or _prompt("Environment", default="dev")
    else:
        if not org_id or not project_id:
            _print("Error: --org-id and --project-id are required with --yes")
            raise SystemExit(1)

    if not org_id or not project_id:
        _print("Error: orgId and projectId are required.")
        raise SystemExit(1)

    if not args.yes and not _confirm("Proceed with local repository initialization?"):
        _print("Aborted.")
        return

    save_local_inf(org_id, project_id, environment)
    _print(f"Initialized local repository context in .inf (Env: {environment}).")


def cmd_create_project(args):
    _warn_local_override("orgId", args.org_id)
    name = args.name
    slug = args.slug
    org_id = _resolve_org_id(args, allow_prompt=not args.yes)
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    identity_id = _parse_id(args.identity_id) or _effective_value("identityId")
    role = args.role

    if not args.yes:
        if not name:
            name = _prompt("Project name")
        if not slug:
            slug = _prompt("Slug", default=name)
        if _confirm("Add machine identity?"):
            if not identity_id:
                identity_id = _interactive_identity_id(api, org_id) or _parse_id(_prompt("Machine identity ID"))
            if not role:
                role = _prompt(f"Role ({', '.join(VALID_ROLES)})", default="member")
        else:
            identity_id = None
    else:
        if not name:
            _print("Error: --name is required with --yes")
            raise SystemExit(1)
        if not slug:
            slug = name
        if not org_id:
            _print("Error: --org-id is required with --yes")
            raise SystemExit(1)
        if identity_id and not role:
            role = "member"

    if role and role not in VALID_ROLES:
        _print(f"Error: invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}")
        raise SystemExit(1)

    if not args.yes and not _confirm("Proceed?"):
        _print("Aborted.")
        return

    project = api.create_project(name, org_id, slug)["project"]
    _print(f"Created project '{project['name']}' (ID: {project['id']}).")
    if identity_id:
        api.add_identity_to_project(project["id"], identity_id, role)
        _print(f"Added identity {identity_id} with role {role}.")


def cmd_list_orgs(args):
    orgs = load_orgs()
    if not orgs:
        _print("No organizations configured. Run 'ih init token' to add one.")
        return
    for o in orgs:
        _print(f"{o['id']} | {o['name']}")


def cmd_list_projects(args):
    org_id = _resolve_org_id(args, allow_prompt=not getattr(args, "yes", False))
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    projects = api.list_projects().get("projects", [])
    if not projects:
        _print("No projects found.")
        return
    for p in projects:
        _print(f"{p['id']} | {p['name']} | {p['slug']}")


def cmd_list_identities(args):
    _warn_local_override("orgId", args.org_id)
    org_id = _resolve_org_id(args, allow_prompt=not getattr(args, "yes", False))
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    identities = api.list_identities(org_id).get("identities", [])
    if not identities:
        _print("No identities found.")
        return
    for i in identities:
        _print(f"{i.get('identityId', i.get('id'))} | {i.get('identity', {}).get('name', 'unknown')} | {i.get('role','')}")


def cmd_set(args):
    dtype = args.type
    value = args.value
    if dtype not in DEFAULT_TYPES:
        _print(f"Error: invalid type '{dtype}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
        raise SystemExit(1)

    if not value:
        if dtype == "orgId":
            value = _interactive_org_id()
        else:
            org_id = _resolve_org_id(args, allow_prompt=True)
            if not org_id:
                _print("Error: orgId is required.")
                raise SystemExit(1)
            api = _api_for_org_or_exit(org_id)
            if dtype == "projectId":
                value = _interactive_project_id(api) or _parse_id(_prompt("Project ID"))
            elif dtype == "environment":
                project_id = _effective_value("projectId")
                if not project_id:
                    project_id = _interactive_project_id(api) or _parse_id(_prompt("Project ID"))
                value = _interactive_environment(api, project_id) or _prompt("Environment", default="dev")
            elif dtype == "identityId":
                value = _interactive_identity_id(api, org_id) or _parse_id(_prompt("Machine identity ID"))

    if not value:
        _print("Error: value is required. Use --value or run in interactive mode.")
        raise SystemExit(1)

    if dtype in ("orgId", "identityId", "projectId"):
        value = _parse_id(value)

    if dtype == "orgId":
        org_ids = get_org_ids()
        if org_ids and value not in org_ids:
            _print(f"Error: organization '{value}' not found in configured orgs. Run 'ih init token' to add it.")
            raise SystemExit(1)
    set_local_value(dtype, value)
    _print(f"Local {dtype} set to: {value}")


def cmd_unset(args):
    dtype = args.type
    if dtype not in DEFAULT_TYPES:
        _print(f"Error: invalid type '{dtype}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
        raise SystemExit(1)
    remove_local_value(dtype)
    _print(f"Local {dtype} removed.")


def _resolve_target(api, args):
    _warn_local_override("projectId", getattr(args, "project_id", None))
    project_id = _parse_id(getattr(args, "project_id", None)) or _effective_value("projectId")
    environment = getattr(args, "environment", None) or _effective_value("environment") or "dev"
    if not project_id:
        if not getattr(args, "yes", False):
            project_id = _interactive_project_id(api) or _parse_id(_prompt("Project ID"))
        else:
            _print("Error: --project-id is required with --yes")
            raise SystemExit(1)
    if not getattr(args, "environment", None) and not _effective_value("environment") and not getattr(args, "yes", False):
        environment = _interactive_environment(api, project_id) or environment
    return project_id, environment


def cmd_pull(args):
    org_id = _resolve_org_id(args, allow_prompt=not args.yes)
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    project_id, environment = _resolve_target(api, args)
    secrets = api.list_secrets(project_id, environment).get("secrets", [])
    if args.p:
        for s in secrets:
            _print(f"{s['secretKey']}={s.get('secretValue','')}")
        _print(f"Pulled secrets from Env: {environment} (printed to stdout).")
        return
    path = args.file or ".env"
    _write_env_file(path, secrets)
    _print(f"Pulled secrets from Env: {environment} to file: {path}.")


def _pair_updates(keys, values):
    if len(keys) != len(values):
        _print("Error: -k and -v must be provided in pairs.")
        raise SystemExit(1)
    return list(zip(keys, values))


def cmd_push(args):
    org_id = _resolve_org_id(args, allow_prompt=not args.yes)
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    project_id, environment = _resolve_target(api, args)

    has_file = bool(args.file)
    has_inline = bool(args.k or args.v)
    if has_file and has_inline:
        _print("Error: use either -f or -k/-v, not both.")
        raise SystemExit(1)

    if has_inline:
        updates = _pair_updates(args.k or [], args.v or [])
        source_desc = "inline key/value input"
    elif not has_file and not args.yes:
        secret_name, is_new = _interactive_secret_name(api, project_id, environment, allow_new=True)
        secret_value = _prompt("Secret value", secret=True)
        updates = [(secret_name, secret_value)]
        source_desc = "interactive input"
        if is_new:
            _print(f"New secret selected: {secret_name}")
    else:
        path = args.file or ".env"
        try:
            updates = _parse_env_file(path)
        except FileNotFoundError:
            _print(f"Error: file not found '{path}'")
            raise SystemExit(1)
        except ValueError as e:
            _print(f"Error: {e}")
            raise SystemExit(1)
        source_desc = f"file: {path}"

    if not updates:
        _print("Error: no values to push.")
        raise SystemExit(1)

    current = {s.get("secretKey"): s.get("secretValue", "") for s in api.list_secrets(project_id, environment).get("secrets", [])}
    if not args.yes:
        for k, nv in updates:
            ov = current.get(k)
            _print(f"{k}: {('<MISSING>' if ov is None else ov)} -> {nv}")
        if not _confirm("Proceed?"):
            _print("Aborted.")
            return

    for k, v in updates:
        try:
            api.update_secret(project_id, environment, k, v)
        except RuntimeError as e:
            if "404" in str(e):
                api.create_secret(project_id, environment, k, v)
            else:
                raise

    out_file = args.file or ".env"
    synced_local = False
    if Path(out_file).exists():
        secrets = api.list_secrets(project_id, environment).get("secrets", [])
        _write_env_file(out_file, secrets)
        synced_local = True
    _print(f"Pushed {len(updates)} secrets to Env: {environment} from {source_desc}.")
    if synced_local:
        _print(f"Updated local file: {out_file}.")


def cmd_history(args):
    org_id = _resolve_org_id(args, allow_prompt=not args.yes)
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    project_id, environment = _resolve_target(api, args)
    secret_name = args.name
    if not secret_name:
        if args.yes:
            _print("Error: --name is required with --yes")
            raise SystemExit(1)
        secret_name, _ = _interactive_secret_name(api, project_id, environment, allow_new=False)

    result = api.get_secret(project_id, environment, secret_name)
    current_version = result.get("secret", {}).get("version", 1)
    _print(f"Env: {environment}")
    _print(f"History for '{secret_name}' (current version: {current_version})")
    for v in range(current_version, 0, -1):
        try:
            s = api.get_secret(project_id, environment, secret_name, version=v).get("secret", {})
            _print(f"v{v} | updatedAt={s.get('updatedAt','')} | value={s.get('secretValue','')}")
        except Exception:
            _print(f"v{v} | not available")


def cmd_rollback(args):
    org_id = _resolve_org_id(args, allow_prompt=not args.yes)
    if not org_id:
        _print("Error: orgId is required.")
        raise SystemExit(1)
    api = _api_for_org_or_exit(org_id)
    project_id, environment = _resolve_target(api, args)
    secret_name = args.name
    version = args.version
    out_file = args.file or ".env"

    if not secret_name:
        if args.yes:
            _print("Error: --name is required with --yes")
            raise SystemExit(1)
        secret_name, _ = _interactive_secret_name(api, project_id, environment, allow_new=False)
    if not version:
        if args.yes:
            _print("Error: --version is required with --yes")
            raise SystemExit(1)
        version = _prompt("Version to rollback to")

    try:
        version = int(version)
    except ValueError:
        _print(f"Error: invalid version '{version}'")
        raise SystemExit(1)

    old = api.get_secret(project_id, environment, secret_name, version=version).get("secret", {})
    old_value = old.get("secretValue", "")

    if not args.yes and not _confirm(f"Rollback '{secret_name}' to version {version}?"):
        _print("Aborted.")
        return

    api.update_secret(project_id, environment, secret_name, old_value)

    synced_local = False
    if Path(out_file).exists():
        secrets = api.list_secrets(project_id, environment).get("secrets", [])
        _write_env_file(out_file, secrets)
        synced_local = True

    _print(f"Rolled back secret '{secret_name}' to version {version} in Env: {environment}.")
    if synced_local:
        _print(f"Updated local file: {out_file}.")


def main():
    parser = argparse.ArgumentParser(prog="ih", description="inf-hub CLI")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize ih")
    init_sub = p_init.add_subparsers(dest="init_command")

    p_init_token = init_sub.add_parser("token", help="Configure API token")
    p_init_token.add_argument("--token", help="Infisical API token")
    p_init_token.add_argument("--org-id", help="Organization ID bound to this token")
    p_init_token.add_argument("--org-name", help="Organization name (for display)")
    p_init_token.add_argument("--yes", "-y", action="store_true", help="Non-interactive")
    p_init_token.add_argument("--skip-checks", action="store_true", help="Skip token validation and org-id verification")

    p_init_folder = init_sub.add_parser("folder", help="Initialize local .inf context")
    a = p_init_folder.add_argument("--org-id", help="Organization ID")
    a = p_init_folder.add_argument("--project-id", help="Project ID")
    a = p_init_folder.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    p_init_folder.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_create = sub.add_parser("create", help="Create resources")
    create_sub = p_create.add_subparsers(dest="create_object")
    p_create_project = create_sub.add_parser("project", help="Create project")
    p_create_project.add_argument("--name", help="Project name")
    p_create_project.add_argument("--slug", help="Project slug")
    a = p_create_project.add_argument("--org-id", help="Organization ID")
    a = p_create_project.add_argument("--identity-id", help="Machine identity ID")
    p_create_project.add_argument("--role", choices=VALID_ROLES, help="Identity role")
    p_create_project.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_list = sub.add_parser("list", help="List resources")
    list_sub = p_list.add_subparsers(dest="list_object")
    p_lo = list_sub.add_parser("orgs", help="List organizations")
    a = p_lo.add_argument("--org-id", help="Organization ID")
    p_lo.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_lp = list_sub.add_parser("projects", help="List projects")
    a = p_lp.add_argument("--org-id", help="Organization ID")
    p_lp.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_li = list_sub.add_parser("identities", help="List identities")
    a = p_li.add_argument("--org-id", help="Organization ID")
    p_li.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_set = sub.add_parser("set", help="Set context value")
    p_set.add_argument("type", choices=DEFAULT_TYPES, help="Value type")
    a = p_set.add_argument("--value", help="Value")

    p_unset = sub.add_parser("unset", help="Unset context value")
    p_unset.add_argument("type", choices=DEFAULT_TYPES, help="Value type")

    p_pull = sub.add_parser("pull", help="Pull env from remote")
    a = p_pull.add_argument("--org-id", help="Organization ID")
    a = p_pull.add_argument("--project-id", help="Project ID")
    a = p_pull.add_argument("--environment", "-e", help="Environment")
    p_pull.add_argument("-f", "--file", help="Output file path")
    p_pull.add_argument("-p", action="store_true", help="Print to stdout")
    p_pull.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_push = sub.add_parser("push", help="Push env to remote")
    a = p_push.add_argument("--org-id", help="Organization ID")
    a = p_push.add_argument("--project-id", help="Project ID")
    a = p_push.add_argument("--environment", "-e", help="Environment")
    p_push.add_argument("-f", "--file", help="Input file path")
    p_push.add_argument("-k", action="append", help="Secret key (repeatable)")
    p_push.add_argument("-v", action="append", help="Secret value (repeatable)")
    p_push.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_hist = sub.add_parser("history", help="Show secret history")
    a = p_hist.add_argument("--org-id", help="Organization ID")
    a = p_hist.add_argument("--project-id", help="Project ID")
    a = p_hist.add_argument("--environment", "-e", help="Environment")
    a = p_hist.add_argument("--name", help="Secret name")
    p_hist.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    p_rb = sub.add_parser("rollback", help="Rollback secret and sync local file")
    a = p_rb.add_argument("--org-id", help="Organization ID")
    a = p_rb.add_argument("--project-id", help="Project ID")
    a = p_rb.add_argument("--environment", "-e", help="Environment")
    a = p_rb.add_argument("--name", help="Secret name")
    p_rb.add_argument("--version", help="Version to rollback to")
    p_rb.add_argument("-f", "--file", help="Local file to sync (default: .env)")
    p_rb.add_argument("--yes", "-y", action="store_true", help="Non-interactive")

    argcomplete.autocomplete(parser, default_completer=None)
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "init":
            if getattr(args, "init_command", None) == "folder":
                cmd_init_folder(args)
            else:
                cmd_init_token(args)
            return
        if args.command == "create":
            if args.create_object != "project":
                _print("Error: missing create object. Use: ih create project")
                raise SystemExit(1)
            cmd_create_project(args)
            return
        if args.command == "list":
            if args.list_object == "orgs":
                cmd_list_orgs(args)
            elif args.list_object == "projects":
                cmd_list_projects(args)
            elif args.list_object == "identities":
                cmd_list_identities(args)
            else:
                _print("Error: missing list object. Use: ih list orgs|projects|identities")
                raise SystemExit(1)
            return
        if args.command == "set":
            cmd_set(args)
            return
        if args.command == "unset":
            cmd_unset(args)
            return
        if args.command == "pull":
            if args.p and args.file:
                _print("Error: use either -p or -f, not both.")
                raise SystemExit(1)
            cmd_pull(args)
            return
        if args.command == "push":
            cmd_push(args)
            return
        if args.command == "history":
            cmd_history(args)
            return
        if args.command == "rollback":
            cmd_rollback(args)
            return
    except KeyboardInterrupt:
        _print("\nOperation cancelled.")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        msg = str(e)
        if "API error" in msg:
            _print(f"Error: {msg}")
        elif "not configured" in msg.lower():
            _print(f"Error: {msg}")
            _print("Run 'ih init' to configure.")
        elif "unauthorized" in msg.lower() or "401" in msg:
            _print("Error: Unauthorized. Check your API token.")
            _print("Run 'ih init token --token YOUR_TOKEN' to update.")
        elif "forbidden" in msg.lower() or "403" in msg:
            _print("Error: Forbidden. You don't have permission for this operation.")
        else:
            _print(f"Error: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
