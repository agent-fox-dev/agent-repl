# Implementation Plan: agent_repl Core

## Overview

This plan documents the implementation of the `agent_repl` framework — a Python REPL-style TUI for AI agent interaction. All tasks are marked complete as this spec documents existing code. Property-based tests using hypothesis target the pure/testable modules.

## Tasks

- [x] 1. Core type system and exceptions
  - [x] 1.1 Define data models, protocols, and enums in `types.py`
    - Config, Theme, SlashCommand, Plugin/AgentPlugin protocols, StreamEvent/StreamEventType, ConversationTurn, FileContent, TokenUsage/TokenStatistics, ParsedInput/InputType, CommandContext/AppContext
    - _Requirements: 16.1_
  - [x] 1.2 Define custom exceptions in `exceptions.py`
    - FileContextError, PluginLoadError, AgentError, ConfigError, ClipboardError
  - [x] 1.3 Define constants in `constants.py`
    - DEFAULT_CLAUDE_MODEL, DEFAULT_PINNED_COMMANDS, MAX_PINNED_DISPLAY

- [x] 2. Input parsing
  - [x] 2.1 Implement `parse_input` in `input_parser.py`
    - Classify input as SLASH_COMMAND or FREE_TEXT
    - Extract command name/args for slash commands
    - Extract @mentions for free text via regex `r'@(\S+)'`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x]* 2.2 Write property tests for input parser
    - **Property 1: Input classification is exhaustive and correct**
    - **Validates: Requirements 1.1, 1.2, 1.6**
    - **Property 2: At-mention extraction captures all @references**
    - **Validates: Requirements 1.3**
    - **Property 3: Slash command round-trip (name + args reconstruction)**
    - **Validates: Requirements 1.4, 1.5**

- [x] 3. Command registry
  - [x] 3.1 Implement `CommandRegistry` in `command_registry.py`
    - register, get, all_commands (sorted), completions (prefix match), pinned_commands (ordered + deduped)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  - [x]* 3.2 Write property tests for command registry
    - **Property 4: Command register/get round trip**
    - **Validates: Requirements 2.1, 2.2, 2.3**
    - **Property 5: All commands are sorted**
    - **Validates: Requirements 2.4**
    - **Property 6: Prefix completions are correct and sorted**
    - **Validates: Requirements 2.5**
    - **Property 7: Pinned command resolution ordering and deduplication**
    - **Validates: Requirements 2.6, 3.6**

- [x] 4. Slash command completer
  - [x] 4.1 Implement `SlashCommandCompleter` in `completer.py`
    - Bare `/` shows pinned commands (capped at MAX_PINNED_DISPLAY)
    - `/<prefix>` filters all commands by prefix
    - Non-slash input yields nothing
    - ESC suppression until text changes
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [x]* 4.2 Write property tests for completer
    - **Property 8: Completer bare slash yields only pinned commands**
    - **Validates: Requirements 3.1**
    - **Property 9: Completer prefix filtering matches correctly**
    - **Validates: Requirements 3.2**
    - **Property 10: Completer yields nothing for non-slash input**
    - **Validates: Requirements 3.3**
    - **Property 11: Completer suppression lifecycle**
    - **Validates: Requirements 3.4, 3.5**

- [x] 5. Session management
  - [x] 5.1 Implement `Session` in `session.py`
    - add_turn with token accumulation, get_history (copy), clear, get_last_assistant_content, replace_with_summary
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  - [x]* 5.2 Write property tests for session
    - **Property 12: Session history preserves insertion order and returns a copy**
    - **Validates: Requirements 4.1, 4.3**
    - **Property 13: Session token accumulation is additive**
    - **Validates: Requirements 4.2**
    - **Property 14: Session last assistant content returns most recent**
    - **Validates: Requirements 4.5, 4.6**
    - **Property 15: Session replace_with_summary produces single-turn history**
    - **Validates: Requirements 4.4, 4.7**

- [x] 6. File context resolution
  - [x] 6.1 Implement `resolve_file_context` in `file_context.py`
    - File reading (UTF-8), directory recursion (sorted), error handling for missing/binary
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x]* 6.2 Write property tests for file context
    - **Property 16: File context round trip for text files**
    - **Validates: Requirements 5.1**
    - **Property 17: Directory resolution returns all files sorted**
    - **Validates: Requirements 5.2**
    - **Property 18: Missing path raises FileContextError**
    - **Validates: Requirements 5.3**
    - **Property 19: Binary file raises FileContextError**
    - **Validates: Requirements 5.4**

