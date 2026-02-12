# Implementation Plan: Agent Input Requests

<!-- AGENT INSTRUCTIONS
- Implement exactly ONE top-level task group per session
- Follow the git-flow: feature branch from main -> implement -> test -> merge to main -> push
- Update checkbox states as you go: [-] in progress, [x] complete
- Do NOT proceed past a SESSION BOUNDARY marker
- Read .af/steering/coding.md for the full workflow
-->

## Overview

Implementation proceeds in five task groups: (1) add the `INPUT_REQUEST` event
type and stream handler dispatch, (2) implement the approval mode TUI prompt,
(3) implement the choice mode TUI prompt with arrow key navigation, (4)
implement the text input mode, (5) integration tests with a mock agent.
Dependencies are linear: group 1 provides the framework, groups 2-4 implement
each mode, and group 5 validates end-to-end.

## Test Commands

- Unit tests: `uv run pytest -q tests/`
- Property tests: `uv run pytest -q tests/ -k property`
- All tests: `uv run pytest tests/`
- Linter: `uv run ruff check src/ tests/`

## Tasks

- [x] 1. Input Request Event Type and Stream Handler Dispatch
  - [x] 1.1 Add `INPUT_REQUEST` to `StreamEventType` enum
    - Add `INPUT_REQUEST = "input_request"` to `StreamEventType` in `types.py`
    - _Requirements: 1.1_

  - [x] 1.2 Add `_collect_input()` method to `StreamHandler`
    - Private async method that dispatches to TUI based on `input_type`
    - Accepts `prompt`, `input_type`, `choices` parameters
    - Returns `str | dict` (response value)
    - For unknown `input_type`, show error and return `"reject"`
    - _Requirements: 2.3_

  - [x] 1.3 Add `INPUT_REQUEST` branch to `handle_stream()`
    - Stop spinner if active
    - Finalize live text if active (set `live_started = False`)
    - Extract `prompt`, `input_type`, `choices`, `response_future` from event data
    - Guard: if `response_future` is None, log warning and `continue`
    - Call `await self._collect_input(prompt, input_type, choices)`
    - Resolve `response_future.set_result(response)`
    - If response is `"reject"`: show info message, `break`
    - Otherwise: restart spinner and continue loop
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 6.1, 6.3_

  - [x] 1.4 Write unit tests for stream handler INPUT_REQUEST dispatch
    - Mock TUI methods (not yet implemented, use stubs)
    - Test: INPUT_REQUEST with approval -> future resolved, stream continues
    - Test: INPUT_REQUEST with rejection -> future resolved, stream breaks
    - Test: INPUT_REQUEST without response_future -> warning logged, skipped
    - Test: Spinner/live text stopped before prompt
    - Test: Spinner restarted after non-rejection
    - Test: Partial content preserved on rejection
    - Test: Multiple INPUT_REQUESTs handled sequentially
    - **Property 1: Stream Pause Guarantee**
    - **Property 2: Future Resolution Guarantee**
    - **Property 5: Rejection Cancels Stream**
    - **Property 6: UI State Cleanup Before Prompt**
    - **Property 7: History Preservation on Rejection**
    - **Validates: Requirements 2.1-2.5, 6.1-6.5**

  - [x] 1.V Verify task group 1
    - [x] All new tests pass: `uv run pytest -q tests/ -k "input_request"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 1.1, 2.1-2.5, 6.1-6.5 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 1 is complete. Do NOT continue to task group 2 in this session. -->

- [x] 2. Checkpoint - Event Type and Dispatch Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 3. Approval Mode TUI Prompt
  - [x] 3.1 Implement `prompt_approval()` in `TUIShell`
    - Async method: `async def prompt_approval(self, prompt: str, choices: list[str]) -> str`
    - Render prompt text in default style
    - Render `[a] {choices[0]}` in info_color and `[r] {choices[1]}` in error_color
    - Use a dedicated `PromptSession` with `? ` glyph in info_color
    - Accept `a`, `1` for approve; `r`, `2` for reject (case-insensitive)
    - Re-prompt on invalid input with hint
    - Re-prompt on empty input (no default)
    - Handle `KeyboardInterrupt` as reject
    - Return `"approve"` or `"reject"`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 3.2 Wire approval mode in `_collect_input()`
    - Call `self._tui.prompt_approval(prompt, choices)` for `input_type == "approval"`
    - Validate `choices` has exactly 2 items; if not, show error, return `"reject"`
    - _Requirements: 1.4, Edge Case 1.1_

  - [x] 3.3 Write unit tests for `prompt_approval()`
    - Input `a` -> returns `"approve"`
    - Input `1` -> returns `"approve"`
    - Input `r` -> returns `"reject"`
    - Input `2` -> returns `"reject"`
    - Case-insensitive: `A`, `R` work
    - Invalid input then valid -> re-prompts, returns correct value
    - Empty input -> re-prompts
    - KeyboardInterrupt -> returns `"reject"`
    - Custom choice labels rendered correctly
    - **Property 3: Approval Binary Constraint**
    - **Property 8: Re-prompt on Invalid Input**
    - **Validates: Requirements 3.1-3.6, Edge Cases 3.E1, 3.E2**

  - [x] 3.V Verify task group 3
    - [x] All new tests pass: `uv run pytest -q tests/ -k "approval"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 3.1-3.6 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 3 is complete. Do NOT continue to task group 4 in this session. -->

