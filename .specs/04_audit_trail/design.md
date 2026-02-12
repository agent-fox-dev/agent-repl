# Design Document: Audit Trail

## Overview

The audit trail is implemented as a standalone `AuditLogger` class that
writes timestamped, labeled entries to a plain-text log file. It integrates
at two points: the REPL (for input events) and the TUI (for output events).
The `Config.audit` flag enables it at startup, and `/audit` toggles it at
runtime. The logger is passed as an optional dependency to both REPL and
TUIShell, keeping the audit concern decoupled from core logic.

## Architecture

```mermaid
flowchart TD
    A[Config.audit] -->|true| B[App._setup creates AuditLogger]
    B --> C[AuditLogger]
    C -->|set_audit_logger| D[TUIShell]
    C -->|passed to| E[REPL]
    D -->|show_info, show_error, etc.| C
    E -->|user input, commands| C
    F[/audit command] -->|toggle| C
    C -->|write entries| G[".af/audit_YYYYMMDD_HHMMSS.log"]
```

### Module Responsibilities

1. **audit_logger.py** (NEW) - `AuditLogger` class: file creation, timestamped
   entry writing, start/stop lifecycle, flush-per-entry.
2. **types.py** - Add `audit: bool = False` to `Config` dataclass.
3. **app.py** - Create `AuditLogger`, wire to TUI and REPL, start if
   `config.audit` is True.
4. **tui.py** - Accept optional `AuditLogger`; log output in `show_info()`,
   `show_error()`, `show_warning()`, `show_tool_result()`,
   `finalize_live_text()`, `show_banner()`.
5. **repl.py** - Accept optional `AuditLogger`; log user input after
   `prompt_input()` with appropriate label (`INPUT` or `COMMAND`).
6. **builtin_commands.py** - Register `/audit` slash command.

## Components and Interfaces

### New: `audit_logger.py`

```python
class AuditLogger:
    """Writes timestamped audit entries to a log file."""

    def __init__(self, directory: str = ".af") -> None:
        self._directory = directory
        self._file: TextIO | None = None
        self._file_path: str | None = None
        self._active: bool = False

    @property
    def active(self) -> bool: ...

    @property
    def file_path(self) -> str | None: ...

    def start(self) -> str:
        """Create a new audit file and start logging.
        Returns the file path. Raises OSError on failure."""

    def stop(self) -> None:
        """Write final entry, close file, deactivate."""

    def log(self, entry_type: str, content: str) -> None:
        """Write a timestamped entry. No-op if not active."""

    def _write_entry(self, entry_type: str, content: str) -> None:
        """Format and write a single entry, flush immediately."""

    def _generate_filename(self) -> str:
        """Generate audit_YYYYMMDD_HHMMSS.log filename."""
```

Entry format: `[2025-01-15T14:30:00.123] [INFO] content text here`

### Modified: `types.py`

```python
@dataclass
class Config:
    # ... existing fields ...
    audit: bool = False  # NEW
```

### Modified: `app.py`

In `__init__()`:
```python
self._audit_logger = AuditLogger()
```

In `_setup()`, after plugin loading:
```python
# Wire audit logger to TUI and REPL
self._tui.set_audit_logger(self._audit_logger)

# Start auditing if configured
if self._config.audit:
    try:
        path = self._audit_logger.start()
        self._tui.show_info(f"Audit started: {path}")
    except OSError as e:
        logger.warning("Failed to start auditing: %s", e)
```

In `run()`, after REPL exits:
```python
if self._audit_logger.active:
    self._audit_logger.stop()
```

Pass `self._audit_logger` to REPL constructor.

### Modified: `tui.py`

New method:
```python
def set_audit_logger(self, audit_logger: AuditLogger) -> None:
    self._audit_logger = audit_logger
```

Updated output methods add audit logging:
```python
def show_info(self, text: str) -> None:
    self._console.print(Text(text, style=self._theme.info_color))
    if self._audit_logger and self._audit_logger.active:
        self._audit_logger.log("INFO", text)
```

Same pattern for `show_error` (`ERROR`), `show_warning` (`WARNING`),
`show_tool_result` (`TOOL_RESULT`), `finalize_live_text` (`AGENT`),
`show_banner` (`SYSTEM`).

### Modified: `repl.py`

Constructor accepts optional `AuditLogger`:
```python
def __init__(self, ..., audit_logger: AuditLogger | None = None) -> None:
    self._audit_logger = audit_logger
```

In `run()`, after `prompt_input()`:
```python
raw = await self._tui.prompt_input()
if self._audit_logger and self._audit_logger.active and raw.strip():
    if raw.strip().startswith("/"):
        self._audit_logger.log("COMMAND", raw.strip())
    else:
        self._audit_logger.log("INPUT", raw.strip())
```

### New: `/audit` slash command

In `builtin_commands.py`:
```python
SlashCommand(
    name="audit",
    description="Toggle audit trail recording",
    handler=_handle_audit,
    cli_exposed=True,
)
```

Handler accesses `AuditLogger` via a reference stored on `App` or passed
through `CommandContext`. The simplest path: store the `AuditLogger` on
`PluginContext` or add it to `CommandContext`.

Design decision: add `audit_logger: Any = None` to `CommandContext`.

