# Communication

Split by audience. The rule: **if it isn't in the repo, it wasn't decided.**

## Agents: typed message bus

No free chat between agents. Free chat turns into noise and loops at scale. Messages are typed and attached to a task or module:

| Type | Effect |
|---|---|
| `question` | Pauses the task. Routed to the module owner or knowledge holder. |
| `finding` | Published. Subscribers to the module/topic are notified. |
| `objection` | Blocks a merge or decision until resolved. |
| `handoff` | Checkpoint plus notes for the next agent. |
| `escalation` | Goes to a human (owner or coordinator). |
| `feedback` | About crowd itself, not the project. Goes to crowd's own repo (P13). |

Agents subscribe by module or topic. This is a blackboard system: coordination through shared state, not conversation.

v0: issue comments with a prefix (`QUESTION:`, `FINDING:`, `OBJECTION:`, `HANDOFF:`). Feedback is an issue in crowd's repo, filed by `crowd feedback`, labelled `crowd:feedback`. v1: the event log, exposed via MCP so any agent gets these as tools.

## Feedback on crowd itself

Every agent on every project uses crowd, so they're the best testers it has. When crowd gets in the way, the agent runs `crowd feedback "..."` and carries on with its task (P13). It never fixes crowd inside another project's task.

- **Private by default.** A report carries the crowd version, OS, command and task type. The project's name and task ID are only included with `--share`.
- **No pile-ups.** An identical open report gets a `+1` comment instead of a new issue.
- **Reports aren't tasks.** A reflect task on crowd's repo groups repeated reports. Maintainers then post real tasks, with tests first (P2), the same as any other change.

## Humans

- **Discord:** community and chatter. A bot posts digests and merges ("harvests"). Your pet DMs you when it needs you.
- **GitHub Discussions:** proposals (RFCs). Accepted ones are written into `.crowd/kb/decisions.md`.
- **Owner notifications:** escalations only, in real time (push, email or Discord DM). Everything else in a daily digest.

## What never happens

- Decisions made only in Discord.
- Agents reading Discord as context.
- Agents messaging each other outside the bus.
