# CLAUDE.md

Context for Claude Code sessions on this repo.

## What this is

crowd (working name): a coordination layer that lets volunteers' AI agents work on one software project together, mostly unattended. It is also its own first project. It will be built by its own crowd once v0 works.

Read in this order: `BRIEF.md` → `PRINCIPLES.md` → `docs/architecture.md` → `docs/roadmap.md`.

## Current stage

**v0 draft.** Docs, templates, a gate workflow, and a single-file Python CLI (`cli/crowd.py`) that uses the GitHub CLI (`gh`) for issues as the task board. No server yet.

## Decisions already made (don't re-argue; see `.crowd/kb/decisions.md`)

- State lives in an append-only event log; agents are disposable.
- No free chat between agents. Typed messages only. Discord is for humans.
- No sandboxing. Native speed; route *whose* code runs where.
- Points are low-stakes. Reputation (separate, quiet) gates trust.
- Pet metaphor (Tamagotchi-style), not farm. Never use the Tamagotchi name in product.
- v0 uses GitHub primitives: issues = tasks, labels = status, branches = leases, comments = checkpoints, Actions = gate.
- Look before you write: `crowd ready` (read-only) and the owner's opt-in come before anything is written to a target repo (D-11, P12).
- Protected paths need human review: `.github/`, `PRINCIPLES.md`, `cli/gate/`, `.crowd/policy/`.

## Working style

- Plain language in docs. Short over exhaustive.
- Incremental, with go/no-go checkpoints.
- Complete files, not fragments.
