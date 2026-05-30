# PYTHON_ARGCOMPLETE_OK
import argparse
import getpass
import os
import sys

import argcomplete

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


def get_base_url_or_exit():
    base_url = os.environ.get("INFISICAL_API_URL")
    if not base_url:
        print("Error: INFISICAL_API_URL is not set.")
        print("Set it with:")
        print("  export INFISICAL_API_URL=https://app.infisical.com")
        raise SystemExit(1)
    return base_url


def prompt(label, secret=False, default=None):
    suffix = f" [{default}]" if default else ""
    if secret:
        value = getpass.getpass(f"{label}{suffix}: ")
    else:
        value = input(f"{label}{suffix}: ")
    return value.strip() if value.strip() else default


def confirm(message):
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
    org_id = _parse_id(args.org_id) if args.org_id else None
    project_id = _parse_id(args.project_id) if args.project_id else None
    environment = args.environment or "dev"

    if not args.yes:
        if not org_id:
            org_id = prompt("Organization ID")
        if not project_id:
            project_id = prompt("Project ID")
        if not environment:
            environment = prompt("Environment", default="dev")
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
            org_id = prompt("Organization ID")
        add_identity = input("Add machine identity? [y/N]: ").strip().lower()
        if add_identity == "y":
            if not identity_id:
                identity_id = prompt("Machine identity ID")
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
        confirm = input("\nProceed? [Y/n]: ").strip().lower()
        if confirm == "n":
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

    print("Organizations:")
    for org in orgs:
        print(f"  ID: {org['id']}")
        print(f"    Projects: {len(org['projects'])}")
        for proj in org["projects"]:
            print(f"      - {proj}")
        print()


def cmd_list_projects(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    result = api.list_projects()
    projects = result.get("projects", [])

    if not projects:
        print("No projects found.")
        return

    print("Projects:")
    for project in projects:
        print(f"  {project['name']}")
        print(f"    ID:   {project['id']}")
        print(f"    Slug: {project['slug']}")
        envs = project.get("environments", [])
        if envs:
            print(f"    Environments:")
            for env in envs:
                print(f"      - {env['name']} (slug: {env['slug']})")
        print()


def cmd_list_identities(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "org_id", "orgId")
    org_id = _parse_id(args.org_id) or _get_default_with_local_override("orgId")
    if not org_id:
        org_id = prompt("Organization ID")

    result = api.list_identities(org_id)
    identities = result.get("identities", [])

    if not identities:
        print("No identities found.")
        return

    print("Machine Identities:")
    for identity in identities:
        name = identity.get("identity", {}).get("name", "unknown")
        identity_id = identity.get("identityId", identity.get("id"))
        role = identity.get("role", "")
        print(f"  {name}")
        print(f"    ID:   {identity_id}")
        print(f"    Role: {role}")


def cmd_set_default(args):
    dtype = args.type
    value = args.value

    if dtype not in DEFAULT_TYPES:
        print(f"Error: invalid type '{dtype}'. Must be one of: {', '.join(DEFAULT_TYPES)}")
        raise SystemExit(1)

    if value:
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

    print("Defaults:")
    for key in DEFAULT_TYPES:
        entry = defaults.get(key)
        value = entry.get("value") if isinstance(entry, dict) else entry

        if not value:
            print(f"  {key}: <Unset>")
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

        if label:
            print(f"  {key}: {value} ({label})")
        else:
            print(f"  {key}: {value}")


def cmd_show_env(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"

    if not project_id:
        if not args.yes:
            project_id = prompt("Project ID")
        else:
            print("Error: --project-id is required with --yes (or set default with: infisical-utils set-default --type projectId --value <id>)")
            raise SystemExit(1)

    result = api.list_secrets(project_id, environment)
    secrets = result.get("secrets", [])

    if not secrets:
        print(f"No secrets found in project {project_id} for environment {environment}")
        return

    key_width = max(len(s["secretKey"]) for s in secrets)
    key_width = max(key_width, 3)

    print(f"{'KEY':<{key_width}}  VALUE")
    print(f"{'-'*key_width}  {'-'*40}")
    for secret in secrets:
        key = secret["secretKey"]
        value = secret.get("secretValue", "")
        print(f"{key:<{key_width}}  {value}")


def cmd_get_env(args):
    token = get_token_or_exit()
    base_url = get_base_url_or_exit()
    api = InfisicalAPI(base_url, token)

    _warn_local_override(args, "project_id", "projectId")
    project_id = _parse_id(args.project_id) or _get_default_with_local_override("projectId")
    environment = args.environment or _get_default_with_local_override("environment") or "dev"

    if not project_id:
        if not args.yes:
            project_id = prompt("Project ID")
        else:
            print("Error: --project-id is required with --yes (or set default with: infisical-utils set-default --type projectId --value <id>)")
            raise SystemExit(1)

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
            project_id = prompt("Project ID")
        else:
            print("Error: --project-id is required with --yes (or set default with: infisical-utils set-default --type projectId --value <id>)")
            raise SystemExit(1)

    updates = []
    for item in args.set:
        if "=" not in item:
            print(f"Error: invalid format '{item}'. Use KEY=VALUE")
            raise SystemExit(1)
        key, value = item.split("=", 1)
        updates.append((key.strip(), value.strip()))

    if not updates:
        print("Error: no updates specified. Use --set KEY=VALUE")
        raise SystemExit(1)

    if not args.yes:
        print(f"Will update {len(updates)} secret(s) in environment '{environment}':")
        for key, value in updates:
            print(f"  {key} = {value}")
        if not confirm("Proceed?"):
            return

    for key, value in updates:
        try:
            api.update_secret(project_id, environment, key, value)
            print(f"Updated: {key}")
        except RuntimeError as e:
            if "404" in str(e):
                try:
                    api.create_secret(project_id, environment, key, value)
                    print(f"Created: {key}")
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
            project_id = prompt("Project ID")
        else:
            print("Error: --project-id is required with --yes")
            raise SystemExit(1)

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
            project_id = prompt("Project ID")
        else:
            print("Error: --project-id is required with --yes")
            raise SystemExit(1)

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
    sd.add_argument("--value", help="Value to set (omit to remove)")

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
    ue.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    sh = sub.add_parser("show-env-history", help="Show version history for a secret")
    arg = sh.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = sh.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    sh.add_argument("--name", help="Secret name")
    sh.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    rb = sub.add_parser("rollback-env", help="Rollback a secret to a previous version")
    arg = rb.add_argument("--project-id", help="Project ID")
    arg.completer = _complete_project_ids
    arg = rb.add_argument("--environment", "-e", help="Environment slug (default: dev)")
    arg.completer = _complete_environments
    rb.add_argument("--name", help="Secret name")
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
