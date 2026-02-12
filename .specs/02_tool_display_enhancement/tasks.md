# Implementation Plan: Tool Display Enhancement

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from main -> implement -> test -> merge to main -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

Implementation proceeds in four task groups: (1) include tool input in events
and render the compact summary, (2) replace Panel with dim text and add collapse
logic, (3) add the `Ctrl+O` expand shortcut, (4) integration tests and cleanup.
Dependencies flow linearly: task group 1 provides data for 2, and 2 provides
stored results for 3.

## Test Commands

- Unit tests: `uv run pytest -q tests/`
- Property tests: `uv run pytest -q tests/ -k property`
- All tests: `uv run pytest tests/`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [x] 1. Enhanced Tool Invocation Display
  - [x] 1.1 Include tool input in TOOL_USE_START event
    - In `claude_agent.py:_translate_message()`, add `block.input` to the
      `TOOL_USE_START` event data dict (default to `{}` if attr missing)
    - _Requirements: 1.6_

  - [x] 1.2 Implement `_format_compact_summary()` helper
    - Add module-level function in `tui.py`
    - Input: `dict[str, Any]` -> Output: `str`
    - Format each key-value pair as `key: value`, separated by two spaces
    - Truncate values > 60 chars with "..."
    - Serialize nested objects to JSON before truncating
    - Return empty string for empty dict
    - Handle None values as empty string `""`
    - _Requirements: 1.2, 1.3, Edge Cases 1.1, 1.2, 1.3_

  - [x] 1.3 Add `show_tool_use()` method to `TUIShell`
    - Render "Using tool: {name}" in info_color
    - If input is non-empty, render compact summary on next line in dim style
    - _Requirements: 1.1, 1.4, 1.5_

  - [x] 1.4 Update `stream_handler.py` to use `show_tool_use()`
    - Change `TOOL_USE_START` handling to extract `input` from event data
    - Call `self._tui.show_tool_use(name, tool_input)` instead of
      `self._tui.show_info(f"Using tool: {name}")`
    - _Requirements: 1.1_

  - [x] 1.5 Write unit tests for `_format_compact_summary()`
    - Empty dict -> empty string
    - Single key -> "key: value"
    - Multiple keys -> "key1: val1  key2: val2"
    - Long value (>60 chars) -> truncated with "..."
    - None value -> `key: ""`
    - Nested dict -> JSON-serialized and truncated
    - **Property 2: Compact Summary Completeness**
    - **Property 3: Value Truncation Bound**
    - **Validates: Requirements 1.2, 1.3**

  - [x] 1.6 Write unit tests for `show_tool_use()`
    - Verify tool name line rendered
    - Verify compact summary line rendered for non-empty input
    - Verify no summary line for empty input
    - **Property 9: Empty Input Omission**
    - **Validates: Requirements 1.1, 1.4, 1.5**

  - [x] 1.V Verify task group 1
    - [x] All new tests pass: `uv run pytest -q tests/ -k "tool_use or compact_summary"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 1.1-1.6 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [x] 2. Checkpoint - Tool Invocation Display Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 3. Dim Tool Output with Collapsible Results
  - [x] 3.1 Add `_collapsed_results` state to `TUIShell.__init__()`
    - `self._collapsed_results: list[str] = []`
    - _Requirements: 3.6, 3.7_

  - [x] 3.2 Modify `show_tool_result()` to use dim text instead of Panel
    - Remove `Panel` import usage for tool results
    - Render header line: icon + tool name in themed color
    - Render result body in dim style
    - For non-error results > 3 lines: show first 3 lines + collapse hint,
      store full result in `_collapsed_results`
    - For error results: always show full output
    - For empty results: show header only
    - Handle Rich markup in result text (escape or use highlight=False)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 3.3 Add `clear_collapsed_results()` method
    - Called when session is cleared (integrate with `/clear` command)
    - _Requirements: 3.7_

  - [x] 3.4 Write unit tests for dim tool output rendering
    - Short result (<=3 lines) -> full output in dim style, no hint
    - Long result (>3 lines) -> 3 lines + collapse hint
    - Error result (>3 lines) -> full output, no collapse
    - Empty result -> header only
    - Exactly 3 lines -> no collapse
    - Verify no Panel instantiation
    - **Property 4: No Panel Usage**
    - **Property 5: Collapse Threshold**
    - **Property 6: Error Output Completeness**
    - **Validates: Requirements 2.1-2.4, 3.1-3.5**

  - [x] 3.5 Write unit tests for collapsed result storage
    - Verify full text stored on collapse
    - Verify storage grows with each collapse
    - Verify clear resets storage
    - **Property 7: Collapsed Storage Integrity**
    - **Validates: Requirements 3.6, 3.7**

  - [x] 3.V Verify task group 3
    - [x] All new tests pass: `uv run pytest -q tests/ -k "tool_result or collapsed"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 2.1-2.4, 3.1-3.7 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [x] 4. Checkpoint - Dim Output and Collapse Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 5. Ctrl+O Expand Shortcut
  - [x] 5.1 Add `Ctrl+O` key binding in `TUIShell.__init__()`
    - Add `@self._kb.add("c-o")` handler alongside existing `Ctrl+Y` binding
    - If `_collapsed_results` is non-empty, call `show_expanded_result()`
    - If empty, show info message: "No collapsed output to expand."
    - Guard against activation during active streaming (`_live_active` or
      `_spinner_active`)
    - _Requirements: 4.1, 4.2, 4.3, 4.5, Edge Cases 4.1, 4.2_

  - [x] 5.2 Implement `show_expanded_result()` method
    - Display the last element of `_collapsed_results` in dim style
    - _Requirements: 4.2, 4.4_

  - [x] 5.3 Update collapse hint to reference shortcut
    - Change hint format to include "(Ctrl+O to expand)"
    - e.g., "▸ 47 more lines (Ctrl+O to expand)"
    - _Requirements: 4.6_

  - [x] 5.4 Write unit tests for `Ctrl+O` expand behavior
    - No collapsed results -> info message
    - Single collapsed result -> shows full output in dim style
    - Multiple collapsed results -> shows most recent only
    - Verify expanded output uses dim style
    - Verify no action during streaming (if testable)
    - **Property 8: Expand Index Validity**
    - **Validates: Requirements 4.1-4.6**

  - [x] 5.V Verify task group 5
    - [x] All new tests pass: `uv run pytest -q tests/ -k "expand"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 4.1-4.6 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 5 is complete. Do NOT continue to task group 6 in this session. -->

- [ ] 6. Checkpoint - Expand Shortcut Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 7. Integration Tests and Cleanup
  - [ ] 7.1 Write integration test: full stream with tool input display
    - Simulate TOOL_USE_START with input data flowing through stream_handler
    - Verify TUI receives correct name + input
    - **Property 1: Tool Input Inclusion**
    - **Validates: Requirements 1.1, 1.6**

  - [ ] 7.2 Write integration test: stream with collapsible output
    - Simulate TOOL_RESULT with >3 lines flowing through stream_handler
    - Verify collapse behavior end-to-end
    - **Validates: Requirements 3.1-3.4**

  - [ ] 7.3 Write property-based tests with Hypothesis
    - Arbitrary dicts for compact summary (Property 2, 3)
    - Arbitrary multi-line strings for collapse threshold (Property 5)
    - **Validates: Properties 2, 3, 5**

  - [ ] 7.4 Update existing tests for new rendering
    - Fix any tests that assert Panel-based output
    - Ensure stream_handler tests reflect new show_tool_use() call
    - _Requirements: all_

  - [ ] 7.V Verify task group 7
    - [ ] All new tests pass: `uv run pytest -q tests/`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] All 9 correctness properties validated by tests

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
| 1.1 (tool name + summary display) | 1.3, 1.4 | 1.6 |
| 1.2 (compact key: value format) | 1.2 | 1.5 |
| 1.3 (truncation at 60 chars) | 1.2 | 1.5 |
| 1.4 (dim summary line) | 1.3 | 1.6 |
| 1.5 (omit empty input) | 1.3 | 1.6 |
| 1.6 (input in event data) | 1.1 | 7.1 |
| 2.1 (dim style output) | 3.2 | 3.4 |
| 2.2 (header with icon) | 3.2 | 3.4 |
| 2.3 (no Panel) | 3.2 | 3.4 |
| 2.4 (dim color scheme) | 3.2 | 3.4 |
| 3.1 (collapse >3 lines) | 3.2 | 3.4 |
| 3.2 (hint with line count) | 3.2 | 3.4 |
| 3.3 (triangle indicator) | 3.2 | 3.4 |
| 3.4 (full display <=3 lines) | 3.2 | 3.4 |
| 3.5 (errors never collapsed) | 3.2 | 3.4 |
| 3.6 (store collapsed text) | 3.1, 3.2 | 3.5 |
| 3.7 (sequential indexing) | 3.1 | 3.5 |
| 4.1 (Ctrl+O binding) | 5.1 | 5.4 |
| 4.2 (expand most recent) | 5.1, 5.2 | 5.4 |
| 4.3 (registered in KeyBindings) | 5.1 | 5.4 |
| 4.4 (dim expanded output) | 5.2 | 5.4 |
| 4.5 (no results message) | 5.1 | 5.4 |
| 4.6 (hint references Ctrl+O) | 5.3 | 5.4 |

## Notes

- The `Panel` import in `tui.py` may still be needed for other uses; only remove
  it if tool results were the sole user.
- The `Ctrl+O` binding lives in `tui.py` alongside the existing `Ctrl+Y`
  binding, keeping all keyboard shortcuts co-located.
- Collapsed result storage is per-session and lives on the `TUIShell` instance.
  It is cleared alongside conversation history via `/clear`.
