# Requirements Document

## Introduction

**agent_repl** is a Python library and REPL-style TUI framework for building
CLI applications that interact with AI agents. It provides a terminal interface
with free-form input, streamed responses, slash commands, a plugin system, and
an optional default Claude agent. All capabilities are delivered through a
uniform plugin architecture.

## Glossary

| Term | Definition |
|------|------------|
| REPL | Read-Eval-Print Loop; the core interaction cycle of the application. |
| Slash command | User input beginning with `/` followed by a command name (e.g. `/help`). |
| Free text | User input that is not a slash command; forwarded to the active agent. |
| `@path` mention | A token in free text prefixed with `@` referencing a file or directory whose contents are injected into agent context. |
| StreamEvent | A typed event emitted by an agent during response streaming (TEXT_DELTA, TOOL_USE_START, TOOL_RESULT, USAGE, ERROR). |
| Plugin | A module that provides slash commands and/or agent behavior, loaded via a `create_plugin()` factory. |
| AgentPlugin | A plugin that additionally implements `send_message()` and `compact_history()` to act as the active AI agent. |
| Session | The in-memory state holding an ordered list of conversation turns and accumulated token statistics. |
| Conversation turn | A single exchange unit recording role, content, file context, tool uses, and token usage. |
| CommandRegistry | The central store for all registered slash commands, supporting lookup, listing, and completion. |
| Pinned commands | A configurable ordered subset of commands surfaced first during tab completion on bare `/`. |
| TUIShell | The terminal UI layer using Rich for rendering and prompt_toolkit for async input. |
| Gutter bar | A colored vertical bar rendered to the left of streamed and completed agent responses. |
| agent_factory | A callable in `Config` that creates the active `AgentPlugin` instance. The sole mechanism for establishing the active agent. |
| Spawned session | An independent agent session with empty context, running alongside the primary REPL session. |
| Pre-hook / Post-hook | Synchronous callables executed before and after a spawned agent session, respectively. |
| claude-agent-sdk | The Python SDK for interacting with Claude (formerly claude-code-sdk). |
| `.af/config.toml` | TOML configuration file for plugin loading and plugin-specific settings. |

## Requirements

### Requirement 1: REPL Loop

**User Story:** As a developer, I want a conversational REPL loop so that I can
interact with an AI agent through a persistent terminal session.

#### Acceptance Criteria

1.1. THE repl SHALL read user input from the terminal and process it
continuously until an exit condition is met.

1.2. WHEN the user enters empty or whitespace-only input, THE repl SHALL
silently ignore it and re-display the prompt.

1.3. WHEN the user invokes `/quit`, THE repl SHALL terminate the loop.

1.4. WHEN the user presses Ctrl+C or Ctrl+D AND no agent task is in flight,
THE repl SHALL terminate the loop.

1.5. WHEN the user presses Ctrl+C or Ctrl+D AND an agent task is in flight,
THE repl SHALL cancel the running task and re-display the prompt without
exiting.

1.6. WHEN the user enters input starting with `/` followed by one or more
non-whitespace characters, THE repl SHALL classify it as a slash command
and dispatch it to the CommandRegistry.

1.7. WHEN the user enters input that is not a slash command, THE repl SHALL
classify it as free text and forward it to the active agent.

1.8. THE repl SHALL use asyncio as its concurrency model.

#### Edge Cases

1.E1. IF no agent is configured WHEN the user enters free text, THEN THE repl
SHALL display an error message indicating no agent is available and
re-display the prompt.

1.E2. IF the active agent raises an exception during message processing, THEN
THE repl SHALL display the error message and continue the loop.

1.E3. IF a slash command is not found in the CommandRegistry, THEN THE repl
SHALL display an error message listing the unknown command and continue.

---

### Requirement 2: Input Parsing

**User Story:** As a user, I want my input to be correctly classified as
either a slash command or free text with file mentions, so that commands are
dispatched and file contents are injected automatically.

#### Acceptance Criteria

2.1. WHEN the user enters input starting with `/` followed by one or more
non-whitespace characters, THE input_parser SHALL classify it as a slash
command.

