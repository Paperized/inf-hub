# infisical-utils

[![PyPI version](https://badge.fury.io/py/infisical-utils.svg)](https://badge.fury.io/py/infisical-utils)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful CLI tool that extends Infisical's capabilities with advanced development features. Built for developers who need smart tab completion for project IDs and names, secret versioning with rollback, configurable defaults to avoid repetitive typing, and seamless environment variable management. Whether you're creating projects, managing machine identities, or working with secrets across multiple environments, infisical-utils streamlines your workflow with intelligent autocompletion and clean error handling.

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

# Initialize with your API token
infisical-utils init
```

### Optional: create an alias

For faster typing, add an alias to your shell config:

```bash
# zsh
echo 'alias iu="infisical-utils"' >> ~/.zshrc
source ~/.zshrc

# bash
echo 'alias iu="infisical-utils"' >> ~/.bashrc
source ~/.bashrc
```

Then use it like:
```bash
iu show-env
iu list-projects
iu update-env --set "KEY=value" --yes
```

## Features

### Smart Tab Completion

Dynamic autocompletion that fetches real data from your Infisical instance:

```bash
infisical-utils show-env --project-id <TAB>
# Shows: 78f1a670-... | seal365
#         1ad6b099-... | Certificate Manager

infisical-utils show-env --environment <TAB>
# Shows: dev  staging  prod
```

Setup autocompletion:
```bash
# zsh
echo 'eval "$(register-python-argcomplete infisical-utils)"' >> ~/.zshrc
source ~/.zshrc

# bash
echo 'eval "$(register-python-argcomplete infisical-utils)"' >> ~/.bashrc
source ~/.bashrc
```

### Configurable Defaults

Set default values to avoid typing IDs repeatedly:

```bash
infisical-utils set-default --type org-id --value "uuid"
infisical-utils set-default --type project-id --value "uuid"
infisical-utils set-default --type identity-id --value "uuid"
infisical-utils set-default --type environment --value "dev"

# Show all defaults with resolved names
infisical-utils show-defaults

# Remove a default
infisical-utils unset-default --type project-id
```

### Project Management

Create and manage Infisical projects:

```bash
# List organizations
infisical-utils list-orgs

# List projects with environments
infisical-utils list-projects

# Create project with custom slug
infisical-utils create-project --name "My Project" --slug "my-project"

# Create project and add identity with role
infisical-utils create-project --name "my-project" --identity-id "uuid" --role admin --yes
```

### Identity Management

Manage machine identities and their project memberships:

```bash
# List identities
infisical-utils list-identities

# List identities for specific org
infisical-utils list-identities --org-id "uuid"
```

### Secret Management

View, update, and rollback secrets with full versioning support:

```bash
# View secrets in tabular format
infisical-utils show-env
infisical-utils show-env --environment staging

# Export secrets to .env file
infisical-utils get-env > .env
infisical-utils get-env --environment prod > .env.prod

# Update secrets (creates new version automatically)
infisical-utils update-env --set "KEY=value"
infisical-utils update-env --set "KEY1=val1" --set "KEY2=val2" --yes

# View version history
infisical-utils show-env-history --name "API_KEY"

# Rollback to previous version
infisical-utils rollback-env --name "API_KEY" --version 2 --yes
```

### Clean Error Handling

No stacktraces, just clear error messages:

```bash
# API error 404: resource not found
# API error 403: insufficient permissions
# API error 401: invalid token
# Missing configuration: suggestion to run init
# Invalid input: specific message with correct format
```

## Command Reference

| Command | Description |
|---------|-------------|
| `init` | Configure API token |
| `set-default` | Set default values for org, project, identity, environment |
| `unset-default` | Remove a default value |
| `show-defaults` | Show all configured defaults with resolved names |
| `list-orgs` | List accessible organizations |
| `list-projects` | List projects with environments |
| `list-identities` | List machine identities |
| `create-project` | Create new project with optional identity and role |
| `show-env` | Display secrets in tabular format |
| `get-env` | Export secrets as KEY=VALUE (redirectable) |
| `update-env` | Update secrets (auto-creates new version) |
| `show-env-history` | Show version history for a secret |
| `rollback-env` | Restore secret to previous version |

All commands support `--yes` flag for non-interactive mode.

## Value Resolution Priority

Values are resolved in this order:
1. Explicit command-line parameter (`--project-id "uuid"`)
2. Configured default value (`set-default --type project-id`)
3. Hardcoded value (e.g., environment = "dev")
4. Interactive prompt (if not `--yes`)

## Examples

### Typical workflow

```bash
# 1. Initial configuration
export INFISICAL_API_URL="https://eu.infisical.com"
infisical-utils init

# 2. Discover available IDs
infisical-utils list-orgs
infisical-utils set-default --type org-id --value "uuid-from-list"

infisical-utils list-projects
infisical-utils set-default --type project-id --value "uuid-from-list"

infisical-utils list-identities
infisical-utils set-default --type identity-id --value "uuid-from-list"

# 3. Work with secrets
infisical-utils show-env
infisical-utils update-env --set "NEW_KEY=new-value"
infisical-utils get-env > .env
```

### Backup and restore

```bash
# Backup
infisical-utils get-env > backup.env

# Modify
infisical-utils update-env --set "API_KEY=new-value" --yes

# Check history
infisical-utils show-env-history --name "API_KEY"

# Rollback if needed
infisical-utils rollback-env --name "API_KEY" --version 2 --yes
```

## Configuration

The tool stores configuration in `~/.config/infisical-utils/config.json`:
- API token
- Default values (org, project, identity, environment)

Secrets are never stored locally - they're always retrieved from Infisical.

## Development

```bash
# Clone repository
git clone git@github.com:Paperized/infisical-utils.git
cd infisical-utils

# Install in editable mode
pip install -e .

# Test commands
infisical-utils --help
```

## License

MIT
