# Implementation Plan: agent_repl

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from develop -> implement -> test -> merge to develop -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

The implementation follows a bottom-up dependency order: foundational types and
utilities first, then core infrastructure, then UI and streaming, then the REPL
loop and orchestration, and finally the agent integration, spawning, CLI
invocation, and the canonical example. Each task group is scoped to one coding
session.

## Test Commands

- Unit tests: `uv run pytest tests/ -q --ignore=tests/integration`
- Property tests: `uv run pytest tests/ -q -m property`
- Integration tests: `uv run pytest tests/integration/ -q`
- All tests: `uv run pytest tests/ -q`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [x] 1. Project Scaffolding + Core Types
  - [x] 1.1 Initialize project structure
    - Create `src/agent_repl/` package with `__init__.py`, `py.typed`
    - Create `src/agent_repl/agents/__init__.py`
    - Create `tests/__init__.py`, `tests/integration/__init__.py`
    - Create `tests/conftest.py` with shared fixtures
    - _Requirements: 15.1, 15.2, 16.5_

  - [x] 1.2 Create `pyproject.toml`
    - Project name `agent_repl`, version `0.1.0`, requires-python `>=3.12`
    - Dependencies: `rich`, `prompt-toolkit`, `claude-agent-sdk`, `httpx`
    - Dev dependencies: `pytest`, `pytest-asyncio`, `hypothesis`, `ruff`
    - Build system: `hatchling` with `packages = ["src/agent_repl"]`
    - Tool config: `asyncio_mode = "auto"`, ruff `target-version = "py312"`, `line-length = 100`
    - _Requirements: 16.5, 16.8, 16.9_

  - [x] 1.3 Create `Makefile`
    - `build`: `uv build`
    - `test`: `uv run pytest tests/ -q`
    - `lint`: `uv run ruff check src/ tests/`
    - `package`: `uv build --wheel --sdist`
    - `clean`: remove `__pycache__`, `.pyc`, `*.egg-info`, `dist/`, `build/`
    - _Requirements: 16.7_

  - [x] 1.4 Implement `src/agent_repl/types.py`
    - `StreamEventType` enum (TEXT_DELTA, TOOL_USE_START, TOOL_RESULT, USAGE, ERROR)
    - Frozen dataclasses: `Theme`, `StreamEvent`, `TokenUsage`, `FileContext`, `ToolUse`
    - Mutable dataclass: `ConversationTurn`
    - Config dataclasses: `SlashCommand`, `Config`, `SpawnConfig`
    - Context dataclasses: `MessageContext`, `CommandContext`, `PluginContext`
    - `Plugin` protocol (name, description, get_commands, on_load, on_unload, get_status_hints)
    - `AgentPlugin` protocol extending Plugin (default_model, send_message, compact_history)
    - _Requirements: 15.1_

  - [x] 1.5 Implement `src/agent_repl/constants.py`
    - `DEFAULT_MAX_PINNED_DISPLAY = 6`
    - `DEFAULT_MAX_FILE_SIZE = 512_000`
    - `DEFAULT_PINNED_COMMANDS = ["help", "quit"]`
    - `DEFAULT_CONFIG_PATH = ".af/config.toml"`
    - `APP_NAME = "agent_repl"`

  - [x] 1.6 Implement `src/agent_repl/exceptions.py`
    - `AgentReplError(Exception)` -- base
    - `AgentError(AgentReplError)` -- agent failures
    - `PluginError(AgentReplError)` -- plugin loading/registration errors
    - `ConfigError(AgentReplError)` -- config loading errors
    - `ClipboardError(AgentReplError)` -- clipboard failures
    - `FileContextError(AgentReplError)` -- file resolution errors

  - [x] 1.7 Set up public API exports in `__init__.py`
    - Export: `App`, `Config`, `Theme`, `Plugin`, `AgentPlugin`, `SlashCommand`, `StreamEvent`, `StreamEventType`
    - `App` import will be deferred (not yet implemented); export the types that exist
    - _Requirements: 15.1, 15.2_

  - [x] 1.8 Write unit tests for types and exceptions
    - `tests/test_types.py`: dataclass construction, default values, enum values, protocol runtime checks
    - `tests/test_exceptions.py`: exception hierarchy, inheritance, message formatting
    - **Validates: Requirements 15.1, 15.2**

  - [x] 1.V Verify task group 1
    - [x] All new tests pass: `uv run pytest tests/test_types.py tests/test_exceptions.py -q`
    - [x] Linter clean: `uv run ruff check src/ tests/`
    - [x] Project builds: `make build`
    - [x] Requirements 15.1, 15.2, 16.5, 16.7, 16.8, 16.9 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [x] 2. Checkpoint - Foundation Types Complete
  - Ensure all tests pass, project builds, linter clean.

<!-- SESSION BOUNDARY -->