2.2. WHEN a slash command is classified, THE input_parser SHALL split on the
first whitespace to extract the command name (without the `/` prefix) and
an optional argument string (the remainder).

2.3. WHEN the user enters free text containing `@path` references (`@`
followed by one or more non-whitespace characters), THE input_parser
SHALL extract all `@`-prefixed tokens as file mentions.

2.4. THE input_parser SHALL treat `@` at end of input or `@` followed by
whitespace as literal text, not a file mention.

#### Edge Cases

2.E1. WHEN the user enters only `/` with no following non-whitespace
characters, THE input_parser SHALL treat it as free text.

2.E2. WHEN the user enters `/` followed by whitespace and then text, THE
input_parser SHALL treat it as free text.

2.E3. WHEN the user enters a slash command with no argument string (e.g.
`/help`), THE input_parser SHALL return an empty argument string.

---

### Requirement 3: File Context Resolution

**User Story:** As a user, I want to reference files and directories with
`@path` in my messages so that the AI agent has access to their contents.

#### Acceptance Criteria

3.1. WHEN a file path is referenced with `@`, THE file_context_resolver SHALL
read the file as UTF-8 text and inject its contents into the agent
context.

3.2. WHEN a directory path is referenced with `@`, THE file_context_resolver
SHALL read all text files in the directory (non-recursively), sorted
alphabetically by path, excluding files matched by any `.gitignore` rules
in scope.

3.3. THE file_context_resolver SHALL enforce a configurable maximum file size
limit (in bytes) to prevent blowing the context window.

3.4. THE file_context_resolver SHALL only process text files (skip binary
files).

#### Edge Cases

3.E1. IF a referenced path does not exist, THEN THE file_context_resolver
SHALL produce a clear error message identifying the missing path.

3.E2. IF a referenced file is binary or not valid UTF-8, THEN THE
file_context_resolver SHALL produce a clear error message identifying
the file and the reason it was skipped.

3.E3. IF a referenced file exceeds the configured size limit, THEN THE
file_context_resolver SHALL produce an error message indicating the file
is too large, including the limit.

3.E4. IF a referenced directory is empty or contains no eligible text files,
THEN THE file_context_resolver SHALL produce an informational message.

3.E5. IF a referenced directory contains a `.gitignore` file, THEN THE
file_context_resolver SHALL exclude files matching its patterns from the
results.

---

### Requirement 4: Slash Command System

**User Story:** As a user, I want a command system with tab completion so that
I can quickly discover and invoke available commands.

#### Acceptance Criteria

4.1. THE command_registry SHALL support registration of SlashCommand objects,
each with a name, description, handler callable, and optional metadata.

4.2. THE command_registry SHALL support lookup by exact command name.

4.3. THE command_registry SHALL support alphabetically-sorted listing of all
registered commands.

4.4. THE command_registry SHALL support prefix-based completion (given a
prefix, return all commands whose names start with that prefix).

4.5. THE command_registry SHALL support pinned commands -- a configurable
ordered set of commands.

4.6. WHEN the user types bare `/` and presses Tab, THE completer SHALL show
only pinned commands, up to a configurable maximum count.

4.7. WHEN the user types `/<prefix>` and presses Tab, THE completer SHALL
show all commands whose names start with `<prefix>`, sorted
alphabetically.

4.8. WHEN the user presses ESC while completions are visible, THE completer
SHALL dismiss the completion menu until the input text changes.

4.9. THE completer SHALL integrate with prompt_toolkit's completion system.

#### Edge Cases

4.E1. IF no commands match the typed prefix, THEN THE completer SHALL show no
completions.

4.E2. IF the pinned commands list is empty, THEN bare `/` Tab SHALL show no
completions.

4.E3. IF a command is registered with a name that already exists, THEN THE
command_registry SHALL replace the previous registration (allowing plugin
override of built-in commands).

---

### Requirement 5: Built-in Commands

**User Story:** As a user, I want essential commands available out of the box
so that I can manage my REPL session without additional configuration.

#### Acceptance Criteria

5.1. WHEN the user invokes `/help`, THE system SHALL display a list of all
registered commands with their descriptions.

