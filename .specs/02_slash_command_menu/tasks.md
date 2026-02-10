# Implementation Plan: Slash Command Menu

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from develop -> implement -> test -> merge to develop -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

Implementation proceeds in three task groups:

1. **Data model extensions** — Add `pinned` field to `SlashCommand`, add
   `pinned_commands` to `Config`, extend `CommandRegistry` with pinned query.
2. **Custom completer** — Implement `SlashCommandCompleter` with pinned/filter
   logic and property tests.
3. **TUI and App integration** — Wire the completer into `TUIShell` and `App`,
   replacing `WordCompleter`. Enable `complete_while_typing`.

This order ensures that each layer is testable independently before
integration.

## Test Commands

- Unit tests: `uv run pytest -q tests/`
- Property tests: `uv run pytest -q tests/test_completer.py`
- All tests: `uv run pytest tests/`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [x] 1. Data Model Extensions
  - [x] 1.1 Add `pinned` field to `SlashCommand` dataclass
    - Add `pinned: bool = False` to `SlashCommand` in `src/agent_repl/types.py`
    - Ensure default value preserves backward compatibility
    - _Requirements: 2.5, 5.3_

  - [x] 1.2 Add `pinned_commands` field to `Config` dataclass
    - Add `pinned_commands: list[str] | None = None` to `Config` in `src/agent_repl/types.py`
    - Default `None` means "use built-in defaults"
    - _Requirements: 2.2, 5.1_

  - [x] 1.3 Mark built-in commands as pinned
    - Set `pinned=True` on `help` and `quit` commands in `src/agent_repl/builtin_commands.py`
    - _Requirements: 2.3_

  - [x] 1.4 Add `pinned_commands()` method to `CommandRegistry`
    - Add method `pinned_commands(self, pinned_names: list[str]) -> list[SlashCommand]`
    - Returns commands matching `pinned_names` in order, then appends any
      commands with `pinned=True` not already included, deduplicates
    - Skip names that are not registered (no error)
    - _Requirements: 2.6_

  - [x] 1.5 Add `DEFAULT_PINNED_COMMANDS` and `MAX_PINNED_DISPLAY` constants
    - Add to `src/agent_repl/constants.py`:
      - `DEFAULT_PINNED_COMMANDS = ["help", "quit"]`
      - `MAX_PINNED_DISPLAY = 6`
    - _Requirements: 2.3, 2.4, 5.1_

  - [x] 1.6 Write unit tests for data model extensions
    - Test `SlashCommand` default `pinned=False`
    - Test `Config` default `pinned_commands=None`
    - Test `CommandRegistry.pinned_commands()` ordering, dedup, missing names
    - **Property 5: Pinned Merge and Deduplication**
    - **Property 8: Backward Compatibility Default**
    - **Validates: Requirements 2.2, 2.3, 2.5, 2.6, 5.1, 5.3**

  - [x] 1.V Verify task group 1
    - [x] All new tests pass: `uv run pytest -q tests/test_types.py tests/test_command_registry.py`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [x] 2. Checkpoint - Data Model Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 3. Custom SlashCommandCompleter
  - [x] 3.1 Create `src/agent_repl/completer.py`
    - Implement `SlashCommandCompleter(Completer)` with:
      - `__init__(self, commands, pinned_names, max_pinned_display=6)`
      - `update_commands(self, commands, pinned_names)` for post-init updates
      - `get_completions(self, document, complete_event)` yielding `Completion` objects
    - Logic:
      - If input does not start with `/` -> yield nothing
      - If input is exactly `/` -> yield pinned commands (up to max)
      - If input is `/<prefix>` -> yield all commands whose name starts with prefix
    - Each `Completion` has `display="/{name}"` and `display_meta=description`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.4, 3.1, 3.2, 3.3_

  - [x] 3.2 Write unit tests for `SlashCommandCompleter`
    - Test: input `/` yields only pinned commands
    - Test: input `/he` yields commands starting with `he`
    - Test: input `/nonexistent` yields empty
    - Test: input `hello` yields nothing
    - Test: input `hello /` yields nothing (not at start)
    - Test: empty input yields nothing
    - Test: pinned cap at 6
    - Test: `display` and `display_meta` format
    - **Property 1: Pinned-Only Initial Display**
    - **Property 2: Prefix Filter Completeness**
    - **Property 3: Empty Prefix Reversion**
    - **Property 4: Non-Slash Inactivity**
    - **Property 6: Display Format Correctness**
    - **Property 7: Pinned Cap Enforcement**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.4, 3.1, 3.2, 3.3, 3.4**

  - [x] 3.V Verify task group 3
    - [x] All new tests pass: `uv run pytest -q tests/test_completer.py`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.4, 3.1, 3.2, 3.3, 3.4 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [x] 4. Checkpoint - Completer Module Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 5. TUI and App Integration
  - [x] 5.1 Update `TUIShell` to use `SlashCommandCompleter`
    - Replace `WordCompleter([], sentence=True)` with `SlashCommandCompleter`
    - Add `complete_while_typing=True` to `PromptSession`
    - Add `set_completer(commands, pinned_names)` method
    - Remove `set_completions()` method (replaced by `set_completer`)
    - _Requirements: 1.1, 1.3, 4.1, 4.2, 4.3, 5.2_

  - [x] 5.2 Update `App._run_async` to wire the completer
    - After registering all commands, resolve pinned names:
      - Use `Config.pinned_commands` if provided, else `DEFAULT_PINNED_COMMANDS`
    - Pass commands and pinned names to `tui.set_completer()`
    - Replaced old `tui.set_completions(cmd_names)` call
    - _Requirements: 2.2, 5.1_

  - [x] 5.3 Export `SlashCommandCompleter` from `__init__.py`
    - Not added to `__all__` — internal implementation detail, not consumer-facing
    - _Requirements: 5.2_

  - [x] 5.4 Update existing tests for TUI and App
    - Updated `test_tui.py`: replaced `set_completions` tests with `set_completer` tests
    - Updated `test_app.py`: updated `test_plugin_commands_registered` assertion
    - No regressions in existing test suite
    - **Validates: Requirements 4.1, 4.2, 4.3, 5.2**

  - [x] 5.V Verify task group 5
    - [x] All new tests pass: `uv run pytest -q tests/test_tui.py tests/test_app.py`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 1.1, 1.3, 2.2, 4.1, 4.2, 4.3, 5.1, 5.2 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 5 is complete. Do NOT continue to task group 6 in this session. -->

