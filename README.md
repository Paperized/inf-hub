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
- Saved organization list: `ih init token` adds orgs to a local list used for validation and interactive selection
- Interactive menus (questionary) backed by live API data
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

## Interactive-first workflow

All core commands are designed to run comfortably in interactive mode:
- guided prompts and selection menus (questionary)
- API-backed choices for project/environment
- Organization selection from saved list (populated via `ih init token`)

You can run the steps below without flags and let `ih` guide the flow.

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
ih init token
```

By default, `ih init token`:
- Extracts org-id and org-name from the JWT token
- Validates the token by making a test API call
- Uses the extracted org-name as default (you can override it)

Use `--skip-checks` to bypass validation (e.g., when the API is not yet reachable):

```bash
ih init token --skip-checks
```

You can also provide org-name explicitly:

```bash
ih init token --org-name "My Organization"
```

### 3) Initialize current folder

```bash
ih init folder
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
- `ih set TYPE --value VALUE`
- `ih unset TYPE`
- `ih pull [-f path | -p]`
- `ih push [-f path | (-k KEY -v VALUE)...]`
- `ih history --name NAME`
- `ih rollback --name NAME --version N [-f path]`

## Notes

- `ih set/unset` always target local `.inf` context.
- If a command targets an org without a saved token, it fails explicitly and tells you which org token is missing.
- If a command targets an org not in the saved list, it fails and tells you to run `ih init token` to add it.
- `ih push` file mode and inline mode are mutually exclusive.

## Architecture

- Technical architecture and contributor guide: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
