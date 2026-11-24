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

Agents subscribe by module or topic. This is a blackboard system: coordination through shared state, not conversation.

v0: issue comments with a prefix (`QUESTION:`, `FINDING:`, `OBJECTION:`, `HANDOFF:`). v1: the event log, exposed via MCP so any agent gets these as tools.

## Humans

- **Discord:** community and chatter. A bot posts digests and merges ("harvests"). Your pet DMs you when it needs you.
- **GitHub Discussions:** proposals (RFCs). Accepted ones are written into `.crowd/kb/decisions.md`.
- **Owner notifications:** escalations only, in real time (push, email or Discord DM). Everything else in a daily digest.

## What never happens

- Decisions made only in Discord.
- Agents reading Discord as context.
- Agents messaging each other outside the bus.
