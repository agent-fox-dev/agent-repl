# Requirements Document

## Introduction

This specification defines a "copy last agent output" feature for the
`agent_repl` framework. The feature allows users to copy the most recent agent
response (as raw markdown) to the system clipboard using either a slash command
(`/copy`) or a keyboard shortcut.

## Glossary

| Term              | Definition                                                                                   |
|-------------------|----------------------------------------------------------------------------------------------|
| Agent output      | The raw markdown text returned by the agent for a single response turn.                      |
| Gutter            | The colored `▎` character rendered on the left side of agent output by `_LeftGutter`.        |
| Last output       | The `content` field of the most recent `ConversationTurn` with `role="assistant"` in session. |
| System clipboard  | The OS-level clipboard (pasteboard on macOS) accessible via `pbcopy`, `xclip`, etc.          |
| Slash command     | A user input starting with `/` that invokes a registered command handler.                    |
| Keyboard shortcut | A key binding in prompt-toolkit that triggers an action without typing a command.             |

## Requirements

### Requirement 1: Copy via Slash Command

**User Story:** As a user, I want to type `/copy` to copy the last agent
response to my clipboard, so that I can paste it into other applications.

#### Acceptance Criteria

1.1. WHEN the user enters `/copy`, THE system SHALL copy the `content` of the
most recent assistant `ConversationTurn` to the system clipboard as raw markdown
text.

1.2. WHEN the user enters `/copy` AND no assistant turn exists in the session
history, THE system SHALL display the informational message "No agent output to
copy."

1.3. WHEN the user enters `/copy` AND the copy succeeds, THE system SHALL
display the informational message "Copied to clipboard."

1.4. IF the system clipboard operation fails, THEN THE system SHALL display an
error message indicating the failure reason.

1.5. THE `/copy` command SHALL appear in the `/help` output with a description.

1.6. THE `/copy` command SHALL be included in the tab-completion list.

### Requirement 2: Copy via Keyboard Shortcut

**User Story:** As a user, I want to press a keyboard shortcut to copy the last
agent response to my clipboard, so that I can do it without typing a command.

#### Acceptance Criteria

2.1. WHEN the user presses the designated keyboard shortcut at the input prompt,
THE system SHALL copy the `content` of the most recent assistant
`ConversationTurn` to the system clipboard as raw markdown text.

2.2. WHEN the user presses the designated keyboard shortcut AND no assistant
turn exists in the session history, THE system SHALL display the informational
message "No agent output to copy."

2.3. WHEN the user presses the designated keyboard shortcut AND the copy
succeeds, THE system SHALL display the informational message "Copied to
clipboard."

2.4. THE keyboard shortcut SHALL NOT interfere with existing key bindings
(Ctrl+C for cancel, Ctrl+D for EOF, Ctrl+R/Ctrl+S for history search, Tab for
completion).

2.5. THE keyboard shortcut SHALL function while the input prompt is active
(i.e., no agent request is in progress).

### Requirement 3: Clipboard Content Format

**User Story:** As a user, I want the copied text to be the raw markdown source
without any terminal rendering artifacts, so that it is portable and useful in
other applications.

#### Acceptance Criteria

3.1. THE copied text SHALL be the raw markdown source string as stored in the
`ConversationTurn.content` field.

3.2. THE copied text SHALL NOT contain the gutter character (`▎`), ANSI escape
codes, or any Rich rendering artifacts.

3.3. THE copied text SHALL NOT contain leading or trailing whitespace beyond
what exists in the original markdown source.

### Requirement 4: Platform Compatibility

**User Story:** As a user on macOS or Linux, I want the clipboard copy to work
on my platform.

#### Acceptance Criteria

4.1. WHILE the system is running on macOS, THE system SHALL use `pbcopy` for
clipboard operations.

4.2. WHILE the system is running on Linux with X11, THE system SHALL use
`xclip -selection clipboard` for clipboard operations.

4.3. WHILE the system is running on Linux with Wayland, THE system SHALL use
`wl-copy` for clipboard operations.

4.4. IF the required clipboard utility is not available, THEN THE system SHALL
display an error message identifying the missing utility.