- [x] 4. Checkpoint - Approval Mode Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [x] 5. Choice Mode TUI Prompt
  - [x] 5.1 Implement `prompt_choice()` in `TUIShell`
    - Async method: `async def prompt_choice(self, prompt: str, choices: list[str]) -> str | dict[str, Any]`
    - Render prompt text in default style
    - Render numbered choices: `  1) Choice A` with number in info_color
    - Render `  r) Reject` in error_color
    - Create a dedicated `PromptSession` with custom `KeyBindings`:
      - Up arrow: decrement selected index (wrap to bottom)
      - Down arrow: increment selected index (wrap to top)
      - Number keys `1`-`9`: select directly (if in range)
      - `r` key: reject
      - Enter: confirm current selection
    - Highlighted choice shown with `▸` prefix and bold style
    - Non-highlighted choices shown with `  ` prefix
    - Handle `KeyboardInterrupt` as reject
    - Return `{"index": N, "value": "choice text"}` or `"reject"`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 5.2 Wire choice mode in `_collect_input()`
    - Call `self._tui.prompt_choice(prompt, choices)` for `input_type == "choice"`
    - Validate `choices` has at least 2 items; if not, show error, return `"reject"`
    - _Requirements: 1.5, Edge Case 1.1_

  - [x] 5.3 Write unit tests for `prompt_choice()`
    - Numeric input `1` with 3 choices -> returns `{"index": 0, "value": "..."}`
    - Numeric input `3` with 3 choices -> returns `{"index": 2, "value": "..."}`
    - Input `r` -> returns `"reject"`
    - Out-of-range number -> re-prompts
    - Non-numeric input -> re-prompts
    - Single choice (1 item) -> still works with numbered list
    - KeyboardInterrupt -> returns `"reject"`
    - **Property 4: Choice Index Validity**
    - **Property 8: Re-prompt on Invalid Input**
    - **Validates: Requirements 4.1-4.8, Edge Cases 4.E1, 4.E2, 4.E3**

  - [x] 5.4 Write unit tests for arrow key navigation
    - Down arrow changes selection index
    - Up arrow changes selection index
    - Arrow wrap-around at boundaries
    - Enter confirms current highlighted choice
    - Number key overrides arrow selection
    - **Validates: Requirements 4.4, 4.8**

  - [x] 5.V Verify task group 5
    - [x] All new tests pass: `uv run pytest -q tests/ -k "choice"`
    - [x] All existing tests still pass: `uv run pytest tests/`
    - [x] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [x] Requirements 4.1-4.8 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 5 is complete. Do NOT continue to task group 6 in this session. -->

