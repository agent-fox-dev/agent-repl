# PRD: Copy Last Agent Output

## Description

I want a shortcut to copy the last agent output into the clipboard. The text
should be in markdown as displayed but WITHOUT the gutter text `|` on the left
as this is not useful content.

## Clarifications

1. **Trigger type**: Both a keyboard shortcut AND a slash command for
   discoverability.
2. **Content type**: Raw markdown source text as returned by the agent
   (portable, pasteable into any editor). Not ANSI-rendered output.
3. **Empty state**: Show a brief info message like "No agent output to copy"
   when there is no previous agent output.
4. **Feedback**: Show a short confirmation message like "Copied to clipboard"
   using the existing TUI info display after a successful copy.
