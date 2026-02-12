# PRD: Agent Input Requests

## Description

Agents might need approval for tasks or need additional input, e.g. to clarify
things. This is currently not supported.

Requirement 1: If the agent needs an approval, show the choices and either have
a binary selection "approve", "reject" or if there is more than one possibility
a list of choices numbered 1, 2, 3 and the possibility to select one of the
choices by navigating with the cursor or simply typing the number. Rejecting
the choices should abort the current agent session.

## Clarifications

1. **Signal mechanism**: New `StreamEventType` added to the enum. Agent plugins
   yield this event with choices data. Protocol-level solution available to all
   agent plugins.
2. **Abort scope**: "Reject" cancels the current stream only. Conversation
   history is preserved; the user returns to the REPL prompt.
3. **Free-text input**: Also supported as a third input mode. Agent can ask a
   question and the user types a freeform answer.
4. **Protocol scope**: Part of the streaming event model at the protocol level.
   Any `AgentPlugin` can emit input request events.