- [x] 6. Checkpoint - Choice Mode Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 7. Text Input Mode
  - [ ] 7.1 Implement `prompt_text_input()` in `TUIShell`
    - Async method: `async def prompt_text_input(self, prompt: str) -> str`
    - Render prompt text in default style
    - Render hint in dim: `(type r or /reject to abort)`
    - Use `PromptSession` with `? ` glyph in info_color
    - Accept any non-empty string as valid
    - If input is exactly `r` or `/reject`, return `"reject"`
    - Re-prompt on empty input with hint
    - Handle `KeyboardInterrupt` as reject
    - Return input string or `"reject"`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 7.2 Wire text mode in `_collect_input()`
    - Call `self._tui.prompt_text_input(prompt)` for `input_type == "text"`
    - _Requirements: 1.6_

  - [ ] 7.3 Write unit tests for `prompt_text_input()`
    - Valid text input -> returns input string
    - Input `r` -> returns `"reject"`
    - Input `/reject` -> returns `"reject"`
    - Empty input -> re-prompts
    - KeyboardInterrupt -> returns `"reject"`
    - Multi-word input preserved
    - **Property 8: Re-prompt on Invalid Input**
    - **Validates: Requirements 5.1-5.6, Edge Cases 5.E1, 5.E2**

  - [ ] 7.V Verify task group 7
    - [ ] All new tests pass: `uv run pytest -q tests/ -k "text_input"`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] Requirements 5.1-5.6 acceptance criteria met

<!-- SESSION BOUNDARY: Task group 7 is complete. Do NOT continue to task group 8 in this session. -->

- [ ] 8. Checkpoint - Text Input Mode Complete
  - Ensure all tests pass, ask the user if questions arise.

<!-- SESSION BOUNDARY -->

