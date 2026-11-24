# Standards & tooling

Good tooling and standards matter more for a crowd than for a team. We ship a small kit and a guide for projects that already have their own.

## What we ship

- **Readiness check** (`crowd ready <owner/repo>`): read-only. Reports license, your access, whether it's a fork, existing CI and which OS it runs on, the project's own rules, open PRs and label clashes, and prints a draft `.crowd/config.yaml`. Writes nothing anywhere. Always the first step (D-11). Later: scores tests, module boundaries, file sizes, build reproducibility.
- **Generators:** scaffolds for new modules, tasks and context packs, so output is consistent across contributors.
- **Scope checker:** the same rules locally and in CI.
- **Standard configs:** lint/format defaults per language, used when a project has none.

## Ideas borrowed from Nx

- **Project graph + affected:** build and test only what a change touches. Big compute savings at crowd scale.
- **Module boundary rules:** the same idea as task scope, enforced by a linter.
- **Generators:** as above.
- **Shared remote cache:** a big speedup, but only accept entries from trusted builders. One bad entry poisons everyone's builds.

## Guide for projects with their own tools

A project is crowd-ready when:

1. One command builds, one command tests, from a clean checkout.
2. Modules have clear owners and boundaries (or a plan to get there).
3. No file is so large that two tasks can't avoid each other. Split big files first.
4. There's a way to compute "affected" (Nx, Bazel, Turborepo, or a simple path map).
5. Lint and format are automatic.
6. The brief and principles exist, or the owner is available to approve derived ones (T-000).

Map your tools to these six points in `.crowd/config.yaml`. The gate runs whatever is there (`setup`, `policy`, `build`, `lint`, `test`) on the runners in `ci.runners`, so any language and any OS works.

## Respect the project's own rules

Before any task is posted, read the project's contributing guide, content policies, hooks and CI (`crowd ready` lists them). Then:

- add those files to `protected_paths`;
- put the project's own checks in `commands` (a policy check goes in `commands.policy` and runs before the build);
- add anything that must never be committed to `policy.forbid`.

Agents follow the project's rules, not just crowd's.

## First principles

Every project has a `PRINCIPLES.md`. Planners read it first, every task cites it, reflect tasks check for drift. When stuck, reason from the goal and the principles, and record the reasoning in the decision log.
