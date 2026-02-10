# Agent Instructions

This file provides instructions for coding agents working on this repository.

## About the Repo

See `prd.md` for product requirements.

## Spec-Driven Development

This project uses spec-driven development. The authoritative implementation
artifacts live in `.specs/{number}_{specification}/`:

- `requirements.md` (user stories + acceptance criteria)
- `design.md` (architecture + interfaces + correctness properties)
- `tasks.md` (implementation plan + task status)

## Session Start Checklist (MANDATORY)

At the beginning of every coding session:

1. Read `.af/steering/coding.md`
2. Run Step 1 (Get Your Bearings)
3. Run Step 2 (Verification Test)
4. Choose exactly one task from `.specs/{number}_{specification}/tasks.md`

Do not implement anything before completing this checklist.

## One-Task Session Policy (MANDATORY)

- Implement exactly one task group/subtask per session.
- Do not start a second task in the same session.
- If the user requests multiple tasks, complete one task and hand off the rest.
- Do not include unrelated "while here" fixes.

## Workflow and Git Policy

The workflow is defined in:

- `.af/steering/coding.md` (session execution policy)
- `.af/steering/git-flow.md` (branching, commit, merge, push rules)

When implementing a task, update the checkbox states in `.specs/{number}_{specification}/tasks.md` using the following syntax:

| Syntax   | Meaning                |
|----------|------------------------|
| `- [ ]`  | Not started (required) |
| `- [ ]*` | Not started (optional) |
| `- [x]`  | Completed              |
| `- [-]`  | In progress            |
| `- [~]`  | Queued                 |

## Documentation Conventions

- ADRs live in `docs/adr/{decision.md}`
- Other documentation lives in `docs/{topic.md}`

## Session Completion Rule

A session is not complete until all required quality gates pass and task changes
are committed, merged, and pushed according to `.af/steering/coding.md` and `.af/steering/git-flow.md`.
