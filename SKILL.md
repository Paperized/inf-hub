# infisical-utils Skill

## Description

infisical-utils is a CLI utility for managing projects, secrets, and identities on Infisical with advanced features not available in the official CLI.

## When to use this tool

Use infisical-utils when you need to:
- Create Infisical projects with custom configuration (slug, identities, roles)
- Manage secrets with versioning and rollback
- Configure defaults to avoid repeating IDs in every command
- Export environment variables in .env format
- View the history of secret modifications
- Work with multiple organizations/projects efficiently

## Initial Setup

Before using the tool, ensure it's configured:

```bash
# 1. Required environment variable
export INFISICAL_API_URL="https://app.infisical.com"  # or https://eu.infisical.com

# 2. API token (required once)
infisical-utils init --token "your-token" --yes

# 3. (Optional) Defaults to speed up commands
infisical-utils set-default --type org-id --value "uuid"
infisical-utils set-default --type project-id --value "uuid"
infisical-utils set-default --type environment --value "dev"
```

## Main Commands

### Resource Discovery

```bash
# List organizations
infisical-utils list-orgs

# List projects with environments
infisical-utils list-projects

# List identities
infisical-utils list-identities

# Show configured defaults
infisical-utils show-defaults
```

### Project Creation

```bash
# Basic
infisical-utils create-project --name "my-project" --yes

# With custom slug
infisical-utils create-project --name "My Project" --slug "custom-slug" --yes

# With identity and role
infisical-utils create-project --name "my-project" --identity-id "uuid" --role admin --yes

# Complete
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
# View secrets (tabular)
infisical-utils show-env
infisical-utils show-env --environment staging

# Export in .env format
infisical-utils get-env > .env
infisical-utils get-env --environment prod > .env.prod

# Update secrets
infisical-utils update-env --set "KEY=value" --yes
infisical-utils update-env --set "KEY1=val1" --set "KEY2=val2" --yes

# Version history
infisical-utils show-env-history --name "API_KEY"

# Rollback to previous version
infisical-utils rollback-env --name "API_KEY" --version 2 --yes
```

### Default Management

```bash
# Set defaults
infisical-utils set-default --type org-id --value "uuid"
infisical-utils set-default --type project-id --value "uuid"
infisical-utils set-default --type identity-id --value "uuid"
infisical-utils set-default --type environment --value "staging"

# Remove defaults
infisical-utils unset-default --type project-id
```

## Best Practices

### 1. Use defaults to speed up workflow

```bash
# Configure once
infisical-utils set-default --type project-id --value "uuid"
infisical-utils set-default --type environment --value "dev"

# Then use short commands
infisical-utils show-env
infisical-utils update-env --set "KEY=value" --yes
```

### 2. Use --yes for automation

```bash
# In scripts, always use --yes to avoid prompts
infisical-utils create-project --name "auto-project" --yes
infisical-utils update-env --set "KEY=value" --yes
```

### 3. Backup before bulk modifications

```bash
# Backup
infisical-utils get-env > backup-$(date +%Y%m%d).env

# Modifications
infisical-utils update-env --set "KEY1=val1" --set "KEY2=val2" --yes

# If something goes wrong, rollback
infisical-utils show-env-history --name "KEY1"
infisical-utils rollback-env --name "KEY1" --version 2 --yes
```

### 4. Use custom slugs for projects

```bash
# Good: readable and consistent slug
infisical-utils create-project --name "My Project" --slug "my-project" --yes

# Avoid: auto-generated slug with UUID
infisical-utils create-project --name "My Project" --yes  # generates "my-project-a1b2c3"
```

### 5. Always verify with show-env after modifications

```bash
infisical-utils update-env --set "API_KEY=new-value" --yes
infisical-utils show-env  # verify it was updated
```

## Typical Workflows

### Workflow 1: Setup new project

```bash
# 1. Discover org-id
infisical-utils list-orgs

# 2. Create project
infisical-utils create-project \
  --name "New Service" \
  --slug "new-service" \
  --org-id "uuid-from-step-1" \
  --yes

# 3. Set as default
infisical-utils list-projects  # find the new UUID
infisical-utils set-default --type project-id --value "new-uuid"

# 4. Add initial secrets
infisical-utils update-env \
  --set "DATABASE_URL=postgres://..." \
  --set "API_KEY=sk-..." \
  --set "DEBUG=false" \
  --yes

# 5. Verify
infisical-utils show-env
```

