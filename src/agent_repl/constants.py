"""Central constants for agent_repl."""

# Default Claude model used by the Claude agent plugin and Config when not overridden.
DEFAULT_CLAUDE_MODEL = "claude-opus-4-6"

# Slash command menu: commands shown in the initial dropdown before any typing.
DEFAULT_PINNED_COMMANDS: list[str] = ["help", "quit"]

# Maximum number of pinned entries shown in the completion dropdown.
MAX_PINNED_DISPLAY = 6
