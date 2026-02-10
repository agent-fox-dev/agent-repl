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

- [ ] 1. Data Model Extensions
  - [ ] 1.1 Add `pinned` field to `SlashCommand` dataclass
    - Add `pinned: bool = False` to `SlashCommand` in `src/agent_repl/types.py`
    - Ensure default value preserves backward compatibility
    - _Requirements: 2.5, 5.3_

  - [ ] 1.2 Add `pinned_commands` field to `Config` dataclass
    - Add `pinned_commands: list[str] | None = None` to `Config` in `src/agent_repl/types.py`
    - Default `None` means "use built-in defaults"
    - _Requirements: 2.2, 5.1_

  - [ ] 1.3 Mark built-in commands as pinned
    - Set `pinned=True` on `help` and `quit` commands in `src/agent_repl/builtin_commands.py`
    - _Requirements: 2.3_

  - [ ] 1.4 Add `pinned_commands()` method to `CommandRegistry`
    - Add method `pinned_commands(self, pinned_names: list[str]) -> list[SlashCommand]`
    - Returns commands matching `pinned_names` in order, then appends any
      commands with `pinned=True` not already included, deduplicates
    - Skip names that are not registered (no error)
    - _Requirements: 2.6_

  - [ ] 1.5 Add `DEFAULT_PINNED_COMMANDS` and `MAX_PINNED_DISPLAY` constants
    - Add to `src/agent_repl/constants.py`:
      - `DEFAULT_PINNED_COMMANDS = ["help", "quit"]`
      - `MAX_PINNED_DISPLAY = 6`
    - _Requirements: 2.3, 2.4, 5.1_

  - [ ] 1.6 Write unit tests for data model extensions
    - Test `SlashCommand` default `pinned=False`
    - Test `Config` default `pinned_commands=None`
    - Test `CommandRegistry.pinned_commands()` ordering, dedup, missing names
    - **Property 5: Pinned Merge and Deduplication**
    - **Property 8: Backward Compatibility Default**
    - **Validates: Requirements 2.2, 2.3, 2.5, 2.6, 5.1, 5.3**

  - [ ] 1.V Verify task group 1
    - [ ] All new tests pass: `uv run pytest -q tests/test_types.py tests/test_command_registry.py`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [ ] 2. Checkpoint - Data Model Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 3. Custom SlashCommandCompleter
  - [ ] 3.1 Create `src/agent_repl/completer.py`
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

  - [ ] 3.2 Write unit tests for `SlashCommandCompleter`
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

  - [ ] 3.V Verify task group 3
    - [ ] All new tests pass: `uv run pytest -q tests/test_completer.py`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.4, 3.1, 3.2, 3.3, 3.4 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [ ] 4. Checkpoint - Completer Module Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 5. TUI and App Integration
  - [ ] 5.1 Update `TUIShell` to use `SlashCommandCompleter`
    - Replace `WordCompleter([], sentence=True)` with `SlashCommandCompleter`
    - Add `complete_while_typing=True` to `PromptSession`
    - Add `set_completer(completer)` method or accept completer in constructor
    - Remove `set_completions()` method (replaced by completer) or keep for
      backward compat and delegate to completer's `update_commands()`
    - _Requirements: 1.1, 1.3, 4.1, 4.2, 4.3, 5.2_

  - [ ] 5.2 Update `App._run_async` to wire the completer
    - After registering all commands, resolve pinned names:
      - Use `Config.pinned_commands` if provided, else `DEFAULT_PINNED_COMMANDS`
    - Create `SlashCommandCompleter` with resolved command list and pinned names
    - Pass completer to TUIShell
    - Remove old `tui.set_completions(cmd_names)` call (or adapt)
    - _Requirements: 2.2, 5.1_

  - [ ] 5.3 Export `SlashCommandCompleter` from `__init__.py`
    - Add to `__all__` if appropriate for consumers
    - _Requirements: 5.2_

  - [ ] 5.4 Update existing tests for TUI and App
    - Update `test_tui.py` tests that reference `WordCompleter` or
      `set_completions`
    - Update `test_app.py` if it verifies completer setup
    - Ensure no regressions in existing test suite
    - **Validates: Requirements 4.1, 4.2, 4.3, 5.2**

  - [ ] 5.V Verify task group 5
    - [ ] All new tests pass: `uv run pytest -q tests/test_tui.py tests/test_app.py`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 1.1, 1.3, 2.2, 4.1, 4.2, 4.3, 5.1, 5.2 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 5 is complete. Do NOT continue to task group 6 in this session. -->

- [ ] 6. Final Verification
  - [ ] 6.1 Manual smoke test
    - Run `uv run python examples/demo.py --echo`
    - Type `/` and verify pinned commands appear in dropdown
    - Type `/he` and verify filtering works
    - Press Escape and verify menu closes
    - Select a command and verify it inserts correctly
  - [ ] 6.2 Full test suite green
    - `uv run pytest tests/`
    - `uv run ruff check src/ tests/`

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
| 4.1 Escape dismisses menu | 5.1 | 5.4 |
| 4.2 No re-display until input change | 5.1 | 5.4 |
| 4.3 Selection inserts command | 5.1 | 5.4 |
| 5.1 Default pinned when not configured | 1.2, 1.5 | 1.6 (Property 8) |
| 5.2 Preserve non-slash completion | 5.1 | 5.4 |
| 5.3 Backward compat for SlashCommand | 1.1 | 1.6 |

## Notes

- **Escape handling**: prompt-toolkit natively dismisses the completion menu on
  Escape. No custom key binding is needed. The completer just needs to work
  correctly with `complete_while_typing=True`.
- **Tab behavior**: With the new completer, Tab will accept the selected
  completion (prompt-toolkit default). This replaces the old `WordCompleter`
  tab-completion behavior.
- **Plugin commands**: Plugins can declare `pinned=True` on their commands.
  They will appear in the initial dropdown if the total pinned count is <= 6.
