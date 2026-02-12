# PRD: Audit Trail

## Description

Keep an "audit trail" of the terminal and agent session. Add a `Config.audit`
field and `/audit` slash command to the library. When enabled, all terminal
output and input (free text, selected slash commands, agent responses, tool
results, etc.) are recorded to a timestamped audit file in the `.af/` directory.
Each block of output written to the file includes a timestamp to preserve
timing history.

## Clarifications

1. **Flag mechanism**: Add `audit: bool = False` to the `Config` dataclass.
   The embedding application sets it programmatically. The `/audit` slash
   command also toggles auditing at runtime.
2. **`/audit` behavior**: Toggle on/off. Enables auditing if off, disables if
   on. Always shows current status and file path.
3. **File format**: Plain text with ISO 8601 timestamps and type labels like
   `[INPUT]`, `[INFO]`, `[TOOL_RESULT]`, `[ERROR]`. Human-readable.
4. **Scope**: Final content only. Skip transient elements (spinner, partial
   streaming chunks). Log finalized agent responses, tool results, commands,
   errors, and user input.
