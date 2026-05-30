# PYTHON_ARGCOMPLETE_OK
import argparse
import getpass
import os
import sys

import argcomplete
try:
    import questionary
    HAS_QUESTIONARY = True
except Exception:
    HAS_QUESTIONARY = False
try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except Exception:
    HAS_RICH = False

from infisical_utils.config import (
    save_config,
    CONFIG_FILE,
    get_default,
    set_default,
    remove_default,
    load_config,
    DEFAULT_TYPES,
    get_token_or_exit,
    save_token_secure,
    load_token_secure,
    load_local_inf,
    save_local_inf,
)
from infisical_utils.api import InfisicalAPI

VALID_ROLES = ("admin", "member", "viewer", "no-access")
CONSOLE = Console() if HAS_RICH else None


def _print_table(title, columns, rows):
    if HAS_RICH:
        table = Table(title=title)
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(x) for x in row])
        CONSOLE.print(table)
        return
    if title:
        print(title)
    print("  ".join(columns))
    for row in rows:
        print("  ".join(str(x) for x in row))


def _print_diff_rows(title, rows):
    if HAS_RICH:
        table = Table(title=title)
        table.add_column("KEY")
        table.add_column("OLD")
        table.add_column("NEW")
        for key, old_value, new_value in rows:
            old_display = "<MISSING>" if old_value is None else str(old_value)
            table.add_row(str(key), old_display, str(new_value))
        CONSOLE.print(table)
        return
    print(title)
    for key, old_value, new_value in rows:
        old_display = "<MISSING>" if old_value is None else old_value
        print(f"  {key}:")
        print(f"    old: {old_display}")
        print(f"    new: {new_value}")


def _select_from_choices(message, choices):
    if HAS_QUESTIONARY:
        answer = questionary.select(message, choices=choices).ask()
        if answer:
            return answer
    return None


def _interactive_select_org_id(api):
    try:
        orgs = api.list_organizations().get("organizations", [])
    except Exception:
        return None
    if not orgs:
        return None
    choices = [f"{o['id']} | {o.get('name', o['id'])}" for o in orgs]
    selected = _select_from_choices("Select organization", choices)
    return _parse_id(selected) if selected else None


def _interactive_select_project_id(api):
    try:
        projects = api.list_projects().get("projects", [])
    except Exception:
        return None
    if not projects:
        return None
    choices = [f"{p['id']} | {p['name']}" for p in projects]
    selected = _select_from_choices("Select project", choices)
    return _parse_id(selected) if selected else None


def _interactive_select_environment(api, project_id):
    if not project_id:
        return None
    try:
        projects = api.list_projects().get("projects", [])
    except Exception:
        return None
    env_choices = []
    for p in projects:
        if p["id"] == project_id:
            env_choices = [f"{e['slug']} | {e['name']}" for e in p.get("environments", [])]
            break
    if not env_choices:
        return None
    selected = _select_from_choices("Select environment", env_choices)
    return _parse_id(selected) if selected else None


def _interactive_select_identity_id(api, org_id):
    if not org_id:
        return None
    try:
        identities = api.list_identities(org_id).get("identities", [])
    except Exception:
        return None
    if not identities:
        return None
    choices = [
        f"{i.get('identityId', i.get('id'))} | {i.get('identity', {}).get('name', 'unknown')}"
        for i in identities
    ]
    selected = _select_from_choices("Select machine identity", choices)
    return _parse_id(selected) if selected else None


def _load_local_inf_silent():
    try:
        return load_local_inf()
    except Exception:
        return None


