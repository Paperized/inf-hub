class InfHubError(Exception):
    """Base domain error for inf-hub."""


class ConfigError(InfHubError):
    """Raised for invalid or missing local/runtime configuration."""


class ValidationError(InfHubError):
    """Raised for invalid user inputs or command arguments."""


class ApiError(InfHubError):
    """Raised when an API operation fails."""


class InteractiveAbort(InfHubError):
    """Raised when user aborts an interactive prompt."""