### Workflow 2: Migrate secrets between environments

```bash
# 1. Export from staging
infisical-utils get-env --environment staging > staging.env

# 2. Set default to prod
infisical-utils set-default --type environment --value "prod"

# 3. Import to prod (manually or with script)
while IFS='=' read -r key value; do
  infisical-utils update-env --set "$key=$value" --yes
done < staging.env

# 4. Verify
infisical-utils show-env
```

### Workflow 3: Rollback after failed deploy

```bash
# 1. Identify the problem
infisical-utils show-env

# 2. Check history
infisical-utils show-env-history --name "DATABASE_URL"

# 3. Rollback to previous version
infisical-utils rollback-env --name "DATABASE_URL" --version 3 --yes

# 4. Verify
infisical-utils show-env
```

## Error Handling

The tool handles errors cleanly:

```bash
# Error: project not found
Error: API error 404: Project with ID 'invalid-uuid' not found

# Error: insufficient permissions
Error: API error 403: You don't have permission to access this resource

# Error: invalid token
Error: API error 401: Invalid authentication token

# Error: missing configuration
Error: INFISICAL_API_URL is not set
Set it with:
  export INFISICAL_API_URL=https://app.infisical.com
```

## Parameter Priority

Values are resolved in this order:
1. Explicit command-line parameter (`--project-id "uuid"`)
2. Configured default value (`set-default --type project-id`)
3. Hardcoded value (e.g., environment = "dev")
4. Interactive prompt (if not `--yes`)

## Autocompletion

The tool supports dynamic TAB completion:

```bash
infisical-utils show-env --project-id <TAB>
# Shows: 78f1a670-... | seal365
#         1ad6b099-... | Certificate Manager

infisical-utils show-env --environment <TAB>
# Shows: dev  staging  prod
```

Setup:
```bash
# zsh
echo 'eval "$(register-python-argcomplete infisical-utils)"' >> ~/.zshrc
source ~/.zshrc
```

## Important Notes

- The API token is saved in `~/.config/infisical-utils/config.json`
- Defaults are saved in the same file
- The tool does not store secrets locally, it always retrieves them from Infisical
- Every secret modification creates a new version (automatic versioning)
- Rollback creates a new version with the value from the selected version

## Advanced Examples

### Bash script for automatic backup

```bash
#!/bin/bash
set -e

PROJECT_NAME="my-project"
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

for env in dev staging prod; do
  echo "Backing up $env..."
  infisical-utils get-env --environment "$env" > "$BACKUP_DIR/${PROJECT_NAME}_${env}_${DATE}.env"
done

echo "Backup completed in $BACKUP_DIR"
```

### Script for secret synchronization

```bash
#!/bin/bash
set -e

SOURCE_ENV="staging"
TARGET_ENV="prod"

echo "Syncing secrets from $SOURCE_ENV to $TARGET_ENV..."

# Export from source
infisical-utils get-env --environment "$SOURCE_ENV" > /tmp/source.env

# Import to target
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" =~ ^# ]] && continue
  echo "Updating $key..."
  infisical-utils update-env --environment "$TARGET_ENV" --set "$key=$value" --yes
done < /tmp/source.env

rm /tmp/source.env
echo "Sync completed!"
```

## Troubleshooting

### Command not found
```bash
# Verify it's in PATH
which infisical-utils

# If not found, add to PATH
export PATH="$HOME/.local/bin:$PATH"
```

### Authentication error
```bash
# Verify token is valid
infisical-utils list-orgs

# If it fails, reinitialize
infisical-utils init --token "new-token" --yes
```

### Autocompletion not working
```bash
# Verify argcomplete is installed
pip show argcomplete

# Re-register
eval "$(register-python-argcomplete infisical-utils)"
```

## Resources

- PyPI: https://pypi.org/project/infisical-utils/
- Infisical Docs: https://infisical.com/docs
- Infisical API: https://app.infisical.com/api/docs
