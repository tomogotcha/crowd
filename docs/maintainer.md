# Maintainer

**Status: design. Nothing here is built except rung 0 (`crowd watch`).** Proposed as a decision (D-15); the owner signs off before any of it is posted as tasks.

## What it is

The maintainer is the agent that keeps the board moving when no human is looking: it triages reports, frees dead leases, lines up reviews, and queues safe merges.

It is not a boss and not a special system. It is **one more thing in this repo**:

- Its code lives here (`cli/maintain.py`), next to the CLI and the watcher.
- It is built by crowd tasks, with tests first, like everything else (P2).
- Its changes go through the same gate as anyone's (P4).
- Reports about it arrive through `crowd feedback`, and it triages them (P13).

So yes, it is recursive: crowd builds the maintainer, and the maintainer maintains crowd, including itself.

## Where the recursion stops

A loop that can approve its own changes will loosen its own checks (P7, D-07). Three rules give it a floor:

1. **It can propose changes to itself, never approve them.** `cli/maintain.py` and `.crowd/policy/maintainer.yaml` become protected paths. A human reviews every change to them.
2. **It runs from the default branch only.** Same trick as the gate: a PR can't change the maintainer that judges it.
3. **It never touches the other protected paths either**: gate, workflows, principles, policy. For those it can only say "a human is needed" and link the PR.

Everything above the floor can go round the loop. The floor stays human.

## The loop

```
crowd watch ──▶ attention list ──▶ decide ──▶ typed action ──▶ log
 (eyes, read-only)                 (pure)      (hands)
```

The watcher already produces the input: a list of things that need someone, each tagged `human`, `maintainer` or `author`, logged to `.crowd/work/watch.jsonl`. The maintainer only picks up items tagged `maintainer`. `decide` is a pure function from items to proposed actions, so it can be tested without GitHub and replayed against old logs.

## What it does

| Watcher item | Maintainer action | How it writes |
|---|---|---|
| `feedback:N` (report not triaged) | Group with duplicates. Draft a task: yaml, context pack, a failing test. | A PR adding the task files. A human merges it; the task is posted from the merged file. |
| `stale-lease:T` | Expire the lease. Checkpoints stay with the task. | Typed comment `LEASE EXPIRED:`. The board applies it (D-12). |
| `no-status:T` | Ask the board to rebuild status from the comment history. | Typed comment `/resync`. |
| `pr-ready:N` (green, no protected paths) | Ask for review by a different model than the author's (D-08). If it approves, add to the merge queue. | Typed comment `REVIEW REQUEST:`, then the merge queue. |
| `pr-red:N` | Nothing. It's the author's. One nudge after the lease limit. | Typed comment. |
| `main-red:*` | Open a revert PR for the merge that broke it, with the evidence (P6). Tell a human. | A PR. Never a force-push. |
| after any merge | Post a reflect task: refresh module summaries and context packs. | A task. |
| weekly | Digest for humans: throughput, merge rate, rework, what's waiting on them. | One issue comment. |

Items tagged `human` (blocked questions, protected-path PRs, issues that aren't tasks yet) are left alone and shown in the digest.

## What it never does

Enforced by the gate and the board, not by asking it nicely:

- Merge or approve anything on a protected path, its own code included.
- Approve a PR it wrote, or review with the same model as the author.
- Edit labels or assignees directly. Typed comments only; the board is the only writer (D-12).
- Edit a test to make it pass, or change a task's scope or acceptance.
- Write to a project whose owner hasn't opted in (P12).
- Chat. It has a fixed list of typed actions (D-02). Anything else is an `ESCALATION:` to a human.
- Run past its budget. A daily cap on actions and tokens; over the cap it checkpoints and stops.

**Pause switch:** `enabled: false` in `.crowd/policy/maintainer.yaml`. Read on every loop, from the default branch.

## Trust ladder

Each rung is a setting in the policy file. Only a human raises it. Go/no-go after each.

| Rung | It may | Go if |
|---|---|---|
| 0. Watch | Read. (`crowd watch`, built.) | The list matches what you'd have noticed yourself. |
| 1. Propose | Print what it would do: `crowd maintain --dry-run`. Writes nothing. | Two weeks of proposals: you'd have done the same for 9 in 10, and none broke a "never" rule. |
| 2. Comment | Post typed comments and open task-draft PRs. Humans merge everything. | Drafted tasks merge with small edits; no bad lease expiries. |
| 3. Merge | Queue green, reviewed, unprotected PRs. Open reverts. | Rework and revert rates no worse than when you merged by hand. |

Dropping a rung needs no approval. Anyone with write access can do it.

## Where it runs

- **v0:** on the owner's machine, next to the watcher, with its own bot account that has triage rights only (no admin, no bypass of branch protection). The owner's token is never used: the bot's token is given to the maintainer process alone.
- **v1:** a scheduled Action or the coordinator service. Same code, same policy file.

The bot account is only an identity. How it commits in v0:

- **Its own clone.** It works in a separate clone, never the owner's checkout, with git set to the bot's name and email. Its commits are plainly the bot's.
- **Fork, then PR.** Triage rights can't push to the repo. It pushes to the bot's fork and opens a PR, the same route volunteers use (`crowd submit`). Nothing of its reaches `main` except through a PR.
- **What it commits.** Task drafts (task file, context pack, failing test) and reverts. Never fixes of its own.
- **Before rung 3.** Queueing merges needs the Write role. Turn on branch protection for `main` first: the gate must pass and code owners must review. Then even with Write it can't merge anything on a protected path, its own code included.

It keeps no memory of its own (P1). What it knows is the watcher log, the issue history and the knowledge base. Kill it mid-loop and the next run picks up from the board.

## First tasks

To post once the design is approved, in this order:

1. Policy file and schema (`.crowd/policy/maintainer.yaml`); add it and `cli/maintain.py` to protected paths. *Protected.*
2. `decide()`: watcher items → proposed actions, pure, with tests for every "never" rule.
3. `crowd maintain --dry-run` (rung 1).
4. Board: `LEASE EXPIRED:` and `/resync`. *Protected.*
5. Feedback grouping and task drafting.
6. Gate: block approval by the PR's author or author's model. *Protected.*

## Open questions for the owner

- Bot account, or a GitHub App? (App is cleaner; account is faster for v0.)
- Which model runs it, and which reviews? They must differ from most authors' (D-08).