- [x] 3. Input Parsing + File Context Resolution
  - [x] 3.1 Implement `src/agent_repl/input_parser.py`
    - `ParsedCommand` frozen dataclass (name: str, args: str)
    - `ParsedFreeText` frozen dataclass (text: str, mentions: list[str])
    - `ParseResult = ParsedCommand | ParsedFreeText | None`
    - `parse_input(raw: str) -> ParseResult`
    - Slash command detection: `/` + non-whitespace chars → split on first whitespace
    - `@path` mention extraction from free text
    - Empty/whitespace input → None
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.E1, 2.E2, 2.E3_

  - [x] 3.2 Implement `src/agent_repl/file_context.py`
    - `resolve_file_context(path: str, max_file_size: int) -> FileContext`
    - `resolve_mentions(mentions: list[str], max_file_size: int) -> list[FileContext]`
    - File reading: UTF-8 text, size limit check, binary detection
    - Directory reading: non-recursive, text files only, sorted alphabetically
    - `.gitignore` filtering: parse `.gitignore` in the directory and exclude matching files
    - Error handling: missing path, binary file, size exceeded, empty directory
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.E1, 3.E2, 3.E3, 3.E4, 3.E5_

  - [x] 3.3 Write property tests for input_parser
    - `tests/test_input_parser.py`
    - **Property 1: Input Classification Completeness** -- for any string, result is exactly one of None, ParsedCommand, ParsedFreeText
    - **Property 2: Slash Command Parsing** -- `/name args` → ParsedCommand(name, args)
    - **Property 3: Mention Extraction** -- `@path` tokens extracted in order
    - **Validates: Requirements 2.1-2.4, 2.E1-2.E3**

  - [x] 3.4 Write unit and property tests for file_context
    - `tests/test_file_context.py`
    - **Property 12: File Context Size Enforcement** -- files exceeding limit → error FileContext
    - **Property 13: File Context Determinism** -- directory results sorted by path
    - Test: missing path, binary file, valid UTF-8 file, .gitignore filtering, empty directory
    - **Validates: Requirements 3.1-3.4, 3.E1-3.E5**

  - [x] 3.V Verify task group 3
    - [x] All new tests pass: `uv run pytest tests/test_input_parser.py tests/test_file_context.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 2.1-2.4, 2.E1-2.E3, 3.1-3.4, 3.E1-3.E5 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [x] 4. Session Management + Clipboard
  - [x] 4.1 Implement `src/agent_repl/session.py`
    - `TokenStatistics` class
      - `total_input: int`, `total_output: int` (initialized to 0)
      - `accumulate(usage: TokenUsage)` -- adds to totals
      - `format_tokens(count: int) -> str` -- `"NN tokens"` if < 1000, `"NN.NN k tokens"` if >= 1000
      - `format_input() -> str`, `format_output() -> str`
    - `Session` class
      - Internal `_history: list[ConversationTurn]`, `_stats: TokenStatistics`
      - `add_turn(turn)` -- appends and accumulates usage if present
      - `get_history() -> list[ConversationTurn]` -- returns copy
      - `clear()` -- empties history, resets stats
      - `last_assistant_response() -> str | None`
      - `replace_with_summary(summary: str)` -- replaces history with single system turn
      - `stats` property
    - _Requirements: 8.1-8.7, 8.E1, 8.E2, 5.6_

  - [x] 4.2 Implement `src/agent_repl/clipboard.py`
    - `copy_to_clipboard(text: str) -> None`
    - Platform detection: `sys.platform` for macOS; `$WAYLAND_DISPLAY` / `$DISPLAY` for Linux
    - macOS → `pbcopy`; Linux Wayland → `wl-copy`; Linux X11 → `xclip -selection clipboard`
    - Raises `ClipboardError` with descriptive messages for missing utility, unsupported platform, command failure
    - Uses `subprocess.run` with text piped to stdin
    - _Requirements: 9.1, 9.2, 9.3, 9.E1, 9.E2, 9.E3_

  - [x] 4.3 Write property tests for session
    - `tests/test_session.py`
    - **Property 7: Session History Ordering** -- turns returned in insertion order
    - **Property 8: Token Accumulation Correctness** -- totals equal sum of individual usages
    - **Property 9: Token Formatting** -- correct format for any non-negative int
    - **Property 10: Replace With Summary Postcondition** -- exactly one system turn after replace
    - **Property 11: Last Assistant Response** -- returns last assistant content or None
    - **Validates: Requirements 8.1-8.7, 8.E1, 8.E2, 5.6**

  - [x] 4.4 Write unit tests for clipboard
    - `tests/test_clipboard.py`
    - **Property 14: Clipboard Platform Selection** -- exactly one mechanism or error per platform
    - Test macOS (mock `sys.platform == "darwin"`, mock subprocess)
    - Test Linux Wayland (mock `WAYLAND_DISPLAY`, mock subprocess)
    - Test Linux X11 (mock `DISPLAY`, mock subprocess)
    - Test missing utility (FileNotFoundError from subprocess)
    - Test unsupported platform
    - Test command failure (non-zero exit)
    - **Validates: Requirements 9.1-9.3, 9.E1-9.E3**

  - [x] 4.V Verify task group 4
    - [x] All new tests pass: `uv run pytest tests/test_session.py tests/test_clipboard.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 8.1-8.7, 8.E1, 8.E2, 5.6, 9.1-9.3, 9.E1-9.E3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 4 is complete. Do NOT continue to task group 5 in this session. -->

- [x] 5. Checkpoint - Foundation + Core Utilities Complete
  - Ensure all tests pass: types, exceptions, input_parser, file_context, session, clipboard.

<!-- SESSION BOUNDARY -->