def _load_local_inf_or_exit():
    try:
        return load_local_inf()
    except ValueError as e:
        print(f"Error: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"Error: cannot read .inf: {e}")
        raise SystemExit(1)


def _get_default_with_local_override(key):
    local_inf = _load_local_inf_or_exit()
    if local_inf is not None:
        return local_inf.get(key)
    return get_default(key)


def _warn_local_override(args, attr_name, label):
    local_inf = _load_local_inf_silent()
    if local_inf is not None and getattr(args, attr_name, None):
        print(f"Warning: overriding local .inf value for {label}.")


def _get_api_silent():
    """Get API client without raising errors (for completers)."""
    try:
        base_url = os.environ.get("INFISICAL_API_URL")
        if not base_url:
            return None
        config = load_config()
        token = load_token_secure()
        if not token and (not config or "token" not in config):
            return None
        return InfisicalAPI(base_url, token or config["token"])
    except Exception:
        return None


def _parse_id(value):
    """Parse ID from 'UUID | name' format, returning only the UUID."""
    if not value:
        return None
    return value.split("|")[0].strip()


def _complete_project_ids(prefix, **kwargs):
    """Autocomplete for project IDs."""
    api = _get_api_silent()
    if not api:
        return []
    try:
        result = api.list_projects()
        projects = result.get("projects", [])
        return [f"{p['id']} | {p['name']}" for p in projects]
    except Exception:
        return []


def _complete_org_ids(prefix, **kwargs):
    """Autocomplete for organization IDs."""
    api = _get_api_silent()
    if not api:
        return []
    try:
        result = api.list_organizations()
        orgs = result.get("organizations", [])
        return [f"{o['id']} | {o.get('name', 'Organization')}" for o in orgs]
    except Exception:
        return []


def _complete_identity_ids(prefix, **kwargs):
    """Autocomplete for identity IDs."""
    api = _get_api_silent()
    if not api:
        return []
    try:
        org_id = _get_default_with_local_override("orgId")
        if not org_id:
            return []
        result = api.list_identities(org_id)
        identities = result.get("identities", [])
        return [f"{i['identityId']} | {i['identity']['name']}" for i in identities]
    except Exception:
        return []


def _complete_environments(prefix, **kwargs):
    """Autocomplete for environment slugs."""
    api = _get_api_silent()
    if not api:
        return []
    try:
        project_id = _get_default_with_local_override("projectId")
        if not project_id:
            return []
        result = api.list_projects()
        for p in result.get("projects", []):
            if p["id"] == project_id:
                return [env["slug"] for env in p.get("environments", [])]
        return []
    except Exception:
        return []


def _complete_default_value(prefix, parsed_args, **kwargs):
    """Autocomplete for `set-default --value` based on selected --type."""
    dtype = getattr(parsed_args, "type", None)
    if dtype == "orgId":
        return _complete_org_ids(prefix, **kwargs)
    if dtype == "projectId":
        return _complete_project_ids(prefix, **kwargs)
    if dtype == "identityId":
        return _complete_identity_ids(prefix, **kwargs)
    if dtype == "environment":
        return _complete_environments(prefix, **kwargs)
    return []


def _complete_secret_names(prefix, parsed_args, **kwargs):
    """Autocomplete for secret names based on effective project/environment."""
    api = _get_api_silent()
    if not api:
        return []
    try:
        project_id = _parse_id(getattr(parsed_args, "project_id", None)) or _get_default_with_local_override("projectId")
        environment = getattr(parsed_args, "environment", None) or _get_default_with_local_override("environment") or "dev"
        if not project_id:
            return []
        result = api.list_secrets(project_id, environment)
        secrets = result.get("secrets", [])
        return [s.get("secretKey", "") for s in secrets if s.get("secretKey")]
    except Exception:
        return []


def _parse_env_file(file_path):
    updates = []
    with open(file_path) as f:
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                raise ValueError(f"Invalid .env format at line {line_no}: expected KEY=VALUE")
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"Invalid .env format at line {line_no}: empty key")
            updates.append((key, value))
    return updates


def get_base_url_or_exit():
    base_url = os.environ.get("INFISICAL_API_URL")
    if not base_url:
        print("Error: INFISICAL_API_URL is not set.")
        print("Set it with:")
        print("  export INFISICAL_API_URL=https://app.infisical.com")
        raise SystemExit(1)
    return base_url


def prompt(label, secret=False, default=None):
    if HAS_QUESTIONARY:
        if secret:
            value = questionary.password(label).ask()
        else:
            value = questionary.text(label, default=default or "").ask()
            if value is None:
                value = ""
    else:
        suffix = f" [{default}]" if default else ""
        if secret:
            value = getpass.getpass(f"{label}{suffix}: ")
        else:
            value = input(f"{label}{suffix}: ")
    return value.strip() if value.strip() else default