- [ ] 9. Integration Tests and End-to-End Validation
  - [ ] 9.1 Create mock agent that yields INPUT_REQUEST events
    - Async generator that yields TEXT_DELTA, then INPUT_REQUEST, then
      more TEXT_DELTA (if approved)
    - Support all three input modes
    - _Requirements: all_

  - [ ] 9.2 Write integration test: approval flow (approve path)
    - Mock agent yields text, then approval request
    - User approves -> agent continues, more text yielded
    - Verify complete conversation turn with all text content
    - **Property 1: Stream Pause Guarantee**
    - **Property 2: Future Resolution Guarantee**
    - **Validates: Requirements 2.3-2.5, 3.5**

  - [ ] 9.3 Write integration test: approval flow (reject path)
    - Mock agent yields text, then approval request
    - User rejects -> stream cancelled
    - Verify partial conversation turn, history preserved
    - **Property 5: Rejection Cancels Stream**
    - **Property 7: History Preservation on Rejection**
    - **Validates: Requirements 6.1-6.5**

  - [ ] 9.4 Write integration test: choice flow
    - Mock agent yields choice request with 3 options
    - User selects option 2
    - Verify agent receives `{"index": 1, "value": "..."}`, continues
    - **Property 4: Choice Index Validity**
    - **Validates: Requirements 4.6**

  - [ ] 9.5 Write integration test: text input flow
    - Mock agent yields text input request
    - User provides free-text answer
    - Verify agent receives exact text, continues
    - **Validates: Requirements 5.4**

  - [ ] 9.6 Write integration test: multiple input requests
    - Mock agent yields two sequential INPUT_REQUEST events
    - Both handled correctly, stream completes
    - **Validates: Edge Case 2.E2**

  - [ ] 9.7 Write property-based tests
    - Generate arbitrary choice lists (2-20 items), verify index range in
      response (Property 4)
    - Generate approval requests, verify response is always binary
      (Property 3)
    - **Validates: Properties 3, 4**

  - [ ] 9.8 Update existing stream_handler tests
    - Ensure existing tests still pass with new event type in enum
    - Verify unknown event types are silently ignored
    - _Requirements: all_

  - [ ] 9.V Verify task group 9
    - [ ] All new tests pass: `uv run pytest -q tests/`
    - [ ] All existing tests still pass: `uv run pytest tests/`
    - [ ] No linter warnings introduced: `uv run ruff check src/ tests/`
    - [ ] All 8 correctness properties validated by tests

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
| 1.1 (INPUT_REQUEST enum) | 1.1 | 1.4 |
| 1.2 (event data schema) | 1.3 | 1.4 |
| 1.3 (three input_type values) | 1.2 | 1.4 |
| 1.4 (approval choices = 2) | 3.2 | 3.3 |
| 1.5 (choice choices >= 2) | 5.2 | 5.3 |
| 1.6 (text choices empty) | 7.2 | 7.3 |
| 2.1 (stop spinner) | 1.3 | 1.4 |
| 2.2 (finalize live text) | 1.3 | 1.4 |
| 2.3 (render prompt, collect input) | 1.2, 1.3 | 1.4 |
| 2.4 (resolve future) | 1.3 | 1.4, 9.2 |
| 2.5 (continue on non-reject) | 1.3 | 1.4, 9.2 |
| 2.6 (agent awaits future) | agent plugin | 9.2 |
| 3.1 (approval display) | 3.1 | 3.3 |
| 3.2 (approval colors) | 3.1 | 3.3 |
| 3.3 (accept a/1) | 3.1 | 3.3 |
| 3.4 (accept r/2) | 3.1 | 3.3 |
| 3.5 (approve response) | 3.1 | 3.3, 9.2 |
| 3.6 (reject response + cancel) | 3.1 | 3.3, 9.3 |
| 4.1 (choice display numbered) | 5.1 | 5.3 |
| 4.2 (choice number color) | 5.1 | 5.3 |
| 4.3 (numeric input) | 5.1 | 5.3 |
| 4.4 (arrow key navigation) | 5.1 | 5.4 |
| 4.5 (reject option) | 5.1 | 5.3 |
| 4.6 (choice response dict) | 5.1 | 5.3, 9.4 |
| 4.7 (choice reject + cancel) | 5.1 | 5.3 |
| 4.8 (highlight current) | 5.1 | 5.4 |
| 5.1 (text display) | 7.1 | 7.3 |
| 5.2 (text prompt glyph) | 7.1 | 7.3 |
| 5.3 (non-empty input) | 7.1 | 7.3 |
| 5.4 (text response) | 7.1 | 7.3, 9.5 |
| 5.5 (reject hint) | 7.1 | 7.3 |
| 5.6 (r or /reject aborts) | 7.1 | 7.3 |
| 6.1 (reject breaks loop) | 1.3 | 1.4, 9.3 |
| 6.2 (partial turn finalized) | 1.3 | 1.4, 9.3 |
| 6.3 (rejection info message) | 1.3 | 1.4, 9.3 |
| 6.4 (history preserved) | 1.3 | 1.4, 9.3 |
| 6.5 (return to REPL prompt) | 1.3 | 9.3 |

## Notes

- The `asyncio.Future` approach requires no changes to the `AgentPlugin`
  protocol signature. The `send_message()` return type remains
  `AsyncIterator[StreamEvent]`. The future is carried inside the event data
  dict.
- Arrow key navigation for choice mode uses a dedicated `PromptSession` with
  custom `KeyBindings`, not the main REPL prompt session. This avoids
  interference with the existing key bindings (Ctrl+Y, etc.).
- The choice mode prompt re-renders the choice list on each arrow key press
  using Rich console output. This is a simple print-based approach (no
  Rich Live needed).
- Agent plugins that don't need input requests are unaffected. The new
  `StreamEventType` member is simply never yielded.
- The `response_future` is created by the agent plugin, not the framework.
  This keeps the control flow simple: the agent owns the future and awaits
  it.
