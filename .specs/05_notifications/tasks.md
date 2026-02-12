# Implementation Plan: Desktop Notifications

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from develop -> implement -> test -> merge to develop -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

Implementation proceeds in seven task groups: (1) create `NotificationConfig`,
backend protocol and implementations, and the `_applescript_quote` helper;
(2) checkpoint; (3) create the `Notifier` class with threshold, debounce, and
foreground detection; (4) checkpoint; (5) wire into Config, App, StreamHandler,
and add the `/notify` command; (6) checkpoint; (7) integration tests and
property-based tests. Dependencies flow linearly: backends must exist before
the Notifier, and the Notifier must exist before wiring.

## Test Commands

- Unit tests: `uv run pytest -q tests/`
- Property tests: `uv run pytest -q tests/ -k property`
- All tests: `uv run pytest tests/`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [ ] 1. Notification Backends and Config
  - [ ] 1.1 Create `src/agent_repl/notifier.py` with `NotificationConfig`
    - Frozen dataclass with fields: `enabled` (bool, default False),
      `sound` (str | None, default "default"), `threshold_seconds` (int,
      default 60), `debounce_seconds` (float, default 5.0)
    - Class method `from_dict(data: dict) -> NotificationConfig` that parses
      a raw dict, clamps `threshold_seconds` to min 60, logs warning and
      returns defaults on type errors
    - _Requirements: 1.1, 1.3, 1.4_

  - [ ] 1.2 Implement `NotificationBackend` protocol
    - Runtime-checkable protocol with `is_available() -> bool` and
      `send(title: str, message: str, sound: str | None) -> None`
    - _Requirements: 8.1_

  - [ ] 1.3 Implement `MacOSBackend`
    - `is_available()`: returns `True` only when `platform.system() == "Darwin"`
      and `shutil.which("osascript") is not None`
    - `send()`: builds AppleScript string with `display notification`, runs
      via `subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)`
    - Catches `subprocess.TimeoutExpired` and `OSError`, logs warning
    - _Requirements: 7.1, 7.3, 7.6, 7.7, 7.8, Edge Cases 7.E1, 7.E2_

  - [ ] 1.4 Implement `NullBackend`
    - `is_available()` returns `False`
    - `send()` is a no-op
    - _Requirements: 8.2, 8.3, Edge Case 8.E2_

  - [ ] 1.5 Implement `_applescript_quote(s: str) -> str`
    - Escapes backslashes, double quotes, replaces newlines with spaces
    - Wraps result in double quotes
    - _Requirements: 7.8, Edge Case 7.E3_

  - [ ] 1.6 Implement `_create_backend() -> NotificationBackend`
    - Returns `MacOSBackend()` if `platform.system() == "Darwin"`, else `NullBackend()`
    - _Requirements: 8.4, 8.5_

  - [ ] 1.7 Write unit tests for backends and config
    - `NotificationConfig` default values correct
    - `from_dict()` parses valid config
    - `from_dict()` clamps `threshold_seconds < 60` to 60
    - `from_dict()` returns defaults on invalid types
    - `from_dict()` ignores unknown keys
    - `NullBackend.is_available()` returns False
    - `NullBackend.send()` is a no-op (no exceptions)
    - `MacOSBackend.is_available()` checks platform and osascript
    - `_applescript_quote()` escapes backslashes, quotes, newlines
    - `_create_backend()` returns MacOS on Darwin, Null otherwise
    - **Property 7: Config Clamping**
    - **Property 8: AppleScript Injection Safety**
    - **Property 11: Null Backend No-Op**
    - **Validates: Requirements 1.1, 1.3, 1.4, 7.8, 8.1-8.5**

  - [ ] 1.V Verify task group 1
    - [ ] All new tests pass: `uv run pytest -q tests/ -k "notif"`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 1.1, 1.3, 1.4, 7.1-7.8, 8.1-8.5 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [ ] 2. Checkpoint - Backends and Config Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 3. Notifier Core
  - [ ] 3.1 Implement foreground detection
    - Module-level `_APPKIT_AVAILABLE` flag (try/except import of AppKit)
    - `_TERMINAL_BUNDLE_IDS` set with known terminal bundle IDs
    - `_is_terminal_foreground() -> bool`: returns False if AppKit unavailable;
      otherwise checks `NSWorkspace.sharedWorkspace().frontmostApplication()`
    - Returns False on any exception (safe fallback)
    - _Requirements: 6.1-6.5, Edge Cases 6.E1, 6.E2_

  - [ ] 3.2 Implement `_PendingNotification` dataclass
    - Fields: `message: str`, `title: str`
    - _Requirements: (internal data structure)_

  - [ ] 3.3 Implement `Notifier.__init__()`
    - Accept `config: NotificationConfig` and `app_name: str`
    - Initialize: `_enabled` from config, `_backend` from `_create_backend()`,
      `_turn_start_time = None`, `_pending = None`, `_debounce_task = None`
    - _Requirements: (constructor)_

  - [ ] 3.4 Implement `Notifier.enabled` property and setter
    - Getter returns `self._enabled`
    - Setter sets `self._enabled`
    - _Requirements: 2.2, 2.3_

  - [ ] 3.5 Implement `Notifier.mark_turn_start()`
    - Sets `self._turn_start_time = time.monotonic()`
    - _Requirements: 4.1_

  - [ ] 3.6 Implement `Notifier._should_notify() -> bool`
    - Returns False if: not enabled, backend not available, no turn start time,
      or elapsed time < threshold_seconds
    - _Requirements: 4.2, 4.3_

  - [ ] 3.7 Implement `Notifier.queue(message: str)`
    - Check `_should_notify()`; if False, return
    - Truncate message to 80 chars (or "Response complete" if empty)
    - Store as `_PendingNotification`
    - Call `_reset_debounce_timer()`
    - _Requirements: 3.1, 3.2, 3.3, 5.1, 5.2_

  - [ ] 3.8 Implement `Notifier._reset_debounce_timer()`
    - Cancel existing debounce task if running
    - Create new `asyncio.Task` calling `_debounce_fire()`
    - _Requirements: 5.1, 5.2, 5.5_

  - [ ] 3.9 Implement `Notifier._debounce_fire()`
    - `await asyncio.sleep(debounce_seconds)`
    - If pending notification exists, call `_deliver()`
    - Clear pending
    - Catch `CancelledError` and return silently
    - _Requirements: 5.3_

  - [ ] 3.10 Implement `Notifier.flush()`
    - Cancel debounce task if running
    - If pending notification exists, call `_deliver()` and clear
    - _Requirements: 5.4, Edge Case 5.E1_

  - [ ] 3.11 Implement `Notifier._deliver(notification)`
    - Check `_is_terminal_foreground()`; if True, return (suppress)
    - Run `backend.send()` via `loop.run_in_executor(None, ...)`
    - _Requirements: 6.1, 6.2, 7.2_

  - [ ] 3.12 Write unit tests for Notifier
    - `mark_turn_start()` records monotonic time
    - `_should_notify()` returns False when disabled
    - `_should_notify()` returns False when backend unavailable
    - `_should_notify()` returns False when elapsed < threshold
    - `_should_notify()` returns True when all conditions met
    - `queue()` stores pending notification with truncated message
    - `queue()` truncates message to 80 chars
    - `queue()` uses "Response complete" for empty message
    - `queue()` discards when threshold not met
    - `flush()` delivers pending notification
    - `flush()` cancels debounce timer
    - `flush()` is no-op with no pending notification
    - `_deliver()` suppresses when terminal is foreground
    - `_deliver()` sends via backend when terminal is background
    - `_deliver()` runs backend.send in executor (non-blocking)
    - Debounce: rapid events produce single delivery
    - **Property 1: Platform Safety**
    - **Property 2: Threshold Guard**
    - **Property 3: Foreground Suppression**
    - **Property 4: Debounce Coalescing**
    - **Property 5: Flush Delivery**
    - **Property 6: Non-Blocking Delivery**
    - **Property 9: Backend Abstraction**
    - **Property 12: Message Truncation**
    - **Validates: Requirements 3.1-3.3, 4.1-4.4, 5.1-5.5, 6.1-6.5, 7.2**

  - [ ] 3.V Verify task group 3
    - [ ] All new tests pass: `uv run pytest -q tests/ -k "notif"`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 3.1-3.3, 4.1-4.4, 5.1-5.5, 6.1-6.5 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [ ] 4. Checkpoint - Notifier Core Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 5. Wiring and /notify Command
  - [ ] 5.1 Add `notifications` field to `Config` in `types.py`
    - Import `NotificationConfig` from `notifier`
    - Add `notifications: NotificationConfig = field(default_factory=NotificationConfig)`
    - _Requirements: 1.2_

  - [ ] 5.2 Add `notifier: Any = None` to `CommandContext` in `types.py`
    - Same pattern as `audit_logger` field
    - _Requirements: (needed for /notify command handler)_

  - [ ] 5.3 Parse `[notifications]` config in `App._setup()`
    - After `load_config()`, extract `raw.get("notifications", {})`
    - Build `NotificationConfig.from_dict(raw_notifications)`
    - Create `self._notifier = Notifier(notification_config, app_name=...)`
    - _Requirements: 1.3, 1.5, Edge Cases 1.E1, 1.E2_

  - [ ] 5.4 Wire Notifier to REPL/StreamHandler
    - Pass `self._notifier` to `REPL` constructor
    - REPL passes it to `StreamHandler` constructor
    - StreamHandler stores as `self._notifier`
    - _Requirements: (wiring)_

  - [ ] 5.5 Add notification triggers to `StreamHandler.handle_stream()`
    - At start: call `self._notifier.mark_turn_start()` if notifier exists
    - On `TOOL_RESULT`: call `await self._notifier.queue(f"Tool completed: {name}")`
    - On `ERROR`: call `await self._notifier.queue(message[:80])`
    - After event loop ends: queue response snippet and call `await self._notifier.flush()`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, Edge Cases 3.E1, 3.E2, 3.E3_

  - [ ] 5.6 Pass `notifier` through `CommandContext` in REPL
    - In `_handle_command()`, set `ctx.notifier = self._notifier`
    - _Requirements: (needed for /notify command)_

  - [ ] 5.7 Implement `/notify` command handler
    - Add `_handle_notify(ctx)` in `builtin_commands.py`
    - Toggle `notifier.enabled`, show info message
    - Handle None notifier with error message
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, Edge Cases 2.E1, 2.E2_

  - [ ] 5.8 Register `/notify` in `BuiltinCommandsPlugin.get_commands()`
    - Add `SlashCommand(name="notify", description="Toggle desktop notifications", handler=_handle_notify, cli_exposed=True)`
    - _Requirements: 2.1, 2.5_

  - [ ] 5.9 Update default config template in `config_loader.py`
    - Add commented-out `[notifications]` section with all keys
    - _Requirements: 1.6_

  - [ ] 5.10 Write unit tests for wiring and /notify
    - `Config.notifications` defaults to `NotificationConfig()`
    - `CommandContext.notifier` defaults to None
    - `/notify` toggles `notifier.enabled` from False to True
    - `/notify` toggles `notifier.enabled` from True to False
    - `/notify` with None notifier shows error
    - `/notify` is cli_exposed
    - StreamHandler calls `mark_turn_start()` at stream start
    - StreamHandler queues on TOOL_RESULT, ERROR, response complete
    - StreamHandler calls `flush()` at stream end
    - Config template includes `[notifications]` section
    - **Property 10: Runtime Toggle Independence**
    - **Validates: Requirements 1.2, 1.6, 2.1-2.5, 3.1-3.4**

  - [ ] 5.V Verify task group 5
    - [ ] All new tests pass: `uv run pytest -q tests/ -k "notif"`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 1.2, 1.6, 2.1-2.5, 3.1-3.4 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 5 is complete. Do NOT continue to task group 6 in this session. -->

