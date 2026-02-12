# Requirements Document

## Introduction

This specification adds support for agent-initiated input requests during
streaming. Agents can pause their response stream to ask the user for approval,
present a list of choices, or request free-text input. The user's response is
communicated back to the agent, which then continues or aborts based on the
answer.

## Glossary

| Term | Definition |
|------|------------|
| Input request | An event emitted by an agent during streaming that pauses the stream and prompts the user for input |
| Approval mode | A binary input request with exactly two options: approve or reject |
| Choice mode | An input request presenting a numbered list of options for the user to select from |
| Text mode | An input request prompting the user for free-form text input |
| Response future | An `asyncio.Future` object carried in the event data that the stream handler resolves with the user's response |
| Stream pause | The state where the async generator is suspended awaiting the response future |
| Rejection | The user declining an approval or choice request, which cancels the current stream |

## Requirements

### Requirement 1: Input Request Event Type

**User Story:** As a framework developer, I want a protocol-level mechanism for agents to request user input during streaming, so that any agent plugin can pause and ask the user for feedback.

#### Acceptance Criteria

1. THE `StreamEventType` enum SHALL include an `INPUT_REQUEST` member with value `"input_request"`.
2. WHEN an agent needs user input, THE agent plugin SHALL yield a `StreamEvent` with type `INPUT_REQUEST` and a data dict containing: `prompt` (str), `input_type` (str: `"approval"`, `"choice"`, or `"text"`), `choices` (list[str], required for approval and choice types), and `response_future` (asyncio.Future).
3. THE `input_type` field SHALL accept exactly three values: `"approval"`, `"choice"`, and `"text"`.
4. WHEN `input_type` is `"approval"`, THE `choices` list SHALL contain exactly two items (the approve label and the reject label).
5. WHEN `input_type` is `"choice"`, THE `choices` list SHALL contain at least two items.
6. WHEN `input_type` is `"text"`, THE `choices` list SHALL be empty or omitted.

#### Edge Cases

1. IF the `choices` list is empty AND `input_type` is `"approval"` or `"choice"`, THEN THE stream handler SHALL treat it as an error and display an error message.
2. IF the `response_future` is missing from the event data, THEN THE stream handler SHALL skip the input request and log a warning.

---

### Requirement 2: Stream Pause and Resume

**User Story:** As a user, I want the agent's stream to pause while I make a selection, so that the agent waits for my input before continuing.

#### Acceptance Criteria

