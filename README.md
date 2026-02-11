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
| `/copy` | Copy the last agent response (raw markdown) to the system clipboard |
| `Ctrl+Y` | Same as `/copy` — copy last agent output to clipboard |

Clipboard support requires `pbcopy` (macOS), `xclip` (Linux/X11), or `wl-copy` (Linux/Wayland).

## Documentation

- [Library API overview](docs/api.md) — public imports and types
- [Examples](examples/README.md) — how to run the demo app

## License

MIT — see [LICENSE](LICENSE).