- [ ] 6. Checkpoint - Wiring Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 7. Integration and Property-Based Tests
  - [ ] 7.1 Write integration test: full stream with notifications
    - Create Notifier with enabled=True, threshold=0 (test override), mock backend
    - Simulate a stream with TEXT_DELTA + TOOL_RESULT + USAGE events
    - Verify `mark_turn_start()` called at start
    - Verify notification queued and flushed
    - Verify mock backend received `send()` call with expected args
    - **Property 5: Flush Delivery**
    - **Validates: Requirements 3.1, 3.3, 3.4**

  - [ ] 7.2 Write integration test: threshold prevents notification
    - Create Notifier with enabled=True, threshold=60
    - Simulate a short stream (<60s elapsed)
    - Verify no notification delivered
    - **Property 2: Threshold Guard**
    - **Validates: Requirements 4.2, 4.3**

  - [ ] 7.3 Write integration test: debounce coalesces tool results
    - Create Notifier with short debounce window
    - Queue multiple events rapidly
    - Verify only one notification delivered with last event's content
    - **Property 4: Debounce Coalescing**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ] 7.4 Write integration test: foreground suppression
    - Mock `_is_terminal_foreground()` to return True
    - Queue and flush a notification
    - Verify backend.send() was NOT called
    - **Property 3: Foreground Suppression**
    - **Validates: Requirements 6.1, 6.2**

  - [ ] 7.5 Write property-based tests
    - Generate arbitrary strings, verify `_applescript_quote()` never
      produces unescaped quotes or backslashes in output
      (**Property 8: AppleScript Injection Safety**)
    - Generate random `threshold_seconds` values, verify clamping to >= 60
      (**Property 7: Config Clamping**)
    - Generate random elapsed times and threshold values, verify
      `_should_notify()` returns correct result
      (**Property 2: Threshold Guard**)
    - Generate random message strings, verify truncation to <= 80 chars
      (**Property 12: Message Truncation**)
    - **Validates: Properties 2, 7, 8, 12**

  - [ ] 7.6 Update existing tests for compatibility
    - Ensure App tests pass with new `notifications` config field
    - Ensure REPL tests pass with optional `notifier` parameter
    - Ensure StreamHandler tests pass with `notifier=None` default
    - _Requirements: all_

  - [ ] 7.V Verify task group 7
    - [ ] All new tests pass: `uv run pytest -q tests/`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] All 12 correctness properties validated by tests

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
| 1.1 (NotificationConfig dataclass) | 1.1 | 1.7 |
| 1.2 (Config.notifications field) | 5.1 | 5.10 |
| 1.3 (parse [notifications] from TOML) | 5.3 | 5.10 |
| 1.4 (clamp threshold_seconds >= 60) | 1.1 | 1.7, 7.5 |
| 1.5 (missing section = defaults) | 5.3 | 5.10 |
| 1.6 (default template includes section) | 5.9 | 5.10 |
| 2.1 (/notify registered) | 5.8 | 5.10 |
| 2.2 (/notify toggle on) | 5.7 | 5.10 |
| 2.3 (/notify toggle off) | 5.7 | 5.10 |
| 2.4 (no persistence) | 5.7 | 5.10 |
| 2.5 (cli_exposed) | 5.8 | 5.10 |
| 3.1 (response complete trigger) | 5.5 | 5.10, 7.1 |
| 3.2 (error trigger) | 5.5 | 5.10 |
| 3.3 (tool result trigger) | 5.5 | 5.10, 7.1 |
| 3.4 (flush at stream end) | 5.5 | 5.10, 7.1 |
| 4.1 (record turn start) | 5.5 | 5.10 |
| 4.2 (threshold check) | 3.6 | 3.12, 7.2 |
| 4.3 (discard below threshold) | 3.6 | 3.12, 7.2 |
| 4.4 (minimum 60s) | 1.1 | 1.7, 7.5 |
| 5.1 (start debounce timer) | 3.8 | 3.12, 7.3 |
| 5.2 (replace + restart on new event) | 3.7, 3.8 | 3.12, 7.3 |
| 5.3 (deliver on timer expiry) | 3.9 | 3.12, 7.3 |
| 5.4 (flush cancels timer + delivers) | 3.10 | 3.12, 7.1 |
| 5.5 (asyncio.Task timer) | 3.8 | 3.12 |
| 6.1 (check foreground before deliver) | 3.11 | 3.12, 7.4 |
| 6.2 (suppress if foreground) | 3.11 | 3.12, 7.4 |
| 6.3 (AppKit NSWorkspace) | 3.1 | 3.12 |
| 6.4 (known terminal bundle IDs) | 3.1 | 3.12 |
| 6.5 (fallback if no AppKit) | 3.1 | 3.12 |
| 7.1 (osascript subprocess) | 1.3 | 1.7 |
| 7.2 (run_in_executor) | 3.11 | 3.12 |
| 7.3 (display notification command) | 1.3 | 1.7 |
| 7.4 (title = app_name) | 3.3, 3.7 | 3.12 |
| 7.5 (message = content) | 3.7 | 3.12 |
| 7.6 (sound name if not None) | 1.3 | 1.7 |
| 7.7 (omit sound if None) | 1.3 | 1.7 |
| 7.8 (AppleScript escaping) | 1.5 | 1.7, 7.5 |
| 8.1 (NotificationBackend protocol) | 1.2 | 1.7 |
| 8.2 (MacOSBackend) | 1.3 | 1.7 |
| 8.3 (NullBackend) | 1.4 | 1.7 |
| 8.4 (Darwin → MacOSBackend) | 1.6 | 1.7 |
| 8.5 (non-Darwin → NullBackend) | 1.6 | 1.7 |
| 8.6 (protocol-only interaction) | 3.11 | 3.12 |

## Notes

- The `notifier` field on `CommandContext` uses `Any` typing to avoid a
  circular import between `types.py` and `notifier.py`. The actual type
  is `Notifier | None`.
- For testing, `threshold_seconds` clamping only applies during `from_dict()`
  parsing. The constructor accepts any int, allowing tests to use values like
  `threshold_seconds=0` for immediate notification eligibility.
- The `_is_terminal_foreground()` function is module-level (not a method)
  to facilitate mocking in tests. Patch `agent_repl.notifier._is_terminal_foreground`.
- Debounce tests should use `asyncio.sleep()` mocking or short debounce windows
  (e.g., 0.1s) to avoid slow test runs.
- The foreground detection list of terminal bundle IDs is intentionally
  non-exhaustive. Users with unlisted terminals will receive notifications
  even when the terminal is in the foreground — an acceptable trade-off.
