# Implementation Plan: Audit Trail

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from main -> implement -> test -> merge to main -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

Implementation proceeds in five task groups: (1) create the `AuditLogger` class
with file management and entry formatting, (2) add `Config.audit` and wire the
logger into `App`, (3) integrate audit logging into TUI output methods, (4)
integrate audit logging into REPL input recording and add the `/audit` command,
(5) integration tests. Dependencies flow linearly: the logger must exist before
it can be wired, and wiring must complete before TUI/REPL integration.

## Test Commands

- Unit tests: `uv run pytest -q tests/`
- Property tests: `uv run pytest -q tests/ -k property`
- All tests: `uv run pytest tests/`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [x] 1. AuditLogger Core
  - [x] 1.1 Create `src/agent_repl/audit_logger.py`
    - `AuditLogger` class with `__init__(directory: str = ".af")`
    - Internal state: `_directory`, `_file` (TextIO | None), `_file_path`
      (str | None), `_active` (bool)
    - Properties: `active` (bool), `file_path` (str | None)
    - _Requirements: 1.3, 1.4_

  - [x] 1.2 Implement `_generate_filename()` method
    - Return `audit_YYYYMMDD_HHMMSS.log` using `datetime.now()`
    - _Requirements: 1.4_

  - [x] 1.3 Implement `start()` method
    - Create `.af/` directory if it doesn't exist (`os.makedirs(exist_ok=True)`)
    - Generate filename, build full path
    - Open file in append mode
    - Set `_active = True`
    - Write `[SYSTEM] Audit started` entry
    - Return file path
    - On failure: raise `OSError` (caller handles)
    - _Requirements: 1.3, 1.5, 6.4, 6.5, Edge Cases 1.E1, 1.E2_

  - [x] 1.4 Implement `stop()` method
    - Write `[SYSTEM] Audit stopped` entry
    - Flush and close file
    - Set `_active = False`
    - _Requirements: 2.5, 6.6_

  - [x] 1.5 Implement `log(entry_type, content)` method
    - No-op if not active
    - Format: `[{ISO 8601 timestamp}] [{entry_type}] {content}`
    - Timestamp: `datetime.now().isoformat(timespec="milliseconds")`
    - Write entry + newline to file
    - Flush immediately after write
    - On I/O error: log warning, set `_active = False`, close file
    - _Requirements: 5.1, 5.2, 5.3, 6.1, Edge Cases 6.E1, 6.E2_

  - [x] 1.6 Implement `_write_entry()` internal method
    - Shared formatting logic for `log()`, start, and stop
    - _Requirements: 5.3_

  - [x] 1.7 Write unit tests for AuditLogger
    - `start()` creates file in directory
    - `start()` creates directory if missing
    - `start()` raises OSError if directory unwritable
    - `stop()` closes file
    - `stop()` writes final SYSTEM entry
    - `log()` writes formatted entry
    - `log()` is no-op when inactive
    - `log()` flushes after each entry
    - `log()` disables auditing on I/O error
    - Filename matches `audit_\d{8}_\d{6}\.log` pattern
    - Entry format matches expected regex
    - Start entry is first, stop entry is last
    - **Property 1: Entry Timestamp Ordering**
    - **Property 2: Entry Format Compliance**
    - **Property 3: Flush Per Entry**
    - **Property 4: No-Op When Inactive**
    - **Property 5: Start/Stop Bookends**
    - **Property 7: File Creation on Start**
    - **Property 8: Graceful Failure**
    - **Validates: Requirements 1.3-1.5, 5.1-5.3, 6.1-6.6**

  - [x] 1.V Verify task group 1
    - [x] All new tests pass: `uv run pytest -q tests/ -k "audit_logger"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 1.3-1.5, 5.1-5.3, 6.1-6.6 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [x] 2. Checkpoint - AuditLogger Core Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 3. Config and App Wiring
  - [x] 3.1 Add `audit: bool = False` to `Config` dataclass
    - Add field to `Config` in `types.py`
    - _Requirements: 1.1_

  - [x] 3.2 Add `audit_logger: Any = None` to `CommandContext`
    - Add field to `CommandContext` in `types.py`
    - _Requirements: (needed for /audit command handler access)_

  - [x] 3.3 Wire AuditLogger in `App.__init__()`
    - Create `self._audit_logger = AuditLogger()`
    - _Requirements: 1.2_

  - [x] 3.4 Wire AuditLogger in `App._setup()`
    - Call `self._tui.set_audit_logger(self._audit_logger)`
    - If `self._config.audit` is True, call `self._audit_logger.start()`
      wrapped in try/except OSError
    - _Requirements: 1.2, Edge Cases 1.E1, 1.E2_

  - [x] 3.5 Wire AuditLogger in `App.run()`
    - Pass `self._audit_logger` to `REPL` constructor
    - After REPL exits, call `self._audit_logger.stop()` if active
    - _Requirements: 6.2, 6.3_

  - [x] 3.6 Update `REPL.__init__()` to accept `AuditLogger`
    - Add optional `audit_logger` parameter
    - Store as `self._audit_logger`
    - _Requirements: 3.1_

  - [x] 3.7 Pass `audit_logger` through `CommandContext` in REPL
    - In `_handle_command()`, set `ctx.audit_logger = self._audit_logger`
    - _Requirements: (needed for /audit command)_

  - [x] 3.8 Write unit tests for Config and App wiring
    - `Config(audit=True)` field exists and defaults to False
    - `App._setup()` starts auditing when `config.audit=True`
    - `App._setup()` handles start failure gracefully
    - `App.run()` stops auditing on exit
    - REPL receives audit_logger
    - **Validates: Requirements 1.1, 1.2, 6.2, 6.3**

  - [x] 3.V Verify task group 3
    - [x] All new tests pass: `uv run pytest -q tests/ -k "audit"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 1.1-1.2, 6.2-6.3 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [x] 4. Checkpoint - App Wiring Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 5. TUI Output Audit Integration
  - [x] 5.1 Add `set_audit_logger()` method to `TUIShell`
    - Store optional `AuditLogger` reference as `self._audit_logger`
    - Default to `None` in `__init__`
    - _Requirements: 4.1-4.6_

  - [x] 5.2 Add audit logging to `show_info()`
    - After console print, call `self._audit_logger.log("INFO", text)`
      if logger is set and active
    - _Requirements: 4.1_

  - [x] 5.3 Add audit logging to `show_error()`
    - Log with type `ERROR`
    - _Requirements: 4.2_

  - [x] 5.4 Add audit logging to `show_warning()`
    - Log with type `WARNING`
    - _Requirements: 4.3_

  - [x] 5.5 Add audit logging to `show_tool_result()`
    - Log with type `TOOL_RESULT`, content: `"{icon} {name}: {result}"`
    - _Requirements: 4.4_

  - [x] 5.6 Add audit logging to `finalize_live_text()`
    - Log with type `AGENT`, content: full accumulated text
    - Only log if there is non-empty text
    - _Requirements: 4.5_

  - [x] 5.7 Add audit logging to `show_banner()`
    - Log with type `SYSTEM`, content: app name, version, agent info
    - _Requirements: 4.6_

  - [x] 5.8 Verify transient methods are NOT audited
    - Confirm `start_spinner`, `stop_spinner`, `start_live_text`,
      `append_live_text` do NOT call the audit logger
    - _Requirements: 4.7_

  - [x] 5.9 Write unit tests for TUI audit integration
    - Mock AuditLogger, verify each show_* method calls `log()` with
      correct entry type
    - Verify no audit calls when logger is None
    - Verify no audit calls when logger is inactive
    - Verify transient methods don't call audit
    - Verify finalize_live_text logs complete text
    - Verify show_tool_result includes name and result
    - **Validates: Requirements 4.1-4.7**

  - [x] 5.V Verify task group 5
    - [x] All new tests pass: `uv run pytest -q tests/ -k "tui_audit or tui_output"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 4.1-4.7 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 5 is complete. Do NOT continue to task group 6 in this session. -->

- [x] 6. Checkpoint - TUI Audit Integration Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 7. REPL Input Audit and /audit Command
  - [x] 7.1 Add input audit logging to `REPL.run()`
    - After `prompt_input()` and before `parse_input()`, log the raw input
    - If input starts with `/`: log with type `COMMAND`
    - Otherwise: log with type `INPUT`
    - Only log non-empty (stripped) input
    - _Requirements: 3.1, 3.2, 3.3, 3.4, Edge Case 3.E1_

  - [x] 7.2 Implement `_handle_audit()` command handler
    - Add handler function in `builtin_commands.py`
    - Access `AuditLogger` via `ctx.audit_logger`
    - If `audit_logger` is None: show error
    - If active: call `stop()`, show "Audit stopped: {path}"
    - If inactive: call `start()`, show "Audit started: {path}"
    - Catch OSError from `start()` and show error
    - _Requirements: 2.2, 2.3, 2.4, 2.5, Edge Case 2.E1_

  - [x] 7.3 Register `/audit` in `BuiltinCommandsPlugin.get_commands()`
    - Add SlashCommand with `name="audit"`, `cli_exposed=True`
    - _Requirements: 2.1, 2.6_

  - [x] 7.4 Write unit tests for REPL input auditing
    - Free text input logged as `INPUT`
    - Slash command logged as `COMMAND`
    - Empty input not logged
    - Audit logger inactive: no logging
    - Audit logger None: no crash
    - **Property 6: Input Classification**
    - **Validates: Requirements 3.1-3.4, Edge Case 3.E1**

  - [x] 7.5 Write unit tests for `/audit` command
    - Toggle on: calls start(), shows path
    - Toggle off: calls stop(), shows path
    - Start failure: shows error, stays off
    - No logger: shows error
    - CLI-exposed flag is True
    - **Validates: Requirements 2.1-2.6, Edge Case 2.E1**

  - [x] 7.V Verify task group 7
    - [x] All new tests pass: `uv run pytest -q tests/ -k "audit"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 2.1-2.6, 3.1-3.4 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 7 is complete. Do NOT continue to task group 8 in this session. -->

