# Requirements Document

## Introduction

This document captures the requirements for `agent_repl`, a Python library and REPL-style TUI framework for building CLI applications that interact with AI agents. It provides a terminal interface with free-form input, streamed responses, slash commands, a plugin system, and an optional default Claude agent. These requirements describe the system as currently implemented.

## Glossary

- **App**: The top-level entry point class that accepts a Config, creates subsystems, loads plugins, and runs the REPL loop.
- **REPLCore**: The read-eval-print loop that reads user input, parses it, and dispatches to slash commands or the agent.
- **TUIShell**: The terminal user interface layer using Rich for output rendering and prompt_toolkit for async input with history and completions.
- **InputParser**: The module that classifies raw user input as either a slash command or free text, and extracts `@path` mentions.
- **CommandRegistry**: A registry that stores slash commands by name and provides lookup, prefix-based completions, and pinned command resolution.
- **SlashCommandCompleter**: A prompt_toolkit Completer that shows pinned commands on bare `/` and filters by prefix on `/<prefix>`.
- **Session**: The conversation history manager that stores ordered ConversationTurn objects and accumulates token statistics.
- **StreamHandler**: The module that consumes an async stream of StreamEvent objects from an agent and coordinates TUI display.
- **FileContextResolver**: The module that resolves `@path` mentions into FileContent objects by reading files or directories.
- **Clipboard**: The platform-aware clipboard utility that copies text using pbcopy (macOS), xclip (Linux/X11), or wl-copy (Wayland).
- **PluginLoader**: The module that imports plugin modules by dotted path and calls their `create_plugin()` factory.
- **PluginRegistry**: The registry that manages loaded plugins, routes their commands, and identifies the active agent plugin.
- **ConfigLoader**: The module that reads plugin configuration from `.af/plugins.toml` TOML files.
- **ClaudeAgentPlugin**: The default agent plugin that integrates with Claude via the Claude Code SDK.
- **Plugin**: A protocol defining the interface for plugins (name, description, commands, lifecycle hooks).
- **AgentPlugin**: A protocol extending Plugin with `send_message()` and `compact_history()` methods.
- **StreamEvent**: A dataclass representing a single event in an agent response stream (text delta, tool use, usage, error).
- **ConversationTurn**: A dataclass representing one turn in a conversation (role, content, file context, tool uses, token usage).
- **ParsedInput**: A dataclass representing classified user input with type, raw text, command name/args, and at-mentions.
- **SlashCommand**: A dataclass representing a registered command with name, description, help text, handler, and pinned flag.
- **FileContent**: A dataclass representing a file's path and text content.
- **TokenStatistics**: A dataclass that accumulates total input and output token counts across a session.

## Requirements

### Requirement 1: Input Parsing

**User Story:** As a developer using the REPL, I want my input to be correctly classified and parsed, so that slash commands and free text are handled appropriately.

#### Acceptance Criteria

1. WHEN a user enters text starting with `/` followed by one or more non-whitespace characters, THE InputParser SHALL classify the input as SLASH_COMMAND and extract the command name and arguments.
2. WHEN a user enters text that does not start with `/` followed by a non-whitespace character, THE InputParser SHALL classify the input as FREE_TEXT.
3. WHEN free text contains `@path` references (@ followed by non-whitespace characters), THE InputParser SHALL extract all at-mention paths into a list.
4. WHEN a slash command has arguments after the command name, THE InputParser SHALL split on the first whitespace to separate the command name from the argument string.
5. WHEN a slash command has no arguments, THE InputParser SHALL set the command arguments to an empty string.
6. WHEN input is only `/` or `/ text` (slash followed by whitespace), THE InputParser SHALL classify the input as FREE_TEXT.

### Requirement 2: Command Registry

**User Story:** As a framework consumer, I want to register and look up slash commands, so that the REPL can dispatch user commands to the correct handlers.

#### Acceptance Criteria