- [x] 6. Command Registry + Config Loader
  - [x] 6.1 Implement `src/agent_repl/command_registry.py`
    - `CommandRegistry` class
      - Internal `_commands: dict[str, SlashCommand]`
      - `register(command: SlashCommand)` -- stores by name (last-write-wins for overrides)
      - `get(name: str) -> SlashCommand | None` -- exact lookup
      - `list_all() -> list[SlashCommand]` -- alphabetically sorted by name
      - `complete(prefix: str) -> list[SlashCommand]` -- prefix match, sorted alphabetically
      - `get_pinned(pinned_names: list[str], max_count: int) -> list[SlashCommand]` -- returns registered commands in pinned order, capped at max_count
    - _Requirements: 4.1-4.5, 4.E1-4.E3_

  - [x] 6.2 Implement `src/agent_repl/config_loader.py`
    - `LoadedConfig` dataclass (plugin_paths: list[str], raw: dict[str, Any])
    - `load_config(path: str = ".af/config.toml") -> LoadedConfig`
    - Missing file → create default template, return empty LoadedConfig
    - Malformed TOML → log warning, return empty LoadedConfig
    - Valid TOML → extract `[plugins].paths` list, return full raw dict
    - Default template content: commented example with `[plugins]` section
    - _Requirements: 10.10, 10.11, 10.12, 10.13_

  - [x] 6.3 Write property tests for command_registry
    - `tests/test_command_registry.py`
    - **Property 4: Command Registry Lookup Consistency** -- last registered handler wins; list_all alphabetical
    - **Property 5: Prefix Completion Correctness** -- exact subset matching prefix, sorted
    - **Property 6: Pinned Command Subset** -- only registered + pinned, in pinned order, capped
    - **Validates: Requirements 4.1-4.5, 4.E1-4.E3**

  - [x] 6.4 Write unit tests for config_loader
    - `tests/test_config_loader.py`
    - **Property 20: Config File Resilience** -- never raises for any file state
    - Test valid TOML with plugins
    - Test missing file → template created
    - Test malformed TOML → warning logged, empty config
    - Test empty file → empty config
    - Test plugin-specific sections accessible via `raw`
    - **Validates: Requirements 10.10-10.13**

  - [x] 6.V Verify task group 6
    - [x] All new tests pass: `uv run pytest tests/test_command_registry.py tests/test_config_loader.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 4.1-4.5, 4.E1-4.E3, 10.10-10.13 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 6 is complete. Do NOT continue to task group 7 in this session. -->

- [x] 7. Plugin System (Loader + Registry)
  - [x] 7.1 Implement `src/agent_repl/plugin_loader.py`
    - `load_plugin(dotted_path: str) -> Plugin | None`
    - Import module via `importlib.import_module`
    - Look for `create_plugin()` callable on the module
    - Call `create_plugin()` and return result
    - On `ImportError` → log warning with path and error, return None
    - On missing `create_plugin` → log warning, return None
    - On `create_plugin()` exception → log warning, return None
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 7.2 Implement `src/agent_repl/plugin_registry.py`
    - `PluginRegistry` class
      - Internal `_plugins: list[Plugin]`, `_active_agent: AgentPlugin | None`
      - `register(plugin: Plugin, command_registry: CommandRegistry)`:
        - Call `plugin.get_commands()` and register each in CommandRegistry
        - If plugin is AgentPlugin → call `set_agent()`
        - Track in `_plugins`
      - `set_agent(agent: AgentPlugin)`:
        - If `_active_agent` is already set → raise `PluginError`
        - Set `_active_agent = agent`
      - `active_agent` property → returns `_active_agent`
      - `plugins` property → returns copy of `_plugins`
      - `get_status_hints() -> list[str]`:
        - Collect hints from all plugins' `get_status_hints()`
        - Return concatenated list
    - _Requirements: 10.4, 10.5, 10.6, 10.E1, 10.E2_

  - [x] 7.3 Write property tests for plugin system
    - `tests/test_plugin_system.py`
    - **Property 15: Plugin Command Registration** -- all commands from get_commands() are in registry after register()
    - **Property 16: Agent Singleton Invariant** -- second agent registration raises PluginError
    - **Validates: Requirements 10.1-10.6, 10.E1, 10.E2**

  - [x] 7.4 Write unit tests for plugin_loader
    - `tests/test_plugin_loader.py`
    - Test successful import and factory call
    - Test missing module → None with logged warning
    - Test module without create_plugin → None with logged warning
    - Test create_plugin raises → None with logged warning
    - **Validates: Requirements 10.1-10.3**

  - [x] 7.V Verify task group 7
    - [x] All new tests pass: `uv run pytest tests/test_plugin_system.py tests/test_plugin_loader.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 10.1-10.6, 10.E1, 10.E2 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 7 is complete. Do NOT continue to task group 8 in this session. -->

- [x] 8. Checkpoint - Core Infrastructure Complete
  - Ensure all tests pass across all modules implemented so far.
  - Verify module dependency graph matches design: types ← input_parser, file_context, session, clipboard, command_registry, config_loader, plugin_loader, plugin_registry.

<!-- SESSION BOUNDARY -->