- [x] 6. Final Verification
  - [x] 6.1 Manual smoke test
    - Programmatic end-to-end integration test verified:
    - `/` shows pinned commands only (`/help`, `/quit`)
    - `/he` filters to `/help`
    - `/v` filters to `/version` (non-pinned, type-ahead only)
    - Non-slash input yields no completions
    - Custom `Config.pinned_commands` respected with declarative merge
    - Display format correct (name + description)
    - Note: interactive Escape/selection behavior is prompt-toolkit built-in
  - [x] 6.2 Full test suite green
    - `uv run pytest tests/` — 301 passed
    - `uv run ruff check` — clean on all spec-02 files (pre-existing issues in claude_agent.py unrelated)

<!-- SESSION BOUNDARY -->

- [ ] 7. ESC Dismiss Fix
  - [ ] 7.1 Add suppression mechanism to `SlashCommandCompleter`
    - Add `_suppressed: bool = False` and `_suppressed_text: str = ""` fields
    - Add `suppress()` method that sets `_suppressed = True` and stores current text
    - In `get_completions()`, check `_suppressed`: if text unchanged yield nothing,
      if text changed clear the flag and proceed normally
    - _Requirements: 4.1, 4.2_

  - [ ] 7.2 Add ESC key binding in `TUIShell._create_key_bindings()`
    - Import `has_completions` filter from `prompt_toolkit.filters`
    - Bind `"escape"` with `filter=has_completions` to:
      1. Set `event.current_buffer.complete_state = None`
      2. Call `self._completer.suppress()`
    - _Requirements: 4.1_

  - [ ] 7.3 Write tests for ESC dismiss behavior
    - Test: `suppress()` causes `get_completions()` to yield nothing
    - Test: after suppression, changing text re-enables completions
    - Test: suppression only applies while text is unchanged
    - Test: ESC key binding is registered with `has_completions` filter
    - **Property 9: ESC Suppression**
    - **Validates: Requirements 4.1, 4.2**

  - [ ] 7.V Verify task group 7
    - [ ] All new tests pass: `uv run pytest -q tests/test_completer.py tests/test_tui.py`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 4.1, 4.2 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 7 is complete. Do NOT continue to task group 8 in this session. -->

