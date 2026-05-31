from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:
    org_id: str
    project_id: str
    environment: str
    yes: bool = False


@dataclass(frozen=True)
class SecretUpdate:
    key: str
    value: str


@dataclass(frozen=True)
class CommandResult:
    message: str
    updated_local_file: str | None = None
