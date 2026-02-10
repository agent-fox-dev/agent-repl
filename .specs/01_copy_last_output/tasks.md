# Implementation Plan: Copy Last Agent Output

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from develop -> implement -> test -> merge to develop -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

The implementation is ordered so foundational modules (clipboard utility,
session accessor) are built first, followed by the slash command, then the
keyboard shortcut. Tests accompany each group.

## Test Commands

- Unit tests: `uv run pytest -q tests/`
- Property tests: `uv run pytest -q tests/ -k property`
- All tests: `uv run pytest -q tests/`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [ ] 1. Clipboard utility and session accessor
  - [ ] 1.1 Add `ClipboardError` to `exceptions.py`
    - Add a new exception class `ClipboardError(Exception)` with a docstring
    - _Requirements: 1.4, 4.4_

  - [ ] 1.2 Create `src/agent_repl/clipboard.py`
    - Implement `copy_to_clipboard(text: str) -> None`
    - Detect platform via `sys.platform`
    - On `darwin`: invoke `pbcopy` via `subprocess.run`, pipe text to stdin
    - On `linux`: check `$XDG_SESSION_TYPE` or `$WAYLAND_DISPLAY` for Wayland
      (`wl-copy`), else fall back to `xclip -selection clipboard`
    - Use `shutil.which()` to verify the utility exists before calling it
    - Raise `ClipboardError` with a descriptive message if utility is missing
      or subprocess returns non-zero
    - Encode text as UTF-8 for stdin
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4_

  - [ ] 1.3 Add `get_last_assistant_content()` to `Session`
    - Iterate `self._history` in reverse; return `content` of the first turn
      with `role == "assistant"`, or `None` if none found
    - _Requirements: 1.1, 1.2, 2.1, 2.2_

  - [ ] 1.4 Write tests for clipboard and session accessor
    - **Unit:** `test_get_last_assistant_content` with empty history, user-only
      history, single assistant, multiple assistants
    - **Unit:** `test_copy_to_clipboard_calls_pbcopy` (mock `subprocess.run` and
      `sys.platform`)
    - **Unit:** `test_copy_to_clipboard_missing_utility` (mock `shutil.which`
      returning `None`)
    - **Property 1: Content Integrity** — generate arbitrary strings via
      Hypothesis, mock subprocess, verify stdin receives the exact bytes
    - **Property 2: Last-Turn Selection** — generate lists of
      `ConversationTurn`, verify the method returns the content of the last
      assistant turn
    - **Validates: Requirements 1.1, 1.2, 1.4, 3.1, 3.2, 3.3, 4.1, 4.4**

  - [ ] 1.V Verify task group 1
    - [ ] All new tests pass: `uv run pytest -q tests/test_clipboard.py tests/test_session.py`
    - [ ] All existing tests still pass: `uv run pytest -q tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 1.1, 1.2, 1.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [ ] 2. Checkpoint — Clipboard & Session Accessor Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 3. Slash command and keyboard shortcut
  - [ ] 3.1 Add `/copy` command to `builtin_commands.py`
    - Create `create_copy_command() -> SlashCommand` with name `"copy"`,
      description `"Copy last agent output to clipboard"`,
      help_text explaining the command
    - Handler: call `session.get_last_assistant_content()`; if `None`, call
      `tui.display_info("No agent output to copy.")`; else call
      `clipboard.copy_to_clipboard(text)`, then
      `tui.display_info("Copied to clipboard.")`
    - Wrap clipboard call in `try/except ClipboardError` and call
      `tui.display_error(str(e))` on failure
    - Add `create_copy_command()` to `get_builtin_commands()` return list
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ] 3.2 Add `Ctrl+Y` key binding to `TUIShell`
    - In `__init__`, create a prompt-toolkit `KeyBindings` instance
    - Register `Ctrl+Y` handler that performs the same copy logic as `/copy`
    - The handler needs access to the `Session`; add a `set_session` method or
      accept the session reference during initialization
    - Pass the key bindings to the `PromptSession` constructor
    - Ensure `Ctrl+Y` does not conflict with existing bindings (Ctrl+C, Ctrl+D,
      Ctrl+R, Ctrl+S, Tab)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 3.3 Write tests for `/copy` command and keyboard shortcut
    - **Unit:** `test_copy_command_success` — mock session with assistant turn,
      mock clipboard, verify `display_info("Copied to clipboard.")` called
    - **Unit:** `test_copy_command_no_output` — mock empty session, verify
      `display_info("No agent output to copy.")` called
    - **Unit:** `test_copy_command_clipboard_error` — mock clipboard raising
      `ClipboardError`, verify `display_error` called
    - **Property 3: Empty-Session Guard** — generate sessions with no assistant
      turns, verify clipboard is never invoked
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3**

  - [ ] 3.V Verify task group 3
    - [ ] All new tests pass: `uv run pytest -q tests/test_builtin_commands.py tests/test_tui.py`
    - [ ] All existing tests still pass: `uv run pytest -q tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 1.1–1.6, 2.1–2.5 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [ ] 4. Documentation and final verification
  - [ ] 4.1 Update `README.md` with `/copy` command and `Ctrl+Y` shortcut
    - _Requirements: 1.5_

  - [ ] 4.2 Update `docs/api.md` if it documents commands or key bindings
    - _Requirements: 1.5_

  - [ ] 4.3 Final end-to-end verification
    - [ ] All tests pass: `uv run pytest -q tests/`
    - [ ] Linter clean: `uv run ruff check src/ tests/`
    - [ ] Manual smoke test: run the app, get an agent response, type `/copy`,
      verify clipboard contains raw markdown
    - [ ] Manual smoke test: press `Ctrl+Y` at prompt, verify same behavior