- [x] 9. TUI Shell + Stream Handler
  - [x] 9.1 Implement `src/agent_repl/tui.py`
    - `TUIShell` class with Rich `Console` and prompt_toolkit `PromptSession`
    - `__init__(self, config: Config)`: initialize console, theme, prompt session
    - `show_banner(app_name, version, agent_name, model)`: render startup banner with name, version, agent info, `/help` hint
    - `show_markdown(text: str)`: render text as Rich Markdown with colored gutter bar
    - `show_info(text: str)`: render info message in theme info color
    - `show_error(text: str)`: render error message in theme error color
    - `show_warning(text: str)`: render warning message
    - `show_tool_result(name, result, is_error)`: render Rich Panel labeled with tool name, styled for success/error
    - `start_spinner(text="Thinking...")`: start Rich spinner/status
    - `stop_spinner()`: stop and clear spinner
    - `start_live_text()`: begin Rich Live display with gutter bar
    - `append_live_text(text: str)`: append text to live display
    - `finalize_live_text()`: stop live display, render final markdown
    - `copy_to_clipboard(text: str)`: delegate to clipboard module, show success/error message
    - `async prompt_input() -> str`: prompt_toolkit async prompt with history, toolbar, Ctrl+Y binding
    - `set_completer(completer)`: set the prompt_toolkit completer
    - `set_toolbar_provider(provider: Callable[[], list[str]])`: set callback for bottom toolbar content
    - _Requirements: 7.1-7.10, 7.E1, 7.E2_

  - [x] 9.2 Implement `src/agent_repl/stream_handler.py`
    - `StreamHandler` class
    - `__init__(self, tui: TUIShell, session: Session)`
    - `async handle_stream(events: AsyncIterator[StreamEvent]) -> ConversationTurn`:
      - Initialize accumulators: text parts, tool uses, token usage, first_content flag
      - Start spinner
      - Iterate over events:
        - `TEXT_DELTA`: dismiss spinner on first content; append to live text; accumulate text
        - `TOOL_USE_START`: dismiss spinner on first content; show tool info line
        - `TOOL_RESULT`: render tool panel; record ToolUse
        - `USAGE`: accumulate TokenUsage
        - `ERROR`: if `fatal` → stop spinner, show error, break; else show error, continue
      - Finalize: stop spinner if still running, finalize live text, build ConversationTurn
      - Add turn to session
      - Return turn
    - _Requirements: 6.1-6.9, 6.E1, 6.E2_

  - [x] 9.3 Write unit tests for TUI Shell
    - `tests/test_tui.py`
    - Test banner output contains app name, version, agent info
    - Test markdown rendering calls Rich
    - Test info/error/warning message display
    - Test tool result panel rendering (success vs error styling)
    - Test spinner start/stop lifecycle
    - Test live text append and finalize
    - Test Ctrl+Y triggers clipboard copy
    - Test toolbar provider callback invocation
    - Mock Rich Console and prompt_toolkit for isolation
    - **Validates: Requirements 7.1-7.10, 7.E1, 7.E2**

  - [x] 9.4 Write unit and property tests for stream_handler
    - `tests/test_stream_handler.py`
    - **Property 19: Stream Finalization** -- any stream (including empty) produces exactly one ConversationTurn
    - Test TEXT_DELTA accumulation
    - Test TOOL_USE_START info display
    - Test TOOL_RESULT panel rendering and ToolUse recording
    - Test USAGE token accumulation
    - Test non-fatal ERROR → continues stream
    - Test fatal ERROR → terminates stream
    - Test spinner dismissed on first content event
    - Test empty stream produces empty turn
    - Test cancelled stream produces partial turn
    - **Validates: Requirements 6.1-6.9, 6.E1, 6.E2**

  - [x] 9.V Verify task group 9
    - [x] All new tests pass: `uv run pytest tests/test_tui.py tests/test_stream_handler.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 6.1-6.9, 6.E1, 6.E2, 7.1-7.10, 7.E1, 7.E2 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 9 is complete. Do NOT continue to task group 10 in this session. -->

- [x] 10. Slash Command Completer + Built-in Commands
  - [x] 10.1 Implement `src/agent_repl/completer.py`
    - `SlashCommandCompleter(Completer)` class
    - `__init__(self, registry, pinned_names, max_pinned=6)`
    - `_dismissed: bool` flag, reset on text change
    - `get_completions(document, complete_event)`:
      - If `_dismissed` → yield nothing
      - If text is exactly `/` → yield pinned commands (via `registry.get_pinned()`)
      - If text starts with `/` and has more chars → yield `registry.complete(prefix)` alphabetically
      - Otherwise → yield nothing
    - `dismiss()` → set `_dismissed = True`
    - `reset_dismiss()` → set `_dismissed = False`
    - Integrate with prompt_toolkit key bindings for ESC dismiss
    - _Requirements: 4.6-4.9, 4.E1, 4.E2_

  - [x] 10.2 Implement `src/agent_repl/builtin_commands.py`
    - `BuiltinCommandsPlugin` class implementing Plugin protocol
    - `name = "builtin"`, `description = "Built-in REPL commands"`
    - `get_commands()` returns list of SlashCommand objects:
      - `/help`: list all registered commands with descriptions (accesses CommandContext.registry)
      - `/quit`: sets a quit flag or raises a sentinel to exit the REPL
      - `/version`: displays `config.app_name` and `config.app_version`
      - `/copy`: gets `session.last_assistant_response()`, calls `tui.copy_to_clipboard()`; shows info if None
      - `/agent`: gets `plugin_registry.active_agent`, shows name + default_model; shows info if None
      - `/stats`: gets `session.stats`, formats with `format_input()` and `format_output()`; shows "0 tokens" if no usage
    - `on_load()`, `on_unload()`, `get_status_hints()` -- minimal implementations
    - _Requirements: 5.1-5.7, 5.E1-5.E4_

  - [x] 10.3 Write tests for completer
    - `tests/test_completer.py`
    - Test bare `/` returns only pinned commands in pinned order
    - Test `/<prefix>` returns matching commands alphabetically
    - Test no matches returns empty
    - Test empty pinned list → bare `/` returns nothing
    - Test ESC dismiss → no completions
    - Test reset_dismiss after text change → completions resume
    - Test max_pinned cap
    - Incorporate Properties 5 and 6 (prefix and pinned correctness)
    - **Validates: Requirements 4.6-4.9, 4.E1, 4.E2**

  - [x] 10.4 Write unit tests for built-in commands
    - `tests/test_builtin_commands.py`
    - Test `/help` lists all registered commands
    - Test `/quit` triggers exit
    - Test `/version` displays app name and version
    - Test `/copy` copies last response; test no-response case shows info
    - Test `/copy` with clipboard error shows error
    - Test `/agent` shows agent name and model; test no-agent case
    - Test `/stats` formatting: 0 tokens, < 1000, >= 1000
    - **Validates: Requirements 5.1-5.7, 5.E1-5.E4**

  - [x] 10.V Verify task group 10
    - [x] All new tests pass: `uv run pytest tests/test_completer.py tests/test_builtin_commands.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 4.6-4.9, 4.E1, 4.E2, 5.1-5.7, 5.E1-5.E4 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 10 is complete. Do NOT continue to task group 11 in this session. -->

- [x] 11. Checkpoint - All Components Complete
  - Ensure all unit and property tests pass across all modules.
  - Verify: types, input_parser, file_context, session, clipboard, command_registry, config_loader, plugin_loader, plugin_registry, tui, stream_handler, completer, builtin_commands.

<!-- SESSION BOUNDARY -->

