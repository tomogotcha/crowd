# Architecture

## Core idea

Agents are disposable workers. All state lives in the system. That fixes the main multi-agent failure: context that lives inside one session and is lost when it ends.

```
            ┌───────────────────────────────┐
 owner ───▶ │ intake: brief → principles →  │
            │ repo map → backlog            │
            └──────────────┬────────────────┘
                           ▼
            ┌───────────────────────────────┐
            │ coordinator                   │
            │  event log (source of truth)  │
            │  task graph + leases          │
            │  matcher (machine cards)      │
            │  message bus                  │
            │  context-pack generator       │
            └──────┬────────────────┬───────┘
                   ▼                ▼
          worker machine     worker machine ...
          local queue        local queue
          agent + pet        agent + pet
                   │                │
                   └──────┬─────────┘
                          ▼
            verify pipeline → merge queue → main
                          │
                          ▼
                reflect → knowledge base
```

## Event log

Append-only. Every claim, checkpoint, message, result, merge and revert is an event. Task status, inboxes and dashboards are views derived from it.

v0: GitHub issues and comments act as the log. v1: a real log (e.g. SQLite/Postgres table or a log file in a dedicated branch), mirrored to GitHub.

Event shape: see `.crowd/schemas/event.yaml`.

## Work units

Every task has a type. Each type consumes certain inputs and produces typed outputs.

| Type | Produces |
|---|---|
| research | findings (facts with sources/evidence) |
| plan | child tasks, each with interface + tests |
| implement | a PR |
| test | test files, or results on specific hardware |
| review | approve / request changes / objection |
| reflect | proposed knowledge-base changes |

Plan tasks are how coordination scales: trusted planners split epics into tasks, with a cap on how many children each can spawn.

Task shape: see `.crowd/templates/task.yaml`.

## Leases

Claiming a task takes a lease with a time limit and pins the base commit. An expired lease returns the task to the pool *with its checkpoints*. Leases also lock the code regions in scope, so two agents never edit the same function.

## Checkpoints

Required every N steps and before stopping:

```
done:    what changed
learned: facts worth keeping
next:    what the next step is
open:    questions or risks
```

An expired lease resumes from the last checkpoint. That's the whole trick.

## Memory tiers

| Tier | What | Who writes |
|---|---|---|
| Log | everything, permanent | system |
| Knowledge base (`.crowd/kb/`) | decisions, module summaries, findings | reviewed tasks only |
| Task workspace | scratch notes, checkpoints | the task's agent |

## Context packs

Generated per task, pinned to a commit, read-only. They contain: goal, where the code sits, the locked interface, relevant code slices, applicable decisions, off-limits list, tests. A stale base means regenerating the pack, not reasoning from old code.

Template: `.crowd/templates/context-pack.md`.

## Budgets

Every task carries a step/token estimate. Going over triggers checkpoint + escalation, never an endless loop. See `docs/pet.md`.
