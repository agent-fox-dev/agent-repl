# Requirements Document

## Introduction

This specification covers two enhancements to the agent-repl TUI's tool display:
(1) showing detailed tool input alongside tool invocation messages, and
(2) replacing boxed tool output with dim/grey collapsible text.

## Glossary

| Term | Definition |
|------|------------|
| Tool invocation | The moment an agent begins using a tool, rendered as a `TOOL_USE_START` stream event |
| Tool result | The output returned after a tool completes, rendered as a `TOOL_RESULT` stream event |
| Compact summary | A one-line key=value representation of a tool's input parameters |
| Collapsed output | Tool output truncated to a fixed number of lines with a hint showing how many lines are hidden |
| Expand | The action of viewing the full output of a previously collapsed tool result |
| Panel | A Rich library `Panel` widget that draws a bordered box around content |

## Requirements

### Requirement 1: Enhanced Tool Invocation Display

**User Story:** As a user, I want to see what a tool is doing (not just its name) so that I can understand the agent's actions without inspecting logs.

#### Acceptance Criteria

1. WHEN a `TOOL_USE_START` event is received, THE TUI SHALL display the tool name on one line (e.g., "Using tool: bash") followed by a compact summary of the tool input on a subsequent line.
2. THE compact summary SHALL display input parameters as `key: value` pairs, separated by two spaces, on a single line.
3. WHEN an input value exceeds 60 characters, THE TUI SHALL truncate it to 60 characters and append an ellipsis ("...").
4. THE compact summary line SHALL be styled as dim text to visually distinguish it from the tool name line.
5. WHEN the tool input is empty, THE TUI SHALL display only the tool name line without a summary line.
6. THE `TOOL_USE_START` stream event data SHALL include the tool input dictionary alongside the tool name.

#### Edge Cases

1. IF the tool input contains no keys, THEN THE TUI SHALL omit the compact summary line entirely.
2. IF a tool input value is `null` or an empty string, THEN THE TUI SHALL display the key with an empty value (e.g., `key: ""`).
3. IF the tool input contains nested objects, THEN THE TUI SHALL display the top-level key with a truncated JSON string as the value.

---

### Requirement 2: Tool Output Color Styling

**User Story:** As a user, I want tool output visually separated from assistant text without heavy box borders so that the output is less noisy and easier to scan.

#### Acceptance Criteria

1. WHEN a tool result is displayed, THE TUI SHALL render the output text in dim style (Rich "dim" style) instead of inside a Rich Panel.
2. THE TUI SHALL display a header line above the tool output containing the tool name with a success icon ("checkmark") or error icon ("cross"), styled with the appropriate theme color (info_color for success, error_color for errors).
3. THE TUI SHALL NOT use a Rich `Panel` (bordered box) for tool result rendering.
4. THE tool output color scheme SHALL be `dim` for normal tool output text.

#### Edge Cases

1. IF the tool result is an empty string, THEN THE TUI SHALL display only the header line with no output body.
2. IF the tool result contains Rich markup characters, THEN THE TUI SHALL render them as literal text (no markup interpretation).

---

### Requirement 3: Collapsible Tool Output

**User Story:** As a user, I want long tool outputs collapsed to a few lines so that I can follow the agent's progress without being overwhelmed by verbose output.

#### Acceptance Criteria

1. WHEN a non-error tool result exceeds 3 lines, THE TUI SHALL display only the first 3 lines of output followed by a collapse hint.
2. THE collapse hint SHALL display the number of hidden lines in dim style (e.g., "... 47 more lines").
3. THE collapse hint SHALL use a right-pointing triangle character as a visual indicator (e.g., "▸ 47 more lines").
4. WHEN a tool result is 3 lines or fewer, THE TUI SHALL display the full output without a collapse hint.
5. WHILE displaying an error tool result (is_error=True), THE TUI SHALL always display the full output regardless of line count.
6. THE TUI SHALL store the full text of each collapsed tool result for later retrieval.
7. THE stored collapsed results SHALL be indexed sequentially (most recent = last) within the current session.

#### Edge Cases

1. IF the tool result contains exactly 3 lines, THEN THE TUI SHALL display all 3 lines without a collapse hint.
2. IF the tool result contains only whitespace lines beyond the first 3, THEN THE TUI SHALL still count them and show the collapse hint.
3. IF the collapsed output contains 1 hidden line, THEN THE hint SHALL read "▸ 1 more line" (singular).

---

### Requirement 4: Expand via Keyboard Shortcut

**User Story:** As a user, I want to quickly view the full output of a collapsed tool result using a keyboard shortcut so that I can inspect details without leaving the prompt.

#### Acceptance Criteria

1. THE TUI SHALL bind `Ctrl+O` as a keyboard shortcut to expand the most recently collapsed tool result.
2. WHEN the user presses `Ctrl+O`, THE TUI SHALL display the full output of the most recently collapsed tool result in dim style.
3. THE `Ctrl+O` key binding SHALL be registered in `TUIShell.__init__()` alongside the existing `Ctrl+Y` binding, using the prompt_toolkit `KeyBindings` API.
4. THE expanded output SHALL be rendered in dim style, consistent with normal tool output rendering.
5. WHEN the user presses `Ctrl+O` and there are no stored collapsed results, THE TUI SHALL display an informational message: "No collapsed output to expand."
6. THE collapse hint line SHALL include a reference to the shortcut (e.g., "▸ 47 more lines (Ctrl+O to expand)").

#### Edge Cases

1. IF multiple tool results have been collapsed, THEN `Ctrl+O` SHALL expand the most recent one only.
2. IF `Ctrl+O` is pressed while the agent is streaming a response, THEN THE TUI SHALL ignore the keypress (no action taken during active streaming).
