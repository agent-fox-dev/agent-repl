# Requirements Document

## Introduction

This specification adds an audit trail feature to agent-repl. When enabled,
all user input and system output is recorded to a timestamped plain-text log
file in the `.af/` directory. Auditing can be enabled via the `Config.audit`
field at startup or toggled at runtime with the `/audit` slash command.

## Glossary

| Term | Definition |
|------|------------|
| Audit trail | A chronological record of all user inputs and system outputs during a session |
| Audit log | The plain-text file where audit entries are written |
| Audit entry | A single timestamped line in the audit log with a type label and content |
| Entry type | A label classifying the audit entry (e.g., `INPUT`, `INFO`, `ERROR`) |
| Audit session | The period between audit start and audit stop (or application exit) |

## Requirements

### Requirement 1: Audit Configuration

**User Story:** As a library consumer, I want to enable auditing via configuration so that I can activate the audit trail when launching my application.

#### Acceptance Criteria

1. THE `Config` dataclass SHALL include an `audit` field of type `bool` with a default value of `False`.
2. WHEN `Config.audit` is `True`, THE application SHALL start auditing automatically during `App._setup()`.
3. WHEN auditing starts, THE system SHALL create a new audit log file in the `.af/` directory.
4. THE audit log filename SHALL follow the pattern `audit_YYYYMMDD_HHMMSS.log` using the local timestamp of when auditing started.
5. IF the `.af/` directory does not exist, THEN THE system SHALL create it before writing the audit file.

#### Edge Cases

1. IF the `.af/` directory cannot be created (permissions), THEN THE system SHALL log a warning and continue without auditing.
2. IF the audit file cannot be opened for writing, THEN THE system SHALL log a warning and disable auditing.

---

### Requirement 2: Audit Slash Command

**User Story:** As a user, I want to toggle auditing on and off during my session with a `/audit` command so that I can start recording when needed.

#### Acceptance Criteria

1. THE system SHALL register an `/audit` slash command in `BuiltinCommandsPlugin`.
2. WHEN the user invokes `/audit` AND auditing is off, THE system SHALL start auditing and display: "Audit started: {file_path}".
3. WHEN the user invokes `/audit` AND auditing is on, THE system SHALL stop auditing and display: "Audit stopped: {file_path}".
4. WHEN auditing is toggled on via `/audit`, THE system SHALL create a new audit log file (not append to an existing one).
5. WHEN auditing is toggled off via `/audit`, THE system SHALL close the audit file and flush all pending writes.
6. THE `/audit` command SHALL also be CLI-exposed (`cli_exposed=True`).

#### Edge Cases

1. IF `/audit` is invoked and the file cannot be created, THEN THE system SHALL display an error message and leave auditing disabled.

---

### Requirement 3: Input Recording

**User Story:** As a user reviewing the audit trail, I want to see every input I provided during the session, including free text and slash commands.

#### Acceptance Criteria

1. WHILE auditing is active, THE system SHALL record every user input returned by `prompt_input()` as an audit entry.
2. WHEN the user submits free text, THE audit entry SHALL use the type label `INPUT`.
3. WHEN the user submits a slash command, THE audit entry SHALL use the type label `COMMAND`.
4. THE input entry SHALL contain the exact raw text the user typed.

#### Edge Cases

1. IF the user submits empty input (whitespace only), THEN THE system SHALL NOT record an audit entry (consistent with parse_input returning None).

---

### Requirement 4: Output Recording

**User Story:** As a user reviewing the audit trail, I want to see all system output so that I can reconstruct what happened during the session.

#### Acceptance Criteria

1. WHILE auditing is active AND `show_info()` is called, THE system SHALL record the text with type label `INFO`.
2. WHILE auditing is active AND `show_error()` is called, THE system SHALL record the text with type label `ERROR`.
3. WHILE auditing is active AND `show_warning()` is called, THE system SHALL record the text with type label `WARNING`.
4. WHILE auditing is active AND `show_tool_result()` is called, THE system SHALL record the tool name, error status, and result text with type label `TOOL_RESULT`.
5. WHILE auditing is active AND `finalize_live_text()` is called, THE system SHALL record the complete accumulated streaming text with type label `AGENT`.
6. WHILE auditing is active AND `show_banner()` is called, THE system SHALL record the banner information with type label `SYSTEM`.
7. THE system SHALL NOT record transient output: spinner start/stop, partial streaming text chunks (append_live_text), or start_live_text.

#### Edge Cases

1. IF the output text is empty, THEN THE system SHALL still record the entry with an empty content field.
2. IF the output text contains multiple lines, THEN THE system SHALL record all lines as a single entry (multiline entries are allowed).

---

### Requirement 5: Timestamp Format

**User Story:** As a user analyzing the audit trail, I want precise timestamps on every entry so that I can reconstruct the timing of events.

#### Acceptance Criteria

1. EACH audit entry SHALL begin with an ISO 8601 timestamp in the format `[YYYY-MM-DDTHH:MM:SS.mmm]` using local time with millisecond precision.
2. THE timestamp SHALL be followed by a space, the type label in square brackets, a space, and the content.
3. THE complete entry format SHALL be: `[{timestamp}] [{type}] {content}`.

#### Edge Cases

1. IF the system clock changes during a session (e.g., NTP sync), THEN timestamps SHALL still reflect the current system time (no monotonic guarantee needed).

---

### Requirement 6: Audit File Lifecycle

**User Story:** As a user, I want the audit file to be properly managed so that no data is lost.

#### Acceptance Criteria

1. THE system SHALL flush writes to the audit file after each entry (no buffering across entries).
2. WHEN the application exits normally (via `/quit` or EOF), THE system SHALL close the audit file if auditing is active.
3. WHEN the application exits abnormally (exception or signal), THE system SHALL attempt to close the audit file via cleanup.
4. THE audit file SHALL be opened in append mode so that partial writes from crashes are preserved.
5. WHEN auditing starts, THE system SHALL write a `[SYSTEM] Audit started` entry as the first line.
6. WHEN auditing stops, THE system SHALL write a `[SYSTEM] Audit stopped` entry as the last line before closing.

#### Edge Cases

1. IF a write to the audit file fails (disk full, I/O error), THEN THE system SHALL log a warning and disable auditing gracefully (no crash).
2. IF the audit file is deleted externally while auditing is active, THEN THE next write attempt SHALL fail and auditing SHALL be disabled with a warning.