- [x] 7. Clipboard operations
  - [x] 7.1 Implement `clipboard.py`
    - Platform detection (macOS/Wayland/X11), utility check, subprocess execution
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  - [x]* 7.2 Write unit tests for clipboard
    - Test platform detection with mocked sys.platform and env vars
    - Test missing utility and subprocess failure error paths
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 8. Stream event handling
  - [x] 8.1 Implement `handle_stream` in `stream_handler.py`
    - TEXT_DELTA streaming, TOOL_USE_START info, TOOL_RESULT panels, USAGE accumulation, ERROR display
    - ConversationTurn creation and session addition
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  - [x]* 8.2 Write property tests for stream handler
    - **Property 20: Stream handler turn content equals concatenated text deltas**
    - **Validates: Requirements 7.1, 7.7**
    - **Property 21: Stream handler records all tool uses**
    - **Validates: Requirements 7.4**
    - **Property 22: Stream handler accumulates token usage**
    - **Validates: Requirements 7.5**

- [x] 9. Plugin system
  - [x] 9.1 Implement `plugin_loader.py`
    - Import by dotted path, call create_plugin(), log and skip on failure
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 9.2 Implement `plugin_registry.py`
    - Store plugins, route commands, detect agent via duck typing
    - _Requirements: 9.1, 9.2, 9.3_
  - [x]* 9.3 Write unit tests for plugin system
    - Test plugin loading, missing factory, import failure
    - Test plugin registration and agent detection
    - _Requirements: 8.1, 8.2, 8.3, 9.1, 9.2, 9.3_

- [x] 10. Configuration loading
  - [x] 10.1 Implement `config_loader.py`
    - Read .af/plugins.toml, create default if missing, handle malformed TOML
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  - [x]* 10.2 Write unit tests for config loader
    - Test valid TOML, missing file creation, malformed TOML, permission errors
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 11. Built-in commands
  - [x] 11.1 Implement built-in commands in `builtin_commands.py`
    - /help, /quit, /version, /copy
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  - [x]* 11.2 Write unit tests for built-in commands
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 12. TUI shell
  - [x] 12.1 Implement `TUIShell` in `tui.py`
    - Rich console output, prompt_toolkit input, streaming display with gutter bar
    - Spinner animation, markdown rendering, tool result panels
    - Ctrl+Y clipboard, ESC completion dismissal
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_
  - [x]* 12.2 Write unit tests for TUI shell
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [x] 13. REPL core loop
  - [x] 13.1 Implement `REPLCore` in `repl.py`
    - Main loop, input parsing, command dispatch, free text dispatch
    - File context resolution, agent streaming, cancellation handling
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  - [x]* 13.2 Write unit tests for REPL core
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [x] 14. Application orchestration
  - [x] 14.1 Implement `App` in `app.py`
    - Create subsystems, register built-ins, load plugins, initialize agent, set up completer, run REPL
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_
  - [x]* 14.2 Write unit tests for App
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [x] 15. Claude agent integration
  - [x] 15.1 Implement `ClaudeAgentPlugin` in `agents/claude_agent.py`
    - Claude Code SDK integration, Vertex/API key auth, /clear and /compact commands
    - Prompt building from history and file context
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_
  - [x]* 15.2 Write unit tests for Claude agent
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

- [x] 16. Public API and packaging
  - [x] 16.1 Configure `__init__.py` exports and `pyproject.toml`
    - Export App, Config, Theme, Plugin, AgentPlugin, SlashCommand, StreamEvent, StreamEventType
    - _Requirements: 16.1_
  - [x]* 16.2 Write unit tests for public API exports
    - _Requirements: 16.1_

## Notes

- All tasks are marked complete — this spec documents existing implemented code
- Tasks marked with `*` are optional property/unit test tasks
- Property tests use `hypothesis` as the PBT framework
- Each property test references its design document property number
- Modules suitable for PBT: input_parser, command_registry, completer, session, file_context, stream_handler
- Modules tested with unit tests only: clipboard, config_loader, plugin system, built-in commands, TUI, REPL, App, Claude agent
