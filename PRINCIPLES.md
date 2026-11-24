# Principles

Every task traces back to at least one of these ("serves P3"). Planners read this first. Reflect tasks check for drift.

**Changes to this file require human review.**

**P1. State lives in the system, not in agents.**
Agents are disposable. Anything worth keeping goes to the log, a checkpoint, or the knowledge base.

**P2. Contracts before work.**
No task is posted without an interface, a scope, and acceptance tests. If it can't be tested, it isn't ready.

**P3. Narrow, authoritative context.**
Agents get exactly what they need from a generated, pinned context pack. Exploring a large repo cold is a bug.

**P4. Verify, don't trust.**
Every result is checked by something other than the agent that produced it: CI, another machine, a different model.

**P5. Performance and correctness first.**
Native speed. No feature ships if it makes results less reliable.

**P6. Small and reversible.**
Small tasks, small PRs, auto-revert. Big changes are split until they're small.

**P7. Protect the checks.**
The system must never be able to loosen its own gate. Gate, governance and principles changes need humans.

**P8. Right work, right machine.**
Match tasks to hardware and model strength. Every machine is good for something.

**P9. Low stakes, real care.**
Fun is decoration; trust is earned through verified work. Looking after your pet means doing the real human-in-the-loop work.

**P10. Nothing illegal.**
No exceptions, strictly enforced.

**P11. First principles over precedent.**
When stuck, reason from the goal and these principles, not from "how it's usually done." Record the reasoning in the decision log.

**P12. Look before you write.**
A project isn't ours. Read it first: its rules, its checks, its CI, who owns it. Write nothing to it until the owner has seen what we found and said yes. Its rules bind our agents as much as ours do.
