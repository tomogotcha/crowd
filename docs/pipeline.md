# PR pipeline: submit → review → test → regression → merge

Fully automated. Humans step in only for protected paths and escalations.

1. **Pre-flight (local).** `crowd check`: scope, lint, affected tests. Cheap failures never reach the shared queue.
2. **Gate.** Scope and module-boundary rules, diff size, correct base commit, protected paths, policy scan.
3. **Test.** Affected projects only, on a matched worker that didn't write the code.
4. **Regression.**
   - Correctness: full suite for everything downstream of the change.
   - Performance: benchmarks on the *same hardware class* as the baseline (machine cards make this possible).
   - Flaky tests: fails once, passes on rerun on another machine → quarantined and posted as a task, doesn't block the PR.
5. **Review.** A *different model* checks the PR against the context pack and `PRINCIPLES.md`. Critical tasks also get two contributors doing the same task, and the results are compared.
6. **Merge queue.** Tests changes in batches. A failing batch is split to find the bad PR.
7. **After merge.** Watch for regressions; auto-revert opens a task with the evidence attached.

## v0

Steps 1–2 and a basic 3 run in `.github/workflows/gate.yml`: a scope job, then the project's own commands from `.crowd/config.yaml` on the runners it lists. Only `crowd/T-*` PRs are gated; the project's other PRs never see it.

Work CI can't check (a real GPU, a device, data only volunteers have) uses `hardware` in `must_pass`: a matched machine runs `crowd verify <pr>` and posts `RESULT: pass|fail` for the head commit, and the gate re-runs and reads it.

Labels and leases are applied by `.github/workflows/board.yml` from typed comments and crowd PR events (opened → `in_review`, merged → `done`), so contributors on forks need no write access. Merge queue uses GitHub's built-in merge queue. Review and regression are manual until v1.
