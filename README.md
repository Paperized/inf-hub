# infisical-utils

[![PyPI version](https://badge.fury.io/py/infisical-utils.svg)](https://badge.fury.io/py/infisical-utils)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A CLI for Infisical with project-aware defaults, interactive REST-backed menus, bulk `.env` secret updates, secret version rollback, and smart autocompletion.

## Quick Setup

### Install with pipx (recommended)

```bash
pipx install infisical-utils
```

### Install with pip

```bash
pip install infisical-utils
```

### Development mode

```bash
git clone git@github.com:Paperized/infisical-utils.git
cd infisical-utils
pip install -e .
```

### Configure

```bash
# Set your Infisical instance URL
export INFISICAL_API_URL="https://app.infisical.com"  # or https://eu.infisical.com

# Initialize token (secure keyring storage)
infisical-utils init
# or
infisical-utils init token --token "your-token" --yes
```

## Key Features

### Secure Token Storage

The token is stored in OS keyring (via `keyring`), not in plain text config.

### Folder-level Configuration (`.inf`)

You can initialize a working folder with local defaults:

```bash
infisical-utils init folder
# or non-interactive
infisical-utils init folder --org-id "uuid" --project-id "uuid" --environment dev --yes
```

This creates `./.inf` (YAML):

```yaml
orgId: your-org-id
projectId: your-project-id
environment: dev
```

When `.inf` exists in current folder, operational commands use it as default context.

### Value Resolution Priority

Values are resolved in this order:
1. Explicit command-line parameter (e.g. `--project-id`)
2. Local `./.inf` value (if present)
3. Global configured default (`set-default`)
4. Hardcoded fallback (e.g. `environment=dev`)
5. Interactive selection/prompt (if not `--yes`)

### Interactive Menus (REST-backed)

In interactive mode (without `--yes`), IDs and environment are selected from live Infisical data (organizations, projects, environments, identities) using terminal menus.

### Smart Tab Completion

Dynamic completion is available for IDs, environments, and secret names.

```bash
infisical-utils show-env --project-id <TAB>
infisical-utils show-env --environment <TAB>
infisical-utils set-default --type orgId --value <TAB>
infisical-utils show-env-history --name <TAB>
```

Setup:

```bash
# zsh
echo 'eval "$(register-python-argcomplete infisical-utils)"' >> ~/.zshrc
source ~/.zshrc
```

### Bulk Secret Update from `.env`

`update-env` supports both single/multi key updates and full file ingest:

```bash
# key-by-key
infisical-utils update-env --set "KEY=value"

# bulk from .env
infisical-utils update-env --file .env
```

In interactive mode it shows a per-key old/new diff before confirmation.

### Rich Console Output

Tables and diffs are rendered with `rich` when available (fallback to plain output otherwise).

## Command Reference

| Command | Description |
|---------|-------------|
| `init` / `init token` | Configure API token in secure keyring |
| `init folder` | Create local `.inf` defaults in current directory |
| `set-default` | Set global defaults (`orgId`, `projectId`, `identityId`, `environment`) |
| `unset-default` | Remove a global default |
| `show-defaults` | Show configured global defaults with resolved labels |
| `list-orgs` | List accessible organizations |
| `list-projects` | List projects with environments |
| `list-identities` | List machine identities |
| `create-project` | Create new project with optional identity + role |
| `show-env` | Display secrets in table format |
| `get-env` | Export secrets as `KEY=VALUE` |
| `update-env` | Update secrets using `--set` and/or `--file` |
| `show-env-history` | Show version history for a secret |
| `rollback-env` | Restore secret to a previous version |

All commands support `--yes` for non-interactive automation.

## Examples

### Typical local project workflow

```bash
# 1. Token setup (once)
export INFISICAL_API_URL="https://eu.infisical.com"
infisical-utils init

# 2. Folder context setup
infisical-utils init folder

# 3. Work with secrets (uses .inf defaults)
infisical-utils show-env
infisical-utils update-env --file .env
```

### Override with warning in initialized folder

In a folder with `.inf`, overriding `--project-id` or `--org-id` prints a warning to make the context switch explicit.

### Backup and rollback

```bash
# Backup
infisical-utils get-env > backup.env

# Update
infisical-utils update-env --set "API_KEY=new-value" --yes

# Check history
infisical-utils show-env-history --name "API_KEY"

# Rollback
infisical-utils rollback-env --name "API_KEY" --version 2 --yes
```

### Docker Compose Integration (`iu-dc`)

Shell function (add to `.zshrc` / `.bashrc`) that fetches secrets into a temporary `.env.inf` and runs `docker compose`:

```bash
iu-dc() {
    [ -f .inf ] || { echo "Error: not an infisical-utils project" >&2; return 1; }
    trap 'rm -f .env.inf' EXIT INT TERM
    infisical-utils get-env -y > .env.inf || return 1
    docker compose --env-file .env.inf "$@"
}
```

Usage:

```bash
iu-dc up -d
iu-dc down
iu-dc exec app python manage.py migrate
```

The `.env.inf` file is cleaned up automatically (even on Ctrl+C). Docker Compose files in `.inf`-enabled folders should reference `env_file: .env.inf` instead of `.env`.

**Zsh completion:**

```bash
compdef iu-dc=docker
```

## Configuration

Global config file: `~/.config/infisical-utils/config.json`
- global defaults (`orgId`, `projectId`, `identityId`, `environment`)

Local folder config: `./.inf`
- folder defaults (`orgId`, `projectId`, `environment`)

Token storage:
- secure OS keyring backend (`keyring`, optional `keyring-pass` backend package installed)

## Development

```bash
git clone git@github.com:Paperized/infisical-utils.git
cd infisical-utils
pip install -e .
infisical-utils --help
```