- [x] 8. Checkpoint - REPL and Command Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 9. Integration Tests and Property Tests
  - [x] 9.1 Write integration test: full session with audit
    - Create App with `Config(audit=True)`
    - Simulate: banner → user input → agent response → tool use →
      command → exit
    - Read audit file, verify all entries present in order
    - Verify first entry is `[SYSTEM] Audit started`
    - Verify last entry is `[SYSTEM] Audit stopped`
    - **Property 5: Start/Stop Bookends**
    - **Validates: Requirements 1.2, 4.1-4.6, 6.5, 6.6**

  - [x] 9.2 Write integration test: /audit toggle mid-session
    - Start without audit, invoke `/audit` to enable
    - Verify new file created
    - Invoke `/audit` again to disable
    - Verify file closed and contains correct entries
    - **Validates: Requirements 2.2-2.5**

  - [x] 9.3 Write integration test: audit file survives crash
    - Start audit, write entries, simulate crash (don't call stop)
    - Verify file contains flushed entries up to crash point
    - **Property 3: Flush Per Entry**
    - **Validates: Requirement 6.4**

  - [x] 9.4 Write property-based tests
    - Generate arbitrary strings, verify entry format regex (Property 2)
    - Generate sequences of log calls, verify timestamp ordering
      (Property 1)
    - Generate inputs starting with `/` and not, verify classification
      (Property 6)
    - **Validates: Properties 1, 2, 6**

  - [x] 9.5 Update existing tests
    - Ensure App tests pass with new `audit` config field
    - Ensure REPL tests pass with optional `audit_logger` parameter
    - Ensure TUI tests pass with `_audit_logger = None` default
    - _Requirements: all_

  - [x] 9.V Verify task group 9
    - [x] All new tests pass: `uv run pytest -q tests/`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] All 8 correctness properties validated by tests

