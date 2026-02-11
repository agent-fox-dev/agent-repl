# Product Requirements Document: agent_repl

## Overview

**agent_repl** is a Python library and REPL-style TUI framework for building
CLI applications that interact with AI agents. It provides a terminal interface
with free-form input, streamed responses, slash commands, a plugin system, and
an optional default Claude agent.

The framework targets developers who want a turnkey conversational interface to
an AI agent without building terminal UI plumbing from scratch. It is both a
ready-to-use tool (launch the REPL and talk to Claude) and a framework (swap in
your own agent, add plugins, register custom slash commands).

## Architectural Constraint: Plugins All the Way Down

All capabilities of the REPL are provided through the plugin architecture. Every
slash command, every agent integration, and every piece of extensible behavior is
a plugin -- including the default, built-in ones (`/help`, `/quit`, `/version`,
`/copy`, etc.) and the default Claude agent. There is no separate "core command"
path; built-in commands are simply plugins that the framework loads by default.

This constraint ensures a uniform extension model: anything a built-in command
can do, a third-party plugin can also do. It also means the framework's own
behavior can be overridden or replaced by registering a plugin that provides an
alternative implementation of the same command name.

## Key Capabilities

### 1. Conversational REPL Loop

The core interaction model is a read-eval-print loop. The user types input at a
prompt; the system classifies it as either a **slash command** (`/help`,
`/quit`, ...) or **free text** destined for the active AI agent. Empty or
whitespace-only input is silently ignored. The loop runs continuously until the
user exits with `/quit`, Ctrl+C, or Ctrl+D. If an agent task is in flight when
the user presses Ctrl+C or Ctrl+D, the running task is cancelled rather than
exiting the loop.

### 2. Input Parsing

Input that starts with `/` followed by one or more non-whitespace characters is
classified as a slash command; everything else is free text. The parser splits
slash commands on the first whitespace to extract the command name and an
optional argument string. Free text may contain **`@path` mentions** (`@` followed
by non-whitespace characters), which are extracted so the system can inject file
contents into the agent context.

### 3. File Context Resolution

When the user includes `@path` references in free text, the system resolves them
before forwarding the message to the agent. For a file path the resolver reads
UTF-8 content; for a directory it recursively reads all contained files, sorted
by path. Non-existent paths and binary / non-UTF-8 files produce clear error
messages.

### 4. Slash Command System

Commands are stored in a **CommandRegistry** that supports lookup by exact name,
alphabetically-sorted listings, and prefix-based completion. The registry also
supports **pinned commands** -- a configurable ordered set of commands surfaced
first when the user types bare `/` and presses Tab.

A **SlashCommandCompleter** integrates with `prompt_toolkit` to provide
interactive Tab completion:

- On bare `/`: show only pinned commands (up to a configurable max).
- On `/<prefix>`: show all matching commands alphabetically.
- Pressing ESC dismisses completions until the text changes.

### 5. Built-in Commands

The framework ships with essential built-in commands, each implemented as a
plugin using the same plugin API available to third-party extensions:

| Command    | Behavior |
|------------|----------|
| `/help`    | Lists all registered commands with descriptions. |
| `/quit`    | Terminates the REPL. |
| `/version` | Displays the application name and version. |
| `/copy`    | Copies the last assistant output to the system clipboard. |
| `/agent`   | Displays the current agent and its default model. |
| `/stats`   | Displays the amount of tokens sent and received. |

### 6. Streamed Agent Responses

Agent responses arrive as an async stream of **StreamEvent** objects. The
**StreamHandler** processes these events in real time:

- **TEXT_DELTA** -- text is appended to a live-updating terminal display.
- **TOOL_USE_START** -- an info line shows the tool name.
- **TOOL_RESULT** -- the result is rendered in a panel; tool use is recorded.
- **USAGE** -- token counts are accumulated into session statistics.
- **ERROR** -- the spinner stops and the error is displayed.

When the first content event arrives the "Thinking..." spinner is dismissed.
When the stream ends, the full response is finalized as a conversation turn with
accumulated text, tool uses, and token usage.

### 7. Rich Terminal UI

The **TUIShell** layer uses **Rich** for output rendering and **prompt_toolkit**
for async input with history and completions:

- Streamed text appears in a live view with a colored left gutter bar.
- Completed responses are rendered as markdown with the same gutter.
- A spinner with "Thinking..." text is shown while the agent processes.
- Tool results are displayed in labeled panels distinguishing success from error.
- Ctrl+Y copies the last assistant output to the clipboard.
- The prompt includes a horizontal rule above and below, a colored prompt glyph, input history, and Tab completion.
- Contextual information (keyboard shortcuts, hints etc) can be displayed below the prompt

### 8. Session & Conversation History

A **Session** maintains an ordered list of conversation turns. Each turn records
the role, content, optional file context, tool uses, and token usage. Token
statistics are accumulated across turns. The session supports:

- Adding turns and accumulating token usage.
- Retrieving a copy of the history.
- Clearing the history.
- Retrieving the last assistant response (or None if none exists).
- Replacing the history with a single summary turn (`replace_with_summary`).

### 9. Clipboard Integration

A platform-aware **Clipboard** utility copies text to the system clipboard:

