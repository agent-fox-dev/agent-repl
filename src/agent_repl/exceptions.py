"""Custom exception types for agent_repl."""


class FileContextError(Exception):
    """Raised when file context resolution fails (missing path, binary file, etc.)."""


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""


class AgentError(Exception):
    """Raised when agent interaction fails (connection error, API error, etc.)."""


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


class ClipboardError(Exception):
    """Raised when a clipboard operation fails (missing utility, subprocess error)."""