1. WHEN a SlashCommand is registered, THE CommandRegistry SHALL store the command and make it retrievable by name.
2. WHEN a command is looked up by name and exists, THE CommandRegistry SHALL return the SlashCommand object.
3. WHEN a command is looked up by name and does not exist, THE CommandRegistry SHALL return None.
4. WHEN all commands are requested, THE CommandRegistry SHALL return all registered commands sorted alphabetically by name.
5. WHEN completions are requested for a prefix, THE CommandRegistry SHALL return all command names that start with the prefix, sorted alphabetically.
6. WHEN pinned commands are requested with a list of pinned names, THE CommandRegistry SHALL return commands in the order of the pinned names list first, then any commands with `pinned=True` not already included, with no duplicates.

### Requirement 3: Slash Command Completion

**User Story:** As a REPL user, I want tab completion for slash commands, so that I can discover and quickly enter commands.

#### Acceptance Criteria

1. WHEN the input is exactly `/`, THE SlashCommandCompleter SHALL yield only pinned commands up to the configured maximum display count.
2. WHEN the input starts with `/<prefix>`, THE SlashCommandCompleter SHALL yield all commands whose names start with the prefix, sorted alphabetically.
3. WHEN the input does not start with `/`, THE SlashCommandCompleter SHALL yield no completions.
4. WHEN the user presses ESC to dismiss completions, THE SlashCommandCompleter SHALL suppress further completions until the input text changes.
5. WHEN the completer is suppressed and the input text changes, THE SlashCommandCompleter SHALL resume yielding completions.
6. WHEN pinned commands are resolved, THE SlashCommandCompleter SHALL include config-specified pinned names first (in order), then any commands with `pinned=True` not already included, capped at the maximum display count.

### Requirement 4: Session Management

**User Story:** As a REPL user, I want my conversation history to be maintained, so that the agent has context from previous turns.

#### Acceptance Criteria

1. WHEN a ConversationTurn is added, THE Session SHALL append the turn to the ordered history list.
2. WHEN a turn with token_usage is added, THE Session SHALL accumulate the token usage into the session's TokenStatistics.
3. WHEN the history is requested, THE Session SHALL return a copy of the ordered list of conversation turns.
4. WHEN the session is cleared, THE Session SHALL reset the history to empty.
5. WHEN the last assistant content is requested and assistant turns exist, THE Session SHALL return the content of the most recent assistant turn.
6. WHEN the last assistant content is requested and no assistant turns exist, THE Session SHALL return None.
7. WHEN replace_with_summary is called, THE Session SHALL clear the history and replace it with a single assistant turn containing the summary text.

### Requirement 5: File Context Resolution

**User Story:** As a REPL user, I want to reference files and directories with `@path` mentions, so that I can provide file context to the agent.

#### Acceptance Criteria

1. WHEN a file path is resolved and the file exists, THE FileContextResolver SHALL return a FileContent object with the file path and its UTF-8 text content.
2. WHEN a directory path is resolved, THE FileContextResolver SHALL recursively read all files in the directory and return FileContent objects sorted by path.
3. WHEN a path does not exist, THE FileContextResolver SHALL raise a FileContextError with a descriptive message.
4. WHEN a file contains binary or non-UTF-8 content, THE FileContextResolver SHALL raise a FileContextError indicating the file is binary or non-text.

### Requirement 6: Clipboard Operations

**User Story:** As a REPL user, I want to copy agent output to my system clipboard, so that I can paste it elsewhere.

#### Acceptance Criteria

1. WHEN running on macOS, THE Clipboard SHALL use `pbcopy` to copy text.
2. WHEN running on Linux with Wayland, THE Clipboard SHALL use `wl-copy` to copy text.
3. WHEN running on Linux with X11, THE Clipboard SHALL use `xclip -selection clipboard` to copy text.
4. WHEN the required clipboard utility is not found on the system, THE Clipboard SHALL raise a ClipboardError.
5. WHEN the clipboard subprocess fails, THE Clipboard SHALL raise a ClipboardError with the stderr output.
6. WHEN running on an unsupported platform, THE Clipboard SHALL raise a ClipboardError.