```python
async def _handle_audit(ctx: CommandContext) -> None:
    audit = ctx.audit_logger
    if audit is None:
        ctx.tui.show_error("Audit logger not available.")
        return
    if audit.active:
        audit.stop()
        ctx.tui.show_info(f"Audit stopped: {audit.file_path}")
    else:
        try:
            path = audit.start()
            ctx.tui.show_info(f"Audit started: {path}")
        except OSError as e:
            ctx.tui.show_error(f"Failed to start audit: {e}")
```

## Data Models

### Audit log entry format

```
[{ISO 8601 timestamp}] [{TYPE}] {content}
```

Examples:
```
[2025-01-15T14:30:00.123] [SYSTEM] Audit started
[2025-01-15T14:30:01.456] [SYSTEM] agent-repl v0.1.0 | Agent: Claude (claude-opus-4-6)
[2025-01-15T14:30:05.789] [INPUT] What is the weather today?
[2025-01-15T14:30:06.012] [AGENT] I don't have access to real-time weather data...
[2025-01-15T14:30:10.345] [COMMAND] /stats
[2025-01-15T14:30:10.346] [INFO] Sent: 1.23 k tokens
[2025-01-15T14:30:10.347] [INFO] Received: 0.45 k tokens
[2025-01-15T14:30:15.678] [TOOL_RESULT] ✓ bash: file1.py\nfile2.py
[2025-01-15T14:30:20.000] [ERROR] Agent error: connection timeout
[2025-01-15T14:30:25.000] [SYSTEM] Audit stopped
```

### Entry types

| Type | Source | Description |
|------|--------|-------------|
| `SYSTEM` | show_banner, start/stop | Session lifecycle events |
| `INPUT` | prompt_input (free text) | User free-text input |
| `COMMAND` | prompt_input (slash cmd) | Slash command invocation |
| `INFO` | show_info | Informational output |
| `ERROR` | show_error | Error messages |
| `WARNING` | show_warning | Warning messages |
| `AGENT` | finalize_live_text | Complete agent response text |
| `TOOL_RESULT` | show_tool_result | Tool execution results |

### Audit file naming

Pattern: `audit_YYYYMMDD_HHMMSS.log`
Directory: `.af/`
Full path example: `.af/audit_20250115_143000.log`

## Correctness Properties

### Property 1: Entry Timestamp Ordering

*For any* sequence of audit entries written during a session, the timestamps
SHALL be monotonically non-decreasing (each entry's timestamp >= the previous
entry's timestamp).

**Validates: Requirement 5.1**

### Property 2: Entry Format Compliance

*For any* audit entry, the entry SHALL match the regex pattern
`^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\] \[\w+\] .*`.

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 3: Flush Per Entry

*For any* call to `AuditLogger.log()`, the entry SHALL be flushed to disk
before `log()` returns.

**Validates: Requirement 6.1**

### Property 4: No-Op When Inactive

*For any* call to `AuditLogger.log()` while `active` is False, the method
SHALL perform no I/O and return immediately.

**Validates: Requirement 4.7 (transient exclusion), general behavior**

### Property 5: Start/Stop Bookends

*For any* audit session, the first entry SHALL have type `SYSTEM` containing
"Audit started" and the last entry SHALL have type `SYSTEM` containing
"Audit stopped".

**Validates: Requirements 6.5, 6.6**

### Property 6: Input Classification

*For any* user input starting with `/`, the audit entry SHALL use type
`COMMAND`. For any other non-empty input, the entry SHALL use type `INPUT`.

**Validates: Requirements 3.2, 3.3**

### Property 7: File Creation on Start

*For any* call to `AuditLogger.start()`, a new file SHALL be created with
a filename matching the pattern `audit_\d{8}_\d{6}\.log` in the configured
directory.

**Validates: Requirements 1.3, 1.4, 2.4**

### Property 8: Graceful Failure

*For any* I/O error during `log()`, the system SHALL disable auditing and
log a warning rather than raising an exception to the caller.

**Validates: Requirements 1.E1, 1.E2, 6.E1, 6.E2**

## Error Handling

| Error Condition | System Behavior |
|----------------|-----------------|
| `.af/` directory missing | Create it; if creation fails, warn and skip auditing |
| Audit file cannot be opened | Warn, leave auditing disabled |
| Write fails (disk full) | Warn, disable auditing, no crash |
| File deleted externally | Next write fails, warn, disable auditing |
| `Config.audit=True` but `.af/` unwritable | Warn at startup, continue without auditing |
| `/audit` toggle but logger not wired | Show error: "Audit logger not available." |

## Definition of Done

A task group is complete when ALL of the following are true:

1. All subtasks within the group are checked off (`[x]`)
2. All property tests for the task group pass
3. All previously passing tests still pass (no regressions)
4. No linter warnings or errors introduced
5. Code is committed on a feature branch and pushed to remote
6. Feature branch is merged back to `main`
7. `tasks.md` checkboxes are updated to reflect completion

## Testing Strategy

- **Unit tests**: Test `AuditLogger` in isolation: start/stop lifecycle,
  entry formatting, flush behavior, filename generation, error handling.
- **Unit tests**: Test TUI audit integration with mock logger.
- **Unit tests**: Test REPL input classification (INPUT vs COMMAND labels).
- **Unit tests**: Test `/audit` command toggle behavior.
- **Property-based tests**: Generate arbitrary strings and verify entry format
  compliance (Property 2).
- **Property-based tests**: Generate sequences of log calls and verify
  timestamp ordering (Property 1).
- **Integration tests**: Full session with auditing enabled, verify log file
  content matches expected entries.
- **Integration tests**: Start auditing, write entries, stop, verify file
  is closed and readable.
