# agent_repl Example Application

A self-contained demonstration of the `agent_repl` framework's consumer API.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

From the project root:

```bash
uv sync
```

## Usage

### Default Mode (Claude Agent)

Requires an `ANTHROPIC_API_KEY` environment variable (or equivalent auth
such as `CLAUDE_CODE_USE_VERTEX`):

```bash
uv run python examples/demo.py
```

If no credentials are present, the app starts gracefully with built-in
commands only.

### Echo Mode (No API Key Needed)

Uses a lightweight echo agent that mirrors your input back:

```bash
uv run python examples/demo.py --echo
```

## Files

| File | Description |
|---|---|
| `demo.py` | Entry-point script. Creates `Config`, instantiates `App`, calls `run()`. Supports `--echo` flag. |
| `demo_plugin.py` | Custom plugin implementing the `Plugin` protocol. Registers `/greet` and `/stats` commands. Exposes `create_plugin()` factory. |
| `echo_agent.py` | Lightweight `AgentPlugin` that echoes user input as `StreamEvent`s. Provides `/clear` and `/compact` commands. |
| `__init__.py` | Empty init file making the `examples/` directory importable for tests. |

## Available Commands

| Command | Source | Description |
|---|---|---|
| `/help` | Built-in | List all available commands |
| `/version` | Built-in | Show app name and version |
| `/quit` | Built-in | Exit the application |
| `/greet` | Demo plugin | Display a greeting message |
| `/stats` | Demo plugin | Show session token usage statistics |
| `/clear` | Echo agent | Clear conversation history |
| `/compact` | Echo agent | Replace history with a summary |
