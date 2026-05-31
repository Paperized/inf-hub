# inf-hub

`inf-hub` (`ih`) is a small, practical “git for envs” built on top of [Infisical](https://infisical.com/).

It helps you manage environment variables as a versioned operational workflow (pull, push, history, rollback) while keeping project context in each folder.

Infisical can be self-hosted, including free/self-managed setups:
- https://infisical.com/
- https://github.com/Infisical/infisical
- https://infisical.com/docs/self-hosting/overview

## What it does

- Git-style CLI for env workflows: `pull`, `push`, `history`, `rollback`
- Folder-local context via `.inf` (`tokenId`, `projectId`, `environment`)
- Multi-token model: one credential per `tokenId` in keyring (`tokenId:{tokenId}`)
- Saved token list for validation and interactive selection
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
- `ih-dc` (shell function for docker compose integration)

## Interactive-first workflow

All core commands are designed to run comfortably in interactive mode:
- guided prompts and selection menus (questionary)
- API-backed choices for project/environment
- Token selection from saved list (populated via `ih register token`)

## Minimal first-run

### 1) Set API URL

```bash
export INFISICAL_API_URL="https://your-infisical-host"
```

### 2) Register token

```bash
ih register token
```

By default, `ih register token`:
- Extracts org-id from JWT
- Requires a unique `tokenId` name
- Stores secret in keyring as `tokenId:{tokenId}`

### 3) Initialize current folder

```bash
ih init folder
```

This creates `.inf` in current directory. Commands then use local context unless overridden by flags.

## Quick usage

```bash
# Pull remote env to local file (.env by default)
ih pull

# Pull remote env to custom file
ih pull -f .env.inf

# Print env to stdout (no file write)
ih pull -p

# Push local .env (default)
ih push

# Push custom file
ih push -f .env.prod

# Update local .env keys only (no remote changes)
ih update -k API_URL -v https://... -k DEBUG -v false

# Interactive local update (key list from remote + local file)
ih update

# Secret history
ih history --name API_KEY

# Rollback and sync local file (.env default, or custom with -f)
ih rollback --name API_KEY --version 2 -f .env.rollback

# Docker Compose integration (requires shell function from .zshrc)
ih-dc up -d
```

## Shell integration (Docker Compose)

Add to `.zshrc` or `.bashrc`:

```bash
ih-dc() {
    [ -f .inf ] || { echo "Error: not an inf-hub project" >&2; return 1; }
    setopt localtraps
    trap 'rm -f .env.inf' EXIT INT TERM
    ih pull -p > .env.inf || return 1
    docker compose --env-file .env.inf "$@"
}
```

Then use `ih-dc` as a drop-in replacement for `docker compose`:

```bash
ih-dc up -d
ih-dc logs -f
ih-dc down
```

## Command map

- `ih register token`
- `ih unregister token`
- `ih init folder`
- `ih create project`
- `ih list orgs|projects|identities`
- `ih set TYPE --value VALUE`
- `ih unset TYPE`
- `ih pull [-f path | -p]`
- `ih push [-f path]`
- `ih update [-f path | (-k KEY -v VALUE)...]`
- `ih history --name NAME`
- `ih rollback --name NAME --version N [-f path]`

## Notes

- `ih set/unset` always target local `.inf` context.
- If a command targets an unknown tokenId, it fails and asks you to run `ih register token`.
- `ih push` always pushes a full env file (`.env` by default).
- `ih update` only updates local files and never writes to remote.

## Architecture

- Technical architecture and contributor guide: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
