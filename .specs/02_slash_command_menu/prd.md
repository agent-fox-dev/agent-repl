# PRD: Slash Command Menu

When a user types "/", a list of slash commands is shown.

1. If the user hits "esc", the list should disappear/collapse.
2. In case the list gets too long (more than 5-6 items) only show the most
   important commands. The rest should only show when the user types, based on
   the characters typed. Like "type-ahead" in a form.

## Clarifications

1. **UI placement:** Use prompt-toolkit's built-in completion dropdown menu that
   appears above/below the cursor (standard autocomplete UX).

2. **Priority / pinned commands:** Manual pinned list based on configuration.
   Some essential commands always show (e.g., help, quit). The pinned list is
   configurable. Only pinned commands appear in the initial dropdown; all others
   require type-ahead filtering.

3. **Trigger timing:** The command list appears immediately when "/" is typed as
   the first character on the line. No delay.

4. **Display format:** Each entry shows the command name plus its description
   (e.g., `/help --- Show available commands`).