- [x] 12. REPL Loop + App Orchestration
  - [x] 12.1 Implement `src/agent_repl/repl.py`
    - `REPL` class
    - `__init__(self, session, tui, command_registry, plugin_registry, config)`
    - `async run()`:
      - Loop: `tui.prompt_input()` → `parse_input()` → dispatch
      - `None` result (empty input) → continue
      - `ParsedCommand` → look up in `command_registry.get(name)`
        - Found → build `CommandContext`, call handler, catch exceptions → show error + continue
        - Not found → `tui.show_error("Unknown command: /name")`
      - `ParsedFreeText` → check `plugin_registry.active_agent`
        - None → `tui.show_error("No agent configured")`
        - Present → resolve `@path` mentions via `file_context.resolve_mentions()`, build `MessageContext`, call `agent.send_message()`, pass stream to `StreamHandler.handle_stream()`
        - Catch agent exceptions → show error + continue
      - Ctrl+C handling (`KeyboardInterrupt`):
        - If agent task in flight → cancel it, continue loop
        - If not → exit loop
      - Ctrl+D handling (`EOFError`):
        - Same logic as Ctrl+C
    - _Requirements: 1.1-1.8, 1.E1-1.E3_

  - [x] 12.2 Implement `src/agent_repl/app.py`
    - `App` class
    - `__init__(self, config: Config | None = None)`:
      - `self._config = config or Config()`
      - Create `Session`, `TUIShell`, `CommandRegistry`, `PluginRegistry`
    - `async _setup()`:
      - Register `BuiltinCommandsPlugin` (always loaded first)
      - Load config from `.af/config.toml` via `config_loader.load_config()`
      - Load plugins from `Config.plugins` + `LoadedConfig.plugin_paths` via `plugin_loader`
      - For each loaded plugin: call `on_load()` (catch exceptions → log + skip), then `plugin_registry.register()`
      - If `config.agent_factory` provided → create agent, register
      - Set up `SlashCommandCompleter` with registry and pinned commands
      - `tui.set_completer(completer)`
      - Set up toolbar provider → `plugin_registry.get_status_hints`
    - `async run()`:
      - Call `_setup()`
      - Show banner via `tui.show_banner()`
      - Create and run `REPL`
    - _Requirements: 1.8, 10.4-10.6, 10.10-10.12, 7.9_

  - [x] 12.3 Complete public API exports in `__init__.py`
    - Now that `App` exists, finalize all exports
    - _Requirements: 15.1, 15.2_

  - [x] 12.4 Write unit tests for REPL
    - `tests/test_repl.py`
    - **Property 18: Graceful Error Recovery** -- command handler exception → error shown, loop continues
    - Test empty input → re-prompt (no dispatch)
    - Test slash command dispatch → correct handler called
    - Test unknown command → error message shown
    - Test free text → agent.send_message called with correct MessageContext
    - Test free text with @path mentions → file contexts resolved and included
    - Test no agent configured → error message shown
    - Test agent exception → error shown, loop continues
    - Test Ctrl+C during agent task → task cancelled, loop continues
    - Test Ctrl+C with no task → loop exits
    - Test Ctrl+D → same as Ctrl+C
    - Use mock TUI, mock agent, mock registry
    - **Validates: Requirements 1.1-1.8, 1.E1-1.E3**

  - [x] 12.5 Write unit tests for App
    - `tests/test_app.py`
    - Test initialization creates all subsystems
    - Test plugin loading from Config.plugins
    - Test plugin loading from config.toml
    - Test agent_factory creates and registers agent
    - Test agent_factory not provided → no agent (with warning)
    - Test multiple agents → PluginError
    - Test banner displayed on run
    - Test completer set up with correct pinned commands
    - **Validates: Requirements 10.4-10.6, 10.E1**

  - [x] 12.V Verify task group 12
    - [x] All new tests pass: `uv run pytest tests/test_repl.py tests/test_app.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 1.1-1.8, 1.E1-1.E3, 10.4-10.6, 10.E1, 7.9, 15.1, 15.2 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 12 is complete. Do NOT continue to task group 13 in this session. -->

- [x] 13. Default Claude Agent
  - [x] 13.1 Implement `src/agent_repl/agents/claude_agent.py`
    - `ClaudeAgentPlugin` class implementing AgentPlugin
    - `name = "Claude"`, `description = "Anthropic Claude agent via claude-agent-sdk"`
    - `default_model: str` -- detected from SDK or config
    - Authentication detection:
      - Check `ANTHROPIC_API_KEY`, `CLAUDE_CODE_USE_VERTEX`, `CLAUDE_CODE_USE_BEDROCK` env vars
      - If none set → raise `AgentError` with setup instructions listing all methods
    - `async send_message(context: MessageContext) -> AsyncIterator[StreamEvent]`:
      - Build prompt from `context.history` and `context.file_contexts`
      - Use `claude_agent_sdk.query()` or `ClaudeSDKClient` to send
      - Translate SDK `Message` objects to framework `StreamEvent` objects:
        - `AssistantMessage` with `TextBlock` → `TEXT_DELTA`
        - `AssistantMessage` with `ToolUseBlock` → `TOOL_USE_START`
        - `UserMessage` with `ToolResultBlock` → `TOOL_RESULT`
        - `ResultMessage` with usage → `USAGE`
        - `AssistantMessage` with error → `ERROR` (fatal based on error type)
      - Yield events as they arrive
    - `get_commands()`:
      - `/clear`: clear session history
      - `/compact`: ask agent to summarize history, call `session.replace_with_summary()`
    - `compact_history(session: Session) -> str`:
      - Send summarization prompt to agent
      - Collect full response text
      - Return summary string
    - `get_status_hints()`: return model info or empty list
    - `on_load()`, `on_unload()`: manage SDK client lifecycle
    - _Requirements: 11.1-11.7, 11.E1-11.E3_

  - [x] 13.2 Write unit tests for Claude agent
    - `tests/test_claude_agent.py`
    - Test authentication detection (API key, Vertex, Bedrock)
    - Test no auth → AgentError with instructions
    - Test send_message stream translation (mock SDK responses)
    - Test TextBlock → TEXT_DELTA
    - Test ToolUseBlock → TOOL_USE_START
    - Test ToolResultBlock → TOOL_RESULT
    - Test ResultMessage usage → USAGE
    - Test error → ERROR with correct fatal flag
    - Test /clear handler clears session
    - Test /compact handler generates summary and replaces history
    - Test SDK import failure → graceful degradation (log warning)
    - **Validates: Requirements 11.1-11.7, 11.E1-11.E3**

  - [x] 13.V Verify task group 13
    - [x] All new tests pass: `uv run pytest tests/test_claude_agent.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 11.1-11.7, 11.E1-11.E3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 13 is complete. Do NOT continue to task group 14 in this session. -->