<!-- SESSION BOUNDARY -->

### Checkbox States

| Syntax   | Meaning                |
|----------|------------------------|
| `- [ ]`  | Not started (required) |
| `- [ ]*` | Not started (optional) |
| `- [x]`  | Completed              |
| `- [-]`  | In progress            |
| `- [~]`  | Queued                 |

## Traceability

| Requirement | Implemented By Task | Verified By Test                |
|-------------|---------------------|---------------------------------|
| 1.1         | 3.1                 | test_copy_command_success       |
| 1.2         | 3.1                 | test_copy_command_no_output     |
| 1.3         | 3.1                 | test_copy_command_success       |
| 1.4         | 1.1, 1.2, 3.1      | test_copy_command_clipboard_error, test_copy_to_clipboard_missing_utility |
| 1.5         | 3.1, 4.1           | test_copy_in_help (manual)      |
| 1.6         | 3.1                 | tab-completion (manual)         |
| 2.1         | 3.2                 | test_ctrl_y_binding             |
| 2.2         | 3.2                 | test_ctrl_y_no_output           |
| 2.3         | 3.2                 | test_ctrl_y_success             |
| 2.4         | 3.2                 | test_ctrl_y_no_conflict         |
| 2.5         | 3.2                 | test_ctrl_y_at_prompt           |
| 3.1         | 1.2                 | Property 1: Content Integrity   |
| 3.2         | 1.2                 | Property 1: Content Integrity   |
| 3.3         | 1.2                 | Property 1: Content Integrity   |
| 4.1         | 1.2                 | test_copy_to_clipboard_calls_pbcopy |
| 4.2         | 1.2                 | test_copy_to_clipboard_xclip    |
| 4.3         | 1.2                 | test_copy_to_clipboard_wl_copy  |
| 4.4         | 1.1, 1.2           | test_copy_to_clipboard_missing_utility, Property 5 |

## Notes

- The project has no tests directory yet; task group 1 will create `tests/`
  with `__init__.py` and initial test files.
- `Ctrl+Y` is typically "yank" in readline/Emacs keybindings. prompt-toolkit
  uses Emacs mode by default, where `Ctrl+Y` yanks from the kill ring. This
  binding will override that behavior. If this is undesirable, an alternative
  like `Ctrl+\\` or `F5` can be chosen during implementation.
- The clipboard module does not use any third-party clipboard libraries to keep
  the dependency footprint minimal.