### Requirement 7: Stream Event Handling

**User Story:** As a REPL user, I want agent responses to be streamed to the terminal in real time, so that I can see output as it is generated.

#### Acceptance Criteria

1. WHEN a TEXT_DELTA event is received, THE StreamHandler SHALL append the text to the live streaming display.
2. WHEN the first content event is received, THE StreamHandler SHALL stop the thinking spinner.
3. WHEN a TOOL_USE_START event is received, THE StreamHandler SHALL display an informational message with the tool name.
4. WHEN a TOOL_RESULT event is received, THE StreamHandler SHALL display the result in a panel and record the tool use.
5. WHEN a USAGE event is received, THE StreamHandler SHALL create a TokenUsage and accumulate it into the session statistics.
6. WHEN an ERROR event is received, THE StreamHandler SHALL stop the spinner and display the error message.
7. WHEN the stream completes, THE StreamHandler SHALL finish the streaming display, create a ConversationTurn with the full text, tool uses, and token usage, and add the turn to the session.

### Requirement 8: Plugin Loading

**User Story:** As a framework consumer, I want to load plugins by module path, so that I can extend the REPL with custom commands and agents.

#### Acceptance Criteria

1. WHEN a plugin module is loaded by dotted path, THE PluginLoader SHALL import the module and call its `create_plugin()` factory function.
2. WHEN a plugin module does not have a `create_plugin()` function, THE PluginLoader SHALL log an error and skip the plugin.
3. WHEN a plugin module fails to import, THE PluginLoader SHALL log the error and continue loading remaining plugins.

### Requirement 9: Plugin Registry

**User Story:** As a framework consumer, I want plugins to be registered and their commands routed, so that plugin commands are available in the REPL.

#### Acceptance Criteria

1. WHEN a plugin is registered, THE PluginRegistry SHALL store the plugin and register all its commands with the CommandRegistry.
2. WHEN a plugin with `send_message` and `compact_history` methods is registered and no agent is set, THE PluginRegistry SHALL set the plugin as the active agent.
3. WHEN the active agent is requested, THE PluginRegistry SHALL return the current agent plugin or None.

### Requirement 10: Configuration Loading

**User Story:** As a framework consumer, I want plugin configuration loaded from a TOML file, so that I can configure plugins without code changes.

#### Acceptance Criteria

1. WHEN `.af/plugins.toml` exists and is valid TOML, THE ConfigLoader SHALL parse and return the configuration dictionary.
2. WHEN `.af/plugins.toml` does not exist, THE ConfigLoader SHALL create the file with a default template and return the parsed default configuration.
3. WHEN `.af/plugins.toml` contains malformed TOML, THE ConfigLoader SHALL log a warning and return an empty dictionary.
4. WHEN the config directory cannot be created due to permissions, THE ConfigLoader SHALL log a warning and return the parsed default configuration.

### Requirement 11: REPL Loop

**User Story:** As a REPL user, I want a continuous input loop that dispatches my input to commands or the agent, so that I can interact with the system.

#### Acceptance Criteria

1. WHEN a slash command is entered and the command exists, THE REPLCore SHALL execute the command handler with a CommandContext.
2. WHEN a slash command is entered and the command does not exist, THE REPLCore SHALL display an error message suggesting `/help`.
3. WHEN free text is entered with `@path` mentions, THE REPLCore SHALL resolve file context and send the text with context to the agent.
4. WHEN free text is entered and no agent is configured, THE REPLCore SHALL display an error message.
5. WHEN Ctrl+C or Ctrl+D is pressed with no agent task running, THE REPLCore SHALL exit the loop.
6. WHEN Ctrl+C or Ctrl+D is pressed with an agent task running, THE REPLCore SHALL cancel the agent task.
7. WHEN empty or whitespace-only text is entered, THE REPLCore SHALL ignore the input.

