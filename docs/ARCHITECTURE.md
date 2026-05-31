# Architecture

## Overview
`inf-hub` is a CLI-first tool for managing Infisical environments with a git-like workflow.

Design goals:
- Keep command UX simple and mostly interactive by default.
- Keep business logic separate from prompt/IO logic.
- Keep extension points clear for contributors.

## Module Layout
- `inf_hub/cli.py`: argparse parser, command dispatch, top-level error mapping.
- `inf_hub/commands.py`: command handlers (init/create/list/set/pull/push/history/rollback).
- `inf_hub/services.py`: reusable use-case logic (target resolution, env parsing, sync policy, push/rollback operations).
- `inf_hub/runtime.py`: runtime/context resolution helpers (`orgId`, `.inf`, API factory).
- `inf_hub/ui.py`: interactive and non-interactive UI adapter (prompt/select/autocomplete/confirm).
- `inf_hub/config.py`: local config and keyring persistence.
- `inf_hub/api.py`: low-level Infisical API wrapper.
- `inf_hub/errors.py`: domain error hierarchy.
- `inf_hub/models.py`: internal dataclasses for command/service contracts.

## Execution Model
1. CLI parses args in `cli.py`.
2. Dispatcher routes to command handler in `commands.py`.
3. Command resolves context (`orgId`, `projectId`, `environment`) using runtime/services.
4. Command executes API operations through `api.py`.
5. Optional local sync is applied according to policy (e.g. only sync if target file exists for push/rollback).
6. Errors are normalized to user-facing messages and exit codes in one place (`cli.py`).

## Context Precedence
For command execution context:
- Explicit CLI args override everything.
- `.inf` local values are used when available.
- Interactive selection/prompt is used when values are still missing and command is not `--yes`.

No global default layer is used for execution context.

## Interaction Standards
- Use autocomplete/select when choosing from known API-backed lists (org/project/environment/identity/secret name/role).
- Use free-text prompt only for truly free values (project name, slug, secret value, rollback version, etc.).
- In read-only secret selection flows, choose from existing secret names only.

## Error and Exit Conventions
- Validation/config errors return exit code `1` with `Error: ...` message.
- Interactive user cancellation returns exit code `130`.
- API and unexpected errors are mapped in `cli.py` to stable user-facing output.

## Reuse Guidelines for Contributors
When adding a command:
1. Add parser args in `cli.py`.
2. Implement orchestration in `commands.py` using existing services.
3. Keep reusable logic in `services.py` (not in command body).
4. Keep UI interactions in `ui.py` helpers.
5. Raise domain errors (`ValidationError`, `ConfigError`, etc.) rather than printing ad hoc errors.

## Testing Strategy
- Unit tests for services/runtime/helpers.
- CLI integration tests for core command flows.
- Keep behavior-focused tests for context precedence, interactive selection fallbacks, and sync policies.
