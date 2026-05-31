# Architecture

## Overview
`inf-hub` is a CLI-first tool for managing Infisical environments with a git-like workflow.

Design goals:
- interactive UX by default
- clear module boundaries
- easy extensibility for contributors

## Module Layout
- `inf_hub/cli.py`: argparse parser, dispatch, top-level error mapping.
- `inf_hub/commands.py`: command handlers.
- `inf_hub/services.py`: reusable use-case logic.
- `inf_hub/runtime.py`: context resolution and API client construction.
- `inf_hub/ui.py`: prompt/select/confirm adapter.
- `inf_hub/config.py`: local config + keyring persistence.
- `inf_hub/api.py`: Infisical API wrapper.
- `inf_hub/errors.py`: domain errors.
- `inf_hub/models.py`: internal dataclasses.

## Token-Centric Model
- Authentication key is `tokenId` (user-defined unique name).
- Secret is stored in keyring using `tokenId:{tokenId}`.
- Config stores token metadata list (`tokenId`, `orgId`).
- `.inf` stores local execution context (`tokenId`, `projectId`, `environment`).

## Context Precedence
Execution context precedence:
1. explicit CLI args
2. local `.inf`
3. interactive selection

## Interaction Standards
- Use arrow-key list selection for known choices (token/project/environment/identity/secret/role).
- Use text prompt only for free-form inputs (secret value, project name, rollback version, etc.).

## Error and Exit Conventions
- Validation/config errors: exit code `1` with `Error: ...`.
- Interactive cancel: exit code `130`.
- API/unexpected errors mapped in `cli.py`.

## Contributor Guidelines
When adding commands:
1. Add parser/flags in `cli.py`.
2. Put orchestration in `commands.py`.
3. Reuse/extend `services.py` for shared logic.
4. Keep UI interactions in `ui.py`.
5. Raise domain errors instead of ad hoc prints.
