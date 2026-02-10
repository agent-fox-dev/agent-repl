# agent_repl — Library API Overview

This page summarizes the public API of the **agent_repl** package for consumers building their own agent REPL applications.

## Entry point

```python
from agent_repl import App, Config

config = Config(
    app_name="my-app",
    app_version="1.0.0",
    default_model="claude-opus-4-6",
    agent_factory=None,  # optional; None = default Claude agent
    plugins=[],          # optional list of plugin module names
    theme=None,          # optional Theme for TUI colors
)
app = App(config)
app.run()  # blocking; starts the REPL
```

## Configuration and types

| Import | Description |
|--------|-------------|
| `Config` | Dataclass: `app_name`, `app_version`, `default_model`, `agent_factory`, `plugins`, `theme` |
| `Theme` | Dataclass for TUI colors: `prompt_color`, `cli_output_color`, `agent_gutter_color`, `agent_text_color`, `tool_color`, `tool_error_color` |

## Plugin and agent interfaces

| Import | Description |
|--------|-------------|
| `Plugin` | Protocol: `name`, `description`, `get_commands()`, `on_load()`, `on_unload()` |
| `AgentPlugin` | Protocol extending `Plugin`: `send_message()`, `compact_history()` |
| `SlashCommand` | Dataclass: `name`, `description`, `help_text`, `handler` |

## Stream and session types

| Import | Description |
|--------|-------------|
| `StreamEvent` | Dataclass: `type`, `content`, `metadata` |
| `StreamEventType` | Enum: `TEXT_DELTA`, `TOOL_USE_START`, `TOOL_INPUT_DELTA`, `TOOL_RESULT`, `USAGE`, `ERROR` |

For full interface definitions, data models, and correctness properties, see [specs/agent_repl/design.md](../specs/agent_repl/design.md).