- [ ] 8. Checkpoint - ESC Dismiss Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

### Checkbox States

| Syntax   | Meaning                |
|----------|------------------------|
| `- [ ]`  | Not started (required) |
| `- [ ]*` | Not started (optional) |
| `- [x]`  | Completed              |
| `- [-]`  | In progress            |
| `- [~]`  | Queued                 |

Tasks are **required by default**. Mark optional tasks with `*` after checkbox: `- [ ]* Optional task`

### Test Task Annotations

- Unit/integration tests: `**Validates: Requirements X.Y**`
- Property-based tests: `**Property N: [Name]**` (references design doc properties)

## Traceability

| Requirement | Implemented By Task | Verified By Test |
|-------------|---------------------|------------------|
| 1.1 Menu activation on `/` | 3.1, 5.1 | 3.2 |
| 1.2 Name + description display | 3.1 | 3.2 (Property 6) |
| 1.3 Immediate activation | 3.1, 5.1 | 3.2 |
| 1.4 No activation mid-line | 3.1 | 3.2 (Property 4) |
| 2.1 Pinned-only initial display | 3.1 | 3.2 (Property 1) |
| 2.2 Configurable pinned list | 1.2, 5.2 | 1.6 |
| 2.3 Default pinned: help, quit | 1.3, 1.5 | 1.6 (Property 8) |
| 2.4 Max 6 pinned entries | 1.5, 3.1 | 3.2 (Property 7) |
| 2.5 `pinned` field on SlashCommand | 1.1 | 1.6 |
| 2.6 Merge and dedup pinned | 1.4 | 1.6 (Property 5) |
| 3.1 Prefix filtering | 3.1 | 3.2 (Property 2) |
| 3.2 Real-time filter update | 3.1 | 3.2 |
| 3.3 Empty results for no match | 3.1 | 3.2 |
| 3.4 Revert to pinned on backspace | 3.1 | 3.2 (Property 3) |
| 4.1 Escape dismisses menu | 7.1, 7.2 | 7.3 (Property 9) |
| 4.2 No re-display until input change | 7.1 | 7.3 (Property 9) |
| 4.3 Selection inserts command | 5.1 | 5.4 |
| 5.1 Default pinned when not configured | 1.2, 1.5 | 1.6 (Property 8) |
| 5.2 Preserve non-slash completion | 5.1 | 5.4 |
| 5.3 Backward compat for SlashCommand | 1.1 | 1.6 |

## Notes

- **Escape handling**: prompt-toolkit does NOT natively bind ESC to dismiss
  completions (Emacs mode uses Ctrl+G, Vi mode uses Ctrl+E). A custom ESC key
  binding is required (task group 7). Additionally, `complete_while_typing`
  re-triggers completions immediately after cancellation, so the completer
  needs a suppression flag to prevent this (see design doc "ESC Dismiss
  Mechanism").
- **Tab behavior**: With the new completer, Tab will accept the selected
  completion (prompt-toolkit default). This replaces the old `WordCompleter`
  tab-completion behavior.
- **Plugin commands**: Plugins can declare `pinned=True` on their commands.
  They will appear in the initial dropdown if the total pinned count is <= 6.
