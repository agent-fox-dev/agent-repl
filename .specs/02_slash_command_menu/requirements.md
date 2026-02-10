# Requirements Document

## Introduction

This specification defines the behavior of a slash command completion menu for
the agent_repl TUI. When a user types `/` at the beginning of an input line,
a dropdown menu of available slash commands appears, allowing the user to
browse, filter, and select commands without memorizing their names.

## Glossary

| Term | Definition |
|------|------------|
| Completion menu | A prompt-toolkit dropdown that appears near the cursor showing selectable entries |
| Pinned command | A slash command marked as always visible in the initial dropdown (before any filtering) |
| Type-ahead filtering | Narrowing the displayed command list in real time as the user types characters after `/` |
| Slash command | A user-invocable action prefixed with `/` (e.g., `/help`, `/quit`) |
| Completion entry | A single row in the completion menu showing a command name and description |

## Requirements

### Requirement 1: Slash Command Menu Activation

**User Story:** As a user, I want a menu of available slash commands to appear
when I type `/`, so that I can discover and select commands without memorizing
them.

#### Acceptance Criteria

1.1. WHEN the user types `/` as the first character on an otherwise empty input
line, THE system SHALL display a completion menu containing slash commands.

1.2. WHILE the completion menu is displayed, THE system SHALL show each entry
with the command name and its description (e.g., `/help --- Show available
commands`).

1.3. THE system SHALL activate the completion menu immediately upon the `/`
keystroke, without any intentional delay.

1.4. IF the user types `/` at a position other than the start of the input line
(e.g., mid-sentence), THEN THE system SHALL NOT display the completion menu.

### Requirement 2: Pinned Commands and Initial Display

**User Story:** As a user, I want to see only the most important commands by
default, so that I am not overwhelmed by a long list.

#### Acceptance Criteria

2.1. WHEN the completion menu is first shown (user has typed only `/`), THE
system SHALL display only pinned commands.

2.2. THE system SHALL provide a configurable list of pinned command names via
the `Config` dataclass.

2.3. THE system SHALL pin `help` and `quit` by default when no explicit pinned
list is provided.

2.4. THE system SHALL display at most 6 pinned entries in the initial dropdown.
IF more than 6 commands are marked as pinned, THE system SHALL display the first
6 in registration order.

2.5. THE system SHALL allow the `SlashCommand` dataclass to declare a command as
pinned via a `pinned` boolean field (default `False`).

2.6. WHEN determining the set of pinned commands, THE system SHALL merge
commands declared as `pinned=True` on the `SlashCommand` with the configured
`pinned_commands` list, removing duplicates. The configured list takes
precedence for ordering.

### Requirement 3: Type-Ahead Filtering

**User Story:** As a user, I want to find any command by typing part of its
name, so that I can quickly reach commands that are not in the initial pinned
list.

#### Acceptance Criteria

3.1. WHEN the user types characters after `/`, THE system SHALL filter the
completion menu to show all commands whose names start with the typed prefix,
regardless of whether they are pinned.

3.2. WHILE the user is typing a prefix, THE system SHALL update the completion
menu in real time (on each keystroke) to reflect the current filter.

3.3. IF no commands match the typed prefix, THEN THE system SHALL display an
empty completion menu (no entries).

3.4. WHEN the user deletes characters (e.g., via Backspace) back to just `/`,
THE system SHALL revert to showing only pinned commands.

### Requirement 4: Dismissing the Completion Menu

**User Story:** As a user, I want to dismiss the command list by pressing
Escape, so that I can continue typing freely without the menu in the way.

#### Acceptance Criteria

4.1. WHEN the completion menu is visible and the user presses the Escape key,
THE system SHALL close the completion menu.

4.2. WHILE the completion menu is dismissed, THE system SHALL NOT re-display the
menu until the user modifies the input text (e.g., types or deletes a
character).

4.3. WHEN the user selects a completion entry (e.g., via Enter or Tab), THE
system SHALL insert the selected command text into the input line and close the
completion menu.

### Requirement 5: Backward Compatibility

**User Story:** As a developer using the agent_repl library, I want existing
code to continue working without changes if I do not configure pinned commands.

#### Acceptance Criteria

5.1. IF `pinned_commands` is not provided in `Config`, THEN THE system SHALL use
the default pinned list (`["help", "quit"]`).

5.2. THE system SHALL preserve existing tab-completion behavior for non-slash
inputs.

5.3. THE system SHALL continue to support the existing `SlashCommand` dataclass
interface without requiring consumers to specify the new `pinned` field
(it defaults to `False`).