5.2. WHEN the user invokes `/quit`, THE system SHALL terminate the REPL loop.

5.3. WHEN the user invokes `/version`, THE system SHALL display the
application name and version string.

5.4. WHEN the user invokes `/copy`, THE system SHALL copy the last assistant
response text to the system clipboard.

5.5. WHEN the user invokes `/agent`, THE system SHALL display the name of the
current active agent and its `default_model` property.

5.6. WHEN the user invokes `/stats`, THE system SHALL display the cumulative
token counts since REPL start, formatted as `NN tokens` when the count
is less than 1000, or `NN.NN k tokens` when the count is 1000 or
greater. Both sent and received counts SHALL be shown.

5.7. All built-in commands SHALL be implemented as plugins using the same
plugin API available to third-party extensions.

#### Edge Cases

5.E1. IF `/copy` is invoked and no assistant response exists in the session,
THEN THE system SHALL display an informational message.

5.E2. IF `/copy` is invoked and the clipboard utility is unavailable, THEN THE
system SHALL display a descriptive error (delegated to the clipboard
module).

5.E3. IF `/agent` is invoked and no agent is configured, THEN THE system SHALL
display a message indicating no agent is active.

5.E4. IF `/stats` is invoked and no tokens have been exchanged, THEN THE
system SHALL display zero counts.

---

### Requirement 6: Streamed Agent Responses

**User Story:** As a user, I want agent responses to stream incrementally so
that I see output as it is generated rather than waiting for completion.

#### Acceptance Criteria

6.1. THE stream_handler SHALL process StreamEvent objects in real time as they
arrive from the active agent's async stream.

6.2. WHEN a TEXT_DELTA event arrives, THE stream_handler SHALL append the text
to a live-updating terminal display.

6.3. WHEN a TOOL_USE_START event arrives, THE stream_handler SHALL display an
informational line showing the tool name.

6.4. WHEN a TOOL_RESULT event arrives, THE stream_handler SHALL render the
result in a labeled panel distinguishing success from error, and record
the tool use.

6.5. WHEN a USAGE event arrives, THE stream_handler SHALL accumulate the token
counts into the session's statistics.

6.6. WHEN an ERROR event arrives AND the error is non-fatal (e.g. a
recoverable model error), THE stream_handler SHALL display the error and
continue processing the stream.

6.7. WHEN an ERROR event arrives AND the error is a hard technical failure
(e.g. lost connectivity, API unavailable), THE stream_handler SHALL stop
the spinner, display the error, and terminate the stream.

6.8. WHEN the first content event (TEXT_DELTA or TOOL_USE_START) arrives, THE
stream_handler SHALL dismiss the "Thinking..." spinner.

6.9. WHEN the stream ends, THE stream_handler SHALL finalize the response as a
conversation turn with accumulated text, tool uses, and token usage.

#### Edge Cases

6.E1. IF the stream yields no content events before ending, THEN THE
stream_handler SHALL dismiss the spinner and finalize an empty turn.

6.E2. IF the stream is cancelled (via Ctrl+C), THEN THE stream_handler SHALL
finalize a partial turn with whatever content was accumulated.

---

### Requirement 7: Rich Terminal UI

**User Story:** As a user, I want a polished terminal interface with markdown
rendering, spinners, and visual structure so that interactions are clear and
pleasant.

#### Acceptance Criteria

7.1. THE tui_shell SHALL use Rich for all output rendering and prompt_toolkit
for async input with history and tab completion.

7.2. WHILE agent response text is streaming, THE tui_shell SHALL display it in
a live view with a colored left gutter bar.

7.3. WHEN an agent response is complete, THE tui_shell SHALL render it as
Rich markdown with the same colored left gutter bar.

7.4. WHILE the agent is processing (before the first content event), THE
tui_shell SHALL display a spinner with "Thinking..." text.

7.5. THE tui_shell SHALL display tool results in labeled Rich panels,
visually distinguishing success from error.

7.6. WHEN the user presses Ctrl+Y, THE tui_shell SHALL copy the last
assistant response text to the system clipboard.

7.7. THE tui_shell SHALL display a prompt with a horizontal rule separator, a
colored prompt glyph, input history navigation, and tab completion.

