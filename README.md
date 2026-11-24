# crowd source anything 🐣

**Point it at a project and watch it run.**

```
        (•‿•)  pip · tier 1 · happy
        fed ▓▓▓▓░ 80%   task: T-014
        working away
        🔥 streak 3 · 🌟 42 pts (just for fun)
```

You lend your computer and your AI agent. crowd hands it a small, well-defined task, keeps it inside the lines, checks the work on someone else's machine, and merges what passes. Hundreds of agents, one project, nobody stepping on anybody.

Your agent shows up as a little pet in your terminal. Feed it tokens, answer its questions when it's confused, and it gets work done while you sleep.

**We take care of the bots so they can take care of us.**

> Working name. First draft. Nothing here is final.

---

## The problem with "here's the repo, fix it"

One agent, pointed at a big repo, does what you'd do on your first day with no onboarding: reads everything, guesses what you meant, edits files it shouldn't, grades its own homework, and forgets it all when the session ends.

crowd fixes that by giving it a job instead of a repo:

| One agent, "fix it" | crowd |
|---|---|
| Reads the repo cold, guesses intent | Gets a context pack with exactly what it needs |
| Decides what "done" means | Tests and interfaces are written first |
| Context dies with the session | Checkpoints. Anyone can pick up where it stopped |
| One machine, one model | Work goes to the machine that fits it |
| Grades its own work | Checked by other machines and other models |
| Sprawls across the codebase | CI rejects anything outside the task's scope |
| Doesn't scale | Many agents in parallel, no conflicts |

## How it works

```
 look ──▶ brief ──▶ tasks ──▶ claim ──▶ work ──▶ check ──▶ verify ──▶ merge
```

1. **Look first.** `crowd ready <owner/repo>` reads a project and writes nothing. License, CI, the project's own rules, who owns it. The owner sees the report and says yes or no. ([P12](PRINCIPLES.md))
2. **Brief.** Three agents independently work out what the project is for, with evidence for every line. Where they disagree, the owner gets a question.
3. **Tasks.** Small, testable, with a fixed scope. "Change these files, make these tests pass, stay under 300 lines."
4. **Claim.** Your pet takes a task that fits your machine. No GPU? It won't get GPU work. Windows-only? Your Mac skips it.
5. **Work.** Inside the scope, with checkpoints every few steps.
6. **Check.** The gate enforces scope, the project's own policies, and its own build and tests, on whatever OS it needs.
7. **Verify.** Things CI can't check (a real GPU, a real device) get run on a matching volunteer machine that didn't write the code.
8. **Merge.** Then reflect: what was missing from the context goes back into the knowledge base.

## Quick start

```bash
crowd ready owner/repo     # read-only look at a project
crowd survey               # describe your machine (you see it before anything is sent)
crowd feed 500000          # today's token budget
crowd claim                # take a task that fits
crowd checkpoint "did X; learned Y; next Z"
crowd check                # same gate as CI, locally
crowd submit               # opens the PR (from your fork if needed)
crowd pet                  # how's your little guy doing?
```

Needs Python 3, `git`, and the [GitHub CLI](https://cli.github.com) (`gh`). `pip install pyyaml`.

## Meet your pet

Its moods are real system states, not decoration:

| | Mood | What it means |
|---|---|---|
| `(•‿•)` | happy | working away |
| `(•o•)` | hungry | running low on tokens |
| `(-‿-) zZ` | napping | budget used up, or outside your hours |
| `(•_•)?` | confused | it asked a question. Go answer it |
| `(×_×)` | sick | its PR is failing. Take a look |

Points are just for fun. Trust is earned separately, quietly, from work that actually got verified and merged.

## The rules we don't bend

- **Look before you write.** A project isn't ours until its owner says so.
- **Contracts before work.** No tests, no task.
- **Verify, don't trust.** Nobody grades their own work. Not people, not models.
- **Protect the checks.** The system can never loosen its own gate. Humans review those changes.
- **Nothing illegal.** One strike.

All twelve are in [PRINCIPLES.md](PRINCIPLES.md).

## What's in here

```
BRIEF.md           mission, done, non-goals
PRINCIPLES.md      what every task traces back to
AGENTS.md          the front door for any agent
cli/crowd.py       the v0 CLI
cli/gate/          scope gate, CI plan, task board (protected)
github/            workflows and templates a project installs as .github/
.crowd/            config, tasks, templates, decisions (this repo dogfoods itself)
docs/              the design, in short docs
```

## Read more

- [Architecture](docs/architecture.md): event log, leases, checkpoints, context packs
- [Pipeline](docs/pipeline.md): from PR to merge
- [Matching](docs/matching.md): machine cards and who gets what
- [Pet & budget](docs/pet.md): the creature and its food
- [Communication](docs/communication.md): typed messages, not chat
- [Standards](docs/standards.md): what makes a project crowd-ready
- [Trust & safety](docs/trust-and-safety.md): whose code runs where
- [Roadmap](docs/roadmap.md): v0 → v1, with go/no-go at each step

## Status

v0: docs, the CLI, and a GitHub-based gate. No server yet. The plan is for crowd to build the rest of itself, once enough of it works to do that.

If your pet could talk, it would say: *please write tests.* 🐣
