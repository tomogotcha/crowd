# Roadmap

Go/no-go after each stage.

## v0: by hand (1–2 weeks)

- [ ] Repo with these docs, `AGENTS.md`, task issue template, gate workflow, CODEOWNERS
- [ ] `cli/crowd.py`: claim, checkpoint, ask, check, submit, survey, pet (on top of `gh`)
- [ ] Pick a small, well-tested pilot project (ideally your own); run `crowd ready` on it first
- [ ] Run `T-000` (derive the brief) on it, 3 drafts; compare to what you'd have written yourself
- [ ] Approve the brief, write principles; post 10–20 tasks with tests
- [ ] Run 3–5 of your own agents

**Go if:** the derived brief is close to yours, tasks merge cleanly without hand-holding, and resumed leases pick up from checkpoints.

## v0.5: with friends

- [ ] Invite 5–10 people
- [ ] Machine cards and matching by labels
- [ ] Token budgets
- [ ] Simple pet in the CLI
- [ ] Discord bot for digests

**Go if:** strangers' agents merge work, and no context is lost across handoffs.

## v1: builds itself

Posted as tasks on v0:
- [ ] Real event log + coordinator service
- [ ] MCP server (claim, explain, decisions, ask, check, submit)
- [ ] Context-pack generator (regenerates on every merge)
- [ ] Review-by-different-model step
- [ ] Hardware-class regression runs
- [ ] Local queue

**Go if:** the crowd clears its own backlog faster than you could alone.

## v2: open intake

- [ ] `crowd up <repo>`: readiness check → T-000 derived brief → owner Q&A and approval → principles, repo map, backlog
- [ ] Project intake screening and enforcement
- [ ] Reputation tiers and code routing
- [ ] Owner dashboard, pause switch, notifications

## Metrics (track from v0)

Throughput, merge rate, rework rate, cost per merged task, lost-context incidents, time to first merge for a new volunteer.
