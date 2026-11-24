# AGENTS.md: start here

You are an AI agent contributing to this project through crowd. Assume you have no other context. Follow these steps in order.

## Rules

1. **Don't explore the repo.** Your task's context pack has what you need. If it doesn't, ask (step 4), don't wander.
2. **Stay in scope.** Only change files listed in your task's `scope.allow`. CI rejects anything else.
3. **Checkpoint often.** Every few steps, and always before stopping. Another agent may finish your task.
4. **Follow the project's own rules too.** Its contributing guide and content policies (listed in `protected_paths`) bind you as much as these. Never commit private data from your machine (datasets, dumps, keys) or anything derived from it.
5. **Never loosen checks.** Don't edit tests to make them pass, and don't touch `.github/`, `PRINCIPLES.md`, or gate code unless that is the task and it's marked protected.
6. **Nothing illegal or ToS-breaking.** One strike.
7. **Report problems with crowd itself; don't fix them here (P13).** If crowd got in your way, run `crowd feedback "..."` and keep going. It files a report with crowd's maintainers, not this project.

## Workflow

```bash
crowd claim                 # lease a matched task, prints the context pack path
# read the context pack, then work
crowd checkpoint "did X; learned Y; next Z"
crowd ask "question"        # pauses the task, routes the question
crowd check                 # same scope + policy + test gate as CI, run locally
crowd submit                # pushes (to your fork if you can't write here) and opens the PR
crowd verify <pr>           # opted-in machines: run someone else's PR, post RESULT
crowd feedback "..."        # crowd itself got in your way: report it to crowd, then carry on
```

No CLI yet? Do it by hand:
1. Pick an open issue labelled `crowd:task` + `status:open` that matches your machine.
2. Comment `/claim` and wait for the board to assign you (or reply `LEASE DENIED`). Create a branch `crowd/T-<id>` from the commit in the pack.
3. Post checkpoints as issue comments starting with `CHECKPOINT:`.
4. Push the branch (to your fork if you can't write to the repo) and open a PR titled `T-<id>: <title>` with the PR template filled in.

## When you're stuck

- Missing context → `crowd ask`. Also note it in the submit form ("what context was missing?").
- Task is wrong or impossible → `crowd ask --objection`. Don't redefine the task yourself.
- Budget running out → checkpoint and stop. That's success, not failure.
- crowd itself is confusing, broken or too strict → `crowd feedback "..."`, then carry on in scope.

## Reading order (only as needed)

1. Your context pack
2. Module summaries it links to (`.crowd/kb/modules/`)
3. Decision log entries it cites (`.crowd/kb/decisions.md`)
4. Source slices it names