1. WHEN the stream handler encounters an `INPUT_REQUEST` event, THE stream handler SHALL stop the spinner if active.
2. WHEN the stream handler encounters an `INPUT_REQUEST` event AND live text is active, THE stream handler SHALL finalize the live text before prompting.
3. WHEN the stream handler encounters an `INPUT_REQUEST` event, THE stream handler SHALL render the prompt and collect user input via the TUI.
4. WHEN the user provides a response, THE stream handler SHALL resolve the `response_future` with the user's response value.
5. WHEN the response future is resolved with a non-rejection value, THE stream handler SHALL continue iterating the event stream (the agent's async generator resumes).
6. THE agent's async generator SHALL await the `response_future` after yielding the `INPUT_REQUEST` event to pause until the user responds.

#### Edge Cases

1. IF the user presses Ctrl+C during an input prompt, THEN THE stream handler SHALL treat it as a rejection and cancel the stream.
2. IF the stream handler receives multiple `INPUT_REQUEST` events in a single stream, THEN THE stream handler SHALL handle each one sequentially.

---

### Requirement 3: Approval Mode

**User Story:** As a user, I want to approve or reject an agent's proposed action with a simple binary choice, so that I can control what the agent does.

#### Acceptance Criteria

1. WHEN an `INPUT_REQUEST` event has `input_type` of `"approval"`, THE TUI SHALL display the prompt text followed by two options: the approve label and the reject label.
2. THE TUI SHALL render the approval prompt with the approve option styled in info_color and the reject option styled in error_color.
3. THE TUI SHALL accept the input `a` or `1` to select the approve option.
4. THE TUI SHALL accept the input `r` or `2` to select the reject option.
5. WHEN the user selects the approve option, THE stream handler SHALL resolve the response future with the string `"approve"`.
6. WHEN the user selects the reject option, THE stream handler SHALL resolve the response future with the string `"reject"` and cancel the stream.

#### Edge Cases

1. IF the user enters an unrecognized input during approval, THEN THE TUI SHALL re-prompt with a hint showing valid inputs.
2. IF the user presses Enter without input during approval, THEN THE TUI SHALL re-prompt (no default selection).

---

### Requirement 4: Choice Mode

**User Story:** As a user, I want to select from a numbered list of options by typing a number or using arrow keys, so that I can choose precisely among the agent's suggestions.

#### Acceptance Criteria

1. WHEN an `INPUT_REQUEST` event has `input_type` of `"choice"`, THE TUI SHALL display the prompt text followed by a numbered list of choices (1-indexed).
2. THE choices SHALL be displayed with their number prefix in info_color and the choice text in default style.
3. THE TUI SHALL accept a numeric input (1 to N) to select the corresponding choice.
4. THE TUI SHALL support arrow key navigation (Up/Down) to highlight a choice, confirmed with Enter.
5. THE TUI SHALL display a reject option labeled `r) Reject` below the numbered choices.
6. WHEN the user selects a numbered choice, THE stream handler SHALL resolve the response future with a dict containing `"index"` (0-based int) and `"value"` (the choice string).
7. WHEN the user selects reject, THE stream handler SHALL resolve the response future with the string `"reject"` and cancel the stream.
8. WHILE the user navigates with arrow keys, THE TUI SHALL visually highlight the currently selected choice (e.g., with a pointer indicator or bold styling).

#### Edge Cases

1. IF the user enters a number outside the valid range (1-N), THEN THE TUI SHALL re-prompt with a hint showing the valid range.
2. IF the user enters non-numeric, non-`r` input, THEN THE TUI SHALL re-prompt with a hint.
3. IF the choices list contains exactly one item, THEN THE TUI SHALL still display it as a numbered list with a reject option.

---

### Requirement 5: Text Input Mode

**User Story:** As a user, I want to type a free-form response when the agent asks for clarification, so that I can provide detailed input.

#### Acceptance Criteria

1. WHEN an `INPUT_REQUEST` event has `input_type` of `"text"`, THE TUI SHALL display the prompt text followed by a text input prompt.
2. THE text input prompt SHALL use a distinct prompt glyph (e.g., `?` in info_color) to differentiate it from the main REPL prompt.
3. THE TUI SHALL accept any non-empty string as valid input.
4. WHEN the user provides text input, THE stream handler SHALL resolve the response future with the input string.
5. THE TUI SHALL display a hint that the user can type `r` or `/reject` to abort instead of providing input.
6. WHEN the user types `r` or `/reject` as the sole input, THE stream handler SHALL resolve the response future with the string `"reject"` and cancel the stream.

#### Edge Cases

1. IF the user submits empty input (just Enter), THEN THE TUI SHALL re-prompt with a hint that input is required.
2. IF the user presses Ctrl+C during text input, THEN THE stream handler SHALL treat it as a rejection.

---

### Requirement 6: Rejection and Stream Cancellation

**User Story:** As a user, I want rejecting a prompt to immediately stop the agent so that I maintain control over the session.

#### Acceptance Criteria

1. WHEN the user rejects any input request, THE stream handler SHALL break out of the event iteration loop.
2. WHEN the stream is cancelled due to rejection, THE stream handler SHALL finalize any partial content into a `ConversationTurn` and add it to the session history.
3. WHEN the stream is cancelled due to rejection, THE TUI SHALL display an informational message: "Rejected. Agent response cancelled."
4. WHEN the stream is cancelled due to rejection, THE session conversation history SHALL be preserved (not cleared).
5. AFTER rejection, THE REPL SHALL return to the normal input prompt.

#### Edge Cases

1. IF a rejection occurs after the agent has already produced partial text output, THEN THE partial text SHALL be preserved in the conversation turn.
2. IF a rejection occurs immediately (no prior content), THEN THE conversation turn SHALL have empty content.
