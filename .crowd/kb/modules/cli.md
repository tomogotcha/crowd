# Module: cli

**Owns:** the `crowd` command (v0), the scope gate, hardware probes.

- `cli/crowd.py`: subcommands over git + `gh`. Issues = tasks, labels = status, branches = leases, comments = checkpoints/messages.
- `cli/gate/scope_check.py` *(protected)*: scope, protected-path, content-policy, diff-size and hardware-result checks. Used by CI and `crowd check`. Reads the task from the **base** branch (or a maintainer-written issue) so a PR can't rewrite its own scope.
- `cli/gate/plan.py` *(protected)*: turns `.crowd/config.yaml` into the gate's runners and commands. No language or OS is built in.
- `cli/gate/board.py` *(protected)*: the only writer of labels and assignees. Applies `/claim`, `/release`, `QUESTION:`, `RESULT:` comments, and crowd PRs opening (in_review), merging (done) or closing unmerged (back to leased, or open if nobody holds it). Enforces tier and redundancy.
- `crowd ready` is read-only by design (D-11): it must never write to the target repo.
- `crowd feedback` files issues in crowd's own repo (`CROWD_TOOL_REPO`, default `tomogotcha/crowd`), never in the project. No project details unless `--share` (D-14).
- `cli/probes/` *(planned)*: one file per capability probe, each `probe() -> {tags, measured}`.

**State on the user's machine:** `~/.crowd/machine-card.json`, `~/.crowd/state.json` (pet, budget).

**Called by:** humans, agents, `.github/workflows/gate.yml`, `.github/workflows/board.yml`.