### Requirement 12: Built-in Commands

**User Story:** As a REPL user, I want built-in commands for help, quitting, version info, and clipboard copy, so that I have essential REPL functionality.

#### Acceptance Criteria

1. WHEN `/help` is executed, THE App SHALL display all registered commands with their names and descriptions.
2. WHEN `/quit` is executed, THE App SHALL raise SystemExit to terminate the REPL.
3. WHEN `/version` is executed, THE App SHALL display the application name and version from package metadata.
4. WHEN `/copy` is executed and assistant output exists, THE App SHALL copy the last assistant output to the system clipboard.
5. WHEN `/copy` is executed and no assistant output exists, THE App SHALL display an informational message.

### Requirement 13: Application Orchestration

**User Story:** As a framework consumer, I want a single App entry point that wires all subsystems together, so that I can start the REPL with minimal setup.

#### Acceptance Criteria

1. WHEN App.run() is called, THE App SHALL create Session, TUIShell, CommandRegistry, and TokenStatistics subsystems.
2. WHEN the App starts, THE App SHALL register all built-in commands with the CommandRegistry.
3. WHEN the App starts, THE App SHALL load plugins from both the Config and the `.af/plugins.toml` file.
4. WHEN an agent_factory is provided in Config, THE App SHALL use the factory to create the agent.
5. WHEN no agent_factory is provided, THE App SHALL attempt to create a default ClaudeAgentPlugin.
6. WHEN the default Claude agent fails to initialize, THE App SHALL log a warning and continue without an agent.
7. WHEN all plugins and agent are loaded, THE App SHALL set up the slash command completer and start the REPL loop.

### Requirement 14: TUI Display

**User Story:** As a REPL user, I want a rich terminal interface with streaming output, markdown rendering, and visual feedback, so that the interaction is clear and responsive.

#### Acceptance Criteria

1. WHEN agent text is streamed, THE TUIShell SHALL display it in a live updating view with a colored left gutter bar.
2. WHEN streaming completes, THE TUIShell SHALL render the full text as markdown with the gutter bar.
3. WHEN the agent is processing, THE TUIShell SHALL display an animated spinner with "Thinking..." text.
4. WHEN a tool result is displayed, THE TUIShell SHALL render it in a panel with the tool name and error distinction.
5. WHEN Ctrl+Y is pressed, THE TUIShell SHALL copy the last assistant output to the clipboard.
6. WHEN input is prompted, THE TUIShell SHALL display a horizontal rule and a colored prompt with history and tab completion support.

### Requirement 15: Claude Agent Integration

**User Story:** As a REPL user, I want to interact with Claude as the default AI agent, so that I can have AI-assisted conversations.

#### Acceptance Criteria

1. WHEN a message is sent to the Claude agent, THE ClaudeAgentPlugin SHALL build a prompt string from conversation history and file context, and stream the response as StreamEvents.
2. WHEN `/clear` is executed, THE ClaudeAgentPlugin SHALL clear the session conversation history.
3. WHEN `/compact` is executed, THE ClaudeAgentPlugin SHALL summarize the conversation history and replace it with the summary.
4. WHEN Vertex AI environment variables are set, THE ClaudeAgentPlugin SHALL use Vertex AI authentication.
5. WHEN ANTHROPIC_API_KEY is set, THE ClaudeAgentPlugin SHALL use API key authentication.
6. IF no authentication is configured, THEN THE ClaudeAgentPlugin SHALL raise an AgentError with instructions for configuring auth.

### Requirement 16: Public API

**User Story:** As a framework consumer, I want a clean public API exported from the package, so that I can import only what I need.

#### Acceptance Criteria

1. THE `agent_repl` package SHALL export App, Config, Theme, Plugin, AgentPlugin, SlashCommand, StreamEvent, and StreamEventType from its top-level `__init__.py`.
