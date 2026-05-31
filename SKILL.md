# inf-hub Skill

## Description

`inf-hub` (`ih`) is a lightweight “git for envs” on top of Infisical.
It is designed for project bootstrap + versioned env operations (`pull`, `push`, `history`, `rollback`) with folder context via `.inf`.

## Why it is useful

- keeps env workflow operational and repeatable
- binds each folder to token/project/environment
- supports multiple tokens, including many tokens bound to the same organization
- maintains a saved token list for validation and interactive selection
- works in interactive mode with API-backed selection menus

## Minimal setup

```bash
export INFISICAL_API_URL="https://your-infisical-host"

# token metadata is extracted from JWT; tokenId is user-defined and unique
ih register token --token-id "my-token" --token "<token>" --yes

# initialize folder context
ih init folder --token-id "my-token" --project-id "<project-uuid>" --environment dev --yes
```

After this, commands read defaults from `.inf`.

## Local config model

`ih set`/`ih unset` work only on local `.inf` context.
Execution context precedence is: explicit CLI args > local `.inf` > interactive selection.

## Core commands

```bash
ih register token
ih unregister token
ih pull
ih pull -f .env.inf
ih pull -p
ih push
ih push -f .env.prod
ih push -k KEY -v VALUE -k KEY2 -v VALUE2
ih history --name API_KEY
ih rollback --name API_KEY --version 2 -f .env.rollback
```

## Docker Compose integration

Add to `.zshrc`:

```bash
ih-dc() {
    [ -f .inf ] || { echo "Error: not an inf-hub project" >&2; return 1; }
    setopt localtraps
    trap 'rm -f .env.inf' EXIT INT TERM
    ih pull -p > .env.inf || return 1
    docker compose --env-file .env.inf "$@"
}
```

Usage: `ih-dc up -d`, `ih-dc logs -f`, `ih-dc down`
