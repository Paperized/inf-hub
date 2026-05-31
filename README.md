# inf-hub

`inf-hub` (`ih`) is a small, practical “git for envs” built on top of [Infisical](https://infisical.com/).

It helps you manage environment variables as a versioned operational workflow (pull, push, history, rollback) while keeping project context in each folder.

Infisical can be self-hosted, including free/self-managed setups:
- https://infisical.com/
- https://github.com/Infisical/infisical
- https://infisical.com/docs/self-hosting/overview

## What it does

- Git-style CLI for env workflows: `pull`, `push`, `history`, `rollback`
- Folder-local context via `.inf` (`orgId`, `projectId`, `environment`)
- Multi-org token model: one token per org (`orgId:{uuid}` in keyring)
- Interactive menus (questionary) backed by live API data
- Smart autocomplete for org/project/env/secret names
- Clear one-line success messages with target env/file info

## Install

```bash
pipx install inf-hub
# or
pip install inf-hub
```

Main commands:
- `ih`
- `ih-dc`

## Headless setup (Debian/Ubuntu)

`inf-hub` uses Python `keyring` with `keyring-pass`. In headless environments, install and initialize `pass`.

### 1) Install system deps

```bash
sudo apt update
sudo apt install -y pass gnupg2
```

### 2) Create GPG key + init pass store (minimal)

```bash
gpg --batch --passphrase '' --quick-generate-key "ih-test <ih-test@local>" default default 0
KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | awk '/^sec/{print $2}' | tail -n1 | cut -d'/' -f2)
pass init "$KEY_ID"
```

### 3) Optional: force keyring backend

```bash
export PYTHON_KEYRING_BACKEND=keyring_pass.PasswordStoreBackend
```

## Minimal first-run

### 1) Set API URL

```bash
export INFISICAL_API_URL="https://your-infisical-host"
```

### 2) Save token for one org

```bash
ih init token --org-id "<org-uuid>" --token "<access-token>" --yes
```

### 3) Initialize current folder

```bash
ih init folder --org-id "<org-uuid>" --project-id "<project-uuid>" --environment dev --yes
```

This creates `.inf` in current directory. From now on, commands automatically use `.inf` context unless overridden by flags.

## Quick usage

```bash
# Pull remote env to local file (.env by default)
ih pull

# Print env to stdout (no file write)
ih pull -p

# Push local .env (default)
ih push

# Push custom file
ih push -f .env.prod

# Push single keys (inline mode)
ih push -k API_URL -v https://... -k DEBUG -v false

# Secret history
ih history --name API_KEY

# Rollback and sync local file (.env default, or custom with -f)
ih rollback --name API_KEY --version 2 -f .env.rollback
```

## Command map

- `ih init token`
- `ih init folder`
- `ih create project`
- `ih list orgs|projects|identities`
- `ih set TYPE --value VALUE [--global]`
- `ih unset TYPE [--global]`
- `ih pull [-f path | -p]`
- `ih push [-f path | (-k KEY -v VALUE)...]`
- `ih history --name NAME`
- `ih rollback --name NAME --version N [-f path]`

## Notes

- In local scope, `ih set/unset` requires `.inf`; use `--global` for global config.
- If a command targets an org without a saved token, it fails explicitly and tells you which org token is missing.
- `ih push` file mode and inline mode are mutually exclusive.