def confirm(message):
    if HAS_QUESTIONARY:
        return bool(questionary.confirm(message, default=False).ask())
    response = input(f"{message} [y/N]: ")
    return response.lower() in ("y", "yes")


def cmd_init_token(args):
    print("Configure infisical-utils")

    if not os.environ.get("INFISICAL_API_URL"):
        print("Warning: INFISICAL_API_URL is not set.")
        print("Set it with:")
        print("  export INFISICAL_API_URL=https://app.infisical.com")
        print()

    token = args.token

    if not args.yes:
        if not token:
            token = prompt("Infisical token (secret)", secret=True)
    else:
        if not token:
            print("Error: --token is required with --yes")
            raise SystemExit(1)

    if not token:
        print("Error: token is required.")
        raise SystemExit(1)

    save_token_secure(token)
    existing = load_config() or {}
    # Keep only non-sensitive settings in config.json.
    existing.pop("token", None)
    save_config(existing)
    print(f"Configuration saved to {CONFIG_FILE}")


def cmd_init_folder(args):
    api = None
    try:
        base_url = os.environ.get("INFISICAL_API_URL")
        token = get_token_or_exit() if base_url else None
        if base_url and token:
            api = InfisicalAPI(base_url, token)
    except Exception:
        # Folder init can still proceed with manual inputs if API/bootstrap is unavailable.
        api = None

    org_id = _parse_id(args.org_id) if args.org_id else None
    project_id = _parse_id(args.project_id) if args.project_id else None
    environment = args.environment or "dev"

    if not args.yes:
        if not org_id:
            org_id = _interactive_select_org_id(api) or _parse_id(prompt("Organization ID"))
        if not project_id:
            project_id = _interactive_select_project_id(api) or _parse_id(prompt("Project ID"))
        if not environment:
            environment = _interactive_select_environment(api, project_id) or prompt("Environment", default="dev")
    else:
        if not org_id:
            print("Error: --org-id is required with --yes")
            raise SystemExit(1)
        if not project_id:
            print("Error: --project-id is required with --yes")
            raise SystemExit(1)

    if not org_id:
        print("Error: organization ID is required.")
        raise SystemExit(1)
    if not project_id:
        print("Error: project ID is required.")
        raise SystemExit(1)

    if not args.yes:
        print("\nLocal folder defaults (.inf):")
        print(f"  orgId:       {org_id}")
        print(f"  projectId:   {project_id}")
        print(f"  environment: {environment}")
        if not confirm("Proceed?"):
            print("Aborted.")
            return

    save_local_inf(org_id, project_id, environment)
    print("Folder configuration saved to .inf")