- [x] 14. Agent Session Spawning
  - [x] 14.1 Implement `SessionSpawner` in `src/agent_repl/session_spawner.py`
    - `SessionSpawner` class
    - `__init__(self, agent_factory: Callable[..., AgentPlugin])`
    - `async spawn(self, config: SpawnConfig) -> None`:
      - Execute pre-hook (synchronous): `config.pre_hook()`
        - If raises → report error, do NOT start agent, do NOT run post-hook, return
      - Create new agent via `self._agent_factory()`
      - Create empty `MessageContext` with just `config.prompt`
      - Send message and consume full response stream
        - If agent fails → report error, still run post-hook
      - Execute post-hook (synchronous): `config.post_hook()`
        - If raises → report error
    - Support multiple concurrent spawns via `asyncio.create_task()`
    - Expose spawn on `App` class: `async def spawn_session(self, config: SpawnConfig) -> asyncio.Task`
    - _Requirements: 12.1-12.6, 12.E1-12.E3_

  - [x] 14.2 Write unit tests for session spawning
    - `tests/test_session_spawner.py`
    - Test successful spawn: pre-hook called → agent created → message sent → post-hook called
    - Test pre-hook failure: error reported, agent NOT created, post-hook NOT called
    - Test agent failure: error reported, post-hook still called
    - Test post-hook failure: error reported
    - Test parallel spawning: two spawns run concurrently via asyncio
    - Test spawn with no hooks: works without pre/post hooks
    - **Validates: Requirements 12.1-12.6, 12.E1-12.E3**

  - [x] 14.V Verify task group 14
    - [x] All new tests pass: `uv run pytest tests/test_session_spawner.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 12.1-12.6, 12.E1-12.E3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 14 is complete. Do NOT continue to task group 15 in this session. -->

- [x] 15. CLI Slash Command Invocation
  - [x] 15.1 Implement CLI dispatch in `src/agent_repl/app.py`
    - `App.run_cli_command(command_name: str, args: list[str]) -> int`:
      - Call `_setup()` to initialize all subsystems
      - Map `command_name` to slash command name (strip leading `--` if present)
      - Look up command in `CommandRegistry`
      - Verify command has `cli_exposed=True`; if not → error message, return 1
      - Build `CommandContext` with `args=' '.join(args)`, `argv=args`
      - Call handler; catch exceptions → display error, return 1
      - Return 0 on success
    - Add CLI entry point detection in App or a `cli.py` module:
      - Parse `sys.argv` for `--commandName` patterns
      - If found → `run_cli_command()` instead of `run()`
      - If unknown `--flag` → list available CLI commands, exit 1
      - If multiple `--flags` → error or execute first only
    - Mark built-in commands for CLI exposure where appropriate:
      - `/compact`: `cli_exposed=True`
      - `/clear`: `cli_exposed=True`
      - `/version`: `cli_exposed=True`
      - `/help`, `/quit`, `/copy`, `/agent`, `/stats`: `cli_exposed=False`
    - _Requirements: 13.1-13.5, 13.E1-13.E3_

  - [x] 15.2 Write unit tests for CLI invocation
    - `tests/test_cli.py`
    - **Property 17: CLI Command Filtering** -- only cli_exposed commands available
    - Test `--compact` maps to `/compact` command
    - Test parameters passed as list
    - Test non-CLI command (cli_exposed=False) → error, exit 1
    - Test unknown flag → error with available commands list, exit 1
    - Test handler exception → error, exit non-zero
    - Test successful command → exit 0
    - Test multiple flags → error or first-only
    - **Validates: Requirements 13.1-13.5, 13.E1-13.E3**

  - [x] 15.V Verify task group 15
    - [x] All new tests pass: `uv run pytest tests/test_cli.py -q`
    - [x] All existing tests still pass: `uv run pytest tests/ -q --ignore=tests/integration`
    - [x] No linter warnings: `uv run ruff check src/ tests/`
    - [x] Requirements 13.1-13.5, 13.E1-13.E3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 15 is complete. Do NOT continue to task group 16 in this session. -->

- [x] 16. Checkpoint - Full Library Complete
  - [x] All unit and property tests pass (384 unit, 19 property-based).
  - [x] Full linter check passes.
  - [x] All 20 correctness properties have corresponding tests.

<!-- SESSION BOUNDARY -->

- [ ] 17. Canonical Example + Integration Tests
  - [ ] 17.1 Create echo agent example
    - `examples/echo_agent.py`: `EchoAgentPlugin` class
      - Implements `AgentPlugin` protocol
      - `send_message()` echoes back the user's message as TEXT_DELTA events
      - `compact_history()` returns a simple "Session summary" string
      - `default_model = "echo-1.0"`
      - No external dependencies or credentials required
    - _Requirements: 14.3, 14.10, 14.E1_

  - [ ] 17.2 Create demo plugin with custom commands
    - `examples/demo_plugin.py`: `DemoPlugin` class
      - Registers custom slash commands (e.g. `/greet`, `/time`)
      - Demonstrates `get_commands()`, `on_load()`, `get_status_hints()`
    - _Requirements: 14.5_

  - [ ] 17.3 Create main demo application
    - `examples/demo.py`: entry point
      - Creates `Config` with `Theme`, `agent_factory` (echo agent by default, Claude with `--claude` flag)
      - Registers demo plugin
      - Demonstrates `@path` file context usage (documented in comments)
      - Demonstrates CLI slash command invocation (e.g. `python demo.py --version`)
    - `examples/__init__.py`: package marker
    - _Requirements: 14.1, 14.2, 14.4, 14.6, 14.8_

  - [ ] 17.4 Create session spawning example
    - Add to `examples/demo.py` or separate `examples/spawn_demo.py`:
      - Custom slash command `/spawn` that triggers a spawned session
      - Pre-hook: print "Starting isolated task..."
      - Post-hook: print "Isolated task complete."
      - Demonstrates `SpawnConfig` and `App.spawn_session()`
    - _Requirements: 14.7_

  - [ ] 17.5 Write example documentation
    - `examples/README.md`:
      - Overview of example application
      - How to run the echo demo: `uv run python examples/demo.py`
      - How to run with Claude: `uv run python examples/demo.py --claude`
      - How to use CLI invocation: `uv run python examples/demo.py --version`
      - How to use `@path` mentions
      - How to create custom plugins
      - How to use session spawning
    - Add inline comments and docstrings throughout example files
    - _Requirements: 14.9_

  - [ ] 17.6 Write integration tests
    - `tests/integration/test_integration.py`:
      - Test full REPL loop with echo agent: start → send message → receive echo → /quit
      - Test built-in commands in context: /help, /version, /stats, /copy, /agent
      - Test unknown command error recovery
      - Test @path file context injection (create temp files)
      - Test CLI command invocation flow
      - Test plugin loading from dotted path
      - Test error recovery: bad plugin, agent failure, command exception
    - `tests/integration/test_example_app.py`:
      - Test example app imports without error
      - Test echo agent responds
      - Test demo plugin commands are registered
    - **Validates: all requirements end-to-end**

  - [ ] 17.7 Update project README.md
    - Project overview and features
    - Installation instructions (`uv add agent_repl`)
    - Quick start with code example
    - Configuration (`.af/config.toml`)
    - Plugin development guide (brief)
    - Extension points table
    - Link to `examples/README.md` for detailed examples
    - _Requirements: 14.9_

  - [ ] 17.V Verify task group 17
    - [ ] All new tests pass: `uv run pytest tests/integration/ -q`
    - [ ] All existing tests still pass: `uv run pytest tests/ -q`
    - [ ] No linter warnings: `uv run ruff check src/ tests/ examples/`
    - [ ] Example runs: `uv run python examples/demo.py --version`
    - [ ] Requirements 14.1-14.10, 14.E1 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 17 is complete. All implementation is done. -->

- [ ] 18. Final Checkpoint - Release Ready
  - [ ] All tests pass: `uv run pytest tests/ -q`
  - [ ] Linter clean: `uv run ruff check src/ tests/ examples/`
  - [ ] Build succeeds: `make build`
  - [ ] Package succeeds: `make package`
  - [ ] All 20 correctness properties have passing tests
  - [ ] All 16 requirements have traced implementations and tests
  - [ ] README.md and examples/README.md are complete
  - [ ] Clean git status on `develop` branch

### Checkbox States

| Syntax   | Meaning                |
|----------|------------------------|
| `- [ ]`  | Not started (required) |
| `- [ ]*` | Not started (optional) |
| `- [x]`  | Completed              |
| `- [-]`  | In progress            |
| `- [~]`  | Queued                 |

## Traceability

| Requirement | Implemented By Task | Verified By Test |
|-------------|---------------------|------------------|
| 1.1 (REPL continuous loop) | 12.1 | test_repl.py |
| 1.2 (empty input ignored) | 12.1 | test_repl.py |
| 1.3 (/quit exits) | 10.2, 12.1 | test_builtin_commands.py, test_repl.py |
| 1.4 (Ctrl+C/D no task → exit) | 12.1 | test_repl.py |
| 1.5 (Ctrl+C/D with task → cancel) | 12.1 | test_repl.py |
| 1.6 (slash command classification) | 3.1, 12.1 | test_input_parser.py, test_repl.py |
| 1.7 (free text to agent) | 3.1, 12.1 | test_input_parser.py, test_repl.py |
| 1.8 (asyncio) | 12.1, 12.2 | test_repl.py, test_app.py |
| 1.E1 (no agent → error) | 12.1 | test_repl.py |
| 1.E2 (agent exception → continue) | 12.1 | test_repl.py (Property 18) |
| 1.E3 (unknown command → error) | 12.1 | test_repl.py |
| 2.1 (slash detection) | 3.1 | test_input_parser.py (Property 1) |
| 2.2 (command name + args split) | 3.1 | test_input_parser.py (Property 2) |
| 2.3 (@path extraction) | 3.1 | test_input_parser.py (Property 3) |
| 2.4 (@ literal handling) | 3.1 | test_input_parser.py |
| 2.E1 (bare / → free text) | 3.1 | test_input_parser.py |
| 2.E2 (/+whitespace → free text) | 3.1 | test_input_parser.py |
| 2.E3 (no args → empty string) | 3.1 | test_input_parser.py |
| 3.1 (file UTF-8 read) | 3.2 | test_file_context.py |
| 3.2 (directory read sorted) | 3.2 | test_file_context.py (Property 13) |
| 3.3 (size limit) | 3.2 | test_file_context.py (Property 12) |
| 3.4 (text files only) | 3.2 | test_file_context.py |
| 3.E1 (missing path → error) | 3.2 | test_file_context.py |
| 3.E2 (binary → error) | 3.2 | test_file_context.py |
| 3.E3 (size exceeded → error) | 3.2 | test_file_context.py |
| 3.E4 (empty dir → info) | 3.2 | test_file_context.py |
| 3.E5 (.gitignore filtering) | 3.2 | test_file_context.py |
| 4.1 (command registration) | 6.1 | test_command_registry.py (Property 4) |
| 4.2 (exact lookup) | 6.1 | test_command_registry.py |
| 4.3 (sorted listing) | 6.1 | test_command_registry.py |
| 4.4 (prefix completion) | 6.1 | test_command_registry.py (Property 5) |
| 4.5 (pinned commands) | 6.1 | test_command_registry.py (Property 6) |
| 4.6 (bare / → pinned) | 10.1 | test_completer.py |
| 4.7 (prefix → alphabetical) | 10.1 | test_completer.py |
| 4.8 (ESC dismiss) | 10.1 | test_completer.py |
| 4.9 (prompt_toolkit integration) | 10.1 | test_completer.py |
| 4.E1 (no match → empty) | 6.1, 10.1 | test_command_registry.py, test_completer.py |
| 4.E2 (empty pinned → empty) | 6.1, 10.1 | test_command_registry.py, test_completer.py |
| 4.E3 (name override) | 6.1 | test_command_registry.py |
| 5.1 (/help) | 10.2 | test_builtin_commands.py |
| 5.2 (/quit) | 10.2 | test_builtin_commands.py |
| 5.3 (/version) | 10.2 | test_builtin_commands.py |
| 5.4 (/copy) | 10.2 | test_builtin_commands.py |
| 5.5 (/agent) | 10.2 | test_builtin_commands.py |
| 5.6 (/stats format) | 4.1, 10.2 | test_session.py (Property 9), test_builtin_commands.py |
| 5.7 (built-ins are plugins) | 10.2 | test_builtin_commands.py |
| 5.E1 (/copy no response) | 10.2 | test_builtin_commands.py |
| 5.E2 (/copy clipboard error) | 10.2 | test_builtin_commands.py |
| 5.E3 (/agent no agent) | 10.2 | test_builtin_commands.py |
| 5.E4 (/stats zero) | 10.2 | test_builtin_commands.py |
| 6.1 (real-time processing) | 9.2 | test_stream_handler.py |
| 6.2 (TEXT_DELTA → live) | 9.2 | test_stream_handler.py |
| 6.3 (TOOL_USE_START → info) | 9.2 | test_stream_handler.py |
| 6.4 (TOOL_RESULT → panel) | 9.2 | test_stream_handler.py |
| 6.5 (USAGE → accumulate) | 9.2 | test_stream_handler.py |
| 6.6 (non-fatal error → continue) | 9.2 | test_stream_handler.py |
| 6.7 (fatal error → terminate) | 9.2 | test_stream_handler.py |
| 6.8 (spinner dismiss) | 9.2 | test_stream_handler.py |
| 6.9 (stream finalize) | 9.2 | test_stream_handler.py (Property 19) |
| 6.E1 (empty stream → empty turn) | 9.2 | test_stream_handler.py |
| 6.E2 (cancelled → partial turn) | 9.2 | test_stream_handler.py |
| 7.1 (Rich + prompt_toolkit) | 9.1 | test_tui.py |
| 7.2 (live view + gutter) | 9.1 | test_tui.py |
| 7.3 (markdown + gutter) | 9.1 | test_tui.py |
| 7.4 (spinner) | 9.1 | test_tui.py |
| 7.5 (tool panels) | 9.1 | test_tui.py |
| 7.6 (Ctrl+Y clipboard) | 9.1 | test_tui.py |
| 7.7 (prompt with rules) | 9.1 | test_tui.py |
| 7.8 (toolbar via callback) | 9.1 | test_tui.py |
| 7.9 (startup banner) | 9.1, 12.2 | test_tui.py, test_app.py |
| 7.10 (theming) | 9.1 | test_tui.py |
| 7.E1 (Ctrl+Y no response) | 9.1 | test_tui.py |
| 7.E2 (theme degradation) | 9.1 | test_tui.py |
| 8.1 (turn list) | 4.1 | test_session.py (Property 7) |
| 8.2 (token accumulation) | 4.1 | test_session.py (Property 8) |
| 8.3 (add_turn) | 4.1 | test_session.py |
| 8.4 (get_history copy) | 4.1 | test_session.py |
| 8.5 (clear) | 4.1 | test_session.py |
| 8.6 (last_assistant) | 4.1 | test_session.py (Property 11) |
| 8.7 (replace_with_summary) | 4.1 | test_session.py (Property 10) |
| 8.E1 (replace empty session) | 4.1 | test_session.py |
| 8.E2 (last_assistant empty) | 4.1 | test_session.py |
| 9.1 (macOS pbcopy) | 4.2 | test_clipboard.py |
| 9.2 (Linux Wayland wl-copy) | 4.2 | test_clipboard.py |
| 9.3 (Linux X11 xclip) | 4.2 | test_clipboard.py |
| 9.E1 (missing utility) | 4.2 | test_clipboard.py |
| 9.E2 (unsupported platform) | 4.2 | test_clipboard.py |
| 9.E3 (command failure) | 4.2 | test_clipboard.py |
| 10.1 (import + factory) | 7.1 | test_plugin_loader.py |
| 10.2 (missing factory → skip) | 7.1 | test_plugin_loader.py |
| 10.3 (import error → skip) | 7.1 | test_plugin_loader.py |
| 10.4 (registry stores + registers) | 7.2 | test_plugin_system.py (Property 15) |
| 10.5 (agent_factory sole) | 7.2, 12.2 | test_plugin_system.py, test_app.py |
| 10.6 (multi-agent error) | 7.2 | test_plugin_system.py (Property 16) |
| 10.7 (Plugin protocol) | 1.4 | test_types.py |
| 10.8 (AgentPlugin protocol) | 1.4 | test_types.py |
| 10.9 (handler exception → continue) | 12.1 | test_repl.py (Property 18) |
| 10.10 (config.toml loading) | 6.2 | test_config_loader.py |
| 10.11 (missing → template) | 6.2 | test_config_loader.py |
| 10.12 (malformed → fallback) | 6.2 | test_config_loader.py (Property 20) |
| 10.13 (plugin-specific config) | 6.2 | test_config_loader.py |
| 10.E1 (no plugins → warning) | 12.2 | test_app.py |
| 10.E2 (on_load error → skip) | 12.2 | test_app.py |
| 11.1 (claude-agent-sdk) | 13.1 | test_claude_agent.py |
| 11.2 (build prompt + stream) | 13.1 | test_claude_agent.py |
| 11.3 (/clear) | 13.1 | test_claude_agent.py |
| 11.4 (/compact) | 13.1 | test_claude_agent.py |
| 11.5 (auth env vars) | 13.1 | test_claude_agent.py |
| 11.6 (no auth → error) | 13.1 | test_claude_agent.py |
| 11.7 (default_model) | 13.1 | test_claude_agent.py |
| 11.E1 (SDK not installed) | 13.1 | test_claude_agent.py |
| 11.E2 (connection lost) | 13.1 | test_claude_agent.py |
| 11.E3 (invalid auth) | 13.1 | test_claude_agent.py |
| 12.1 (spawn empty context) | 14.1 | test_session_spawner.py |
| 12.2 (parallel spawns) | 14.1 | test_session_spawner.py |
| 12.3 (pre-hook) | 14.1 | test_session_spawner.py |
| 12.4 (post-hook notification) | 14.1 | test_session_spawner.py |
| 12.5 (programmatic + slash) | 14.1 | test_session_spawner.py |
| 12.6 (primary session alive) | 14.1 | test_session_spawner.py |
| 12.E1 (pre-hook fail → abort) | 14.1 | test_session_spawner.py |
| 12.E2 (post-hook fail → report) | 14.1 | test_session_spawner.py |
| 12.E3 (agent fail → post-hook) | 14.1 | test_session_spawner.py |
| 13.1 (CLI invocation) | 15.1 | test_cli.py |
| 13.2 (auto flag mapping) | 15.1 | test_cli.py |
| 13.3 (params as list) | 15.1 | test_cli.py |
| 13.4 (annotated subset) | 15.1 | test_cli.py (Property 17) |
| 13.5 (exit after command) | 15.1 | test_cli.py |
| 13.E1 (unknown flag) | 15.1 | test_cli.py |
| 13.E2 (handler exception) | 15.1 | test_cli.py |
| 13.E3 (multiple flags) | 15.1 | test_cli.py |
| 14.1-14.10 (example) | 17.1-17.5 | test_example_app.py |
| 14.E1 (echo no creds) | 17.1 | test_example_app.py |
| 15.1 (public exports) | 1.7, 12.3 | test_types.py |
| 15.2 (importable) | 1.7, 12.3 | test_types.py |
| 15.3 (API stability) | -- | -- (policy) |
| 16.1 (asyncio) | 12.1 | test_repl.py |
| 16.2 (streaming-first) | 9.2 | test_stream_handler.py |
| 16.3 (graceful degradation) | all error handlers | all error test cases |
| 16.4 (platform support) | 4.2 | test_clipboard.py |
| 16.5 (Python 3.12+) | 1.2 | pyproject.toml |
| 16.6 (single-threaded) | 12.1 | test_repl.py |
| 16.7 (Makefile) | 1.3 | manual verification |
| 16.8 (uv) | 1.2 | pyproject.toml |
| 16.9 (dependencies) | 1.2 | pyproject.toml |

## Notes

- Each task group maps to one coding session per `.af/steering/coding.md`.
- Property-based tests use Hypothesis; mark with `@pytest.mark.property`.
- Mock `claude_agent_sdk` in tests to avoid requiring API credentials.
- Mock `subprocess.run` in clipboard tests to avoid platform dependency.
- Mock Rich Console output capture in TUI tests.
- Use `tmp_path` fixture for file_context tests.
- The develop branch does not exist yet on the `restart` branch; create it
  before starting task group 1.
