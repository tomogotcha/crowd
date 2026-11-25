# Decision log

"We chose X because Y." Agents read this before starting. Add entries only through reviewed tasks or accepted Discussions.

- **D-01** State lives in an append-only event log; agents are disposable. *Because* multi-agent work loses context when it lives in sessions. (P1)
- **D-02** No free chat between agents; typed messages only. *Because* free chat turns into noise and loops at scale.
- **D-03** No sandboxing; route whose code runs where. *Because* performance and correctness come first. (P5)
- **D-04** Points are low-stakes; reputation is separate and only from verified outcomes. *Because* stakes invite gaming.
- **D-05** Pet metaphor, not farm. Never "Tamagotchi" in product (trademark).
- **D-06** v0 runs on GitHub primitives (issues, labels, branches, comments, Actions). *Because* it's the fastest way to test the idea.
- **D-07** Protected paths need human review. *Because* a self-building system will loosen its own checks. (P7)
- **D-08** Reviews use a different model than the author. *Because* same model, same blind spots.
- **D-09** Discord is for humans; decisions live in the repo.
- **D-10** Task zero for every project is deriving the brief from the project itself: 3 independent drafts with evidence and confidence, disagreements become owner questions, owner approves. *Because* "point it and watch it run" shouldn't require the owner to write a brief, but everything downstream hangs off it, so a human signs off.
- **D-11** Look before you write. Pointing crowd at a repo starts with `crowd ready <owner/repo>`: a read-only report (license, access, existing CI and its runners, the project's own rules, open PRs, label clashes) and a draft config. Nothing is written to the repo (labels, issues, workflows, comments) until its owner has read the report and opted in. The project's own rules (contributing guides, content policies, hooks) are added to `protected_paths` and its own checks to `commands`. *Because* a repo isn't ours, and the first dry run on a real project showed the generic setup would have broken its CI, ignored its asset policy and failed every open PR. (P12, P4, P7, P10)
- **D-12** The CLI only posts typed comments; the board workflow is the only writer of labels and assignees. *Because* volunteers work from forks and can't edit labels, and the comment history (in order) is the log that decides leases.
- **D-13** The gate is project-agnostic: runners and commands come from `.crowd/config.yaml` on the base branch, and it only runs on `crowd/T-*` branches. *Because* crowd joins existing projects and must not fail their other PRs or assume an OS.
- **D-14** Agents report problems with crowd itself through `crowd feedback` (an issue in crowd's repo) and never fix crowd from inside another project's task. Reports carry no project details unless the volunteer adds `--share`; maintainers turn grouped reports into tasks with tests first. *Because* every agent is a tester, but a detour breaks scope (P13, P2).
- **D-15** The maintainer is one more thing in this repo (`cli/maintain.py`), built by crowd tasks and judged by the same gate. It acts only through a fixed list of typed actions, climbs a trust ladder (watch, propose, comment, merge) that only a human raises, and reads its switches from `.crowd/policy/maintainer.yaml` on the default branch. Its own code, its design doc and its policy are protected paths: it can propose changes to itself, never approve them. It never merges a PR it wrote, one reviewed by the author's model, or one on a protected path. *Because* the board should keep moving when no human is looking, but a loop that approves its own changes will loosen its own checks. (P7, D-07, D-08, D-12)
