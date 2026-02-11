# agent-repl

**agent_repl** is a Python library and REPL-style TUI framework for building CLI applications that interact with AI agents. It provides a terminal interface with free-form input, streamed responses, slash-commands, plugins, and an optional default Claude agent.

## Install

### As a dependency (another project)

From PyPI (when published):

```shell
uv add agent_repl
# or: pip install agent_repl
```

From this repo (git or path):

```shell
uv add 'agent_repl @ git+https://github.com/agent-fox-dev/agent-repl.git'
# or from a local clone:
uv add --path /path/to/agent-repl
```

### From this repo (development / examples)

```shell
cd agent-repl
uv sync
```

## Quick start

Minimal usage in your own code:

```python
from agent_repl import App, Config

config = Config(
    app_name="my-agent",
    app_version="1.0.0",
    default_model="claude-opus-4-6",
    # agent_factory=my_agent_factory,  # optional; defaults to Claude agent
    # plugins=["my_plugin_module"],  # optional
)
app = App(config)
app.run()
```

See [examples/](examples/) for a full demo (custom plugin, slash-commands, echo agent).

## Built-in commands and shortcuts

| Command / Key | Description |
|---------------|-------------|
| `/help` | Show available commands |
| `/quit` | Exit the REPL |
| `/version` | Show version |
| `/stats` | Show token usage statistics |
| `/agent` | Show active agent info |
| `/compact` | Compact conversation history |
| `/copy` | Copy the last agent response to the clipboard |
| `Ctrl+Y` | Same as `/copy` |
| `@path` | Include file context in your message |

Clipboard support requires `pbcopy` (macOS), `xclip` (Linux/X11), or `wl-copy` (Linux/Wayland).

## Configuration

Create `.af/config.toml` in your project root:

```toml
[plugins]
paths = ["my_package.plugins.custom_plugin"]
```

Or configure programmatically via `Config`:

```python
Config(
    app_name="my-app",
    app_version="1.0.0",
    agent_factory=MyAgentPlugin,       # callable returning an AgentPlugin
    theme=Theme(prompt_color="green"),  # terminal color theme
    pinned_commands=["help", "quit"],   # commands shown first in completions
    max_file_size=100_000,             # max bytes for @path file inclusion
)
```

## Plugin development

A plugin implements the `Plugin` protocol:

```python
from agent_repl.types import PluginContext, SlashCommand, CommandContext

class MyPlugin:
    name = "my_plugin"
    description = "My custom plugin"

    def get_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand(name="mycmd", description="Do something", handler=self._handle),
        ]

    async def on_load(self, context: PluginContext) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_status_hints(self) -> list[str]:
        return []

    async def _handle(self, ctx: CommandContext) -> None:
        ctx.tui.show_info("Hello from my plugin!")
```

An agent extends `Plugin` with `send_message` and `compact_history`:

```python
from agent_repl.types import MessageContext, StreamEvent, StreamEventType

class MyAgent:
    name = "MyAgent"
    description = "My custom agent"
    default_model = "my-model-1.0"

    # ... Plugin methods ...

    async def send_message(self, context: MessageContext):
        yield StreamEvent(type=StreamEventType.TEXT_DELTA, data={"text": "Hello!"})
        yield StreamEvent(type=StreamEventType.USAGE, data={"input_tokens": 0, "output_tokens": 1})

    async def compact_history(self, session) -> str:
        return "Compacted summary"
```

## Extension points

| Extension Point | Protocol | Purpose |
|----------------|----------|---------|
| Agent | `AgentPlugin` | Send messages, stream responses, manage history |
| Plugin | `Plugin` | Add slash commands, lifecycle hooks, status hints |
| Theme | `Theme` | Customize terminal colors |
| Config | `Config` | App name, version, agent factory, plugins, pinned commands |
| Spawn | `SpawnConfig` | Independent background agent sessions with hooks |

## Documentation

- [Library API overview](docs/api.md) — public imports and types
- [Examples](examples/README.md) — how to run the demo app

## License

MIT — see [LICENSE](LICENSE).