- macOS: `pbcopy`
- Linux / Wayland: `wl-copy`
- Linux / X11: `xclip -selection clipboard`

Missing utilities or unsupported platforms produce descriptive errors.

### 10. Plugin System

All REPL capabilities -- built-in commands, the default agent, and user-provided
extensions -- are delivered through a single plugin architecture.

**PluginLoader** imports plugin modules by dotted Python path and calls their
`create_plugin()` factory. Modules that lack the factory or fail to import are
logged and skipped; loading continues for remaining plugins.

**PluginRegistry** stores loaded plugins, registers their commands with the
CommandRegistry, and tracks the **active agent** -- the first registered plugin
that implements `send_message()` and `compact_history()`.

**Configuration** is loaded from `.af/config.toml` (TOML). If the file does
not exist, a default template is created. Malformed TOML logs a warning and
falls back to an empty config.

### 11. Default Claude Agent

The **ClaudeAgentPlugin** provides out-of-the-box integration with Anthropic's
Claude via the Claude Code SDK (claude-code-sdk):

- Builds a prompt from conversation history and file context, then streams
  the response as StreamEvents.
- `/clear` clears conversation history.
- `/compact` summarizes the history and replaces it with the summary.
- Supports Vertex AI authentication (via environment variables) or direct
  Anthropic API key authentication (`ANTHROPIC_API_KEY`).
- Raises a clear error with setup instructions if no authentication is
  configured.

### 12. Agent Session Spawning

The `agent_factory` connects the REPL with a backing agent through an official
client library (e.g. `claude-code-sdk`). Under normal operation a single client
connection is kept alive for the duration of the REPL session so that
conversation context is preserved across interactions.

However, the framework must also support **spawning** independent agent sessions
alongside the primary one. A spawned session starts with a clean, empty context
-- no prior conversation history -- while the original interactive session
continues undisturbed. This is needed for tasks that should always begin with a
"clean sheet", such as self-contained coding tasks that must not be influenced
by earlier conversation.

Spawned sessions support **pre- and post-hooks** that run activities before and
after the agent does its work:

- **Pre-hook**: invoked before the spawned agent session begins. Example: create
  a git worktree so the agent works on an isolated branch.
- **Post-hook**: invoked after the spawned agent session completes. Example:
  merge the worktree back into the main branch and clean up.

Hooks may be arbitrary application code or may themselves invoke another agent.
The hook mechanism should be generic enough to support both patterns.

### 13. Application Orchestration

A single **App** entry point wires everything together:

1. Creates Session, TUIShell, CommandRegistry, and TokenStatistics subsystems.
2. Registers built-in commands.
3. Loads plugins from both the programmatic `Config` and `.af/config.toml`.
4. If an `agent_factory` is provided in Config, uses it; otherwise attempts to
   create a default ClaudeAgentPlugin (logging a warning and continuing without
   an agent if initialization fails).
5. Sets up the slash command completer and starts the REPL loop.

### 14. CLI Slash Command Invocation

While slash commands are primarily used interactively from within the REPL, the
library also supports invoking them directly from the command line. An
application built on agent_repl can expose its registered slash commands as CLI
entry points so that users can run a command in a single shot without entering
the REPL:

```
APP --slashCommand PARAM1 PARAM2
```

For example, if an app named `myagent` registers a `/compact` command, a user
could run `myagent --compact` from the shell. The framework should parse the
CLI arguments, resolve the matching slash command, invoke its handler with the
provided parameters, and exit -- without starting the interactive REPL loop.

This enables scripting and automation workflows where individual slash commands
are useful as standalone operations (e.g. clearing history, compacting context,
exporting state) without requiring an interactive session.

### 15. Public API

The `agent_repl` package exports a clean surface from its top-level
`__init__.py`:

- `App`, `Config`, `Theme`
- `Plugin`, `AgentPlugin`
- `SlashCommand`
- `StreamEvent`, `StreamEventType`

## Extension Points

| Extension point | Mechanism |
|-----------------|-----------|
| Custom agent | Implement `AgentPlugin` protocol; pass via `Config.agent_factory` or as a plugin. |
| Custom commands | Register `SlashCommand` objects, either via a plugin's command list or directly on `CommandRegistry`. |
| Plugins | Create a module with a `create_plugin()` factory; add its dotted path to `.af/config.toml`. |
| Theming | Pass a `Theme` object through `Config` to customize prompt and gutter colors. |

## Technical Requirements

- **Python version**: 3.12 or later.
- **Target platforms**: macOS and Linux are **must-have**; Windows is
  **best-effort** (should work where possible but not a blocking concern).
- **Core dependencies**:
  - [Rich](https://github.com/Textualize/rich) -- terminal output rendering,
    markdown, panels, spinners, live views.
  - [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) --
    async input, key bindings, history, and Tab completion.
  - [claude-code-sdk](https://github.com/anthropics/claude-code-sdk-python) --
    client library for the default Claude agent integration.

## Non-Functional Considerations

- **Streaming-first**: responses render incrementally; the UI never blocks
  waiting for a complete response.
- **Graceful degradation**: missing clipboard tools, import errors, and absent
  API keys produce clear messages rather than crashes.
- **Platform support**: macOS and Linux (X11 and Wayland) are first-class;
  Windows is best-effort.