<!-- SESSION BOUNDARY -->

### Checkbox States

| Syntax   | Meaning                |
|----------|------------------------|
| `- [ ]`  | Not started (required) |
| `- [ ]*` | Not started (optional) |
| `- [x]`  | Completed              |
| `- [-]`  | In progress            |
| `- [~]`  | Queued                 |

### Test Task Annotations

- Unit/integration tests: `**Validates: Requirements X.Y**`
- Property-based tests: `**Property N: [Name]**` (references design doc properties)

## Traceability

| Requirement | Implemented By Task | Verified By Test |
|-------------|---------------------|------------------|
| 1.1 (Config.audit field) | 3.1 | 3.8 |
| 1.2 (auto-start on Config.audit) | 3.4 | 3.8, 9.1 |
| 1.3 (create audit file) | 1.3 | 1.7 |
| 1.4 (filename pattern) | 1.2 | 1.7 |
| 1.5 (create .af/ directory) | 1.3 | 1.7 |
| 2.1 (/audit command registered) | 7.3 | 7.5 |
| 2.2 (/audit toggle on) | 7.2 | 7.5, 9.2 |
| 2.3 (/audit toggle off) | 7.2 | 7.5, 9.2 |
| 2.4 (new file on toggle on) | 7.2 | 7.5, 9.2 |
| 2.5 (close file on toggle off) | 7.2 | 7.5, 9.2 |
| 2.6 (cli_exposed) | 7.3 | 7.5 |
| 3.1 (record user input) | 7.1 | 7.4 |
| 3.2 (INPUT label) | 7.1 | 7.4 |
| 3.3 (COMMAND label) | 7.1 | 7.4 |
| 3.4 (exact raw text) | 7.1 | 7.4 |
| 4.1 (show_info -> INFO) | 5.2 | 5.9, 9.1 |
| 4.2 (show_error -> ERROR) | 5.3 | 5.9, 9.1 |
| 4.3 (show_warning -> WARNING) | 5.4 | 5.9 |
| 4.4 (show_tool_result -> TOOL_RESULT) | 5.5 | 5.9, 9.1 |
| 4.5 (finalize_live_text -> AGENT) | 5.6 | 5.9, 9.1 |
| 4.6 (show_banner -> SYSTEM) | 5.7 | 5.9, 9.1 |
| 4.7 (no transient output) | 5.8 | 5.9 |
| 5.1 (ISO 8601 timestamp) | 1.5 | 1.7 |
| 5.2 (entry format) | 1.5, 1.6 | 1.7 |
| 5.3 (complete format) | 1.6 | 1.7 |
| 6.1 (flush per entry) | 1.5 | 1.7, 9.3 |
| 6.2 (close on normal exit) | 3.5 | 3.8, 9.1 |
| 6.3 (close on abnormal exit) | 3.5 | 3.8 |
| 6.4 (append mode) | 1.3 | 1.7, 9.3 |
| 6.5 (start entry) | 1.3 | 1.7, 9.1 |
| 6.6 (stop entry) | 1.4 | 1.7, 9.1 |

## Notes

- The `AuditLogger` is intentionally kept simple (single-file, no rotation).
  Future specs can add log rotation or compression if needed.
- The logger uses `datetime.now().isoformat(timespec="milliseconds")` for
  timestamps. No timezone info is included (local time assumed).
- Multiline content (e.g., long agent responses) is written as-is. Each
  `log()` call produces one logical entry that may span multiple lines in
  the file. The next entry's timestamp line marks the boundary.
- The `audit_logger` field on `CommandContext` uses `Any` typing to avoid
  a circular import between `types.py` and `audit_logger.py`. The actual
  type is `AuditLogger | None`.
- The `/audit` command is registered in `BuiltinCommandsPlugin` (not a
  separate plugin) since it's a core framework feature.
