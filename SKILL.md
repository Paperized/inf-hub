# infisical-utils Skill

## Description

`infisical-utils` is a CLI utility for managing Infisical projects, identities, and secrets with local folder context, secure token storage, and interactive workflows.

## When to use this tool

Use `infisical-utils` when you need to:
- Initialize secure CLI access with keyring-backed token storage
- Work in a project folder using local `.inf` defaults (`orgId`, `projectId`, `environment`)
- Create projects and manage machine identity memberships
- Read, export, bulk update, inspect history, and rollback secrets
- Use interactive REST-backed menus instead of manually typing IDs

## Initial Setup

```bash
# 1) Required API URL
export INFISICAL_API_URL="https://app.infisical.com"  # or https://eu.infisical.com

# 2) Token setup (stored in OS keyring)
infisical-utils init
# or
infisical-utils init token --token "your-token" --yes

# 3) Optional global defaults
infisical-utils set-default --type orgId --value "uuid"
infisical-utils set-default --type projectId --value "uuid"
infisical-utils set-default --type environment --value "dev"
```

## Folder Initialization (`.inf`)

Set current directory defaults (recommended per project):

```bash
infisical-utils init folder
# or
infisical-utils init folder --org-id "uuid" --project-id "uuid" --environment dev --yes
```

This writes `./.inf`:

```yaml
orgId: your-org-id
projectId: your-project-id
environment: dev
```

## Context Resolution Priority

Operational commands resolve values in this order:
1. Explicit flags (`--project-id`, `--org-id`, `--environment`, ...)
2. Local `./.inf` (if present in current directory)
3. Global defaults (`set-default`)
4. Built-in fallback (`environment=dev`)
5. Interactive menus/prompts (without `--yes`)

Notes:
- In a folder with `.inf`, overriding `--org-id` or `--project-id` prints a warning.
- `--environment` override is expected and does not warn.

## Main Commands

### Discovery

```bash
infisical-utils list-orgs
infisical-utils list-projects
infisical-utils list-identities
infisical-utils show-defaults
```

### Project Creation

```bash
infisical-utils create-project --name "my-project" --yes

infisical-utils create-project \
  --name "My Project" \
  --slug "my-project" \
  --org-id "uuid" \
  --identity-id "uuid" \
  --role admin \
  --yes
```

### Secret Management

```bash
# View/export
infisical-utils show-env
infisical-utils get-env > .env

# Update by key(s)
infisical-utils update-env --set "KEY=value" --yes
infisical-utils update-env --set "KEY1=v1" --set "KEY2=v2" --yes

# Bulk update from .env
infisical-utils update-env --file .env

# History / rollback
infisical-utils show-env-history --name "API_KEY"
infisical-utils rollback-env --name "API_KEY" --version 2 --yes
```

## Docker Compose Integration (`iu-dc`)

Shell function that fetches secrets into a temporary `.env.inf` and runs `docker compose`:

```bash
iu-dc() {
    [ -f .inf ] || { echo "Error: not an infisical-utils project" >&2; return 1; }
    trap 'rm -f .env.inf' EXIT INT TERM
    infisical-utils get-env -y > .env.inf || return 1
    docker compose --env-file .env.inf "$@"
}
```

Usage: `iu-dc up -d`, `iu-dc down`, `iu-dc exec app cmd`, etc. The `.env.inf` is cleaned up automatically. Docker Compose files in `.inf`-enabled folders should use `env_file: .env.inf`.

## Interactive Mode

Without `--yes`, commands use interactive terminal flows:
- selection menus (organizations, projects, environments, identities) backed by REST calls
- confirm prompts for sensitive actions
- diff preview for `update-env` (old vs new values per key)

## Autocompletion

Dynamic TAB completion is available for:
- org/project/identity/environment IDs
- `set-default --value` (based on `--type`)
- secret names (`show-env-history --name`, `rollback-env --name`)

Setup:

```bash
eval "$(register-python-argcomplete infisical-utils)"
```

## Output and Error Handling

- Uses rich table/diff output when `rich` is available; otherwise plain-text fallback.
- Clean errors for API/auth/config/validation issues without noisy tracebacks.

## Important Notes

- Token is stored in OS keyring (`keyring`), not plain config.
- Global defaults are in `~/.config/infisical-utils/config.json`.
- Folder defaults are in `./.inf`.
- Secret updates are versioned by Infisical; rollback creates a new version with previous value.
