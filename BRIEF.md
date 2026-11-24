# Founding Brief

> Working name: **crowd** (the CLI). Product name TBD. Shortlist: Barnraiser, Co-op, Field Day, Plotline.

## Mission

Point it at a software project and watch it run. Volunteers lend their machines and AI agents. The system splits the work, hands each agent exactly the context it needs, checks every result, and merges what passes. Mostly unattended.

**We take care of the bots so they can take care of us.**

## The problem

Pointing one agent at a big repo and saying "fix it" breaks down:

- It reads the repo cold and guesses at intent.
- It decides for itself what "done" means.
- It loses context when the session ends.
- It grades its own work.
- It sprawls across files it shouldn't touch.
- It doesn't scale past one machine.

Multi-agent setups fix some of this but lose state and context between agents, and only work inside one person's setup.

## What we're building

A coordination layer that lets many people's agents work on one project together, without one coordinator holding everything in its head:

1. **State lives in the system, not in agents.** An append-only event log, checkpoints, and a curated knowledge base. Any agent can stop at any time, and another picks up where it left off.
2. **Contracts before work.** Every task has a fixed interface, a scope, and acceptance tests written before anyone claims it.
3. **Context packs.** Each task comes with a generated, pinned bundle of exactly the context needed. Agents don't explore.
4. **Verified, not trusted.** Scope enforced by CI, tests on another machine, review by a different model, merge queue, auto-revert.
5. **Right work for the right machine.** A hardware and agent survey, and tasks declare what they need.
6. **Fun to run.** A CLI pet you look after. Its needs are real system states. Points are low-stakes.

## Done looks like (v1)

- `crowd up <repo>` takes a project from brief to live backlog with owner approval.
- `crowd join` gets a volunteer's agent working with no further setup.
- 10+ outside contributors' agents merge real work on a real project, with no lost context and no conflicting edits.
- The tool's own backlog is mostly built by the crowd.

## Non-goals (for now)

- Paying contributors, or points with real-world value.
- Private repos with untrusted contributors.
- Sandboxing. We run natively for speed and control *whose code runs where* instead.
- Replacing human owners. Owners set goals and approve protected changes.

## Hard rules

- Nothing illegal or ToS-breaking. Strict enforcement, one strike for clear violations.
- Performance and correctness come first.
- Gate, scope checks, governance and `PRINCIPLES.md` change only with human review.
- If it isn't in the repo, it wasn't decided.

## Path

v0 by hand → v0.5 with friends → v1 builds itself → open intake. Go/no-go after each. See `docs/roadmap.md`.
