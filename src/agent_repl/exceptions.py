class AgentReplError(Exception):
    """Base exception for all agent_repl errors."""


class AgentError(AgentReplError):
    """Raised when the agent encounters a failure."""


class PluginError(AgentReplError):
    """Raised on plugin loading or registration errors."""


class ConfigError(AgentReplError):
    """Raised on configuration loading errors."""


class ClipboardError(AgentReplError):
    """Raised on clipboard operation failures."""


class FileContextError(AgentReplError):
    """Raised on file context resolution errors."""
