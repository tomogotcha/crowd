# Trust & safety

## Nothing illegal, strictly enforced

- **Project intake:** open license, verified owner, no scraping, malware, credential harvesting, or ToS-breaking work.
- **Task screening:** automated scan of tasks and PRs for prohibited work. Flagged items wait for a human.
- **One strike** for clear violations. Bans tied to GitHub identity. Full audit log. Narrow appeals path.

## Look before you write

No labels, issues, workflows or comments go to a repo until its owner has seen a `crowd ready` report and opted in (D-11). On a repo you don't control, that means asking the owner first, working on your own fork until they say yes.

## Private data on volunteer machines

Volunteers' machines hold things that must never reach the repo: datasets, game files, keys. Every crowd PR passes the project's `policy.forbid` globs, a file size cap, and the project's own `commands.policy` before anything builds.

## No sandbox: route code instead

We run natively for performance. The risk: an unreviewed PR's tests running on 1,000 volunteer machines. So we control *whose code runs where*:

| Code | Runs on |
|---|---|
| Your own unmerged code | your machine only |
| Others' unmerged code | opted-in, high-reputation machines only |
| `main` and reviewed PRs | everyone |
| Build scripts, dependency changes | nowhere until a human reviews |

In v0, "opted-in" means `limits.run_others_code: true` on the machine card, and `crowd verify` refuses to run otherwise. Its `RESULT` only counts toward the gate from someone other than the author, at tier 2 or above, for the PR's exact head commit.

Fallback: invite-only until trust is established.

## Fake accounts

Reputation means nothing if one person runs 50 accounts. Tie it to something costly: GitHub account age and history, verified email, slow reputation growth.

## Protected paths

Human review required (CODEOWNERS): `.github/`, `PRINCIPLES.md`, `cli/gate/`, `.crowd/policy/`. A self-building system will otherwise loosen its own checks, not from bad intent but because looser checks pass faster.

## Model diversity

The model that reviews is never the one that wrote. Same model, same blind spots.

## Licensing

Contributors agree to a DCO (sign-off) on join. AI-generated code has open legal questions about ownership; settle the project's position before the first outside PR. Not legal advice; get a real opinion.

## Owner controls

Pause/kill switch, dashboard, clear escalation rules.

## Private repos

Out of scope for v1. Public projects or vetted private pools only.
