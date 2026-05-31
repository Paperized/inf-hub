# inf-hub Skill

## Description

`inf-hub` (`ih`) is a lightweight “git for envs” on top of Infisical.
It is designed for project bootstrap + versioned env operations (`pull`, `push`, `history`, `rollback`) with folder context via `.inf`.

## Why it is useful

- keeps env workflow operational and repeatable
- binds each folder to org/project/environment
- supports multi-org by storing one token per org
- works in interactive mode with API-backed selection menus

## Minimal setup

```bash
export INFISICAL_API_URL="https://your-infisical-host"

# token is bound to orgId
ih init token --org-id "<org-uuid>" --token "<token>" --yes

# initialize folder context
ih init folder --org-id "<org-uuid>" --project-id "<project-uuid>" --environment dev --yes
```

After this, commands read defaults from `.inf`.

## Core commands

```bash
ih pull
ih pull -p
ih push
ih push -f .env.prod
ih push -k KEY -v VALUE -k KEY2 -v VALUE2
ih history --name API_KEY
ih rollback --name API_KEY --version 2 -f .env.rollback
```

## Headless Debian/Ubuntu note

If keyring backend is `keyring-pass`, install and initialize `pass`:

```bash
sudo apt update
sudo apt install -y pass gnupg2

gpg --batch --passphrase '' --quick-generate-key "ih-test <ih-test@local>" default default 0
KEY_ID=$(gpg --list-secret-keys --keyid-format LONG | awk '/^sec/{print $2}' | tail -n1 | cut -d'/' -f2)
pass init "$KEY_ID"

export PYTHON_KEYRING_BACKEND=keyring_pass.PasswordStoreBackend
```
