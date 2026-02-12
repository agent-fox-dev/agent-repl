# PRD: Tool Display Enhancement

## Description

Two improvements to how tool usage is displayed in the agent-repl TUI:

1. **Enhanced tool invocation display**: When the agent uses a tool, the TUI
   currently only shows "Using tool: bash". This does not explain what the agent
   is actually doing. The display should include a compact summary of the tool
   input on a new line (e.g., "Using tool: bash" followed by "command: ls -la").

2. **Improved tool output display**: Tool output is currently displayed inside a
   Rich Panel (box with borders). Replace this with dim/grey text (no box) for
   visual separation. If the output exceeds 3 lines, only show the first 3 lines
   and collapse the rest with an expandable hint showing how many lines are hidden.

## Clarifications

1. **Non-bash tool inputs**: Display as a compact one-line summary of all input
   fields (e.g., `edit: file.py old="foo" new="bar"`).
2. **Expand mechanism**: Truncate + hint approach. Show first N lines, then a
   dim "N more lines" hint. User can view full output via a `/expand` command.
3. **Output color**: Dim/grey text - visually recedes, clearly distinct from
   assistant text.
4. **Error output**: Always show full error output without collapsing. Errors
   are important and should never be truncated.