7.8. THE tui_shell SHALL support displaying contextual information below the
prompt line, populated via a plugin callback mechanism where each plugin
can contribute hint text.

7.9. WHEN the REPL starts, THE tui_shell SHALL display a startup banner
showing the application name and version, the active agent name and its
default model, and a hint to type `/help`.

7.10. THE tui_shell SHALL support theming via a Theme object that controls
prompt and gutter colors.

#### Edge Cases

7.E1. IF Ctrl+Y is pressed and no assistant response exists, THEN THE
tui_shell SHALL display an informational message.

7.E2. IF the terminal does not support the configured theme colors, Rich SHALL
degrade gracefully (this is handled by Rich's terminal detection).

---

### Requirement 8: Session Management

**User Story:** As a developer, I want conversation history and token tracking
so that the agent has context and I can monitor usage.

#### Acceptance Criteria

8.1. THE session SHALL maintain an ordered list of conversation turns, each
recording: role (user/assistant/system), content text, optional file
context references, tool uses, and token usage.

8.2. THE session SHALL accumulate token statistics (sent and received) across
all turns.

8.3. THE session SHALL support adding new turns.

8.4. THE session SHALL support retrieving a copy of the full history.

8.5. THE session SHALL support clearing all history.

8.6. THE session SHALL support retrieving the last assistant response, or None
if no assistant turn exists.

8.7. WHEN `replace_with_summary` is called with summary text, THE session
SHALL replace the entire history with a single summary turn.

#### Edge Cases

8.E1. IF `replace_with_summary` is called on an empty session, THEN THE
session SHALL create a session with just the summary turn.

8.E2. IF the last assistant response is requested from an empty session, THEN
THE session SHALL return None.

---

### Requirement 9: Clipboard Integration

**User Story:** As a user, I want to copy agent responses to my clipboard so
that I can paste them into other applications.

#### Acceptance Criteria

9.1. WHILE running on macOS, THE clipboard SHALL use `pbcopy` to copy text.

9.2. WHILE running on Linux with a Wayland display server, THE clipboard SHALL
use `wl-copy` to copy text.

9.3. WHILE running on Linux with an X11 display server, THE clipboard SHALL
use `xclip -selection clipboard` to copy text.

#### Edge Cases

9.E1. IF the required clipboard utility is not installed on the system, THEN
THE clipboard SHALL produce a descriptive error message naming the
missing utility and how to install it.

9.E2. IF the platform is not supported (neither macOS nor Linux, or Linux with
an unknown display server), THEN THE clipboard SHALL produce a
descriptive error message.

9.E3. IF the clipboard utility command fails (non-zero exit code), THEN THE
clipboard SHALL produce an error message including the utility's stderr.

---

### Requirement 10: Plugin System

**User Story:** As a developer, I want a uniform plugin architecture so that
all capabilities -- built-in and third-party -- use the same extension model.

#### Acceptance Criteria

10.1. THE plugin_loader SHALL import plugin modules by dotted Python path and
call their `create_plugin()` factory function.

10.2. IF a plugin module lacks the `create_plugin()` factory, THEN THE
plugin_loader SHALL log a warning and skip the module.

10.3. IF a plugin module fails to import, THEN THE plugin_loader SHALL log the
import error and skip it, continuing to load remaining plugins.

10.4. THE plugin_registry SHALL store loaded plugins, register their commands
with the CommandRegistry, and track the active agent plugin.

10.5. THE system SHALL use the `agent_factory` callable from `Config` as the
sole mechanism for establishing the active agent.

10.6. IF more than one agent is configured (e.g. multiple plugins attempt to
register as agents), THEN THE system SHALL raise an error.

10.7. THE plugin protocol SHALL define: `get_commands()` returning a list of
SlashCommand objects, `on_load()` lifecycle hook, and `on_unload()`
lifecycle hook.

10.8. THE agent_plugin protocol SHALL extend Plugin with: `send_message()`
returning an async iterator of StreamEvent, `compact_history()`, and a
`default_model` string property.

10.9. IF a plugin's command handler raises an exception during execution, THEN
THE system SHALL display the error message to the user and continue the
REPL loop.

10.10. THE system SHALL load plugin module paths from the `[plugins]` section
of `.af/config.toml`.

10.11. IF `.af/config.toml` does not exist, THEN THE system SHALL create a
default template file.

10.12. IF `.af/config.toml` contains malformed TOML, THEN THE system SHALL log
a warning and fall back to an empty configuration.

10.13. Plugins MAY read their own configuration from `.af/config.toml` using
plugin-specific sections.

#### Edge Cases

10.E1. IF no plugins are loaded and no agent_factory is provided, THEN THE
system SHALL start the REPL without an active agent, and display a
warning.

10.E2. IF a plugin's `on_load()` raises an exception, THEN THE system SHALL
log the error and skip the plugin.

---

### Requirement 11: Default Claude Agent

**User Story:** As a user, I want out-of-the-box Claude integration so that I
can start conversing with an AI agent immediately.

#### Acceptance Criteria

11.1. THE claude_agent_plugin SHALL provide integration with Anthropic's Claude
via the claude-agent-sdk (`claude_agent_sdk` package).

11.2. THE claude_agent_plugin SHALL build a prompt from conversation history
and file context, then stream the response as StreamEvent objects.

11.3. WHEN the user invokes `/clear`, THE claude_agent_plugin SHALL clear the
conversation history.

11.4. WHEN the user invokes `/compact`, THE claude_agent_plugin SHALL
summarize the conversation history (by querying the agent) and replace
the session history with the summary via `replace_with_summary`.

11.5. THE claude_agent_plugin SHALL support authentication via environment
variables: `ANTHROPIC_API_KEY` for direct Anthropic access,
`CLAUDE_CODE_USE_VERTEX=1` for Vertex AI, `CLAUDE_CODE_USE_BEDROCK=1`
for Amazon Bedrock.

11.6. IF no authentication is configured (no recognized environment variables
set), THEN THE claude_agent_plugin SHALL raise a clear error with setup
instructions listing the supported authentication methods.

11.7. THE claude_agent_plugin SHALL expose a `default_model` string property
identifying the model in use.

#### Edge Cases

11.E1. IF the claude-agent-sdk is not installed, THEN THE system SHALL log a
warning and continue without the Claude agent (graceful degradation).

11.E2. IF the agent loses connectivity mid-stream, THEN THE stream SHALL
terminate with an ERROR event (hard failure) and the partial response
SHALL be finalized.

11.E3. IF authentication credentials are invalid (rejected by the API), THEN
THE claude_agent_plugin SHALL surface the API error message to the user.

---

### Requirement 12: Agent Session Spawning

**User Story:** As a developer, I want to spawn independent agent sessions
with clean context so that self-contained tasks are not influenced by prior
conversation.

#### Acceptance Criteria

12.1. THE system SHALL support spawning independent agent sessions that start
with empty conversation context, while the primary REPL session continues
undisturbed.

12.2. THE system SHALL support multiple spawned sessions running in parallel.

12.3. Spawned sessions SHALL support a synchronous pre-hook callable that runs
before the agent session begins.

12.4. Spawned sessions SHALL support a synchronous post-hook callable that
runs after the agent session completes, receiving a notification (not the
session result).

12.5. Spawning SHALL be available via the programmatic API, and optionally
via slash commands registered by plugins.

12.6. THE system SHALL keep the primary interactive session alive and
responsive while spawned sessions run.

#### Edge Cases

12.E1. IF a pre-hook raises an exception, THEN THE system SHALL abort the
spawned session with an error and not start the agent.

12.E2. IF a post-hook raises an exception, THEN THE system SHALL report the
error (the agent work is already complete).

12.E3. IF the spawned agent session itself fails, THEN THE system SHALL report
the error to the caller and still execute the post-hook if one was
registered.

---

### Requirement 13: CLI Slash Command Invocation

**User Story:** As a user, I want to invoke slash commands from the shell
command line so that I can use them in scripts and automation without entering
the interactive REPL.

#### Acceptance Criteria

13.1. THE system SHALL support invoking slash commands directly from the
command line in the form `APP --commandName PARAM1 PARAM2`.

13.2. THE system SHALL automatically map slash command names to CLI flags
(e.g. `/compact` becomes `--compact`).

13.3. WHEN CLI parameters are provided after the flag, THE system SHALL pass
them to the command handler as a list.

13.4. Only slash commands explicitly annotated for CLI exposure (via a
metadata flag on `SlashCommand`) SHALL be available as CLI flags.

13.5. WHEN a CLI-invoked command completes, THE system SHALL exit without
starting the interactive REPL loop.

#### Edge Cases

13.E1. IF the user specifies a `--flag` that does not correspond to any
CLI-exposed slash command, THEN THE system SHALL display an error message
listing available CLI commands and exit with a non-zero status code.

13.E2. IF the CLI-invoked command handler raises an exception, THEN THE system
SHALL display the error and exit with a non-zero status code.

13.E3. IF multiple command flags are provided, THEN THE system SHALL execute
only the first one and ignore the rest (or raise an error -- single
command per invocation).

---

### Requirement 14: Canonical Example Application

**User Story:** As a developer integrating agent_repl, I want a comprehensive
example application so that I can understand all major features and use it as
a starting point.

#### Acceptance Criteria

14.1. THE library SHALL include a canonical example application in an
`examples/` directory.

14.2. THE example SHALL demonstrate creating and configuring an `App` with a
`Config` and `Theme`.

14.3. THE example SHALL include a custom `AgentPlugin` implementation (an echo
agent for credential-free testing).

14.4. THE example SHALL include a Claude agent variant that requires valid
credentials.

14.5. THE example SHALL demonstrate registering custom slash commands via a
plugin.

14.6. THE example SHALL demonstrate `@path` file context mentions.

14.7. THE example SHALL demonstrate spawning an independent agent session with
pre- and post-hooks.

14.8. THE example SHALL demonstrate CLI invocation of a slash command.

14.9. THE example SHALL be thoroughly documented with inline comments,
docstrings, and an accompanying README.

14.10. THE example SHALL be runnable out of the box given valid agent
credentials (for the Claude variant) or no credentials (for the echo
variant).

#### Edge Cases

14.E1. IF the echo agent example is run, it SHALL function without any
external API credentials or network access.

---

### Requirement 15: Public API

**User Story:** As a developer, I want a clean, well-defined public API so
that I can import exactly the types I need from a single package.

#### Acceptance Criteria

15.1. THE `agent_repl` package SHALL export the following from its top-level
`__init__.py`: `App`, `Config`, `Theme`, `Plugin`, `AgentPlugin`,
`SlashCommand`, `StreamEvent`, `StreamEventType`.

15.2. All exported types SHALL be importable via
`from agent_repl import <Type>`.

15.3. THE public API SHALL be stable within a major version -- no breaking
changes without a major version bump.

#### Edge Cases

15.E1. IF a consumer imports a name not in the public API, standard Python
`ImportError` behavior SHALL apply (no special handling needed).

---

### Requirement 16: Non-Functional Requirements

**User Story:** As a developer and user, I want the system to be reliable,
responsive, and well-supported across platforms.

#### Acceptance Criteria

16.1. THE system SHALL use asyncio as the explicit concurrency model for all
I/O operations.

16.2. THE system SHALL render agent responses incrementally (streaming-first);
the UI SHALL NOT block waiting for a complete response.

16.3. THE system SHALL degrade gracefully: missing clipboard tools, plugin
import errors, and absent API keys SHALL produce clear user-facing
messages rather than crashes or stack traces.

16.4. THE system SHALL support macOS and Linux (X11 and Wayland) as first-class
platforms. Windows support is best-effort.

16.5. THE system SHALL require Python 3.12 or later.

16.6. THE system SHALL execute commands single-threaded, but the architecture
SHALL be designed to accommodate future concurrency.

16.7. THE system SHALL include a `Makefile` with at minimum these targets:
`build`, `test`, `lint`, `package`, `clean`.

16.8. THE system SHALL use `uv` as the standard package/environment manager.

16.9. THE system SHALL depend on: Rich, prompt-toolkit, and claude-agent-sdk.