def cmd_create_project(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    project_name = args.name
    slug = args.slug
    _warn_local_override(args, "org_id", "orgId")
    org_id = _parse_id(args.org_id) or _get_default_with_local_override("orgId")
    identity_id = _parse_id(args.identity_id) or get_default("identityId")
    role = args.role

    if not args.yes:
        if not project_name:
            project_name = prompt("Project name")
        if not slug:
            slug = prompt("Slug", default=project_name)
        if not org_id:
            org_id = _interactive_select_org_id(api) or _parse_id(prompt("Organization ID"))
        add_identity = confirm("Add machine identity?")
        if add_identity:
            if not identity_id:
                identity_id = _interactive_select_identity_id(api, org_id) or _parse_id(prompt("Machine identity ID"))
            if not role:
                role = prompt(f"Role ({', '.join(VALID_ROLES)})", default="member")
    else:
        if not project_name:
            print("Error: --name is required with --yes")
            raise SystemExit(1)
        if not slug:
            slug = project_name
        if not org_id:
            print("Error: --org-id is required with --yes (or set default with: infisical-utils set-default --type orgId --value <id>)")
            raise SystemExit(1)
        if identity_id and not role:
            role = "member"

    if role and role not in VALID_ROLES:
        print(f"Error: invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}")
        raise SystemExit(1)

    if not args.yes:
        print("\nSummary:")
        print(f"  Project name: {project_name}")
        print(f"  Slug:         {slug}")
        print(f"  Organization: {org_id}")
        if identity_id:
            print(f"  Identity:     {identity_id} (role: {role})")
        if not confirm("Proceed?"):
            print("Aborted.")
            return

    print(f"Creating project '{project_name}'...")
    result = api.create_project(project_name, org_id, slug)
    project = result["project"]
    print(f"Project created: {project['id']}")
    print(f"  Name: {project['name']}")
    print(f"  Slug: {project['slug']}")

    if identity_id:
        print(f"Adding identity {identity_id} with role '{role}'...")
        api.add_identity_to_project(project["id"], identity_id, role)
        print("Identity added.")


def cmd_list_orgs(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    result = api.list_organizations()
    orgs = result.get("organizations", [])

    if not orgs:
        print("No organizations found.")
        return

    rows = []
    for org in orgs:
        rows.append((org["id"], len(org["projects"]), ", ".join(org["projects"])))
    _print_table("Organizations", ["ORG ID", "PROJECT COUNT", "PROJECTS"], rows)


def cmd_list_projects(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    result = api.list_projects()
    projects = result.get("projects", [])

    if not projects:
        print("No projects found.")
        return

    rows = []
    for project in projects:
        envs = project.get("environments", [])
        env_display = ", ".join([f"{e['name']}({e['slug']})" for e in envs]) if envs else "-"
        rows.append((project["name"], project["id"], project["slug"], env_display))
    _print_table("Projects", ["NAME", "ID", "SLUG", "ENVIRONMENTS"], rows)


def cmd_list_identities(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "org_id", "orgId")
    org_id = _parse_id(args.org_id) or _get_default_with_local_override("orgId")
    if not org_id:
        org_id = _interactive_select_org_id(api) or _parse_id(prompt("Organization ID"))

    result = api.list_identities(org_id)
    identities = result.get("identities", [])

    if not identities:
        print("No identities found.")
        return

    rows = []
    for identity in identities:
        name = identity.get("identity", {}).get("name", "unknown")
        identity_id = identity.get("identityId", identity.get("id"))
        role = identity.get("role", "")
        rows.append((name, identity_id, role))
    _print_table("Machine Identities", ["NAME", "ID", "ROLE"], rows)


def cmd_set_default(args):
    dtype = args.type
    value = args.value

    if dtype not in DEFAULT_TYPES:
        print(f"Error: invalid type '{dtype}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
        raise SystemExit(1)

    if value:
        if dtype in ("orgId", "identityId", "projectId"):
            value = _parse_id(value)
        label = None
        try:
            token = get_token_or_exit()
            base_url = get_base_url_or_exit()
            api = InfisicalAPI(base_url, token)

            if dtype == "projectId":
                resolved = api.resolve_project(value)
                if resolved:
                    label = f"{resolved['name']} ({resolved['slug']})"
                else:
                    print(f"Warning: project {value} not found")
            elif dtype == "identityId":
                resolved = api.resolve_identity(value)
                if resolved:
                    label = resolved["name"]
                else:
                    print(f"Warning: identity {value} not found")
            elif dtype == "orgId":
                resolved = api.resolve_org(value)
                if resolved:
                    label = resolved["name"]
                else:
                    print(f"Warning: organization {value} not found")
            elif dtype == "environment":
                project_id = get_default("projectId")
                if project_id:
                    resolved = api.resolve_environment(project_id, value)
                    if resolved:
                        label = resolved["name"]
                    else:
                        print(f"Warning: environment {value} not found in default project")
                else:
                    print("Warning: no default projectId set, cannot verify environment")
        except Exception as e:
            print(f"Warning: could not verify {dtype}: {e}")

        set_default(dtype, value)
        if label:
            print(f"Default {dtype} set to: {value} ({label})")
        else:
            print(f"Default {dtype} set to: {value}")
    else:
        remove_default(dtype)
        print(f"Default {dtype} removed.")


def cmd_unset_default(args):
    args.value = None
    cmd_set_default(args)


def cmd_show_defaults(args):
    config = load_config()
    defaults = config.get("defaults", {}) if config else {}

    api = None
    try:
        base_url = get_base_url_or_exit()
        token = get_token_or_exit()
        api = InfisicalAPI(base_url, token)
    except SystemExit:
        pass

    rows = []
    for key in DEFAULT_TYPES:
        entry = defaults.get(key)
        value = entry.get("value") if isinstance(entry, dict) else entry

        if not value:
            rows.append((key, "<Unset>", ""))
            continue

        label = None
        if api:
            try:
                if key == "projectId":
                    resolved = api.resolve_project(value)
                    if resolved:
                        label = f"{resolved['name']} ({resolved['slug']})"
                elif key == "identityId":
                    resolved = api.resolve_identity(value)
                    if resolved:
                        label = resolved["name"]
                elif key == "orgId":
                    resolved = api.resolve_org(value)
                    if resolved:
                        label = resolved["name"]
                elif key == "environment":
                    project_id = get_default("projectId")
                    if project_id:
                        resolved = api.resolve_environment(project_id, value)
                        if resolved:
                            label = resolved["name"]
            except Exception:
                pass

        rows.append((key, value, label or ""))
    _print_table("Defaults", ["TYPE", "VALUE", "LABEL"], rows)


def cmd_show_env(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"

    if not project_id:
        if not args.yes:
            project_id = _interactive_select_project_id(api) or _parse_id(prompt("Project ID"))
        else:
            print("Error: --project-id is required with --yes (or set default with: infisical-utils set-default --type projectId --value <id>)")
            raise SystemExit(1)
    if not args.environment and not _get_default_with_local_override("environment") and not args.yes:
        environment = _interactive_select_environment(api, project_id) or environment

    result = api.list_secrets(project_id, environment)
    secrets = result.get("secrets", [])

    if not secrets:
        print(f"No secrets found in project {project_id} for environment {environment}")
        return

    rows = [(s["secretKey"], s.get("secretValue", "")) for s in secrets]
    _print_table(f"Secrets ({environment})", ["KEY", "VALUE"], rows)


def cmd_get_env(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"

    if not project_id:
        if not args.yes:
            project_id = _interactive_select_project_id(api) or _parse_id(prompt("Project ID"))
        else:
            print("Error: --project-id is required with --yes (or set default with: infisical-utils set-default --type projectId --value <id>)")
            raise SystemExit(1)
    if not args.environment and not _get_default_with_local_override("environment") and not args.yes:
        environment = _interactive_select_environment(api, project_id) or environment

    result = api.list_secrets(project_id, environment)
    secrets = result.get("secrets", [])

    if not secrets:
        return

    for secret in secrets:
        key = secret["secretKey"]
        value = secret.get("secretValue", "")
        print(f"{key}={value}")


def cmd_update_env(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"

    if not project_id:
        if not args.yes:
            project_id = _interactive_select_project_id(api) or _parse_id(prompt("Project ID"))
        else:
            print("Error: --project-id is required with --yes (or set default with: infisical-utils set-default --type projectId --value <id>)")
            raise SystemExit(1)
    if not args.environment and not _get_default_with_local_override("environment") and not args.yes:
        environment = _interactive_select_environment(api, project_id) or environment

    updates = []
    set_items = args.set or []
    for item in set_items:
        if "=" not in item:
            print(f"Error: invalid format '{item}'. Use KEY=VALUE")
            raise SystemExit(1)
        key, value = item.split("=", 1)
        updates.append((key.strip(), value))

    if args.file:
        try:
            updates.extend(_parse_env_file(args.file))
        except FileNotFoundError:
            print(f"Error: file not found '{args.file}'")
            raise SystemExit(1)
        except ValueError as e:
            print(f"Error: {e}")
            raise SystemExit(1)

    if not updates:
        print("Error: no updates specified. Use --set KEY=VALUE or --file .env")
        raise SystemExit(1)

    try:
        existing = api.list_secrets(project_id, environment).get("secrets", [])
        current_values = {s.get("secretKey"): s.get("secretValue", "") for s in existing}
    except Exception as e:
        print(f"Error: unable to read current secrets for diff: {e}")
        raise SystemExit(1)

    display_updates = []
    for key, new_value in updates:
        old_value = current_values.get(key)
        display_updates.append((key, old_value, new_value))

    if not args.yes:
        _print_diff_rows(
            f"Pending updates ({environment}) - {len(display_updates)} item(s)",
            display_updates,
        )
        if not confirm("Proceed?"):
            return

    for key, old_value, value in display_updates:
        try:
            api.update_secret(project_id, environment, key, value)
            _print_diff_rows("Updated", [(key, old_value, value)])
        except RuntimeError as e:
            if "404" in str(e):
                try:
                    api.create_secret(project_id, environment, key, value)
                    _print_diff_rows("Created", [(key, None, value)])
                except Exception as create_err:
                    print(f"Error creating {key}: {create_err}")
            else:
                print(f"Error updating {key}: {e}")
        except Exception as e:
            print(f"Error updating {key}: {e}")


def cmd_show_env_history(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"
    secret_name = args.name

    if not project_id:
        if not args.yes:
            project_id = _interactive_select_project_id(api) or _parse_id(prompt("Project ID"))
        else:
            print("Error: --project-id is required with --yes")
            raise SystemExit(1)
    if not args.environment and not _get_default_with_local_override("environment") and not args.yes:
        environment = _interactive_select_environment(api, project_id) or environment

    if not secret_name:
        if not args.yes:
            secret_name = prompt("Secret name")
        else:
            print("Error: --name is required with --yes")
            raise SystemExit(1)

    try:
        result = api.get_secret(project_id, environment, secret_name)
        secret = result.get("secret", {})
        current_version = secret.get("version", 1)

        print(f"History for '{secret_name}' in environment '{environment}':")
        print(f"Current version: {current_version}")
        print()

        for v in range(current_version, 0, -1):
            try:
                old_result = api.get_secret(project_id, environment, secret_name, version=v)
                old_secret = old_result.get("secret", {})
                old_value = old_secret.get("secretValue", "")
                updated_at = old_secret.get("updatedAt", "")
                print(f"Version {v}:")
                print(f"  Value: {old_value}")
                print(f"  Updated: {updated_at}")
                print()
            except Exception:
                print(f"Version {v}: (not available)")
                print()
    except Exception as e:
        print(f"Error: {e}")


def cmd_rollback_env(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"
    secret_name = args.name
    version = args.version

    if not project_id:
        if not args.yes:
            project_id = _interactive_select_project_id(api) or _parse_id(prompt("Project ID"))
        else:
            print("Error: --project-id is required with --yes")
            raise SystemExit(1)
    if not args.environment and not _get_default_with_local_override("environment") and not args.yes:
        environment = _interactive_select_environment(api, project_id) or environment

    if not secret_name:
        if not args.yes:
            secret_name = prompt("Secret name")
        else:
            print("Error: --name is required with --yes")
            raise SystemExit(1)

    if not version:
        if not args.yes:
            version = prompt("Version to rollback to")
        else:
            print("Error: --version is required with --yes")
            raise SystemExit(1)

    try:
        version = int(version)
    except ValueError:
        print(f"Error: invalid version '{version}'")
        raise SystemExit(1)

    try:
        old_result = api.get_secret(project_id, environment, secret_name, version=version)
        old_secret = old_result.get("secret", {})
        old_value = old_secret.get("secretValue", "")

        if not args.yes:
            print(f"Will rollback '{secret_name}' to version {version}:")
            print(f"  Value: {old_value}")
            if not confirm("Proceed?"):
                return

        api.update_secret(project_id, environment, secret_name, old_value)
        print(f"Rolled back '{secret_name}' to version {version}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(prog="infisical-utils", description="CLI utilities for Infisical")
    sub = parser.add_subparsers(dest="command")

    ini = sub.add_parser("init", help="Initialize infisical-utils")
    ini_sub = ini.add_subparsers(dest="init_command")

    ini_token = ini_sub.add_parser("token", help="Configure Infisical token")
    ini_token.add_argument("--token", help="Infisical API token")
    ini_token.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    # Backward compatibility: allow `infisical-utils init --token ...`
    ini.add_argument("--token", help=argparse.SUPPRESS)
    ini.add_argument("--yes", "-y", action="store_true", help=argparse.SUPPRESS)

    ini_folder = ini_sub.add_parser("folder", help="Initialize local folder defaults in .inf")
    arg = ini_folder.add_argument("--org-id", help="Organization ID")
    arg.completer = _complete_org_ids
    arg = ini_folder.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = ini_folder.add_argument("--environment", "-e", help="Preferred environment (default: dev)")
    arg.completer = _complete_environments
    ini_folder.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    cp = sub.add_parser("create-project", help="Create a new Infisical project")
    cp.add_argument("--name", help="Project name")
    cp.add_argument("--slug", help="Project slug (defaults to project name)")
    arg = cp.add_argument("--org-id", help="Organization ID")
    arg.completer = _complete_org_ids
    arg = cp.add_argument("--identity-id", help="Machine identity ID to add to the project")
    arg.completer = _complete_identity_ids
    cp.add_argument("--role", choices=VALID_ROLES, help="Role for the machine identity")
    cp.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    lo = sub.add_parser("list-orgs", help="List organizations")

    lp = sub.add_parser("list-projects", help="List projects with environments")

    li = sub.add_parser("list-identities", help="List machine identities")
    arg = li.add_argument("--org-id", help="Organization ID")
    arg.completer = _complete_org_ids

    sd = sub.add_parser("set-default", help="Set or remove a default value")
    sd.add_argument("--type", required=True, choices=DEFAULT_TYPES, help="Type of default to set")
    arg = sd.add_argument("--value", help="Value to set (omit to remove)")
    arg.completer = _complete_default_value

    ud = sub.add_parser("unset-default", help="Remove a default value")
    ud.add_argument("--type", required=True, choices=DEFAULT_TYPES, help="Type of default to remove")

    sub.add_parser("show-defaults", help="Show current default values")

    se = sub.add_parser("show-env", help="Show environment variables in tabular format")
    arg = se.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = se.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    se.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    ge = sub.add_parser("get-env", help="Get environment variables in KEY=VALUE format (redirectable)")
    arg = ge.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = ge.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    ge.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    ue = sub.add_parser("update-env", help="Update environment variables")
    arg = ue.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = ue.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    ue.add_argument("--set", action="append", metavar="KEY=VALUE", help="Set a secret (can be used multiple times)")
    ue.add_argument("--file", help="Load secrets from .env file (KEY=VALUE)")
    ue.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    sh = sub.add_parser("show-env-history", help="Show version history for a secret")
    arg = sh.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = sh.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    arg = sh.add_argument("--name", help="Secret name")
    arg.completer = _complete_secret_names
    sh.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    rb = sub.add_parser("rollback-env", help="Rollback a secret to a previous version")
    arg = rb.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = rb.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    arg = rb.add_argument("--name", help="Secret name")
    arg.completer = _complete_secret_names
    rb.add_argument("--version", help="Version to rollback to")
    rb.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create-project": cmd_create_project,
        "list-orgs": cmd_list_orgs,
        "list-projects": cmd_list_projects,
        "list-identities": cmd_list_identities,
        "set-default": cmd_set_default,
        "unset-default": cmd_unset_default,
        "show-defaults": cmd_show_defaults,
        "show-env": cmd_show_env,
        "get-env": cmd_get_env,
        "update-env": cmd_update_env,
        "show-env-history": cmd_show_env_history,
        "rollback-env": cmd_rollback_env,
    }

    try:
        if args.command == "init":
            if getattr(args, "init_command", None) == "folder":
                cmd_init_folder(args)
            else:
                cmd_init_token(args)
            return
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        error_msg = str(e)
        if "API error" in error_msg:
            print(f"Error: {error_msg}")
        elif "not configured" in error_msg.lower():
            print(f"Error: {error_msg}")
            print("Run 'infisical-utils init' to configure.")
        elif "not found" in error_msg.lower():
            print(f"Error: {error_msg}")
        elif "unauthorized" in error_msg.lower() or "401" in error_msg:
            print("Error: Unauthorized. Check your API token.")
            print("Run 'infisical-utils init --token YOUR_TOKEN' to update.")
        elif "forbidden" in error_msg.lower() or "403" in error_msg:
            print("Error: Forbidden. You don't have permission for this operation.")
        else:
            print(f"Error: {error_msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
